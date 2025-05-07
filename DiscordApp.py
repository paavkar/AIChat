import discord
import os
import dotenv
import asyncio
import io
import datetime
import time
import tempfile
import whisper

# from OllamaChat import OllamaClient
# from TextToSpeech import TTSManager
from SpeechToText import SpeechToTextManager
from constants import audio_to_play_directory as audio_directory, recorded_audio_directory

dotenv.load_dotenv()

class AutoRecordSink(discord.sinks.WaveSink):
    def __init__(self):
        super().__init__()
        self.last_active = time.time()  # record when audio was last received
        self.utterances = []

    # This method is called each time audio data is processed.
    def write(self, data: bytes, user):
        super().write(data, user)
        self.last_active = time.time()  # update on every frame

        self.utterances.append((time.time(), user, data))

# 2. A helper coroutine to monitor for silence.
# When no audio is received for 2 seconds, it stops the current recording.
async def monitor_silence(vc: discord.VoiceClient, sink: AutoRecordSink):
    while True:
        await asyncio.sleep(0.1)
        if time.time() - sink.last_active >= 2:
            vc.stop_recording()  # this triggers the segment callback below
            break

class DiscordClient(discord.Bot):
    def __init__(self, command_prefix):
        super().__init__(command_prefix=command_prefix, intents=discord.Intents.all())
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
        self.segment_event = None
        self.id_to_display_name = {}
        self.stt = SpeechToTextManager()

    async def on_ready(self):
        self.guild_id = int(os.getenv('DISCORD_GUILD'))
        self.guild: discord.Guild = self.get_guild(self.guild_id)
        # self.ollama_client = OllamaClient()
        os.makedirs(audio_directory, exist_ok=True)
        os.makedirs(recorded_audio_directory, exist_ok=True)
        self.channel: discord.VoiceChannel = discord.utils.get(self.guild.channels, name="General")
        self.text_channel: discord.TextChannel = discord.utils.get(self.guild.channels, name="general")
        self.audio_file_path = os.path.join(audio_directory, "output.wav")
        # self.tts_manager = TTSManager()

        print(f'Logged on as {self.user}!')

        await self.get_vc()

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        print(f'Message from {message.author}: {message.content}')
        print(f"Message was sent in {message.channel}")

        #await self.process_commands(message)

        # an example of using ollama
        #ollama_message = await self.ollama_client.ollama_chat_test()

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None and after.channel is None:
            message = f"{member.display_name} left the vc."
            await self.channel.send(message)

    async def get_vc(self):
        if self.guild_id not in self.connections:
            vc: discord.VoiceClient = await self.channel.connect()  # Connect to the voice channel specified
            self.connections.update({self.guild_id: vc})  # Updating the cache with the guild and channel.
        else:
            vc = self.connections[self.guild_id]

        self.vc: discord.VoiceClient = vc

        while vc.is_connected():
            await self.record()

        return vc

    async def record(self):
        # Create a fresh sink for this segment
        sink = AutoRecordSink()

        # Create an event that the callback will set once the segment is finished.
        self.segment_event = asyncio.Event()

        # Start the recording segment.
        self.vc.start_recording(sink, self.segment_callback, self.channel)

        # In parallel, monitor for silence (stopping recording after 2 sec quiet).
        monitor_task = asyncio.create_task(monitor_silence(self.vc, sink))
        # Wait for the segment (silence) event
        await self.segment_event.wait()

        # If the silence task hasn’t finished, cancel it (it may be mid-loop).
        if not monitor_task.done():
            monitor_task.cancel()

        # A short delay before starting the next recording session.
        await asyncio.sleep(0.5)

    async def convert_utterances_usernames(self, sink: AutoRecordSink):
        """Converts stored user IDs in utterances to usernames (or display names)."""
        new_utterances = []
        for timestamp, user_id, data in sink.utterances:
            try:
                if user_id in self.id_to_display_name.keys():
                    username = self.id_to_display_name[user_id]
                else:
                    user_obj = await self.fetch_user(int(user_id))
                    username = user_obj.display_name
                    self.id_to_display_name[user_id] = user_obj.display_name
            except Exception as e:
                print(f"Error retrieving user {user_id}: {e}")
                username = str(user_id)  # fallback in case of an error
            new_utterances.append((timestamp, username, data))
        sink.utterances = new_utterances

    # Callback once recording stops (i.e. when silence is detected)
    async def segment_callback(self, sink_obj: AutoRecordSink, text_channel: discord.TextChannel):
        await self.convert_utterances_usernames(sink_obj)
        # Process the recorded data only if some audio was captured.
        if sink_obj.audio_data:
            # Format a list of users for whom audio was recorded.
            recorded_users = [f"<@{user_id}>" for user_id in sink_obj.audio_data.keys()]
            files = []

            for user_id, audio in sink_obj.audio_data.items():
                display_name = self.id_to_display_name[user_id]
                # Extract the entire content from the BytesIO buffer.
                audio.file.seek(0)
                data = audio.file.read()
                date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

                # Save the data to disk with your desired filename.
                disk_filename = f"{date}-recording_{display_name}.{sink_obj.encoding}"
                self.recording_file_path = os.path.join(recorded_audio_directory, disk_filename)
                with open(self.recording_file_path, "wb") as f:
                    f.write(data)
                print(f"Saved file to disk: {self.recording_file_path}")

                # Create a new BytesIO object for the Discord file,
                # ensuring it starts from the beginning.
                new_file_stream = io.BytesIO(data)
                discord_file = discord.File(new_file_stream, filename=f"{display_name}.{sink_obj.encoding}")
                files.append(discord_file)

            await text_channel.send(
                f"Finished recording audio for: {', '.join(recorded_users)}",
                files=files
            )
            transcription = self.stt.transcribe_audiofile(self.recording_file_path)
            print(transcription)
        else:
            print(f"[{time.strftime("%H:%M:%S", time.localtime(time.time()))}] Silence segment, no data recorded.")
        if sink_obj.utterances:
            combined_text = await self.stt.process_transcriptions(sink_obj)
            # await text_channel.send(f"Combined transcription:\n{combined_text}")
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"transcription_{timestamp}.txt"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(combined_text)
            print(f"[DEBUG] Saved transcription to file {filename}")

        self.segment_event.set()  # signal that the segment is done

    async def play_audio(self, file_path):
        if not self.vc.is_playing():
            source = discord.FFmpegPCMAudio(file_path)
            self.vc.play(source)

    async def stop_record(self):
        if self.guild.id in discord_client.connections:  # Check if the guild is in the cache.
            vc = discord_client.connections[self.guild.id]
            vc.stop_recording()  # Stop recording, and call the callback (once_done).
        else:
            await self.text_channel.respond(
                "I am currently not recording here.")  # Respond with this if we aren't recording.

discord_client = DiscordClient(command_prefix='!')

@discord_client.command()
async def play(ctx):
    await discord_client.play_audio(os.path.join("speech_output", "output.wav"))

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
    await discord_client.stop_record()

@discord_client.command()
async def leave(ctx):
    if discord_client.vc is not None:
        await discord_client.stop_record()
        discord_client.vc = None
        await ctx.voice_client.disconnect()
        del discord_client.connections[ctx.guild.id]  # Remove the guild from the cache.
        await ctx.delete()
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

if __name__ == '__main__':
    discord_client.run(os.getenv("DISCORD_TOKEN"))