# 背景介绍：
我们有 @merged_word_timestamps.csv 和 @words_overlap.csv-like , 
其中：
- @merged_word_timestamps.csv 是whisper ASR听写结果的单词精度时间轴，读取前10行即可了解全文格式；其来源是多个并行的whisper实例的听写结果拼接，每相邻的两段听写结果中大概率有overlap段；
- @words_overlap.csv-like  是对 @merged_word_timestamps.csv  所有overlap部分的去重结果的concat，每两段overlap的去重结果之间会带有标题、行号等信息。

#你需要做：
将 @words_overlap.csv-like 的各个去重结果剪接进入@merged_word_timestamps.csv 中。

## 人类的具体做法：
@words_overlap.csv-like 中，去重结果的每个字都带有 `str(.2f)`的时间戳，人类找到每段overlap的首尾word, 对照其时间戳和文字内容，直接简单删除@merged_word_timestamps.csv 中的对应段落，并将这段去重overlap的具体内容简单复制粘贴进 @merged_word_timestamps.csv 的对应位置。不纠结去重结果内部的时间轴可能存在倒序问题。

## 你可能要注意的地方：
- 不要读取context card, 那与本任务无关；
- overlap的去重结果中可能在words之间夹带了空行。不要保留这些空行。