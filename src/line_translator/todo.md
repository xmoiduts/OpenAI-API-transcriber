gemini-3-flash的缺点：
当使用
```
{start_time} {end_time} content
```
的输入格式喂AI时：
会吐出这样的句子：
- start_time using input end time
- using non-existing start time
- time label broken (e.g. `{1334.5}`  ->  `{133b` ) 
- duplicating lines with just time label and no content