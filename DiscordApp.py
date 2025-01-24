import time
import discord
from discord.ext import commands, voice_recv, tasks
import os
import dotenv
import asyncio
import numpy as np
from scipy.io.wavfile import write

from OllamaChat import OllamaClient
from TextToSpeech import TTSManager
from constants import audio_to_play_directory as audio_directory, recorded_audio_directory

dotenv.load_dotenv()

class DiscordClient(commands.Bot):
    def __init__(self, command_prefix):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.vc = None
        self.text_channel = None
        self.channel = None
        self.guild = None
        self.guild_id = None
        self.ollama_client = None
        self.connections = {}
        self.last_activity = None
        self.audio_file_path = None
        self.recording_file_path = None
        self.tts_manager = None

    async def on_ready(self):
        self.guild_id = int(os.getenv('DISCORD_GUILD'))
        self.guild = self.get_guild(self.guild_id)
        self.ollama_client = OllamaClient()
        os.makedirs(audio_directory, exist_ok=True)
        self.channel = discord.utils.get(self.guild.channels, name="General")
        self.text_channel = discord.utils.get(self.guild.channels, name="general")
        self.audio_file_path = os.path.join(audio_directory, "output.wav")
        self.recording_file_path = os.path.join(recorded_audio_directory, "recording.wav")
        self.tts_manager = TTSManager()

        print(f'Logged on as {self.user}!')

        await self.get_vc()

    async def on_message(self, message):
        if message.author == self.user:
            return
        #print(f'Message from {message.author}: {message.content}')
        #print(self.text_channel)

        await self.process_commands(message)

        # an example of using ollama
        #ollama_message = await self.ollama_client.ollama_chat_test()

    async def on_voice_state_update(self, member, before, after):
        if member == self.user and after.channel is None:
            if self.guild_id in self.connections:
                del self.connections[self.guild_id]
                self.vc = None
                if self.check_activity_task.is_running():
                    self.check_activity_task.stop()
                if self.check_inactivity_task.is_running():
                    self.check_inactivity_task.stop()

    async def get_vc(self):
        if self.guild_id not in self.connections:
            vc = await self.channel.connect(cls=voice_recv.VoiceRecvClient)  # Connect to the voice channel the author is in.
            self.connections.update({self.guild_id: vc})  # Updating the cache with the guild and channel.
        else:
            vc = self.connections[self.guild_id]

        self.vc = vc
        #if not self.check_activity_task.is_running():
        #    self.check_activity_task.start()

        # playing audio when joining the vc doesn't work
        #self.play_audio(self.audio_file_path)

        return vc

    def test_send(self):
        print("test")

    async def record(self):
        if self.vc is None:
            await self.get_vc()

        if len(self.vc.channel.members) > 1 and self.user in self.vc.channel.members:
            try:
                audio_sink = voice_recv.WaveSink(self.recording_file_path)
                if not self.vc.is_listening():
                    self.vc.listen(audio_sink)
                else:
                    return
                if self.check_activity_task.is_running():
                    self.check_activity_task.stop()

                if not self.check_inactivity_task.is_running():
                    self.check_inactivity_task.start()
            except Exception as e:
                print(e)
        else:
            print("Bot not in vc")

    @tasks.loop(seconds=0.1)
    async def check_inactivity_task(self):
        if self.vc is None:
            return

        if self.vc.is_playing():
            return

        current_time = asyncio.get_event_loop().time()

        for member in self.vc.channel.members:
            if member == self.user:
                continue

            if self.vc.get_speaking(member):
                self.last_activity = current_time
                return

        if self.last_activity and (current_time - self.last_activity > 1.0):
            self.vc.stop_listening()

            #if os.path.exists(self.recording_file_path):
            #    await self.text_channel.send(file=discord.File(self.recording_file_path))

            self.check_inactivity_task.stop()
            self.last_activity = None
            #self.check_activity_task.start()

    @tasks.loop(seconds=0.1)
    async def check_activity_task(self):
        if self.vc is None:
            return

        if self.vc.is_playing():
            return

        if len(self.vc.channel.members) > 1:
            for member in self.vc.channel.members:
                if member == self.user:
                    continue

                if not self.vc.is_listening():
                    await self.record()

    #@tasks.loop(seconds=0.1)
    def play_audio(self, file_path):
        if self.vc is None:
            return

        #if self.vc.is_listening():
        #    return

        #wav = self.tts_manager.text_to_audio()
        #audio_data = np.array(wav, dtype=np.int16)
        #sample_rate = 48000
        #write(file_path, sample_rate, audio_data)

        if not self.vc.is_playing():
            audio_source = discord.FFmpegPCMAudio(file_path)
            self.vc.play(audio_source)
        while self.vc.is_playing():
            time.sleep(0.1)

discord_client = DiscordClient(command_prefix='!')

@discord_client.command()
async def play(ctx):
    discord_client.play_audio(os.path.join("speech_output", "output.wav"))

@discord_client.command()
async def join(ctx):
    vc = await discord_client.get_vc()
    #await ctx.send(f"Connected to voice chat: {vc.channel}")

@discord_client.command()
async def record(ctx):
    await discord_client.record()

    #if os.path.exists(audio_file_path):
    #    await ctx.send(file=discord.File(audio_file_path))

@discord_client.command(name="stop")
async def stop_recording(ctx):
    if discord_client.vc is not None and discord_client.vc.is_listening():
        discord_client.vc.stop_listening()
        discord_client.check_inactivity_task.stop()
        #discord_client.check_activity_task.start()
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

@discord_client.command()
async def leave(ctx):
    if discord_client.vc is not None:
        del discord_client.connections[ctx.guild.id]  # Remove the guild from the cache.
        discord_client.vc = None
        await ctx.voice_client.disconnect()
        discord_client.check_inactivity_task.stop()
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

def start_discord_bot():
    discord_client.run(os.getenv("DISCORD_TOKEN"))

if __name__ == '__main__':
    discord_client.run(os.getenv("DISCORD_TOKEN"))