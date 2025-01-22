import time
import discord
from discord.ext import commands, voice_recv, tasks
import os
import dotenv
import asyncio

from OllamaChat import OllamaClient

dotenv.load_dotenv()
audio_directory = "dc_audio"

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
        self.last_activity = None

    async def on_ready(self):
        self.guild_id = int(os.getenv('DISCORD_GUILD'))
        self.guild = self.get_guild(self.guild_id)
        self.channel = discord.utils.get(self.guild.channels, name="General")
        self.text_channel = discord.utils.get(self.guild.channels, name="general")
        print(f'Logged on as {self.user}!')

        #self.vc = await self.get_vc()
        self.ollama_client = OllamaClient()
        os.makedirs(audio_directory, exist_ok=True)

    async def on_message(self, message):
        if message.author == self.user:
            return
        #print(f'Message from {message.author}: {message.content}')
        #print(self.text_channel)

        await self.process_commands(message)

        # an example of using ollama
        #ollama_message = await self.ollama_client.ollama_chat_test()

    async def on_voice_state_update(self, member, before, after):
        #if not before.channel and after.channel:
        #    if self.user not in after.channel.members:
                #await self.get_vc()
                #self.vc.start_recording(
                #    discord.sinks.WaveSink(),  # The sink type to use.
                #    once_done,  # What to do once done.
                #    after.channel  # The channel to disconnect from.
                #)
                #time.sleep(5)
        #        pass
                #self.vc.stop_recording()
        #if member == self.user and not after.channel:
        #    self.vc = None
        #    del self.connections[self.guild.id]
        pass

    async def get_vc(self):
        if self.guild.id not in self.connections:
            vc = await self.channel.connect(cls=voice_recv.VoiceRecvClient)  # Connect to the voice channel the author is in.
            self.connections.update({self.guild.id: vc})  # Updating the cache with the guild and channel.
        else:
            vc = self.connections[self.guild.id]

        self.vc = vc
        return vc

    def test_send(self):
        print("test")

    async def record(self):
        vc = await self.get_vc()
        audio_file_path = os.path.join(audio_directory, "recording.wav")

        if len(self.vc.channel.members) > 1 and self.user in self.vc.channel.members:
            try:
                audio_sink = voice_recv.WaveSink(audio_file_path)
                if not self.vc.is_listening():
                    self.vc.listen(audio_sink)
                else:
                    return
                self.check_inactivity_task.start()
            except Exception as e:
                print(e)
        else:
            print("Bot not in vc")

    @tasks.loop(seconds=0.1)
    async def check_inactivity_task(self):
        audio_file_path = os.path.join(audio_directory, "recording.wav")
        current_time = asyncio.get_event_loop().time()

        for member in self.vc.channel.members:
            if self.vc.get_speaking(member):
                self.last_activity = current_time
                return

        if self.last_activity and (current_time - self.last_activity > 1.0):
            self.vc.stop_listening()
            await self.text_channel.send("stopped recording.")
            # if os.path.exists(audio_file_path):
            #    await self.text_channel.send(file=discord.File(audio_file_path))
            self.check_inactivity_task.stop()
            self.last_activity = None

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
async def record(ctx):
    await discord_client.record()

    #if os.path.exists(audio_file_path):
    #    await ctx.send(file=discord.File(audio_file_path))

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

def start_discord_bot():
    discord_client.run(os.getenv("DISCORD_TOKEN"))