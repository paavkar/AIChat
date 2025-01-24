import os
import dotenv
import torch
from TTS.api import TTS

# List available 🐸TTS models
#for model in TTS().list_models():
#    if "/en/" in model:
#        print(model)

dotenv.load_dotenv()
audio_directory = "speech_output"

class TTSManager:

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tts = TTS("tts_models/en/jenny/jenny").to(self.device)
        self.output_path = os.path.join(audio_directory, "output.wav")
        os.makedirs(audio_directory, exist_ok=True)

    def text_to_audio(self, text: str = "It took me quite a long time to develop a voice, and now that I have it I'm not going to be silent."):
        self.tts.tts_to_file(text=text,
                             file_path=self.output_path)

if __name__ == "__main__":
    tts_manager = TTSManager()
    tts_manager.text_to_audio()