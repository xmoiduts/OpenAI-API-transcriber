# seems abandoned, we keep it here in case to use in the future.

# convert openai whisper-transcribed audio json to csv
# input: filename of the verbose transcription json object, 
#   object ref: https://platform.openai.com/docs/api-reference/audio/verbose-json-object
#   note: the timestamp granularity must be word-level, not segment level.
# output: a csv file named identical to input, change .json to .csv
#   format:
#     start end word
#   quoting rule:
#     - do NOT quote normal words
#     - ONLY quote whitespace-only word (e.g. " ") so the content isn't lost

import json
import sys
import os

def _format_word_field(word: str) -> str:
    # Keep consistent with src.asr_postprocess.exporters (offset mode)
    if word.strip() == "":
        word_escaped = word.replace('"', '""')
        return f'"{word_escaped}"'
    return word

def validate_json_data(data):
    """验证JSON数据的基本结构。"""
    # 确保最基本的键存在
    keys = ['task', 'language', 'duration', 'text', 'words']
    for key in keys:
        if key not in data:
            raise ValueError(f"Missing key in JSON data: {key}")
    
    # 检查'words'是否为列表
    if not isinstance(data['words'], list):
        raise ValueError("JSON key 'words' should be a list")

def convert_json_file_to_csv(json_filename):
    # 更改输出文件名拓展名为.csv
    base_filename = os.path.splitext(json_filename)[0]
    csv_filename = f"{base_filename}.csv"
    
    # 尝试打开并读取JSON文件
    try:
        with open(json_filename, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            validate_json_data(data)  # 调用验证函数
    except FileNotFoundError:
        print(f"Error: The file '{json_filename}' was not found.")
        raise
    except json.JSONDecodeError:
        print(f"Error: The file '{json_filename}' contains invalid JSON.")
        raise
    except ValueError as e:
        print(f"Error: {e}")
        raise

    words = data['words']

    # 写入“起止点”格式（参考 src.asr_postprocess.core 的 offset 导出）
    # 每行：{start:.2f} {end:.2f} {word_field}
    rows: list[str] = []
    for word_info in words:
        word = str(word_info.get('word', ''))
        start = float(word_info.get('start', 0.0))
        end = float(word_info.get('end', 0.0))
        start_str = f"{start:.2f}"
        end_str = f"{end:.2f}"
        word_field = _format_word_field(word)
        rows.append(f"{start_str} {end_str} {word_field}")

    with open(csv_filename, 'w', encoding='utf-8') as f:
        f.write("\n".join(rows))
    
    print(f"File '{csv_filename}' created successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py input.json")
        sys.exit(1)
    
    json_filename = sys.argv[1]
    
    try:
        convert_json_file_to_csv(json_filename)
    except Exception as e:
        print(f"An error occurred: {e}")