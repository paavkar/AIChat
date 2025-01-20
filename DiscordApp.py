import discord
from discord.ext import commands
import os
import dotenv

from OllamaChat import OllamaClient

dotenv.load_dotenv()

class DiscordClient(commands.Bot):
    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.vc = None
        self.text_channel = None
        self.channel = None
        self.guild = None
        self.guild_id = None
        self.ollama_client = None
        self.connections = {}
        vc = None

    async def on_ready(self):
        self.guild_id = os.getenv('DISCORD_GUILD')
        self.guild = self.get_guild(int(self.guild_id))
        self.channel = discord.utils.get(self.guild.channels, name="General")
        self.text_channel = discord.utils.get(self.guild.channels, name="general")
        print(f'Logged on as {self.user}!')

        #self.vc = await self.get_vc()
        self.ollama_client = OllamaClient()

    async def on_message(self, message):
        if message.author == self.user:
            return
        print(f'Message from {message.author}: {message.content}')
        print(self.text_channel)

        await self.process_commands(message)

        # an example of using ollama
        ollama_message = await self.ollama_client.ollama_chat_test()

    async def on_voice_state_update(self, member, before, after):
        if member == self.user and after.channel is None:
            del self.connections[self.guild.id]
            print("disconnected")

    async def get_vc(self):
        if self.guild.id not in self.connections:
            vc = await self.channel.connect()  # Connect to the voice channel the author is in.
            self.connections.update({self.guild.id: vc})  # Updating the cache with the guild and channel.
        else:
            vc = self.connections[self.guild.id]

        self.vc = vc
        return vc

    def test_send(self):
        print("test")

bot_intents = discord.Intents.default()
bot_intents.members = True
bot_intents.message_content = True
bot_intents.voice_states = True

#client = discord.Bot(intents=intents)
#client = commands.Bot(command_prefix='!', intents=intents)
discord_client = DiscordClient(command_prefix='!', intents=bot_intents)

@discord_client.command()
async def join(ctx):
    vc = await discord_client.get_vc()
    await ctx.send(f"Connected to voice chat: {vc.channel}")

@discord_client.command()
async def record(ctx: commands.Context):
    vc = await discord_client.get_vc()

    vc.start_recording(
        discord.sinks.WaveSink(),  # The sink type to use.
        once_done,  # What to do once done.
        discord_client.channel  # The channel to disconnect from.
    )

async def once_done(sink: discord.sinks, text_channel: discord.TextChannel,
                    *args):  # Our voice client already passes these in.
    recorded_users = [  # A list of recorded users
        f"<@{user_id}>"
        for user_id, audio in sink.audio_data.items()
    ]
    # await sink.vc.disconnect()  # Disconnect from the voice channel.
    files = [discord.File(audio.file, f"{user_id}.{sink.encoding}") for user_id, audio in
             sink.audio_data.items()]  # List down the files.
    await discord_client.text_channel.send(f"finished recording audio for: {', '.join(recorded_users)}.", files=files)

@discord_client.command(name="stop")
async def stop_recording(ctx):
    if ctx.guild.id in discord_client.connections:  # Check if the guild is in the cache.
        vc = discord_client.connections[ctx.guild.id]
        vc.stop_recording()  # Stop recording, and call the callback (once_done).
        # del connections[ctx.guild.id]  # Remove the guild from the cache.
        # await ctx.delete()  # And delete.
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

@discord_client.command()
async def leave(ctx):
    if ctx.guild.id in discord_client.connections:  # Check if the guild is in the cache.
        #del connections[ctx.guild.id]  # Remove the guild from the cache.
        # await ctx.delete()  # And delete.
        await ctx.voice_client.disconnect()
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.