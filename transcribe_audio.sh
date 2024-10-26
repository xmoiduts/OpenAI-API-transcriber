#!/bin/bash

# usage: ./transcribe_audio.sh -i <input_file> -t <duration_from_start> -s <start_at_seconds>
# input_file: m4a compatible video/audio format, we use audio stream only
# start_at_seconds: from which offset we start transcribing, in integer seconds
# duration_from_start: how long a transcription should be transcribed since -s

API_KEY=$(<"api_key_archive")
echo "API_KEY length is ${#API_KEY}"
API_ENDPOINT="$(<"api_endpoint")/v1/audio/transcriptions"
TMP_DIR="./tmp_audio_segments" # 用于存放切割后的临时文件
mkdir -p ${TMP_DIR}
mkdir -p transcription_result

# 初始化变量
input_file=''
start_time=''
duration=''

# 解析命令行参数
while getopts "i:t:s:" opt; do
  case $opt in
    i) input_file="$OPTARG" # media/xxxx.mp4
    ;;
    t) duration="$OPTARG"
    ;;
    s) start_time="$OPTARG"
    ;;
    \?) echo "无效选项： -$OPTARG" >&2; exit 1
    ;;
  esac
done

# 检查输入参数
if [ -z "$input_file" ] || [ -z "$start_time" ] || [ -z "$duration" ]; then
    echo "请提供音频文件名、开始时间和持续时间。"
    echo "-i <input file> -s <start_at> -t <transcript_duration>"
    exit 1
fi

# 获取输入文件的完整路径和文件名
input_file_fullpath="$(realpath "$input_file")"
input_filename="$(basename "$input_file")"
FILE_NAME_CORE="${input_filename%.*}" # file name without extension name

# 使用ffmpeg切割音频文件，功能不成熟，暂且写死成copy vcodec.
# outsource to a python or bash file: 
# read source file format and audio size
# in scenarios below, send the original input file to openai, no ffmpeg:
#  input is m4a or mp3 
#  (openai supports: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, or webm)
#  and size < 25MB
# else: extract stream, -s and -t is a must
set -x
AUDIO_FILE_PATH="${TMP_DIR}/${FILE_NAME_CORE}_cut.m4a" #m4a
ffmpeg -i "${input_file_fullpath}" -y -ss $start_time -t $duration -vn "$AUDIO_FILE_PATH"
if [ $? -ne 0 ]; then
    echo "Failed to cut audio file. Exiting."
    exit 1
fi


# 使用basename获取文件名（排除扩展名）
filename="$(basename "${AUDIO_FILE_PATH%.*}")"
mkdir -p "transcription_result/${FILE_NAME_CORE}"
RESPONSE_FILE="transcription_result/${FILE_NAME_CORE}/${filename}_ss${start_time}-t${duration}.json"

set +x

if [ ! -f "$AUDIO_FILE_PATH" ]; then
    echo "切割的音频文件未生成，请检查路径和参数"
    exit 1
fi

# 发送请求并处理响应
    #-F "timestamp_granularities[]=word" \
set -x
curl -X POST "$API_ENDPOINT" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@${AUDIO_FILE_PATH}" \
    -F "model=whisper-1" \
    -F "response_format=verbose_json"  \
    -o "$RESPONSE_FILE"
CURL_RET_CODE=$?
set +x


# 检查请求是否成功
if [ $CURL_RET_CODE -eq 0 ]; then
    echo "转录成功，响应信息已保存到$RESPONSE_FILE"
else
    echo "请求失败，请检查脚本的输出来确定错误的原因。"
fi

#python add_timestamps_to_json.py response.json $start_time

# 清理临时文件
# rm -f "$AUDIO_FILE_PATH"