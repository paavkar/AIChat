import os
import dotenv
import torch
from TTS.api import TTS
import time

from constants import audio_to_play_directory as audio_directory

# List available 🐸TTS models
#for model in TTS().list_models():
#    if "/en/" in model:
#        print(model)

dotenv.load_dotenv()

class TTSManager:

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = TTS("tts_models/en/jenny/jenny").to(self.device)
        os.makedirs(audio_directory, exist_ok=True)

    def text_to_audio_file(self, text: str = "It took me quite a long time to develop a voice, and now that I have it I'm not going to be silent.") -> dict:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_path = os.path.join(audio_directory, f"{timestamp}.wav")
        self.model.tts_to_file(text=text, file_path=output_path)

        if os.path.exists(output_path):
            return {"success": True, "output-path": output_path}
        else:
            return {"success": False}

    def text_to_audio(self, text: str):
        wav = self.model.tts(text=text)

        return wav

if __name__ == "__main__":
    tts_manager = TTSManager()
    tts_manager.text_to_audio_file()