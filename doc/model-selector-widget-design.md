# Model Selector Widget 设计文档

## 概述

Model Selector Widget 是一个可复用的 PyQt5 组件，用于在多个 Tab 中选择 AI 模型及其 Provider。该组件采用三栏布局（Model Family → Model → Provider），支持任务过滤、收藏模型/Provider 功能，并通过弹出式面板提供良好的交互体验。

---

## 核心设计理念

### 组件职责

| 职责 | 描述 |
|------|------|
| 任务过滤 | 根据初始化时传入的 `applicable_task` 筛选可用模型 |
| 模型浏览 | 三栏联动浏览：Model Family → Model → Provider |
| 收藏管理 | 支持收藏模型和 Provider，快速访问常用选项 |
| 选择输出 | 输出当前选中的 model name 和 provider name |

### 数据来源

- **模型配置**: 读取 `config.yaml` 中的 `api.models` 节点
- **星标状态**: 独立存储文件（建议 `~/.transcriber/starred_models.yaml`）

---

## 组件 API

### 初始化参数

```python
class ModelSelectorWidget(QWidget):
    def __init__(
        self,
        applicable_task: str,  # 必需：任务类型过滤器 (e.g., "audio-transcription", "text-chat")
        parent: QWidget = None,
        max_popup_height: int = 400,  # 可选：弹出面板最大高度（像素）
    ):
```

**注意**: `applicable_task` 参数在实例化后不可修改，决定了该实例可展示的模型范围。

### 信号 (Signals)

```python
# 当模型+provider选择确认时发射
selection_confirmed = pyqtSignal(str, str)  # (model_api_name, provider_name)

# 当选择变更但未确认时发射（用于预览/调试）
selection_changed = pyqtSignal(str, str)    # (model_api_name, provider_name)
```

### 公共方法

```python
def get_current_selection(self) -> tuple[str, str]:
    """返回当前选中的 (model_api_name, provider_name)"""

def set_selection(self, model: str, provider: str) -> bool:
    """设置当前选择，返回是否设置成功"""

def refresh_models(self):
    """重新从配置文件加载模型列表"""
```

---

## UI 布局设计

### 触发按钮

```
┌──────────────────────────────────┐
│  [Select Model ▼]                │  ← 折叠状态，显示当前选中模型名
└──────────────────────────────────┘
```

- 显示当前选中模型的 `display-name`
- 点击展开三栏选择器

### 弹出面板 (Popup Panel)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ┌─────────┐  ┌───────────────────────────────────┐  ┌──────────────┐  │
│  │Model    │  │   [Chat]  Model:        [OK]      │  │ Providers:   │  │
│  │Family:  │  ├───────────────────────────────────┤  ├──────────────┤  │
│  ├─────────┤  │ ┌───────────────────────────────┐ │  │              │  │
│  │ ☆Starred│  │ │ Whisper Large V2         ☆   │ │  │ aihubmix  ☆ │  │
│  ├─────────┤  │ │ whisper-1                    │ │  │              │  │
│  │ Whisper │  │ └───────────────────────────────┘ │  │ groq      ☆ │  │
│  │         │  │ ┌───────────────────────────────┐ │  │              │  │
│  │ Gemini  │  │ │ Whisper Large V3        ★   │ │  │ self-host ☆ │  │
│  │         │  │ │ whisper-large-v3 [selected]  │ │  │              │  │
│  │ Qwen    │  │ └───────────────────────────────┘ │  │              │  │
│  │         │  │ ┌───────────────────────────────┐ │  │              │  │
│  │ GLM     │  │ │ Gemini 2.5 Pro           ☆   │ │  │              │  │
│  │         │  │ │ gemini-2.5-pro               │ │  │              │  │
│  │ Rednote │  │ └───────────────────────────────┘ │  │              │  │
│  │         │  │           ↕ (scrollable)          │  │              │  │
│  └─────────┘  └───────────────────────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
     ↑                         ↑                              ↑
   固定宽度              可滚动，主内容区                   动态宽度
   ~80px                   stretch                        ~120px
```

### 布局对齐规则

- **Model Family** 列视觉上附着于 **Model** 列左侧（设计意图：虽然 Family 层级高于 Model，但视觉上作为辅助导航）
- **Popup 左边界** 与 Model 列头部 "Model:" 标签左对齐
- 根据屏幕剩余空间，Popup 在按钮上方或下方展开

---

## 三栏数据模型

### Column 1: Model Family

**数据源查询逻辑**:
```python
# 伪 SQL 表达
families = ["★ Starred"] + SELECT DISTINCT model-family 
                           FROM config.api.models 
                           WHERE applicable_task IN model.applicable-tasks
```

**交互行为**:
- 点击 Family 项 → Model 列滚动到该 Family 的第一个模型
- Model 列滚动时 → Family 高亮自动跟随当前可见区域的首个模型所属 Family

### Column 2: Model (Main Column)

**数据源查询逻辑**:
```python
models = [starred_models] + SELECT * FROM config.api.models 
                            WHERE applicable_task IN model.applicable-tasks
                            ORDER BY model-family, display-name
```

**Model Card 结构**:
```
┌────────────────────────────────────────┐
│ Whisper Large V3                    ★ │  ← display-name (大字) + 星标按钮
│ whisper-large-v3                       │  ← api-name (小字，灰色)
└────────────────────────────────────────┘
```

**字段说明**:
| 字段 | 来源 | 说明 |
|------|------|------|
| display-name | `model.display-name` | 用户可读名称 |
| api-name | model key in config | 实际 API 调用名 |
| star status | starred_models.yaml | 用户收藏状态 |

**星标模型显示规则**:
- 星标模型在 "★ Starred" 分组中出现一次
- 同时在其原本 Family 分组中保持位置（可能出现两次）

### Column 3: Providers

**数据源查询逻辑**:
```python
providers = SELECT provider_name 
            FROM current_selected_model.providers
```

**Provider Item 结构**:
```
┌──────────────────────┐
│ aihubmix          ★ │  ← provider name + 星标
└──────────────────────┘
```

**星标显示逻辑**:
| 状态 | 显示 |
|------|------|
| 未 hover 且未星标 | 无图标 |
| hover 未星标 | 浅色线框星 (☆) |
| 已星标 | 彩色填充星 (★) |

---

## 交互逻辑

### 打开/关闭 Popup

| 操作 | 行为 |
|------|------|
| 点击 "Select Model" 按钮 | 展开 Popup |
| 点击 Popup 外部区域 | 关闭 Popup，保存选择 |
| 按 ESC 键 | 关闭 Popup，保存选择 |
| 点击 OK 按钮 | 关闭 Popup，保存选择 |

### Model Card 点击

| 操作 | 行为 |
|------|------|
| 点击 **不同** Model Card | 选中该模型，Provider 列更新，**自动选中该模型的星标 Provider** |
| 点击 **当前已选** Model Card | 无行为（不重置 Provider 选择） |
| 点击 Model Card 上的星标 | Toggle 该模型的星标状态，不关闭 Popup |

### Provider 点击

| 操作 | 行为 |
|------|------|
| 点击 Provider 项 | 选中该 Provider |
| 点击 Provider 星标 | Toggle 该 Provider 的星标状态（相对于当前 Model），如有其他provider也星标，则取消其他provider的星标 |

### Family 点击

| 操作 | 行为 |
|------|------|
| 点击 Family 项 | Model 列滚动到该 Family 的第一个模型 |

### Model 列滚动

| 事件 | 行为 |
|------|------|
| Model 列视口顶部模型变化 | Family 列高亮状态跟随更新 |

---

## 星标状态存储

### 存储位置

```
<project_root>/model_selector_starred.yaml
```

> 注：存储文件位于项目根目录，非隐藏文件，便于版本控制和调试。

### 存储格式

```yaml
# starred_models.yaml
version: 1
starred:
  models:
    - whisper-large-v3
    - gemini-2.5-pro
  providers:
    whisper-large-v3:
      - groq
    gemini-2.5-pro:
      - aihubmix
```

### 读写时机

| 时机 | 操作 |
|------|------|
| Widget 初始化 | 加载星标状态 |
| 点击星标 | 立即保存到文件 |
| Popup 关闭 | 无额外保存（已实时保存） |

---

## 调试输出

每次点击 Model Card 或 Provider 后，在 console 输出：

```
[ModelSelector] Selected: model=whisper-large-v3, provider=groq
[ModelSelector] API Info: endpoint=https://api.groq.com/openai, scheme=openai-whisper
```

> 注意：此处仅打印信息，不执行实际 API 调用。

---

## 文件结构

```
src/gui/components/
├── model_selector/
│   ├── __init__.py
│   ├── model_selector_widget.py    # 主组件 (触发按钮 + Popup 管理)
│   ├── model_selector_popup.py     # 三栏弹出面板
│   ├── model_card.py               # Model 卡片组件
│   ├── family_list.py              # Model Family 列表
│   ├── provider_list.py            # Provider 列表
│   └── starred_storage.py          # 星标状态存储管理
```

---

## 使用示例

### 在 TranscriptionNewTab 中使用

```python
from src.gui.components.model_selector import ModelSelectorWidget

class TranscriptionNewTab(TabInterface):
    def init_ui(self):
        # ...
        
        # 替换原有的 model_selector + provider_selector
        self.model_selector = ModelSelectorWidget(
            applicable_task="audio-transcription",
            max_popup_height=350
        )
        self.model_selector.selection_confirmed.connect(self._on_model_selected)
        
        bottom_section.addWidget(self.model_selector)
        
    def _on_model_selected(self, model_name: str, provider_name: str):
        print(f"Selected: {model_name} @ {provider_name}")
        self.transcriber.set_model_and_provider(model_name, provider_name)
```

### 在 SentenceBuilderTab 中使用

```python
from src.gui.components.model_selector import ModelSelectorWidget

class ChatControlBar(QFrame):
    def init_ui(self):
        # ...
        
        # 替换原有的 QComboBox
        self.model_selector = ModelSelectorWidget(
            applicable_task="text-chat",
            max_popup_height=400
        )
        self.model_selector.selection_confirmed.connect(self._on_model_changed)
        
        layout.addWidget(self.model_selector)
```

---

## 配置依赖

### 从 config.yaml 读取的字段

```yaml
api:
  providers:
    <provider_name>:
      endpoint: <url>
      token: <token>
      
  models:
    <model_key>:
      display-name: <string>
      model-family: <string>
      applicable-tasks:
        - audio-transcription  # 或 text-chat, image-analysis
      api-scheme: <string>
      providers:
        <provider_name>:
          api-name: <string>  # 可选，默认使用 model_key
```

### 可配置的 UI 参数

| 参数 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| `model_selector.max_popup_height` | 构造函数参数 | 400px | Popup 最大高度 |
| Family 列宽度 | 硬编码 | 80px | Model Family 列固定宽度 |
| Provider 列宽度 | 硬编码 | 120px | Provider 列固定宽度 |

---

## 边界情况处理

| 情况 | 处理方式 |
|------|---------|
| 无匹配 applicable_task 的模型 | 显示 "No models available" 占位 |
| 模型无 provider | 显示 "No providers" 占位 |
| 星标的 provider 不存在于当前模型 | 忽略，不自动选中 |
| config.yaml 格式错误 | 捕获异常，显示错误提示 |
| 星标文件不存在 | 创建空文件 |

---

## 后续扩展点

1. **模型搜索**: 在 Model 列顶部添加搜索框
2. **最近使用**: 在 Starred 之后添加 "Recently Used" 分组
3. **模型详情 Tooltip**: Hover Model Card 显示 pricing、rate-limit 等信息
4. **Provider 状态指示**: 显示 Provider 的连通性状态（需要后端支持）

---

## 总结

Model Selector Widget 提供了一个统一的、可复用的模型选择体验，核心特点：

1. **任务过滤**: 通过 `applicable_task` 参数确保只显示相关模型
2. **三栏联动**: Family ↔ Model ↔ Provider 的交互联动
3. **收藏机制**: 模型和 Provider 双层收藏，快速访问
4. **独立存储**: 星标状态独立于主配置，用户友好
5. **复用性强**: 适用于 Transcription、Sentence Builder 等多个 Tab

