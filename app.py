import threading
import asyncio

from TwitchChat import *
from SpeechToText import *
from DiscordApp import *

if __name__ == '__main__':
    # Creates and runs the twitchio bot on a separate thread
    #bot_thread = threading.Thread(target=startTwitchBot)
    #bot_thread.start()

    #speech_thread = threading.Thread(target=start_speech_to_text())
    #speech_thread.start()

    discord_thread = threading.Thread(target=start_discord_bot())
    discord_thread.start()