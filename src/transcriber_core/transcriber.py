import os
import json
import requests
import shutil
from pathlib import Path
from typing import Optional, Callable
from src.configuration_manager.configuration_manager import ConfigManager
from src.util.filename_sanitizer import FilenameSanitizer
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
        
        # Initialize filename sanitizer for Windows MAX_PATH compatibility
        self.filename_sanitizer = FilenameSanitizer(self.result_dir)
        if self.filename_sanitizer.get_max_stem_length() < 50:
            print(f"WARNING: Project path is very deep. Filenames will be "
                  f"aggressively shortened to {self.filename_sanitizer.get_max_stem_length()} characters "
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
        original_length = len(filename)
        result = self.filename_sanitizer.sanitize(filename)
        
        # Log if truncation occurred
        if len(result) < original_length:
            self._log(log_callback, 
                     f"Filename '{filename[:30]}...' exceeds safe length and will be shortened "
                     f"to prevent path errors.")
            self._log(log_callback, f"Shortened filename: '{result}'")
        
        return result

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
                   log_callback: Optional[Callable[[str], None]] = None,
                   perturbation_seed: Optional[int] = None,
                   needs_transcoding: bool = False,
                   target_bitrate: int = 128000,
                   output_format: Optional[str] = None,
                   preserve_audio_clips: bool = False,
                   dry_run: bool = False) -> Optional[dict]:
        """
        Transcribe an audio segment using OpenAI's Whisper API.
        
        Args:
            input_file: Path to input media file
            display_start: Display timestamp in seconds (for output filename)
            actual_start: Actual start time in seconds for cutting the audio
            duration: Duration to transcribe in seconds
            cleanup_tmp: Whether to remove temporary files after transcription
            log_callback: Optional callback function for logging
            perturbation_seed: Optional seed for audio perturbation to bypass caching
            needs_transcoding: Whether transcoding is needed (determined by time_slicer)
            target_bitrate: Target bitrate in bps for transcoding (default 128000 = 128kbps)
            output_format: Output format when transcoding (e.g., 'm4a'). None means keep original.
            preserve_audio_clips: Whether to preserve the cut audio clip in the result directory.
            dry_run: If True, skip the API call and return a dummy result.
            
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
            
            # Determine output format
            if output_format is None:
                # Keep original format
                output_ext = self._get_output_format(input_path)
            else:
                # Use specified format (e.g., 'm4a' for transcoding)
                output_ext = output_format
            
            # Sanitize filenames to avoid path length issues
            safe_file_stem = self._sanitize_filename(file_stem, log_callback=log_callback)
            
            # Generate unique temporary filename to avoid concurrent conflicts
            # Format: {safe_file_stem}_ss{display_start}-t{duration}_cut.{format}
            audio_segment = self.tmp_dir / f"{safe_file_stem}_ss{display_start}-t{duration}_cut.{output_ext}"
            
            self._log(log_callback, f"Using temporary audio file: {audio_segment}")
            
            # Cut audio segment using ffmpeg with optional perturbation and transcoding
            self._log(log_callback, "Cutting audio segment...")
            if needs_transcoding:
                self._log(log_callback, f"Transcoding audio to {target_bitrate/1000:.0f}kbps...")
            if not self._cut_audio_segment(
                input_path, audio_segment, actual_start, 
                duration - (actual_start - display_start), log_callback,
                perturbation_seed=perturbation_seed,
                needs_transcoding=needs_transcoding,
                target_bitrate=target_bitrate):
                return None
            
            # Calculate and log SHA256 if perturbation was applied
            if perturbation_seed is not None:
                sha256_hash = self._calculate_sha256(audio_segment)
                self._log(log_callback, f"Perturbed audio segment created. Seed: {perturbation_seed:04x}, SHA256: {sha256_hash}")

            # Prepare output directory and file with sanitized names
            result_dir = self.result_dir / safe_file_stem
            result_dir.mkdir(parents=True, exist_ok=True)
            
            # Preserve audio clip if requested
            if preserve_audio_clips:
                clips_dir = result_dir / "audio-clips"
                clips_dir.mkdir(exist_ok=True)
                # Copy the temporary audio file to the clips directory
                # Use the same filename as the temporary file
                clip_path = clips_dir / audio_segment.name
                shutil.copy2(audio_segment, clip_path)
                self._log(log_callback, f"Preserved audio clip to: {clip_path}")

            result_file = result_dir / f"{audio_segment.stem}_result.json"
            self._log(log_callback, f"Will save result to: {result_file}")

            # Skip API call if dry run
            if dry_run:
                self._log(log_callback, "Dry run enabled: Skipping API call.")
                result = {
                    "text": "[DRY RUN] Audio processed but not transcribed.",
                    "segments": [],
                    "words": [],
                    "duration": duration
                }
                # Save dummy result
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                return {
                    "result": result,
                    "result_dir": str(result_dir)
                }

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

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _cut_audio_segment(self, 
                        input_file: Path, 
                        output_file: Path, 
                        start_time: int, 
                        duration: int,
                        log_callback: Optional[Callable[[str], None]] = None,
                        perturbation_seed: Optional[int] = None,
                        needs_transcoding: bool = False,
                        target_bitrate: int = 128000) -> bool:
        """Cut audio segment using ffmpeg with format-specific optimizations, optional perturbation, and transcoding."""
        import ffmpeg
        import subprocess
        try:
            # Base stream with timing
            if start_time > 0:
                stream = ffmpeg.input(str(input_file), ss=start_time, t=duration)
            else:
                # Don't use ss for the start of the file to avoid skipping initial audio
                # if video stream starts later than audio stream (input seeking alignment issue)
                stream = ffmpeg.input(str(input_file), t=duration)
            
            # Get input format
            input_ext = input_file.suffix.lower()
            output_ext = output_file.suffix.lower()
            
            # Configure output options based on format
            output_options = {
                'vn': None,  # No video
            }
            
            # Check if we need to apply perturbation
            if perturbation_seed is not None:
                # Apply perturbation using audio filters
                # Generate deterministic noise based on seed
                # The noise level is extremely low (0.0005 = 0.05% of original volume)
                
                # Create noise source with same duration and seed
                # Using anoisesrc filter to generate white noise
                noise = ffmpeg.input(f"anoisesrc=d={duration}:a=0.0005:r=44100:seed={perturbation_seed}", f='lavfi')
                
                # Mix original audio with noise
                stream = ffmpeg.filter([stream, noise], 'amix', inputs=2, duration='first')
                
                # Force re-encoding when perturbation is applied
                self._log(log_callback, f"Applying audio perturbation with seed: {perturbation_seed:04x}")
            
            # Apply transcoding if needed
            if needs_transcoding:
                # Transcode to target bitrate
                output_options['acodec'] = 'aac' if output_ext == '.m4a' else 'libmp3lame'
                output_options['b:a'] = str(target_bitrate)
                self._log(log_callback, f"Transcoding audio to {target_bitrate/1000:.0f}kbps")
            else:
                # Can copy: use copy codec when format matches
                if input_ext == output_ext and input_ext in ['.mp3', '.m4a']:
                    output_options['acodec'] = 'copy'
            
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