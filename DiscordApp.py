import discord
from discord.ext import commands
import os
import dotenv

from OllamaChat import OllamaClient

dotenv.load_dotenv()

class DiscordClient(commands.Bot):
    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)

    async def on_ready(self):
        global guild
        global channel
        global ollama_client
        print(f'Logged on as {self.user}!')
        guild_id = os.getenv('DISCORD_GUILD')
        guild = discord_client.get_guild(int(guild_id))
        channel = discord.utils.get(guild.channels, name="General")

        vc = await self.get_vc()
        ollama_client = OllamaClient()

    async def on_message(self, message):
        print(f'Message from {message.author}: {message.content}')
        if message.author == self.user:
            return

        await self.process_commands(message)

        # an example of using ollama
        ollama_message = await ollama_client.ollama_chat_test()

    async def on_voice_state_update(self, member, before, after):
        if member == self.user and after.channel is None:
            del connections[guild.id]
            print("disconnected")

    async def get_vc(self):
        if guild.id not in connections:
            vc = await channel.connect()  # Connect to the voice channel the author is in.
            connections.update({guild.id: vc})  # Updating the cache with the guild and channel.
        else:
            vc = connections[guild.id]

        return vc

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

#client = discord.Bot(intents=intents)
#client = commands.Bot(command_prefix='!', intents=intents)
discord_client = DiscordClient(command_prefix='!', intents=intents)
connections = {}

@discord_client.command()
async def join(ctx):
    vc = await discord_client.get_vc()
    await ctx.send(f"Connected to voice chat: {vc.channel}")

@discord_client.command()
async def record(ctx):
    vc = await discord_client.get_vc()

    vc.start_recording(
        discord.sinks.WaveSink(),  # The sink type to use.
        once_done,  # What to do once done.
        ctx.channel  # The channel to disconnect from.
    )
    await ctx.respond("Started recording!")

async def once_done(sink: discord.sinks, text_channel: discord.TextChannel, *args):  # Our voice client already passes these in.
    recorded_users = [  # A list of recorded users
        f"<@{user_id}>"
        for user_id, audio in sink.audio_data.items()
    ]
    #await sink.vc.disconnect()  # Disconnect from the voice channel.
    files = [discord.File(audio.file, f"{user_id}.{sink.encoding}") for user_id, audio in sink.audio_data.items()]  # List down the files.
    await text_channel.send(f"finished recording audio for: {', '.join(recorded_users)}.", files=files)

@discord_client.command()
async def stop_recording(ctx):
    if ctx.guild.id in connections:  # Check if the guild is in the cache.
        vc = connections[ctx.guild.id]
        vc.stop_recording()  # Stop recording, and call the callback (once_done).
        #del connections[ctx.guild.id]  # Remove the guild from the cache.
        #await ctx.delete()  # And delete.
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

@discord_client.command()
async def leave(ctx):
    if ctx.guild.id in connections:  # Check if the guild is in the cache.
        del connections[ctx.guild.id]  # Remove the guild from the cache.
        #await ctx.delete()  # And delete.
        await ctx.voice_client.disconnect()
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

def start_discord_bot():
    try:
        discord_client.run(os.getenv("DISCORD_TOKEN"))
    finally:
        pass