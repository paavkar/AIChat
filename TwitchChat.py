import os
import threading
from datetime import datetime, timedelta
import random
import asyncio
from twitchio.ext import commands
from twitchio import *
#from TextToSpeech import *
#from AudioPlayer import *
import dotenv

dotenv.load_dotenv()

TWITCH_CHANNEL_NAME = 'menriq'

class TwitchChat(commands.Bot):
    tts_manager = None
    audio_player = None

    def __init__(self):
        super().__init__(token=os.getenv("TWITCH_ACCESS_TOKEN"), prefix='?', initial_channels=[TWITCH_CHANNEL_NAME])
        #self.tts_manager = TTSManager()
        #self.audio_player = AudioManager()

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f'User id is | {self.user_id}')

    async def event_message(self, message):
        await self.process_message(message)

    async def process_message(self, message: Message):
        print("We got a message from this person: " + message.author.name)
        print("Their message was " + message.content)

def start_twitch_bot():
    twitch_bot = TwitchChat()
    twitch_bot.run()