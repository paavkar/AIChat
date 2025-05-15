import discord
from discord.ext import commands
import os
import dotenv
import asyncio
import io
import datetime
import time
import redis.asyncio as redis
import json
import logging
from pydub import AudioSegment

from OllamaChat import OllamaClient
from TextToSpeech import TTSManager
from SpeechToText import STTManager
from constants import audio_to_play_directory as audio_directory, recorded_audio_directory, transcriptions_directory, BOT_CONFIG_KEY, llm_output_texts_directory

dotenv.load_dotenv()
LOGGER: logging.Logger = logging.getLogger("DiscordClient")

logging.basicConfig(
    level=logging.INFO,  # Adjust this level (DEBUG, INFO, etc.) as needed
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),  # Outputs to the console
        #logging.FileHandler('discord.log', encoding='utf-8', mode='w')  # Outputs to a log file
    ]
)

class AutoRecordSink(discord.sinks.WaveSink):
    def __init__(self):
        super().__init__()
        timestamp = time.time()
        self.last_active = timestamp  # record when audio was last received
        self.utterances = []

    # This method is called each time audio data is processed.
    def write(self, data: bytes, user):
        super().write(data, user)
        timestamp = time.time()
        self.last_active = timestamp  # update on every frame

        try:
            seg = AudioSegment.from_raw(io.BytesIO(data), sample_width=2, frame_rate=48000, channels=2)
            self.utterances.append((timestamp, user, seg))
        except Exception as e:
            LOGGER.error(f"Error parsing audio segment for user {user}: {e}")

# When no audio is received for 2 seconds, a response is triggered.
async def monitor_silence(vc: discord.VoiceClient, sink: AutoRecordSink):
    while True:
        await asyncio.sleep(0.1)
        elapsed = time.time() - sink.last_active
        if elapsed >= 1:
            vc.stop_recording()  # this triggers the segment callback below
            break

class DiscordClient(commands.Bot):
    def __init__(self, command_prefix):
        intents = discord.Intents.all()
        super().__init__(command_prefix=commands.when_mentioned_or(command_prefix), intents=intents)
        self.vc = None
        self.text_channel = None
        self.channel = None
        self.logs_channel = None
        self.guild = None
        self.guild_id = None
        self.connections = {}
        self.id_to_display_name = {}
        self.username_to_id = {}
        self.single_speaker = True
        self.speaker = ""
        self.last_activity = None
        self.recording_file_path = None
        self.segment_event = None
        self.get_response = False
        self.transcription_segments = []
        self.audio_queue = asyncio.Queue()
        self.redis_conn = redis.Redis(host="localhost", port=6379, db=0)
        self.config = {}
        self.twitch_raids = []
        self.priority_messages = []
        self.twitch_subscriptions = []
        self.transcribe_tasks = 0
        self.stt = STTManager()
        self.ollama_client = None
        self.tts = None
        self.previous_silence_segments = []
        self.existing_audio = False

    async def on_ready(self):
        config_data = await self.redis_conn.get(BOT_CONFIG_KEY)
        if config_data:
            self.config = json.loads(config_data)
        else:
            # Set default values if no configuration exists.
            self.config = {
                "timeout_duration": 600,
                "discord_actions_enabled": True,
                "handle_twitch_events": True,
                "dc_invite_link": True
            }
            await self.redis_conn.set(BOT_CONFIG_KEY, json.dumps(self.config))
        self.guild_id = int(os.getenv('DISCORD_GUILD'))
        self.guild: discord.Guild = self.get_guild(self.guild_id)
        self.ollama_client = OllamaClient()
        os.makedirs(audio_directory, exist_ok=True)
        os.makedirs(recorded_audio_directory, exist_ok=True)
        os.makedirs(transcriptions_directory, exist_ok=True)
        os.makedirs(llm_output_texts_directory, exist_ok=True)
        self.channel: discord.VoiceChannel = discord.utils.get(self.guild.channels, name="AIChat")
        self.text_channel: discord.TextChannel = discord.utils.get(self.guild.channels, name="general")
        self.logs_channel: discord.TextChannel = discord.utils.get(self.guild.channels, name="logs")
        self.tts = TTSManager()

        for member in self.guild.members:
            self.username_to_id[member.display_name] = member.id

        asyncio.create_task(self.listen_for_config_updates())
        asyncio.create_task(self.listen_for_twitch_events())
        asyncio.create_task(self._audio_player())
        LOGGER.info(f'Logged on as {self.user}!')
        LOGGER.info(f"User id: {self.user.id}")

        await self.get_vc()

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        print(f'Message from {message.author}: {message.content}')
        print(f"Message was sent in {message.channel}")

        await self.process_commands(message)

    async def listen_for_config_updates(self):
        pubsub = self.redis_conn.pubsub()
        await pubsub.subscribe("config_updates")
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message and message["data"]:
                try:
                    new_config = json.loads(message["data"])
                    # Update local configuration. You might merge dictionaries.
                    self.config.update(new_config)
                    LOGGER.info(f"Configuration updated: {self.config}")
                except Exception as e:
                    LOGGER.error("Failed to process config update:", e)
            await asyncio.sleep(1)

    async def listen_for_twitch_events(self):
        pubsub = self.redis_conn.pubsub()
        await pubsub.subscribe("twitch_events")
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message and message["data"]:
                try:
                    event = json.loads(message["data"])
                    match event["type"]:
                        case "raid":
                            self.twitch_raids.append(event)
                        case "subscription":
                            self.twitch_subscriptions.append(event)
                        case "bits":
                            self.priority_messages.append(event)
                        case "highlight_message":
                            self.priority_messages.append(event)
                except Exception as e:
                    LOGGER.error("Failed to process twitch event:", e)
            await asyncio.sleep(1)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None and after.channel is None:
            message = f"{member.display_name} left the vc: {before.channel.name}."
            await self.logs_channel.send(message)
            LOGGER.info(f"after.channel: {after.channel}")

        update_config = False
        if after.channel is not None and after.channel.id == self.channel.id:
            if before.channel is None or before.channel.id != self.channel.id:
                member_count = len(after.channel.members)
                if member_count > 1:
                    self.config["handle_twitch_events"] = False
                    update_config = True
        elif before.channel is not None and before.channel.id == self.channel.id:
            if after.channel is None or after.channel != self.channel.id:
                member_count = len(before.channel.members)
                if member_count <= 2:
                    self.config["handle_twitch_events"] = True
                    update_config = True

        if update_config:
            config_json = json.dumps(self.config)
            await self.redis_conn.set(BOT_CONFIG_KEY, config_json)
            # Publish to the config_updates channel.
            await self.redis_conn.publish("config_updates", config_json)
            message = f"Updated config: {config_json}"
            #await self.logs_channel.send(message)

    async def get_vc(self, ctx = None):
        if self.guild_id not in self.connections:
            vc: discord.VoiceClient = await self.channel.connect()  # Connect to the voice channel specified
            self.connections.update({self.guild_id: vc})  # Updating the cache with the guild and channel.
        else:
            vc = self.connections[self.guild_id]

        self.vc: discord.VoiceClient = vc

        if ctx is not None:
            await ctx.reply(f"Joined the vc: {vc.channel.name}")

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
        await asyncio.sleep(0.1)

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
                LOGGER.error(f"Error retrieving user {user_id}: {e}")
                username = str(user_id)  # fallback in case of an error
            new_utterances.append((timestamp, username, data))
        sink.utterances = new_utterances

    # Callback once recording stops (i.e. when silence is detected)
    async def segment_callback(self, sink_obj: AutoRecordSink, text_channel: discord.TextChannel):
        # offload handling the audio data on the sink on a separate task so that recording isn't paused
        asyncio.create_task(self.handle_segment(sink_obj))
        self.segment_event.set()  # signal that the segment is done

    async def handle_segment(self, sink_obj):
        await self.convert_utterances_usernames(sink_obj)
        # Process the recorded data only if some audio was captured.
        if sink_obj.audio_data:
            self.transcribe_tasks += 1
            self.previous_silence_segments = []
            self.existing_audio = True
            # Format a list of users for whom audio was recorded.
            recorded_users = [f"<@{user_id}>" for user_id in sink_obj.audio_data.keys()]

            for user_id, audio in sink_obj.audio_data.items():
                display_name = self.id_to_display_name[user_id]
                self.speaker = display_name
                # Extract the entire content from the BytesIO buffer.
                audio.file.seek(0)
                data = audio.file.read()
                date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

                disk_filename = f"{date}-recording_{display_name}.{sink_obj.encoding}"
                self.recording_file_path = os.path.join(recorded_audio_directory, disk_filename)
                with open(self.recording_file_path, "wb") as f:
                    f.write(data)
                LOGGER.info(f"Saved file to disk: {self.recording_file_path}")

            if self.single_speaker:
                LOGGER.info("Started transcribing the audio file.")
                await self.transcribe_segment()
            else:
                LOGGER.info("Started processing individual utterances to get a transcription.")
                await self.transcribe_utterances(sink_obj)
        else:
            LOGGER.info(f"Silence segment, no data recorded.")
            if len(self.previous_silence_segments) >= 3:
                # a check if the silence has been at least 2 seconds to signal for a response process
                if (self.previous_silence_segments[-1] - self.previous_silence_segments[-3] >= 2
                        and not self.get_response and self.existing_audio):
                    LOGGER.info("Signaling to get a response...")
                    self.get_response = True
                    self.existing_audio = False
            else:
                self.previous_silence_segments.append(time.time())

    async def transcribe_segment(self):
        transcription_result = await asyncio.to_thread(
            self.stt.transcribe_audiofile, self.recording_file_path
        )
        await self.process_transcription_result(transcription_result)

    async def transcribe_utterances(self, sink_obj):
        transcription_result = await asyncio.to_thread(
            self.stt.process_utterances, sink_obj
        )
        await self.process_transcription_result(transcription_result)

    async def process_transcription_result(self, transcription_result: dict):
        if transcription_result["success"]:
            LOGGER.info("Transcribing was successful.")
            file_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            timestamp = transcription_result["timestamp"]
            transcription = transcription_result["transcription"]
            segment = {
                "timestamp": timestamp,
            }
            self.transcription_segments.append(segment)
            if self.single_speaker:
                segment["speaker"] = self.speaker
                ts_str = time.strftime("%Y-%m-%d %H.%M:%S", time.localtime(timestamp))
                transcription = f"[{ts_str}] <{self.speaker}>: {transcription}\n"
            else:
                transcription = f"{transcription}"

            filename = f"transcription_{file_timestamp}.txt"
            segment["text"] = transcription

            self.transcribe_tasks -= 1
            if self.transcribe_tasks <= 0 and self.get_response:
                sorted_segments = sorted(self.transcription_segments, key=lambda s: s["timestamp"])

                final_transcription = ""
                for seg in sorted_segments:
                    final_transcription += f"{seg['text']}"

                file_path = os.path.join(transcriptions_directory, filename)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(final_transcription)

                await self.transform_transcription(final_transcription, file_timestamp)
                self.get_response = False
                self.transcription_segments = []
                self.previous_silence_segments = []
        else:
            LOGGER.error(transcription_result["error"])
            message = "There was an error with the transcription process."
            await self.error_message(message)
            self.transcribe_tasks = 0
            self.get_response = False
            self.transcription_segments = []
            self.previous_silence_segments = []

    async def error_message(self, message):
        tts_result = await asyncio.to_thread(self.tts.text_to_audio_file, message)
        if tts_result["success"]:
            await self.queue_audio(tts_result["output-path"])

    async def transform_transcription(self, transcription: str, timestamp: str):
        ollama_result = await self.get_ollama_response(transcription)

        if ollama_result["success"]:
            filename = f"output_{timestamp}.txt"
            file_path = os.path.join(llm_output_texts_directory, filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(ollama_result["response"])

            tts_result = await asyncio.to_thread(self.tts.text_to_audio_file, ollama_result["response"])

            if tts_result["success"]:
                await self.queue_audio(tts_result["output-path"])
            else:
                LOGGER.error("There was an error in the TTS method.")
        else:
            LOGGER.error(ollama_result["error"])
            message = "There was an error creating a response."
            await self.error_message(message)

    async def get_ollama_response(self, message: str) -> dict:
        ollama_response = await self.ollama_client.ollama_chat(message)

        return ollama_response

    async def queue_audio(self, file_path: str):
        """Add an audio file to the playback queue."""
        await self.audio_queue.put(file_path)

    async def play_audio(self, file_path):
        if not self.vc.is_playing():
            source = discord.FFmpegPCMAudio(file_path)
            self.vc.play(source)

    async def _audio_player(self):
        """Background task for playing queued audio files sequentially."""
        while True:
            # Wait for the next file in the queue.
            file_path = await self.audio_queue.get()
            # Create the audio source.
            source = discord.FFmpegPCMAudio(file_path)

            # Create an asyncio.Event that we'll wait on until playback is finished.
            finished = asyncio.Event()

            # Define a function to be run when playback is done.
            def after_playback(error):
                if error:
                    LOGGER.error(f"Playback error: {error}")
                # Safely notify the main thread that playback is complete.
                self.loop.call_soon_threadsafe(finished.set)

            # Begin playback. The callback is called when done.
            self.vc.play(source, after=after_playback)

            # Wait until the audio finishes playing.
            await finished.wait()

    async def stop_record(self):
        if self.guild.id in discord_client.connections:  # Check if the guild is in the cache.
            vc = discord_client.connections[self.guild.id]
            vc.stop_recording()  # Stop recording, and call the callback (once_done).
        else:
            await self.text_channel.respond(
                "I am currently not recording here.")  # Respond with this if we aren't recording.

    async def mod_timeout(self, target: str, *, reason: str = "Voice command"):
        """
        Sends a timeout command for a Twitch user.
        """
        command = {
            "action": "timeout",
            "target": target,
            "reason": reason
        }
        await self.redis_conn.publish("mod_commands", json.dumps(command))
        await self.logs_channel.send(f"Sent timeout command for {target}. Reason: {reason}")

    async def mod_ban(self, target: str, *, reason: str = "Voice command"):
        """
        Sends a ban command for a Twitch user.
        """
        command = {
            "action": "ban",
            "target": target,
            "reason": reason
        }
        await self.redis_conn.publish("mod_commands", json.dumps(command))
        await self.logs_channel.send(f"Sent ban command for {target}")

    async def dm_user(self, username: str, message: str):
        user_id = self.username_to_id[username]
        user = await self.get_or_fetch_user(user_id)
        if self.config["dc_invite_link"]:
            vc_invite = await self.channel.create_invite(max_age=3600, unique=True)
            message += f"\nJoin {self.channel.name}: {vc_invite.url}"
        try:
            await user.send(message)
        except discord.Forbidden:
            LOGGER.error("Could not send the dm.")

discord_client = DiscordClient(command_prefix='!')

@discord_client.command()
async def join(ctx: commands.Context):
    vc = await discord_client.get_vc(ctx)

@discord_client.command()
async def record(ctx: commands.Context):
    if discord_client.vc is not None:
        await discord_client.record()
    else:
        await ctx.reply("I am not currently in a VC. Use the !join command first.")

@discord_client.command(name="stop")
async def stop_recording(ctx: commands.Context):
    await discord_client.stop_record()

@discord_client.command()
async def chat(ctx: commands.Context, *, message):
    ollama_response = await discord_client.get_ollama_response(message)

    if ollama_response["success"]:
        await ctx.reply(ollama_response["response"])
    else:
        await ctx.reply("There was an error creating a response for you.")

@discord_client.slash_command(name="hello", description="Greets the user")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond(f"Hello {ctx.user.display_name}!")

@discord_client.command()
async def leave(ctx: commands.Context):
    if discord_client.vc is not None:
        await discord_client.stop_record()
        await discord_client.vc.disconnect()
        discord_client.vc = None
        del discord_client.connections[ctx.guild.id]
    else:
        await ctx.send("I am currently not in a voice channel.")

if __name__ == '__main__':
    discord_client.run(os.getenv("DISCORD_TOKEN"))