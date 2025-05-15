import time
import os
import dotenv
import whisper
import tempfile
import io
import logging

dotenv.load_dotenv()

LOGGER: logging.Logger = logging.getLogger("SpeechToText")

logging.basicConfig(
    level=logging.INFO,  # Adjust this level (DEBUG, INFO, etc.) as needed
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),  # Outputs to the console
        #logging.FileHandler('discord.log', encoding='utf-8', mode='w')  # Outputs to a log file
    ]
)

class STTManager:
    def __init__(self):
        self.model = whisper.load_model("turbo")

    def transcribe_audiofile(self, file_path):
        # Transcribe the audio file.
        # The transcribe function returns a dictionary containing the transcription and extra info.
        try:
            timestamp = time.time()
            result = self.model.transcribe(audio=file_path, language="en")

            # Return the transcribed text.
            return {"success": True, "transcription": result["text"], "timestamp": timestamp}
        except Exception:
            return {"success": False}

    def transcribe_audio_stream(self, audio_stream: io.BytesIO, model) -> dict:
        """
        Given an io.BytesIO stream (containing WAV audio), writes the stream
        to a temporary file and transcribes it using the provided Whisper model.
        Returns the transcribed text.
        """
        transcription_result = {}
        # Use a temporary file to interface with Whisper.
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        try:
            # Write the BytesIO data to the temporary file.
            with os.fdopen(fd, "wb") as f:
                audio_stream.seek(0)
                data = audio_stream.read()
                f.write(data)

            # Call the Whisper transcription in an executor to avoid blocking.
            result = self.model.transcribe(audio=temp_path, language="en")
            transcription = result.get("text", "").strip()
            transcription_result = {"success": True, "transcription": transcription}
        except Exception as e:
            transcription_result = {"success": False, "error": e}
        finally:
            # Remove the temporary file.
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return transcription_result

    def process_utterances(self, sink_obj) -> dict:
        """
        Sorts the logged audio chunks by timestamp, transcribes each one using Whisper,
        and returns a combined string with one line per utterance containing the timestamp,
        user info, and the transcribed speech.
        """
        # Ensure utterances are in chronological order grouped by the user
        sorted_utterances = sorted(sink_obj.utterances, key=lambda x: (x[1], x[0]))

        merged_utterances = []
        merge_threshold = 0.5
        current_merge = None  # will contain [timestamp, user_id, merged_data]

        LOGGER.info(f"Started merging the utterances. There are {len(sorted_utterances)} utterances in total.")

        for timestamp, user, segment in sorted_utterances:
            if current_merge is None:
                # Initialize with a list of segments.
                current_merge = {
                    "start": timestamp,
                    "end": timestamp,
                    "user": user,
                    "segments": [segment]
                }
            else:
                if user == current_merge["user"]:
                    gap = timestamp - current_merge["end"]
                    if gap < merge_threshold:
                        current_merge["end"] = timestamp
                        current_merge["segments"].append(segment)
                    else:
                        # Finalize current merge.
                        merged_raw = b"".join(seg.raw_data for seg in current_merge["segments"])
                        # noinspection PyProtectedMember
                        concatenated_segment = current_merge["segments"][0]._spawn(merged_raw)
                        merged_utterances.append(
                            (current_merge["end"], current_merge["user"], concatenated_segment)
                        )
                        current_merge = {
                            "start": timestamp,
                            "end": timestamp,
                            "user": user,
                            "segments": [segment]
                        }
                else:
                    # Speaker changed: finalize the merge.
                    merged_raw = b"".join(seg.raw_data for seg in current_merge["segments"])
                    # noinspection PyProtectedMember
                    concatenated_segment = current_merge["segments"][0]._spawn(merged_raw)
                    merged_utterances.append(
                        (current_merge["end"], current_merge["user"], concatenated_segment)
                    )
                    current_merge = {
                        "start": timestamp,
                        "end": timestamp,
                        "user": user,
                        "segments": [segment]
                    }

        if current_merge is not None and current_merge["segments"]:
            merged_raw = b"".join(seg.raw_data for seg in current_merge["segments"])
            # noinspection PyProtectedMember
            concatenated_segment = current_merge["segments"][0]._spawn(merged_raw)
            merged_utterances.append(
                (current_merge["end"], current_merge["user"], concatenated_segment)
            )

        LOGGER.info(f"Merging process is done. There are {len(merged_utterances)} merged utterances in total. "
                    f"Starting transcription...")

        # Sort the merged utterances by time, so that transcription has proper timing
        merged_utterances = sorted(merged_utterances, key=lambda x: x[0])

        full_transcription = ""
        ts = merged_utterances[0][0]
        for timestamp, user, segment in merged_utterances:
            if timestamp < ts:
                ts = timestamp
            # Wrap the raw audio data in a BytesIO object.
            buf = io.BytesIO()
            segment.export(buf, format="wav")
            # Ensure the buffer is positioned at the start.
            buf.seek(0)
            # Transcribe the audio data using the helper.
            transcription_result = self.transcribe_audio_stream(buf, self.model)
            if not transcription_result["success"]:
                return transcription_result
            # Format the timestamp (HH.MM:SS).
            ts_str = time.strftime("%Y-%m-%d %H.%M:%S", time.localtime(timestamp))
            # Append to the full transcription with a user label.
            full_transcription += f"[{ts_str}] <{user}>: {transcription_result["transcription"]}\n"

        return {"success": True, "transcription": full_transcription, "timestamp": ts}