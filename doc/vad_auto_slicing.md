> plan

Auto-slicer
======

> 根据VAD结果自动切分音频，避免送入听写逻辑的音频分片中句子被从中间切断。

# Background:
我们已有 VAD 检测和手动看图切片的逻辑，现在需要研发根据 VAD 结果自动切片的功能。

# Current status:
程序当前是一键对全长视频进行 VAD 分析 + 手动拖动时间轴来查看 & 点选切片范围。拖动需要人工操作 + 定位指定长度的范围（如：推荐的 10 分钟）。对于典型长度高达 120 分钟的视频来说，人工操作重复性高，给人带来苦恼。

当前代码定位：
- 主入口：`src/gui/vad_exp_tab.py`
- 时间轴与手动切片：`src/gui/vad_exp/timeline_widgets.py`
- 时间轴 viewport 控制：`src/gui/vad_exp/timeline_controller.py`
- strength tile 缓存：`src/gui/vad_exp/tile_store.py`
- VAD/amplitude 后台线程：`src/gui/vad_exp/audio_parse_thread.py`
- VAD range merge/store：`src/vad/service.py`, `src/vad/store.py`
- 现有 flyer message：`src/gui/flying_message.py`

# target:
实现一键自动切片，并在用户点击 `send slices to transcribe tab` 明确 approve 后，把 slices 送入 Transcription New tab。

这里的 approval gate 分两层：
- Analysis approval：长媒体上，除启动时自动做的前 3 分钟 strength 外，其余 strength/VAD range 仍然需要用户通过现有 `Approve` 或 Slice Tool 操作触发。
- Slice approval：自动或手动切出的 slices 不直接送去听写，必须点击 Slice Tool 里的 `Send slices to transcribe tab`。

//需要更正你一个事情，我们替换的slice tool panel 对每个vad track是独立的，即:当前就会有3个slice tool panel.

## /btw
实现一个 minimalist countdown timer: hover on tab upper-middle, use flyer message style, updates per 1 second, shows `Waiting for <integer> seconds`, user cannot GUI interact with it, and it does not block any other GUI interactions.

此 countdown timer 在本 tab 内全局有效，应注册/实现到共享的 flyer message 代码：`src/gui/flying_message.py`。现有 `show_flying_message(parent, message, duration=4000)` 已经是非 modal QLabel + QTimer 动画，可以扩展一个可更新文本的 countdown helper，例如 `show_countdown_message(parent, seconds, on_finished=None, anchor="upper-middle")`。不要放进 `vad_exp_tab.py` 作为一次性私有实现，否则后面其他 tab 不能复用。

# behavior-autoslice:
当前切片行为是一键自动多线程开始 `{strength+vad}` 分析，但典型的 120 分钟视频 @ 10min slice 只需要分析 11 个切分点各自前后的两分钟，其余时间都无脑送入 whisper 即可。在 proposed auto slicing 中，应当做程序交互式的 `{切分点判断|vad}` 行为，交替进行这两个操作：

## conflict audit: existing parallel configs
现有并行配置来自 `ConfigManager().get_vad_config()`：
- `parallel_workers`
- `slice_minutes`
- `parallel_min_duration_seconds`

它们服务于 `ChunkedVadCoordinator` 的全长或长 range `{amplitude+vad}` 分析。`ChunkedVadCoordinator.should_use_parallel()` 只有在 request 同时包含 amplitude + VAD，并且 request range 大于 `parallel_min_duration_seconds` 时才启用。Auto-slicer 的 probe window 通常是 2 分钟左右，因此不应复用该 coordinator 的“长 range 并行切块”语义。// add comment to config yaml: does not serve auto-slicer.

实现建议：
- Auto-slicer 单独维护 `AutoSliceConfig`，不要把 `slice length` 写入现有 `tasks.vad.slice_minutes`，因为现有字段表示并行 worker 的内部 chunk 大小，不是 whisper slice length。
- Auto-slicer 每一轮只允许一个 `AudioParseThread` 运行。若用户停止 auto slice，递增 `parse_generation` 并 stop 当前 thread，避免旧结果回写 UI。
- Auto-slicer 触发 `request_analysis_range()` 时，应保留已分析 ranges 的 UI 状态。当前 `request_analysis_range()` 会先 `set_processing_state(processed_ranges=[], active_ranges=[])`，`_on_parse_success()` 也只显示 `current_request_range`，这会覆盖前几轮的处理进度。需要在 `VADExpTab` 维护 accumulated processed ranges。
- approval gate 和 auto-slicer 会共享同一个 `parse_thread`，auto-slicer 工作时应禁用/隐藏全长 `Approve` 行为，或至少让 full analysis approval 不可并发启动。

a. countdown-timer 3s, meanwhile 以当前时间（`max(0:00, latest cut point)`）为 base, 对 `base + slice_length (+/- lookaround)` 进行 VAD + strength 分析，展示 VAD 结果。
- 默认 `slice_length = ~10min`，典型 whisper API slice size。
- 备选 `slice_length = <3min`, `<1min`, `<30s`。
- `~10min` 是 soft limit：优先在中心附近寻找安静切点，允许因为静音点质量而略微超过/低于 10min。
- `<3min`, `<1min`, `<30s` 是 hard limit：切点不得晚于 hard target；若 target 前后找不到可用静音点，退化到 target 附近 strength 最低点或直接 target。
- 默认 lookaround：10min 使用 +/- 60s；3min 使用 +0s/-60s；1min 使用 +0s/-30s；30s 使用 +0s/-30s。后续可放进 memory file。
- countdown timer 和 VAD this segment finish 都有权跳转到 newly-calculated timestamp，但必须带 generation/token：只允许最新一轮 auto/manual navigation 生效，避免 timer 到点后覆盖用户刚刚停止或新一轮计算出的跳转。

b. 对 VAD 结果进行自动切分：找到此区域内靠近切分点中心（即 `base + slice_length`）且**无**语音时长较长的区间，将切分点设置在区间中间：
- 输入：当前 VAD result 中落在 probe window 内的 speech segments。
- silence gaps = probe window 减去 speech segments。
- 候选 gap 至少满足 `gap_duration >= min_silence_sec`，建议默认 0.8s；如果没有候选，则 fallback 到 window 内 strength 最低点；如果 strength 也不可用，则 fallback 到 target。
- 候选排序建议：先按 `abs(candidate - target)` 从小到大，再按 `gap_duration` 从大到小。// when implementing, docstring comment this in code.
- 假设空白区间为 `{a, b}`，原公式 `max((a+b)/2, b-3s)` 与“设置在区间中间”存在语义冲突：长空白区间会被推向右边界。建议实现为 `min((a+b)/2, b-3s)`，也就是优先 midpoint，但保证至少离右边 speech 起点 3s；如果 gap 短于 6s，则退化为 midpoint。// 不改，我们就是要让长空白区间推向右边界，否则whisper在音频前段无语音时会输出无意义内容，需要让每个切片尽快出现语音。
- after calculating this slice point, `{GUI}` jumps time axis to center the new slice point。现有 `TimelineController` 只有 `set_offset_px()`，需要新增 helper，例如 `center_on_time(time_sec)`。

c. 以新的切分点为新 base，重复 a/b。停止条件：
- `base >= duration_sec`
- 用户点击 Auto Slice stop
- VAD/strength 请求失败
- 连续 fallback 没有推进 base（需要最小推进量保护，例如 `next_cut > base + 1s`）

# behavior-manual slice:
a/c 与 autoslice 类似，b 由人工点击。

当前手动工具事实：
- `MethodTimelineTrackWidget.blade_mode_active` 控制刀片模式。
- 普通左键：在当前 hover timestamp 附近添加切分点。
- `Shift + 左键`：如果 snapped timestamp 已存在，则删除该切分点。
- hover preview 会显示当前 slice 的 upcoming duration。

规则：
- 创建一个切分点后，countdown-timer 3s，之后自动跳转至新的切分区域。
- 删除一个切分点后，不做任何自动跳转。
- 手动模式不应启动 VAD request；它只改变 confirmed cuts。// 不对，应该在每次创建一个切分点后，自动启动{基于当前切分点的}对下一个区域的vad request (即步骤a)，因为用户切分点不一定位于切分候选区域的中央，为什么我们不并行请求vad?就是因为下一个vad区域的选择依赖于当前用户切分点选取。
- 只有一个 row/port 能进入 manual slice。当前每个 `VadMethodRow` 自带 blade button，Slice Tool 后应把 manual state 收敛到面板层，避免多个 row 同时开刀片。

# GUI 设计：
定位到现有 `Send Slices` 和 scissor blade 处，替换本行的 2 个按钮，改成 `Slice Tool`。

点击后弹出微型控制窗口 `{Slice Toolpanel}`。控制窗口建议挂在当前 method row 的 control panel 附近，或作为轻量 `QFrame`/`QDialog` 非 modal 弹层；不要阻塞时间轴拖动。

## Slice toolpanel 设计：
第一行：文字 `Slice Tool: <VAD port name>`
- 当前实际可用 port name 是 `Silero VAD` / engine key `silero`。
- placeholder lanes `vad_method_2`, `vad_method_3` 还不应允许真正 auto slice，除非未来接入对应 engine。

第二行：动态文字注释栏 `{notebar}`，承接其他按钮的 onHover 效果。
- 用 eventFilter 或自定义 QPushButton enter/leave 更新 notebar。
- 不要只依赖 Qt tooltip，因为该面板需要把 hover guide 固定显示在同一栏。

第三行：文字 `Slice length:`，按钮 `~10min` `{default, overridable by memory file}` `<3min` `<1min` `<30s`，all mutex toggleable，active = 1。
- 可以 click inactive button 来启用。
- 不能 click active button 来关闭。
- 可以 click 其他 time button 来切换 active。
- `Slicelength.timebuttons.onHover`: notebar 显示 `Propose the length of each slice. ~ is soft target; < is hard maximum.`

第四行：mutex buttons: `Manual Slice` | `Auto Slice`
- `ManualSlice.onHover`: notebar 显示 `Click the timeline to add a cut; Shift+click an existing cut to remove it.`
- `AutoSlice.startbutton.onHover`: notebar 显示 `Start auto slicing from the latest cut point using VAD silence gaps. Click again to stop.`
- mutex: 只能有 <= 1 个模式被激活:
- manual slice disables/greys `{auto slice}` `{send slices}`，uses current toggled-on status and button appearance.
- autoslice disables `{manual slice}` `{send slices}` `{time buttons}` when working，uses toggled-on style when working，click to stop; revives the disabled buttons on autoslice complete.

第五行：按钮 `Send slices to transcribe tab`
- this is the slice approval。
- 调用现有链路：`VADExpTab._on_row_send_slices()` -> `MainWindow.push_slices_to_transcription()` -> `TranscriptionNewTab.replace_slices()`。
- 输出格式保持 `[(start_sec, duration_sec), ...]`，当前 `SegmentBar/SliceManager` 已支持该格式。

GUI 须知：
- 当前 `Send Slices` 显示正常，但小型按钮例如 toggle manual slicing 文字显示不全，仅在按钮最中心有一个芝麻大的像素区域，看不清到底是什么。
- 现有代码里 scissor button 使用 `setFixedSize(36, 28)`，未来如果按钮文字改成 `Manual Slice` 会必然被挤坏。Slice Toolpanel 内按钮不要使用固定 36px 宽度；使用 `setMinimumWidth()` + `QSizePolicy.Preferred/Expanding`。
- `CONTROL_PANEL_WIDTH = 220` 对多文字按钮较紧。若面板嵌入 control panel，需提高宽度或改为 popup；推荐 popup，避免挤压 timeline。
- 避免 Unicode icon-only 作为唯一信息；按钮文字以英文短语为主，icon 只作辅助。
//add above to some GUI principal files.

## approval gate 修改：
当前对于时长 > `APPROVAL_THRESHOLD_SEC` 的媒体，会显示 approval gate，要求用户点击 approve 后才能开始分析。我们将修改此项规定：当时长 > threshold 后，默认对前 3 分钟音频进行 strength 分析。其他时间段内的 strength 和 VAD 则需要如现在一样手动点击 approve 或通过 Slice Tool 触发后才能启动。

代码冲突：
- `VADExpTab.update_from_other_tab()` 当前 long media 分支只 `_show_cached_vad_result()`，不会启动任何 strength。
- `VadApplicationService.request_analysis()` 当前 amplitude-only 会调用 `extract_audio_strength_series(duration_sec=request.media_duration_sec)`，忽略 `request.time_range`，所以不能直接用它做“前 3 分钟 strength”。
- range-scoped strength helper 已存在：`extract_audio_strength_range_series()`，但当前只在 `ChunkedVadCoordinator._build_strength_patch()` 里使用。

实现建议：
- 为 `VadAnalysisOutput` 增加 `amplitude_patch`，或让 range-scoped request 在 partial_update 中返回 patch。
- `request_analysis_range(0, min(180, duration), include_amplitude=True, include_vad=False, auto_started=True)` 应只更新 0-3min 的 tile，而不是 set full strength series。
- long media 初始状态：保留 approve button，用文案说明 `Previewing first 3 minutes strength. Approve to analyze all / selected ranges.`
- 如果用户随后点击 approve 做全长分析，应继续沿用现有 full analysis 行为，但要避免覆盖已经渲染的 patch 时出现闪烁。

# memory file 设计：
项目下已有两类 YAML：
- `config.yaml` / `config.example.yaml`：项目配置和任务配置。
- `model_selector_starred.yaml`：GUI 用户选择状态，位于项目根目录。

新增切片工具记忆文件不应写入 `config.yaml`，因为它是 GUI 个人选择，不是项目任务配置。

建议目录与文件：
- directory: `./gui-state/vad-slicer/`
- file: `preferences.yaml`

建议初始结构：
```yaml
version: 1
slice_length:
  preset: "~10min"
  seconds: 600
  limit_mode: soft
lookaround_seconds:
  "~10min": 60
  "<3min": 30
  "<1min": 15
  "<30s": 8
```

在此文件中，记录用户的切片时长选择。首版只需要持久化 `slice_length`；`lookaround_seconds` 可以先 hard-code，等 UI 有设置入口后再持久化。


===


GPT:
我重读了。你新增的更正很关键，后续实现应按这几个新约束走：

Slice Toolpanel 是每个 VAD track 独立一个，不是全 tab 单例。
静音长 gap 的切点公式保留 max((a+b)/2, b-3s)，目标是让下一个 slice 尽快进入语音。
Manual Slice 创建切点后也要自动发起下一段候选区域的 VAD request，不能只移动 UI。
tasks.vad.slice_minutes 需要在 config.example.yaml 加注释：它服务现有 parallel VAD chunk，不服务 auto-slicer。
我看到还有两个文档内残留冲突建议清理掉：只有一个 row/port 能进入 manual slice 这句和“每个 track 独立 panel”需要重新表述；另外 behavior 里的 lookaround 已改成 +0/-60 等，但 memory YAML 示例还是单值 30/15/8，最好改成 before_seconds/after_seconds 结构。Linter 没有报错。