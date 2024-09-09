# seems abandoned, we keep it here in case to use in the future.

# convert openai whisper-transcribed audio json to csv
# input: filename of the verbose transcription json object, 
#   object ref: https://platform.openai.com/docs/api-reference/audio/verbose-json-object
#   note: the timestamp granularity must be word-level, not segment level.
# output: a csv file named identical to input, change .json to .csv
#   format:
#     word, start, end

import json
import csv
import sys
import os

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

    # 写入CSV文件
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["word", "start", "end"])
        
        for word_info in words:
            word = word_info['word']
            start = round(float(word_info['start']), 2)
            end = round(float(word_info['end']), 2)
            csv_writer.writerow([word, start, end])
    
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