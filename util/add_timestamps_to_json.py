# Seems this file is no longer used, we keep it here in case use in the future. 

import json
import sys

def prune_and_adjust_segments(json_data, start_offset):
    """
    移除多余属性，保留segments的id, start, end, text
    并将ss参数值（秒）累加到每个segment的start属性上
    """
    if 'segments' in json_data:
        pruned_segments = []
        for segment in json_data['segments']:
            pruned_segment = {
                'id': segment['id'],
                'start': segment['start'] + start_offset,
                'end': segment['end'] + start_offset,
                'text': segment['text']
            }
            pruned_segments.append(pruned_segment)
        json_data['segments'] = pruned_segments
    return json_data

def add_duration_and_adjust_start(json_file, start_offset):
    """
    根据起始时间偏移调整segments中的时间戳
    """
    try:
        with open(json_file, 'r+', encoding='utf-8') as file:
            data = json.load(file)
            data = prune_and_adjust_segments(data, int(start_offset))  # 修剪并调整segments时间
            
            # 移动文件指针至文件的开头
            file.seek(0)
            # 写入更新后的JSON数据
            json.dump(data, file, ensure_ascii=False, indent=4)
            # 截断文件以移除旧的内容
            file.truncate()

    except FileNotFoundError:
        print(f"文件 {json_file} 未找到。")
    except json.JSONDecodeError:
        print(f"文件 {json_file} 不是有效的JSON格式。")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    # 接收命令行参数
    if len(sys.argv) != 4:
        print("用法: python script.py <filename> <ss>")
        sys.exit(1)

    json_file_path = sys.argv[1]
    ss = sys.argv[2]  # 开始时间偏移

    add_duration_and_adjust_start(json_file_path, ss)