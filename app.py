import os
import threading
import asyncio

from TwitchChat import *
from SpeechToText import *
from DiscordApp import *

async def main():
    twitchbot = TwitchChat()
    discord_task = discord_client.start(os.getenv("DISCORD_TOKEN"))
    twitch_task = twitchbot.start()
    await asyncio.gather(discord_task, twitch_task)

if __name__ == '__main__':
    # Creates and runs the twitchio bot on a separate thread
    #bot_thread = threading.Thread(target=startTwitchBot)
    #bot_thread.start()

    #discord_thread = threading.Thread(target=discord_client.run(os.getenv('DISCORD_TOKEN')))
    #discord_thread.start()

    asyncio.run(main())