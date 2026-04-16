# Blade Mode 技术实现总结

## 修改文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/gui/vad_exp/timeline_widgets.py` | 主要修改 | 刀片模式的核心：状态、绘制、鼠标交互、按钮、信号 |
| `src/gui/vad_exp_tab.py` | 少量修改 | 连接 send 信号到 MainWindow 路由 |
| `src/gui/main_window.py` | 少量修改 | 新增 `push_slices_to_transcription` 路由方法 |
| `src/gui/transcription_new_tab.py` | 少量修改 | 新增 `replace_slices` 轻量接收方法 |
| `src/gui/segment_bar.py` | bug fix | `seconds_to_hms` 对 float 输入的 int 转换 |

## 架构

```
MethodControlPanel          MethodTimelineTrackWidget
  blade_toggled ─────────▶ set_blade_mode()
  send_clicked ──▶ VadMethodRow._on_send_slices()
                      │  get_slices(duration)
                      │  exit blade mode
                      ▼
                  VadMethodRow.send_slices signal
                      │
                      ▼
                  VADExpTab._on_row_send_slices()
                      │  _get_main_window()
                      ▼
                  MainWindow.push_slices_to_transcription(file, dur, slices)
                      │
                      ▼
                  TranscriptionNewTab.replace_slices(file, dur, slices)
                      │
                      ▼
                  SegmentBar.set_segments(slices)
```

## timeline_widgets.py 详细变更

### 新增导入

`import bisect`, `import math`, `pyqtSignal`, `QPushButton`

### MethodTimelineTrackWidget

**新增状态字段：**

- `blade_mode_active: bool`
- `confirmed_cuts: list[int]` — 排序的整秒切点
- `_hover_time_sec: float | None` — 鼠标当前时刻（灰色线）
- `_snapped_sec: int | None` — 最近整秒（彩色线）
- `_mouse_inside: bool`

**新增方法：**

- `set_blade_mode(active)` — 切换模式，关闭时清除 hover 状态但保留 confirmed 切点
- `get_slices(duration) -> list[tuple[float, float]]` — 切点 → `(start, duration)` 对，用 `math.ceil(duration)` 作为尾边界，过滤掉零时长片段

**鼠标重写（条件性）：**

- `enterEvent` / `leaveEvent`：跟踪 `_mouse_inside`
- `mousePressEvent`：刀片模式下消费左键点击（`bisect.insort` 添加切点，或 shift 移除），不触发父类的拖拽
- `mouseMoveEvent`：刀片模式下计算 hover/snap 坐标并 `update()`，否则委托给父类的拖拽

**paintEvent 新增 `_draw_blade_overlay(painter)`：**

绘制顺序在现有瓦片 + VAD overlay 之后、`painter.end()` 之前：

1. confirmed 切线：accent color, 2px 宽，全高
2. 灰色虚线：跟随鼠标 x
3. proposed 吸附线：accent color + alpha 100, 2px 宽（仅当该秒尚未 confirmed）
4. "upcoming" 文本块：Consolas 10pt，灰底 `(60,60,60,200)` 白字，左上角 `(8, 8)`

### MethodControlPanel

新增两个 `pyqtSignal`：`blade_toggled(bool)`, `send_clicked()`

新增两个按钮水平排列：
- ✂ 按钮（`setCheckable(True)`, 36x28px，checked 时高亮）
- "Send Slices" 按钮（普通触发，28px 高）

新增 `set_blade_checked(checked)` 供外部程序性反选（blockSignals 防止递归）

### VadMethodRow

新增 `send_slices = pyqtSignal(list)` 信号

构造函数中连接：
- `control_panel.blade_toggled → track_widget.set_blade_mode`
- `control_panel.send_clicked → _on_send_slices`

`_on_send_slices()`：调用 `get_slices()`，若刀片模式开启则自动关闭，emit `send_slices`

## vad_exp_tab.py 变更

- 在 `init_ui` 末尾为每个 `method_row` 连接 `send_slices → _on_row_send_slices`
- 新增 `_on_row_send_slices(slices)`：通过 `_get_main_window()` 遍历父级找到 MainWindow，调用 `push_slices_to_transcription`
- 新增 `_get_main_window()`：同 TimeSlicerTab 的 `get_main_window()` 模式

## main_window.py 变更

新增 `push_slices_to_transcription(file_path, duration, slices)`，直接转发到 `transcription_new_tab.replace_slices()`

## transcription_new_tab.py 变更

新增 `replace_slices(file_path, duration, slices)`：
- 设置 `self.file_path`, `self.duration`, `self.slices`
- 更新 `file_info_label` 显示
- 调用 `segment_bar.set_segments(slices, self.needs_transcoding, self.target_bitrate)`
- 启用 `transcribe_button`

与 `update_from_other_tab` 的区别：不覆盖 `needs_transcoding` / `target_bitrate` / `output_format` 等转码设置

## segment_bar.py bug fix

`seconds_to_hms` 方法原先直接对 `seconds` 做 `//` 和 `%`，当输入为 float 时返回 float 类型的 h/m/s，导致 `{h:02d}` 格式化抛出 `ValueError`。修复：在方法入口处 `total = int(seconds)` 后再做算术。
