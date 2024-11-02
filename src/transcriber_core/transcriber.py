import os
import json
import requests
from pathlib import Path
from typing import Optional, Callable

class WhisperTranscriber:
    def __init__(self):
        self.api_key = Path("api_key_archive").read_text().strip()
        self.api_endpoint = Path("api_endpoint").read_text().strip() + "/v1/audio/transcriptions"
        self.tmp_dir = Path("./tmp_audio_segments")
        self.result_dir = Path("./transcription_result")
        
        # Create necessary directories
        self.tmp_dir.mkdir(exist_ok=True)
        self.result_dir.mkdir(exist_ok=True)

    def transcribe(self, 
                   input_file: str | Path, 
                   start_time: int, 
                   duration: int,
                   cleanup_tmp: bool = True,
                   log_callback: Optional[Callable[[str], None]] = None) -> Optional[dict]:
        """
        Transcribe an audio segment using OpenAI's Whisper API.
        
        Args:
            input_file: Path to input media file
            start_time: Start time in seconds
            duration: Duration to transcribe in seconds
            cleanup_tmp: Whether to remove temporary files after transcription
            log_callback: Optional callback function for logging
            
        Returns:
            dict: Transcription result from Whisper API
            None: If transcription fails
        """
        try:
            self._log(log_callback, "Starting transcription process...")

            # Prepare file paths
            input_path = Path(input_file).resolve()
            file_stem = input_path.stem
            output_format = self._get_output_format(input_path)
            audio_segment = self.tmp_dir / f"{file_stem}_cut.{output_format}"
            
            # Cut audio segment using ffmpeg
            self._log(log_callback, "Cutting audio segment...")
            if not self._cut_audio_segment(
                input_path, audio_segment, start_time, duration, log_callback):
                return None

            # Prepare output directory and file
            result_dir = self.result_dir / file_stem
            result_dir.mkdir(exist_ok=True)
            result_file = result_dir / \
                f"{audio_segment.stem}_ss{start_time}-t{duration}.json"
            self._log(log_callback, f"...{result_file}")

            # Call Whisper API
            self._log(log_callback, "Calling Whisper API...")
            result = self._call_whisper_api(audio_segment, result_file, log_callback)

            # Cleanup if requested
            if cleanup_tmp and audio_segment.exists():
                self._log(log_callback, "Cleaning up temporary files...")
                audio_segment.unlink()

            
            if result:
                self._log(log_callback, "Transcription completed successfully.")
            else:
                self._log(log_callback, "Transcription failed.")

            return result

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
            
            # Build ffmpeg command
            cmd = (
                stream
                .output(str(output_file), **output_options)
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

    def _call_whisper_api(self, audio_file: Path, result_file: Path, log_callback: Optional[Callable[[str], None]] = None) -> Optional[dict]:
        """Call OpenAI Whisper API and save result."""
        try:
            self._log(log_callback, "Preparing API call...")
            with open(audio_file, 'rb') as f:
                files = {'file': f}
                headers = {'Authorization': f'Bearer {self.api_key}'}
                data = {
                    'model': 'whisper-1',
                    'response_format': 'verbose_json' 
                } # bug: verbose json not effective, actually responded with json.
                
                self._log(log_callback, "Sending request to Whisper API...")
                response = requests.post(
                    self.api_endpoint,
                    headers=headers,
                    files=files,
                    data=data
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Save result to file
                self._log(log_callback, "Saving transcription result...")
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                return result

        except Exception as e:
            self._log(log_callback, f"API call failed: {e}")
            return None
        
    def _log(self, log_callback: Optional[Callable[[str], None]], message: str):
        """Log a message using the provided callback if available."""
        if log_callback:
            log_callback(message)
        else:
            print(message)