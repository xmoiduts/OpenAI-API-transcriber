#!/bin/bash

# 脚本接收参数或提示输入
API_KEY=$openai_api_key
AUDIO_FILE_PATH="./222_seg1.m4a" # 请替换your_audio.m4a为实际音频文件名
API_ENDPOINT="https://api.openai.com/v1/audio/transcriptions"
# 使用basename获取文件名（包含扩展名）
full_filename=$(basename "$AUDIO_FILE_PATH")
# 使用字符串替换或切片去掉扩展名
filename="${full_filename%.*}"
RESPONSE_FILE="transcription_result/${filename}.json" # 输出的文件名

# 请确保AUDIO_FILE_PATH指向实际的音频文件路径
if [ ! -f "$AUDIO_FILE_PATH" ]; then
    echo "指定的音频文件不存在，请检查路径。"
    exit 1
fi

# 发送请求并处理响应
curl -X POST "$API_ENDPOINT" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@$AUDIO_FILE_PATH" \
    -F "model=whisper-1" \
    -F "response_format=verbose_json" \
    --output $RESPONSE_FILE

    # optional: -F "language=auto" \

# 检查请求是否成功
if [ $? -eq 0 ]; then
    echo "转录成功，响应信息已保存到$RESPONSE_FILE"
else
    echo "请求失败，请检查脚本输出以确定错误原因。"
fi