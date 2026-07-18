# Commit notes (2026-07-18)

## Subject

```
feat: run Assemble Sentence as a grouped task window with shared execution UI
```

## Body

Assemble Sentence used to spawn one popup per subtask, which cluttered the desktop
and made approve / retry / merge hard to oversee. This change hosts every subtask
of a single Assemble run in one ultra-wide `AssembleTaskGroupWindow`, with a shared
bottom toolbar for Approve All, Merge Output, and Close.

Execution UI is factored so the same panel works in both the group cards and the
legacy single-task popup: `TaskExecutionPanel` (prompt run, approval gate, stream,
quench, copy) lives inside each `AssembleSubtaskCard`, while `TaskPopupWindow`
becomes a thin wrapper for Merge Overlaps / Cutpoint. Supporting widgets include
`CompositeRetryButton` (primary retry + thinking popup) and
`ThinkingLevelSelector` (extracted from task cards).

Post-processing is pure and testable in `sentence_builder/assemble_output.py`:
strip trailing CJK/Latin punctuation per line, build ordered merge text with
searchable full-width placeholders for non-mergeable parts, and atomically write
`句轴原文.txt`. Closing a group with work in flight only hides the window so
background runs continue; summary-row magnifiers can reopen and focus a card.

Staged files: `assemble_task_group_window.py`, `composite_retry_button.py`,
`thinking_level_selector.py`, `assemble_output.py` (+ tests), plus wiring in
`sentence_builder_tab.py`, `task_popup_window.py`, `task_card.py`, `__init__.py`.

---

goal: 改善sentence builder中assemble sentence card的体验。



当前：点击 `Sentence Builder` tab -> Assemble Sentence Card 后，多个prompt进度框会一并弹出来，体验不佳。



propose: a new pop-up window, combining all individual task cards of a same task into a single window.



new window:

  title: Task group: Assemble Sentence

  section: horizonal-scrollable layout of individual task cards, individual task card containing everything for the single task card. the window is meant to be ultra-wide.

    single task card alters:

      no close button,

      add "retry" button, wire the `Assemble Sentence` card's `retry` event to the new window -> single task card's `retry` button. when hit retry, reset the current single task card's progress to initial state and directly launch the prompt API call.

      copy outout -> copy part output

      add button: remove trailing 标点符号 (e.g. ，。、)

  section: horizonal scroll bar to navigate through the horizontal scrollable task-cards layout

  section: bottom-toolbar, containing buttons for:

    approve all,

    merge output (to `句轴原文.txt`) # i18n?

    close



function:

  remove trailing 标点符号:

    use the regex of 切除 句尾 句号 。

    ```regex, vscode search bar

    ^(\{[^}]+\}\s+\{[^}]+\}\s+.*?)(?:。|\.|．)$

    ```

  merge output:

    decide the language(stub, use only zh-cn now),

    concatenate all the output into a single file, `{transcribed-media-working-directory}/句轴原文.txt`.



fix these:

  当前 assemble sentence 被注入了“每行正文长度提示” 的sidecar text area, 但其文字高度由于只显示半角数字而无法正确对应左侧实际全角文本。是否可以通过{调整sidecar行高}{or 为sidecar每行增加一个全角空格}来解决？



---



# Implemented (as of this conversation)



以下按**实际落地代码**整理；与上方初始 propose 不一致处以实际代码为准。

实现范围仅限本 conversation 内修改，未改动其他分支/目录。



## 文件清单



| 文件 | 角色 |

|------|------|

| `src/gui/components/task_popup_window.py` | 抽出 `TaskExecutionPanel`；`TaskPopupWindow` 变为兼容包装；自绘 `LengthGutter`；`LLMWorker` 不再劫持 stdout/stderr |

| `src/gui/components/assemble_task_group_window.py` | `AssembleTaskGroupWindow` + `AssembleSubtaskCard` + Merge hover 总览 |

| `src/gui/components/task_card.py` | summary 放大镜可 `focus_line_range` 到任务组内对应卡 |

| `src/gui/components/__init__.py` | 导出 `TaskExecutionPanel` / `AssembleTaskGroupWindow` |

| `src/gui/sentence_builder_tab.py` | Assemble 编排改为单任务组；run-id 隔离；再次 Start 确认 |

| `src/sentence_builder/assemble_output.py` | 尾标点、占位符、拼接、原子写 `句轴原文.txt` |

| `src/sentence_builder/test_assemble_output.py` | 纯逻辑单测 |



Merge Overlaps / Cutpoint 仍走 `TaskPopupWindow` 单窗，行为保持兼容。



## 1. 可嵌入任务执行面板



- `TaskExecutionPanel`：context / console log / response / approve / stop / copy；可嵌入任务组卡或单任务弹窗。

- `TaskPopupWindow`：薄包装，转发 `task_completed` / `gate_approved` / `stream_activity` / `auto_quenched`。

- `LLMWorker`：用 `ChatCore.set_callbacks(on_error=...)` 收错误；**不**重定向进程级 `sys.stdout/sys.stderr`（并发安全）。

- 失败时**保留**已流式 partial output，不再用错误文覆盖 response。

- 行长 sidecar：`ResponseWithLengthPanel` + 自绘 `LengthGutter`，按左侧 `QPlainTextEdit` 的 `QTextBlock` 几何对齐（解决 CJK/半角行高漂移）；不再用双文本框 + 全角空格 hack。



## 2. 任务组窗口 UI / 生命周期



`AssembleTaskGroupWindow`：



- 标题：`Task group: Assemble Sentence`

- 尺寸：当前屏幕 `availableGeometry` 的 **60%** 宽高，居中

- 内容区：固定宽 `CARD_WIDTH=520` 的子任务卡横向排列 + 横向滚动条

- 底栏：`Approve All` | `Merge Output` | `Close`



`AssembleSubtaskCard`（无 Close）：



- 内嵌 `TaskExecutionPanel`（`Copy Part Output`，无 Close）

- 额外：`Retry`、`Remove Trailing Punctuation`、`Mergeable: Yes/No`（可切换）

- Retry：清空 runtime → 绕过审批门禁 → 直接重发 API

- 尾标点：调用 `strip_trailing_punctuation`，**直接改可见输出**；此后 Copy / Merge 用改后文本



Close / 系统关闭：



- 有任务在跑：`hide()`，flying-message `Task running in background`，**不**停 worker

- 无任务在跑：同样 `hide()`，对象保留，可由放大镜再打开

- 旧任务组：创建新组后仍保留到应用退出（dangling，不自动清理）



## 3. 审批与编排（与初稿差异）



初稿/早期 plan 曾写「首个自动、其余 gated」。**实际代码已改为：**



- **每一个**有效 Assemble subtask 初始均为 `needs_approval=True`（待审批）

- 只有子卡 `Approve & Start` 或底栏 `Approve All`（并发批准全部 waiting）才会发请求

- summary 行初始状态均为 `untriggered`



`sentence_builder_tab._on_assemble_start`：



- 创建**一个** `AssembleTaskGroupWindow`，不再 N 个独立 popup

- `_assemble_run_id` 隔离：旧组信号不更新当前 summary

- 当前组仍有 running 时再次 Start：弹确认；确认后建新组、放大镜全部重绑到新组；旧组继续跑但不可再从 magnifier 恢复

- summary Start/Stop/Retry ↔ 组内同一 `line_range` 双向同步

- 放大镜：`bind_result_popup` → `group.focus_line_range(lr)`（show + 横向滚到该卡）



## 4. Mergeable / Merge Output



默认：



- success → mergeable=Yes

- error / interrupted / 未启动 → mergeable=No（写入占位）



手动切换：



- 终态且有输出（或 success）可切；running / waiting / idle 不可切

- 任一任务 running 时禁用 Merge



拼接（`build_merged_text`）：



- 按 1-based `task_index` 排序

- mergeable：写正文（去各 part 首尾空行）

- 非 mergeable：`【sub-task N for lines X-Y】`（全角【】，便于搜索）

- part 间单个 `\n`，文件末尾保留一个 `\n`



写入：



- 路径：`{result_dir}/句轴原文.txt`

- 已存在则确认覆盖；同目录临时文件 + `os.replace` 原子写

- 成功/失败均有提示



Merge 按钮 hover：



- 只读缩略总览（`WA_TransparentForMouseEvents`），离开按钮即关

- 色框：绿=mergeable，红=占位，橙=running

- 文案：`#N` + `start-end`



## 5. 尾标点（与初稿 regex 差异）



初稿 vscode 单行 `。|.|．` 已不用。实际：



```text

TRAILING_PUNCT_CHARS = "，。、,.．!?！？…"

# 每行末尾连续剥离上述字符

```



## 6. 验证



- `src/sentence_builder/test_assemble_output.py`：尾标点、占位、顺序、空行规整、末尾换行、原子写

- `py_compile` + 导入冒烟；离屏检查「全部 subtask waiting for approval」



## 行为速查



```text

Assemble Start

  -> 1x Task group window (60% screen)

  -> all cards: waiting approval

  -> Approve (card) | Approve All

  -> stream / auto-quench / stop / retry

  -> optional: strip trailing punct, toggle Mergeable

  -> Merge Output -> 句轴原文.txt (confirm overwrite)

  -> Close while running -> hide + "Task running in background"

  -> magnifier -> reopen group + scroll to card

```


