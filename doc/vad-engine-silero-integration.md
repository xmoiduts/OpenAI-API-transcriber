# Silero VAD 接入说明

// GPT5.4 writes this file.

本文描述当前仓库里已经落地的第一版 VAD 接入状态，重点覆盖：

- 当前实现对应的现实方案
- 主要代码文件职责
- `Silero VAD` 的可配置参数
- 后续接入新的 VAD engine 时需要改动的点

本文以当前代码为准，不描述尚未实现的 GUI 范围选择器。

## 1. 当前现实方案

### 1.1 目标

当前版本把 `Silero VAD` 放在 `VAD-exp` 页的第 1 条方法轨上，并在 `silero` 之上新增了一层可扩展的 `VAD engine` 抽象。

当前已实现：

- `VAD-exp` 第 1 条轨显示真实 `Silero VAD` 语音段
- 分析入口支持三种模式：
  - `amplitude only`
  - `amplitude + VAD`
  - `VAD only`
- VAD 支持“指定时间范围”分析
- 局部范围得到的 VAD 结果会合并进该媒体对应的内存态全长结果中
- 结果不落盘，只保存在进程内存中

当前尚未实现：

- GUI 上的起止时间输入控件
- 多个真实 VAD engine 的第 2/第 3 轨接入
- VAD 参数在 GUI 中动态可调
- 概率曲线、置信度热力图等更细粒度展示

### 1.2 运行流

当前主流程如下：

1. `Time Slicer` 广播媒体路径和时长给 `VADExpTab`
2. `VADExpTab` 决定是否自动开始分析，或对长音频等待 `Approve`
3. `VADExpTab` 通过 `AudioParseThread` 发起统一分析请求
4. `VadApplicationService` 根据开关执行：
   - 音频强度提取
   - 指定区间的 `Silero VAD`
5. `InMemoryVadResultStore` 将新的区间结果合并进该媒体的全长 VAD 结果
6. `VADExpTab` 把结果映射成 `VadInterval[]`，显示到第 1 条轨

### 1.3 一个重要现实细节

当前代码中：

- `VAD` 是按 `request.time_range` 指定范围执行的
- `amplitude` 仍然是按整段媒体的 `media_duration_sec` 提取的，而不是只取局部范围

这是当前实现与理想统一范围语义之间的差异。这样做的原因是 GUI 里的强度背景轨目前仍按“整段媒体时间轴”组织和缓存。

如果以后希望 `amplitude only` 也严格支持局部时间范围，需要改 `src/vad/service.py` 与 `src/vad_exp/audio_strength_extractor.py` 的调用契约。

## 2. 代码文件简述

### 2.1 GUI 与线程

- `src/gui/vad_exp_tab.py`
  - `VAD-exp` 页面入口
  - 持有 `VadApplicationService`
  - 控制审批、启动分析、接收线程结果、刷新 GUI
  - 提供 `request_analysis_range(...)`，是当前统一分析入口在 GUI 层的落点

- `src/gui/vad_exp/audio_parse_thread.py`
  - 后台线程
  - 把 GUI 请求打包为 `VadAnalysisRequest`
  - 调用 `VadApplicationService.request_analysis(...)`
  - 向 GUI 发回分析结果、失败或取消信号

- `src/gui/vad_exp/timeline_widgets.py`
  - 时间线绘制
  - `VadTimelinePanel.set_method_vad_intervals(...)` 用于按 `method_key` 更新某一条方法轨
  - 第 1 条轨当前显示真实 `silero` 结果，其余轨仍是占位

### 2.2 VAD 领域层

- `src/vad/models.py`
  - 定义领域模型
  - 关键类型：
    - `VadTimeRange`
    - `SpeechSegment`
    - `VadAnalysisRequest`
    - `VadAnalysisResult`
    - `VadAnalysisOutput`

- `src/vad/ports.py`
  - 定义 `VadEnginePort`
  - 新引擎需要实现 `engine_key` 和 `analyze_range(...)`

- `src/vad/store.py`
  - 内存态仓库
  - 负责按 `media_path + engine_key` 保存结果
  - 负责“区间替换 + 归并”的核心逻辑

- `src/vad/service.py`
  - 应用服务层
  - 把 `amplitude` 和 `VAD` 两类工作统一编排
  - 把新得到的 VAD 结果写回 `store`

### 2.3 Silero 适配层

- `src/vad/adapters/silero_adapter.py`
  - 当前唯一真实 VAD engine
  - 用 `ffmpeg` 按指定时间范围解码音频
  - 调用 `silero_vad.load_silero_vad()` 和 `get_speech_timestamps(...)`
  - 把返回结果标准化为 `SpeechSegment`

### 2.4 相关依赖

- `req.txt`
  - 当前新增：
    - `silero-vad`
    - `torch`

## 3. 当前数据契约

### 3.1 分析请求

当前通过 `VadAnalysisRequest` 传递：

- `media_path`
- `time_range`
- `media_duration_sec`
- `engine_key`
- `include_amplitude`
- `include_vad`
- `amplitude_points_per_second`
- `amplitude_sample_rate`

### 3.2 分析结果

当前 `VadAnalysisOutput` 包含：

- `amplitude_series`
- `vad_result`
- `analyzed_segments`
- `status_message`

### 3.3 内存态全长结果

当前 `VadAnalysisResult` 包含：

- `media_path`
- `engine_key`
- `duration_sec`
- `covered_ranges`
- `speech_segments`

其中：

- `covered_ranges` 表示哪些时间段已经被该 engine 真正分析过
- `speech_segments` 是该媒体在该 engine 下的全长聚合结果

## 4. 区间合并策略

当前 `src/vad/store.py` 的行为不是简单追加，而是“替换后归并”：

1. 找到目标 `time_range`
2. 删除旧结果中与该范围重叠的部分
3. 保留重叠范围外的旧 segment
4. 插入本次新 segment
5. 对相邻或相接的 segment 做归并
6. 对 `covered_ranges` 做归并

这样可以支持：

- 重跑同一小段
- 先跑局部，后跑更大范围
- 先有旧结果，再对其中一个区间进行修正

## 5. Silero 如何配置参数

当前 `SileroVadEngine` 的构造参数在 `src/vad/adapters/silero_adapter.py` 中定义。

### 5.1 当前可配置项

- `sample_rate`
  - 默认：`8000`
  - 作用：`ffmpeg` 解码输出采样率，同时传给 `Silero`
  - 说明：当前代码默认走 8k；若后续改为 16k，需要同步验证模型表现与性能

- `threshold`
  - 默认：`0.5`
  - 作用：传给 `get_speech_timestamps(...)`
  - 一般规律：
    - 调高：更保守，更不容易把弱声/噪声判成语音
    - 调低：更激进，更容易抓到弱声，但误检风险更高

- `min_speech_duration_ms`
  - 默认：`250`
  - 作用：最短语音段时长阈值
  - 调大后会过滤更短的语音碎片

- `min_silence_duration_ms`
  - 默认：`100`
  - 作用：分段时需要满足的最短静音时长
  - 调大后会减少切分数量，让语音段更长

### 5.2 当前参数配置位置

当前参数是在 `VADExpTab` 中直接这样实例化的：

```python
self.vad_service = VadApplicationService([SileroVadEngine()])
```

也就是说：

- 现在参数还是代码内固定值
- 尚未做配置文件接入
- 尚未做 GUI 参数面板

### 5.3 如果要修改 Silero 参数

最简单的改法：

```python
self.vad_service = VadApplicationService([
    SileroVadEngine(
        sample_rate=16000,
        threshold=0.45,
        min_speech_duration_ms=200,
        min_silence_duration_ms=120,
    )
])
```

如果后续需要让参数可配置，建议优先级如下：

1. 先接到一个独立的 VAD 配置对象
2. 再从配置文件读取
3. 最后再考虑接到 GUI 控件

## 6. 如果后续加入新的模型，需要改什么

这里的“模型”建议理解为“新的 VAD engine”，例如：

- WebRTC VAD
- pyannote
- 自定义 ONNX VAD
- 其他基于能量或神经网络的分段器

### 6.1 必改文件

#### 1. 新增 engine 适配器

新增类似文件：

- `src/vad/adapters/webrtc_adapter.py`
- `src/vad/adapters/pyannote_adapter.py`

要求：

- 实现 `VadEnginePort`
- 返回统一的 `list[SpeechSegment]`
- 提供唯一的 `engine_key`

#### 2. 注册到应用服务

当前在 `src/gui/vad_exp_tab.py` 中直接创建：

```python
VadApplicationService([SileroVadEngine()])
```

如果增加新 engine，需要把它一起传入，例如：

```python
VadApplicationService([
    SileroVadEngine(),
    WebRtcVadEngine(),
])
```

### 6.2 如果要显示到新的 GUI 轨道

还需要改：

- `src/gui/vad_exp_tab.py`
  - 给 `method_specs` 增加新的一条
  - 为新轨指定 `method_key`

- `src/gui/vad_exp/timeline_widgets.py`
  - 一般不需要大改
  - 只要 `method_key` 和 `VadInterval[]` 能对上，就能画出来

### 6.3 如果要支持新的参数

需要改：

- 对应 adapter 的构造函数
- `VADExpTab` 或后续配置加载层
- 如有需要，再补文档与 GUI 参数面板

### 6.4 如果新 engine 需要不同采样率或不同输入格式

需要重点检查：

- `src/vad/adapters/<new_engine>.py`
  - decode / resample 策略

- `src/vad/service.py`
  - 是否需要把当前 amplitude 提取与 VAD 解码进一步解耦

- `src/gui/vad_exp/timeline_widgets.py`
  - 当前 VAD 展示本身按秒绘制，不强依赖采样率
  - 但如果未来要展示逐帧概率曲线，需要再抽象时间基准

## 7. 建议的后续改进顺序

建议按下面顺序继续演进：

1. 给 `VADExpTab.request_analysis_range(...)` 接一个真实的范围来源
   - 例如 Time Slicer 的 slice
   - 或 VAD 页手动输入起止时间

2. 把 `SileroVadEngine` 的参数抽成配置对象

3. 增加第 2 个真实 VAD engine
   - 用于验证 `ports` 抽象是否稳定

4. 明确 amplitude 的局部范围语义
   - 现在仍偏向“整段背景轨 + 局部 VAD”

5. 再考虑 GUI 参数面板和更细粒度可视化

## 8. 再开新会话时建议优先看的文件

如果未来要继续这块功能，建议优先阅读：

- `doc/vad-engine-silero-integration.md`
- `src/gui/vad_exp_tab.py`
- `src/gui/vad_exp/audio_parse_thread.py`
- `src/vad/service.py`
- `src/vad/adapters/silero_adapter.py`
- `src/vad/store.py`

这几个文件已经覆盖了当前实现的大部分关键决策。 
