import os
import dotenv
import torch
from TTS.api import TTS
from gtts import gTTS

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
        self.output_path = os.path.join(audio_directory, "output.wav")
        os.makedirs(audio_directory, exist_ok=True)

    def text_to_audio(self, text: str = "It took me quite a long time to develop a voice, and now that I have it I'm not going to be silent."):
        self.model.tts_to_file(text=text, file_path=self.output_path)
        wav = self.model.tts(text=text)
        #tts = gTTS(text=text, lang="en")
        #tts.save(self.output_path)
        return wav

if __name__ == "__main__":
    tts_manager = TTSManager()
    tts_manager.text_to_audio()