import os
import random
from gtts import gTTS
from pydub import AudioSegment
import pygame
import dotenv

dotenv.load_dotenv()

AZURE_VOICES = [
    "en-US-DavisNeural",
    "en-US-TonyNeural",
    "en-US-JasonNeural",
    "en-US-GuyNeural",
    "en-US-JaneNeural",
    "en-US-NancyNeural",
    "en-US-JennyNeural",
    "en-US-AriaNeural",
]

AZURE_VOICE_STYLES = [
    # Currently using the 9 of the 11 available voice styles
    # Note that certain styles aren't available on all voices
    "angry",
    "cheerful",
    "excited",
    "hopeful",
    "sad",
    "shouting",
    "terrified",
    "unfriendly",
    "whispering"
]

AZURE_PREFIXES = {
    "(angry)" : "angry",
    "(cheerful)" : "cheerful",
    "(excited)" : "excited",
    "(hopeful)" : "hopeful",
    "(sad)" : "sad",
    "(shouting)" : "shouting",
    "(shout)" : "shouting",
    "(terrified)" : "terrified",
    "(unfriendly)" : "unfriendly",
    "(whispering)" : "whispering",
    "(whisper)" : "whispering",
    "(random)" : "random"
}

class TTSManager:
    azure_speech = None
    azure_synthesiser = None

    def __init__(self):
        pygame.init()
        # Creates an instance of a speech config with specified subscription key and service region.
        # Replace with your own subscription key and service region (e.g., "westus").
        #self.azure_speech = speechsdk.SpeechConfig(subscription=os.getenv('AZURE_TTS_KEY'),
        #                                                 region=os.getenv('AZURE_TTS_REGION'))
        # Set the voice name, refer to https://aka.ms/speech/voices/neural for full list.
        self.azure_speech.speech_synthesis_voice_name = "en-US-AriaNeural"
        # Creates a speech synthesizer. Setting audio_config to None means it won't play the synthesized text out loud.
        #self.azure_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.azure_speech, audio_config=None)

        # Returns the path to the new .wav file

    def text_to_audio(self, text: str, voice_name="random", voice_style="random"):
        if voice_name == "random":
            voice_name = random.choice(AZURE_VOICES)
        if voice_style == "random":
            voice_style = random.choice(AZURE_VOICE_STYLES)

        # Change the voice style if the message includes a prefix
        text = text.lower()
        if text.startswith("(") and ")" in text:
            prefix = text[0:(text.find(")") + 1)]
            if prefix in AZURE_PREFIXES:
                voice_style = AZURE_PREFIXES[prefix]
                text = text.removeprefix(prefix)
        if len(text) == 0:
            print("This message was empty")
            return
        if voice_style == "random":
            voice_style = random.choice(AZURE_VOICE_STYLES)

        ssml_text = (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'"
                     f"xmlns:mstts='http://www.w3.org/2001/mstts' xmlns:emo='http://www.w3.org/2009/10/emotionml'"
                     f"xml:lang='en-US'><voice name='{voice_name}'>"
                     f"<mstts:express-as style='{voice_style}'>{text}</mstts:express-as></voice></speak>")
        #result = self.azure_synthesizer.speak_ssml_async(ssml_text).get()

        output = os.path.join(os.path.abspath(os.curdir),
                              f"_Msg{str(hash(text))}{str(hash(voice_name))}{str(hash(voice_style))}.wav")
        #if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            #stream = speechsdk.AudioDataStream(result)
            #stream.save_to_wav_file(output)
        if False:
            pass
        else:
            # If Azure fails, use gTTS instead. gTTS saves as an mp3 by default, so convert it to a wav file after
            print("\n   Azure failed, using gTTS instead   \n")
            output_mp3 = output.replace(".wav", ".mp3")
            msgAudio = gTTS(text=text, lang='en', slow=False)
            msgAudio.save(output_mp3)
            audiosegment = AudioSegment.from_mp3(output_mp3)
            audiosegment.export(output, format="wav")

        return output