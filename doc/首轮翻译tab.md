接下来我要设计一个全新的tab，所以我们先进行一些讨论。
tab名称：Line Translation
tab作用：对于transcribe后已处理为多行的原文内容，提供分段的翻译功能。
    处理过程略，目前它尚未自动化，还是个人工操作。
    多行原文内容示例：
```
{L1} original text
{L2} of the 
{L3} audio transcription
...
```
其中，花括号包围的是行号，格式为 char + int； 行号达到4位数是非常普遍的。
由于原文内容可以非常庞大，令其译文体积超出LLM单次completion的规模上限(namely 4096 tokens)，因此需要对原文进行分段处理，每次发送给LLM少量行数，以实现成功翻译。

---

# 层次结构设计：

LineTranslationTab (继承自TabInterface)
    mid: LineTranslationPanel (整体可通过tab底部scrollbar水平滚动)
        left: source_panel (垂直填满可视区域) {从上到下:}
            source_drop_zone: 拖放文件区域
            [text: "or" , open_file_button: "open from file"]
            [text: "or" , load_context_button: "load from context"] # disabled if no ctx
            [context_name_panel: underlined text: <context name>]
            # 通过上述任意方式加载后，本Tab内的workspace相关变量应替换为加载内容的目录
            load_to_workspace_button: "->" # 加载数据到右侧工作区的确认门
            meta_textbox: 多行文本框，显示加载内容的元信息:
                "lines信息"
                文件名: <filename>
                行数: <line count>

        mid: translation_status_strip (垂直填满可视区域) 
            固定宽度的状态条，类似交通导航中的拥堵状态条
            从上到下反映每行的翻译状态，每行用一个水平条表示【不准确，更像是一个矩形中不同行数的像素被填上了不同的颜色】
            状态颜色:
                白色: 未翻译
                绿色: 已翻译
                红色: 翻译失败
            特殊滚动行为：随LineTranslationPanel水平滚动，但到达tabwindow左边界时停止继续向左，但不影响trans_units_container的滚动。

        right: workspace_panel {实际翻译工作区}
            top: navigation_strip {固定在顶部的导航条}
                示例:
                    [L1-L100][L101-L200][L201-L300][L301-L400][L501-L600]...
                    当前可见区域用悬浮半透明矩形显示，类似vscode的小地图
            
            bottom: trans_units_container {独立水平滚动的翻译单元容器}
                translation_units水平排列: unit_1, unit_2, unit_3...
                每个translation_unit水平并列: [original_content | translation_content]
                
                original_content:
                    # 所有文本框特性:
                    # 可编辑、纯文本、多行、自动换行、窄滚动条
                    # 可选用vscode组件
                    [text: L1-L100, button: translate]
                    textbox1: 系统提示(所有units共享)
                    textbox2: 当前unit的翻译范围说明
                    textbox3: 历史翻译结果
                    textbox4: 术语表(所有units共享)
                    textbox5: 实际行内容
                    button: "translate" (顶部和底部各一个)

                translation_content:
                    <空白填充对齐>
                    textbox1: 翻译结果
                    [button:continue, button: → (加载结果到下一unit作为上下文)]

# 滚动机制说明
1. LineTranslationPanel作为一个超宽单元，其总宽度为source_panel + status_strip + workspace_panel(含所有translation_units)
2. 仅使用Tab底部scrollbar控制整体水平滚动，无需其他独立滚动机制
3. 特殊的停靠行为：
   - 当向左滚动时，source_panel可完全滚出可视区域
   - status_strip到达左边界时停止向左滚动（停靠）
   - navigation_strip在status_strip停靠后同样停靠在其右侧
   - 此时只有trans_units_container继续响应左滚动
4. 停靠后的视觉效果：
   [status_strip][      navigation_strip     ]
   --------------[...滚动中的translation_units...]

# 交互设计备忘
1. 对翻译面板中识别到的每个行号进行可视化标记，鼠标悬停时显示行号标签并跟随鼠标
2. 鼠标在translation_content中的→按钮悬停时，显示当前translation text box 1指向下一original text box 3的箭头提示
3. translation_status_strip需要支持多线程写入的数据结构，确保实时更新且数据一致
