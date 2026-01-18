已建立 src/sentence_builder 目录。

你需要根据主项目的 ../ ocr 找到workflow的调用方法，并建立 sentence builder 组件。

# sentence builder 组件：
功能：将单字精度的时间轴转为句子精度的时间轴。
将使用LLM 而非基于规则的脚本来拼合句子。

# 数据流：

sentence builder module: calls chatbot-core, sends prompt and file (snippet) to AI model, AI model returns response, sentence builder monitors and postprocesses it.

to GUI: there will be a one-click button with parameter tuner panel in the GUI, invokes sentence builder module. 

gui侧，替换 sentence builder -> chatbot panel （保留panel代码备日后使用），将其替换为数个card view. 由于card view 较高，card views side panel仍需要上下滚动功能。

side panel 整体： [upper: scrollable card view; lower: model selector, settings button (placeholder), no start/stop button.]

card view:
1. name: deduplicate
interior:
  prompt card (load this task template)
  user prompt input (freetext input)
  start button
action:
  once click start button, pop-up a new window and show console logs and LLM prompt of this run. textedit box refer to transcription_new_tab.py. for context sent, make it collapsable. 
  collect reverse-order timing from merged_word_timestamps.csv with a new script. you may need to read latest transcription result folder and write the script. no deep optimization, generate some happy-path result is OK.
  then collect the context of the result timepoints using scripts/rangetime.py (may modify it). 
  create placeholder prompt file and load it into prompt editing textbox.
  then send to llm and collect response. yes response = success. we do not postprocess it now.

2. name: cutpoint
interior:
  prompt card
  user prompt input (freetext input)
  dragbar: lines per segment. onHover: mouse cursor becomes <-> (use same as time_slicer_tab.py), onDrag: update lines per segment by 100 lines.
  above value is for reference only, we load 100 lines around each planned cutpoint and send to llm then let LLM to decide the best cutpoint.
  start button

action:
    once click start button, pop-up a new window same as deduplicate. 
    also, we do not process the response now. just log it.

3. name: assemble sentence
interior:
  prompt card
  a table of sentence chunks line numbers like:
  ```
  line 1-3958 [button: -]
  line 3959-8002 [button: -]
  line 8003-11977 [button: -]
  [button: +]
  ```

  line numbers editable, table items addable and deletable.
  start button
action:
  once click start button, pop-up a new window for every line chunk in the list. each window follow the previous window designs. if possible, apply the rate control.
  also, we do not process the response now. just log it.


# **note and guidance**
上述三个子组件之间暂不考虑集成。我们希望每个组件都至少能跑完happy path. 所以不要过分优化。

