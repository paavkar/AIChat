import time
import os
import dotenv
import whisper
import tempfile
import io
import asyncio
from pydub import AudioSegment

dotenv.load_dotenv()

class SpeechToTextManager:
    def __init__(self):
        self.model = whisper.load_model("turbo")

    def transcribe_audiofile(self, file_path):
        # Transcribe the audio file.
        # The transcribe function returns a dictionary containing the transcription and extra info.
        result = self.model.transcribe(audio=file_path)

        # Return the transcribed text.
        return result["text"]

    async def transcribe_audiostream(self, audio_stream: io.BytesIO, model) -> str:
        """
        Given an io.BytesIO stream (containing WAV audio), writes the stream
        to a temporary file and transcribes it using the provided Whisper model.
        Returns the transcribed text.
        """
        # Use a temporary file to interface with Whisper.
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        try:
            # Write the BytesIO data to the temporary file.
            with os.fdopen(fd, "wb") as f:
                audio_stream.seek(0)
                data = audio_stream.read()
                f.write(data)

            loop = asyncio.get_running_loop()
            # Call the Whisper transcription in an executor to avoid blocking.
            result = await loop.run_in_executor(None, model.transcribe, temp_path)
            transcription = result.get("text", "").strip()

        finally:
            # Remove the temporary file.
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return transcription

    async def process_transcriptions(self, sink_obj) -> str:
        """
        Sorts the logged audio chunks by timestamp, transcribes each one using Whisper,
        and returns a combined string with one line per utterance containing the timestamp,
        user info, and the transcribed speech.
        """
        # Ensure utterances are in chronological order.
        sorted_utterances = sorted(sink_obj.utterances, key=lambda x: x[0])

        merged_utterances = []
        merge_threshold = 1.0
        max_merge_duration = 10.0
        current_merge = None  # will contain [timestamp, user_id, merged_data]

        for timestamp, user, data in sorted_utterances:
            if not isinstance(data, bytes):
                print(data)
                continue  # Skip invalid data.

            try:
                segment = AudioSegment.from_file(io.BytesIO(data), format="wav")
            except Exception as e:
                # If that fails, assume the data is raw PCM.
                try:
                    # Adjust these parameters based on how your audio data is recorded.
                    segment = AudioSegment.from_raw(io.BytesIO(data), sample_width=2, frame_rate=48000, channels=2)
                except Exception as e2:
                    print(f"Error parsing audio segment for user {user}: {e2}")
                    continue

            if current_merge is None:
                # Start a new merge segment.
                current_merge = {
                    "start": timestamp,
                    "end": timestamp,
                    "user": user,
                    "segment": segment
                }
            else:
                # If it's the same speaker, try to merge.
                if user == current_merge["user"]:
                    gap = timestamp - current_merge["end"]
                    overall_duration = timestamp - current_merge["start"]
                    # Check if the gap is small enough and overall duration is within our limit:
                    if gap < merge_threshold and overall_duration < max_merge_duration:
                        # Merge the current utterance.
                        current_merge["end"] = timestamp
                        current_merge["segment"] += segment
                    else:
                        # Either the gap is too large or the merged segment becomes too long.
                        merged_utterances.append(
                            (current_merge["end"], current_merge["user"], current_merge["segment"])
                        )
                        # Start a new merge segment.
                        current_merge = {
                            "start": timestamp,
                            "end": timestamp,
                            "user": user,
                            "segment": segment
                        }
                else:
                    # Different speaker: always finalize the current merge and start a new one.
                    merged_utterances.append(
                        (current_merge["end"], current_merge["user"], current_merge["segment"])
                    )
                    current_merge = {
                        "start": timestamp,
                        "end": timestamp,
                        "user": user,
                        "segment": segment
                    }
        if current_merge is not None:
            merged_utterances.append(
                (current_merge["end"], current_merge["user"], current_merge["segment"])
            )

        full_transcription = ""
        for timestamp, user, segment in merged_utterances:
            # Wrap the raw audio data in a BytesIO object.
            buf = io.BytesIO()
            segment.export(buf, format="wav")
            # Ensure the buffer is positioned at the start.
            buf.seek(0)
            # Transcribe the audio data using the helper.
            transcription = await self.transcribe_audiostream(buf, self.model)
            # Format the timestamp (HH:MM:SS).
            ts_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
            # Append to the full transcription with a user label.
            full_transcription += f"[{ts_str}] {user}: {transcription}\n"

        return full_transcription