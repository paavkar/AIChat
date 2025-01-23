import os
import threading
import asyncio

from TwitchChat import TwitchChat, start_twitch_bot
#from SpeechToText import *
from DiscordApp import discord_client, start_discord_bot

async def main():
    twitchbot = TwitchChat()

    #discord_task = discord_client.start(os.getenv("DISCORD_TOKEN"))
    #twitch_task = twitchbot.start()
    #await asyncio.gather(discord_task, twitch_task)

if __name__ == '__main__':
    twitch_bot = TwitchChat()
    #bot_thread = threading.Thread(target=twitch_bot.run(), daemon=True)
    #bot_thread.start()

    #discord_thread = threading.Thread(target=discord_client.run(os.getenv('DISCORD_TOKEN')))
    #discord_thread.start()

    #loop = asyncio.get_event_loop()
    #loop.create_task(discord_client.start(os.getenv("DISCORD_TOKEN")))
    #loop.create_task(twitch_bot.run())
    #loop.run_forever()

    #asyncio.run(main())
    start_discord_bot()
    #start_twitch_bot()