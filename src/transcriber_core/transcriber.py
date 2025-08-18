import os
import json
import requests
from pathlib import Path
from typing import Optional, Callable
from src.configuration_manager.configuration_manager import ConfigManager
import re
import platform
import hashlib

class WhisperTranscriber:
    def __init__(self):
        self.config_manager = ConfigManager()
        paths = self.config_manager.get_paths_config()
                
        self.tmp_dir = Path(paths.get('tmp_dir', './tmp_audio_segments'))
        self.result_dir = Path(paths.get('result_dir', './transcription_result'))

        # Create necessary directories
        self.tmp_dir.mkdir(exist_ok=True)
        self.result_dir.mkdir(exist_ok=True)
        
        # Calculate maximum safe filename length for Windows MAX_PATH compatibility
        self.max_stem_length = 200  # Default for non-Windows systems
        if platform.system() == "Windows":
            # Windows MAX_PATH is 260, use conservative 240 to account for variations
            WINDOWS_MAX_PATH = 240
            
            # Account for the longest possible suffix we generate:
            # /<safe_stem>/<safe_stem>_ss{start}-t{duration}_cut_result.json
            # Estimate: subdirectory separator + filename with timestamps + extension
            FILENAME_SUFFIX_MARGIN = 80
            
            abs_result_dir_len = len(str(self.result_dir.resolve()))
            
            # Calculate available length for stem (used twice: in directory and filename)
            available_length = WINDOWS_MAX_PATH - abs_result_dir_len - FILENAME_SUFFIX_MARGIN
            calculated_stem_length = available_length // 2
            
            # Ensure minimum viable length
            self.max_stem_length = max(20, calculated_stem_length)
            
            if self.max_stem_length < 50:
                print(f"WARNING: Project path is very deep. Filenames will be "
                      f"aggressively shortened to {self.max_stem_length} characters "
                      f"to prevent Windows MAX_PATH errors.")
        
        # self.api_key = Path("api_key_archive").read_text().strip()
        # self.api_endpoint = Path("api_endpoint").read_text().strip() + "/v1/audio/transcriptions"
        
        self.current_model = None
        self.current_provider = None

    def _sanitize_filename(self, filename: str, log_callback: Optional[Callable[[str], None]] = None) -> str:
        """
        Sanitize filename and apply hash-based truncation if needed to prevent Windows MAX_PATH issues.
        
        Args:
            filename: Original filename to sanitize
            log_callback: Optional callback for logging messages
            
        Returns:
            str: Sanitized filename, potentially with hash suffix if truncated
        """
        # Step 1: Basic sanitization of illegal characters
        # Remove/replace: < > : " | ? * and control characters
        sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '_', filename)
        
        # Replace brackets with parentheses (safer for paths)
        sanitized = sanitized.replace('[', '(').replace(']', ')')
        
        # Remove multiple consecutive spaces and replace with single space
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        sanitized = sanitized.rstrip('.-_ ')
        
        # Ensure the result is not empty
        if not sanitized:
            sanitized = "unnamed_file"
        
        # Step 2: Check if truncation and hashing are needed
        if len(sanitized) > self.max_stem_length:
            self._log(log_callback, 
                     f"Filename '{sanitized[:30]}...' exceeds safe length and will be shortened "
                     f"to prevent path errors.")
            
            # Generate deterministic hash from original filename to ensure uniqueness
            hash_suffix = hashlib.sha1(filename.encode('utf-8')).hexdigest()[:8]
            
            # Calculate prefix length to fit within our limit
            prefix_length = self.max_stem_length - len(hash_suffix) - 1  # -1 for underscore
            prefix_length = max(1, prefix_length)  # Ensure at least 1 character for prefix
            
            # Truncate and combine with hash
            truncated_prefix = sanitized[:prefix_length].rstrip('.-_ ')
            if not truncated_prefix:  # Fallback if prefix becomes empty
                truncated_prefix = "file"
            
            result = f"{truncated_prefix}_{hash_suffix}"
            self._log(log_callback, f"Shortened filename: '{result}'")
            return result
        
        return sanitized

    def set_model_and_provider(self, model: str, provider: str) -> bool:
        """
        Set both model and provider, validating configurations and loading necessary settings.
        
        Args:
            model: Name of the model to use
            provider: Name of the provider to use
            
        Returns:
            bool: True if both model and provider were set successfully, False otherwise
        """
        # Validate model exists
        model_config = self.config_manager.get_model_config(model)
        if not model_config:
            print(f"Error: Model '{model}' not found in configuration")
            return False
        
        # Validate provider exists for model
        if provider not in model_config.get('providers', {}):
            print(f"Error: Provider '{provider}' not found for model '{model}'")
            return False

        # Load API endpoint and token
        self.api_endpoint = self.config_manager.get_provider_endpoint(provider)
        if not self.api_endpoint:
            print(f"Error: No endpoint configured for provider '{provider}'")
            return False
        
        self.api_key = self.config_manager.get_provider_token(provider)
        if not self.api_key:
            print(f"Error: No API token configured for provider '{provider}'")
            return False
        
        # Get proxy settings if configured
        self.proxy_settings = self.config_manager.get_proxy_for_provider(model, provider)
        print(f"Proxy settings for provider '{provider}':"
              f"{self.proxy_settings}")
        
        # use segment precise when configured, otherwise word precise, is a Groq whisper API mitigation.
        self.timestamp_granularities = model_config['providers'][provider].get('timestamp_granularities', 'word')

        # Store model, provider and rate limit settings
        self.current_model = model
        self.current_provider = provider
        self.rate_limit_config = model_config['providers'][provider].get('rate-limit', {})
        
        # Add API endpoint suffix for transcription
        self.api_endpoint = f"{self.api_endpoint}/v1/audio/transcriptions"
        
        return True

    def transcribe(self, 
                   input_file: str | Path, 
                   display_start: int,
                   actual_start: int, 
                   duration: int,
                   cleanup_tmp: bool = True,
                   log_callback: Optional[Callable[[str], None]] = None) -> Optional[dict]:
        """
        Transcribe an audio segment using OpenAI's Whisper API.
        
        Args:
            input_file: Path to input media file
            display_start: Display timestamp in seconds (for output filename)
            actual_start: Actual start time in seconds for cutting the audio
            duration: Duration to transcribe in seconds
            cleanup_tmp: Whether to remove temporary files after transcription
            log_callback: Optional callback function for logging
            
        Returns:
            dict: Transcription result from Whisper API
            None: If transcription fails
        """
        try:
            # Set the log callback for configuration manager
            self.config_manager.set_log_callback(log_callback)

            self._log(log_callback, "Starting transcription process...")

            # Prepare file paths
            input_path = Path(input_file).resolve()
            file_stem = input_path.stem
            output_format = self._get_output_format(input_path)
            
            # Sanitize filenames to avoid path length issues
            safe_file_stem = self._sanitize_filename(file_stem, log_callback=log_callback)
            
            # Generate unique temporary filename to avoid concurrent conflicts
            # Format: {safe_file_stem}_ss{display_start}-t{duration}_cut.{format}
            audio_segment = self.tmp_dir / f"{safe_file_stem}_ss{display_start}-t{duration}_cut.{output_format}"
            
            self._log(log_callback, f"Using temporary audio file: {audio_segment}")
            
            # Cut audio segment using ffmpeg
            self._log(log_callback, "Cutting audio segment...")
            if not self._cut_audio_segment(
                input_path, audio_segment, actual_start, 
                duration - (actual_start - display_start), log_callback):
                return None

            # Prepare output directory and file with sanitized names
            result_dir = self.result_dir / safe_file_stem
            result_dir.mkdir(parents=True, exist_ok=True)
            result_file = result_dir / f"{audio_segment.stem}_result.json"
            self._log(log_callback, f"Will save result to: {result_file}")

            # Call Whisper API
            self._log(log_callback, "Calling Whisper API...")
            result = self._call_whisper_api(
                audio_segment, 
                result_file, 
                actual_start,
                display_start,
                log_callback
            )

            # Cleanup if requested
            if cleanup_tmp and audio_segment.exists():
                self._log(log_callback, "Cleaning up temporary files...")
                audio_segment.unlink()

            
            if result:
                self._log(log_callback, "Transcription completed successfully C.")
                # Return both result and the directory path for GUI integration
                return {
                    "result": result,
                    "result_dir": str(result_dir)
                }
            else:
                self._log(log_callback, "Transcription failed.")
                return None

        except Exception as e:
            self._log(log_callback, f"Transcription failed: {e}")
            return None

    def _get_output_format(self, input_file: Path) -> str:
        """Determine appropriate output format based on input file."""
        input_ext = input_file.suffix.lower()
        
        # For common lossy formats, maintain original format
        if input_ext in ['.mp3']:
            return input_ext[1:]  # Remove dot
        
        # For container formats (mp4, flv, etc), extract to m4a
        return 'm4a'

    def _cut_audio_segment(self, 
                        input_file: Path, 
                        output_file: Path, 
                        start_time: int, 
                        duration: int,
                        log_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Cut audio segment using ffmpeg with format-specific optimizations."""
        import ffmpeg
        import subprocess
        try:
            # Base stream with timing
            stream = ffmpeg.input(str(input_file), ss=start_time, t=duration)
            
            # Get input format
            input_ext = input_file.suffix.lower()
            output_ext = output_file.suffix.lower()
            
            # Configure output options based on format
            output_options = {
                'vn': None,  # No video
            }
            
            # For lossy sources, use copy codec when format matches
            if input_ext == output_ext and input_ext in ['.mp3', '.m4a']:
                output_options['acodec'] = 'copy'

            # TODO: else re-encode to around up to 16khz quality per Whisper architecture.
            
            # Build ffmpeg command
            cmd = (
                stream
                .output(str(output_file), **output_options)
                .overwrite_output()  # Add this line to overwrite existing files
                .compile()
            )
            
            # Print the command that will be executed
            self._log(log_callback, f"Executing FFmpeg command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                encoding='utf-8', 
                universal_newlines=True
            )
            
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self._log(log_callback, output.strip())
            
            rc = process.poll()
            return rc == 0
        except ffmpeg.Error as e:
            self._log(log_callback, f"FFmpeg error: {e.stderr}")
            return False

    def _call_whisper_api(self,
                          audio_file: Path,
                          result_file: Path,
                          actual_start: int,
                          display_start: int,
                          log_callback: 
                            Optional[Callable[[str], None]] = None) -> Optional[dict]:
        """Call OpenAI Whisper API and save result."""
        try:
            self._log(log_callback, "Preparing API call...")
            with open(audio_file, 'rb') as f:
                files = {'file': f}
                headers = {'Authorization': f'Bearer {self.api_key}'}
                data = {
                    'model': self.current_model,
                    'response_format': 'verbose_json'
                }

                # groq mitigation: fetch segment result if using groq, then process to word-precise-like format.
                if self.timestamp_granularities == 'word':
                    data['timestamp_granularities[]'] = 'word'

                # Add proxy settings if configured
                proxies = self.proxy_settings if hasattr(self, 'proxy_settings') else None
                self._log(log_callback, f"Sending request to Whisper API using"
                                        f" model: {self.current_model} with"
                                        f" provider {self.current_provider}"
                                        f" via proxy {proxies}")
                
                response = requests.post(
                    self.api_endpoint,
                    headers=headers,
                    files=files,
                    data=data,
                    proxies=proxies, timeout= 100
                    #timeout=10 # TODO: move to config
                )
                response.raise_for_status()
                
                result = response.json()
                # Adjust timestamps in result
                result = self._adjust_timestamps(result, actual_start)
                # groq mitigation:
                result_seg = None
                if self.timestamp_granularities == 'segment':
                    result_seg = result
                    result = self._convert_segments_to_words(result)
                # Save result to file
                self._log(log_callback, "Saving transcription result...")
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                    self._log(log_callback, f"dumped {f}")
                if result_seg:
                    segment_file = result_file.parent / (result_file.stem + "_segments.json")
                    with open(segment_file, 'w', encoding='utf-8') as f:
                        json.dump(result_seg, f, ensure_ascii=False, indent=2)
                        #self._log(log_callback, f"dumped {f}")
                
                return result
        except requests.exceptions.HTTPError as e:
            # Get the response content for more details
            error_detail = e.response.json() if e.response.content else str(e)
            self._log(log_callback, f"API call failed: {e}\nError details: {error_detail}")
            return None
        except Exception as e:
            self._log(log_callback, f"API call failed: {e}")
            return None

    def _adjust_timestamps(self, result: dict, time_offset: int) -> dict:
        """
        Adjust timestamps in transcription result by adding an offset.
        
        Args:
            result: Original transcription result from Whisper API
            time_offset: Time offset in seconds to add to timestamps
            
        Returns:
            dict: Adjusted transcription result
        """
        if not result or time_offset == 0:
            return result
            
        # Create a deep copy to avoid modifying the original
        adjusted = result.copy()

        # WHY the two duration adjustments below?
        # preserve whisper-transcribed duration
        adjusted["real_duration"] = result["duration"]
        
        # Adjust duration if present
        if 'duration' in adjusted:
           adjusted['duration'] += time_offset
        
        # Adjust word-level timestamps
        if 'words' in adjusted:
            for word in adjusted['words']:
                if 'start' in word:
                    word['start'] += time_offset
                if 'end' in word:
                    word['end'] += time_offset

        # Adjust segment-level timestamps
        if 'segments' in adjusted:
            for segment in adjusted['segments']:
                if 'start' in segment:
                    segment['start'] += time_offset
                if 'end' in segment:
                    segment['end'] += time_offset
                    
        return adjusted
    
    def _convert_segments_to_words(self, segment_result: dict) -> dict:
        """
        Convert segment-precise transcription result to word-precise format.
        Each segment becomes a single "word" entry with the same timing.

        Background:
            Groq supports no `word` timestamp granularities but will do
            so, we don't want to miss such a fast API provider. So we make
            this mitigation to utilize its segment-level result.
        
        Args:
            segment_result: Original segment-precise transcription result
            
        Returns:
            dict: Converted word-precise transcription result
        """
        if not segment_result or 'segments' not in segment_result:
            return segment_result
            
        word_result = segment_result.copy()
        
        # Convert segments to words format
        words = []
        # segment timestamp-specific, assembling all the segments to a paragraph.
        sentences = " ".join([segment['text'].strip() for segment in segment_result['segments']])
        for segment in segment_result['segments']:
            word_entry = {
                'word': segment['text'].strip(),
                'start': segment['start'],
                'end': segment['end']
            }
            words.append(word_entry)
        
        # Replace segments with words in result
        word_result['sentences'] = sentences
        word_result['words'] = words
        if 'segments' in word_result:
            del word_result['segments']
        
        return word_result
        
    def _log(self, log_callback: Optional[Callable[[str], None]], message: str):
        """Log a message using the provided callback if available."""
        if log_callback:
            log_callback(message)
        else:
            print(message)