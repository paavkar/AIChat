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

from OllamaChat import OllamaClient
from TextToSpeech import TTSManager
from SpeechToText import SpeechToTextManager
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

class DiscordClient(commands.Bot):
    def __init__(self, command_prefix):
        intents = discord.Intents.all()
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.vc = None
        self.text_channel = None
        self.channel = None
        self.logs_channel = None
        self.guild = None
        self.guild_id = None
        self.ollama_client = None
        self.connections = {}
        self.last_activity = None
        self.recording_file_path = None
        self.tts_manager = None
        self.segment_event = None
        self.id_to_display_name = {}
        self.stt = SpeechToTextManager()
        self.redis_conn = redis.Redis(host="localhost", port=6379, db=0)
        self.config = {}
        self.username_to_id = {}
        self.audio_queue = asyncio.Queue()
        self.single_speaker = True
        self.speaker = ""

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
        self.channel: discord.VoiceChannel = discord.utils.get(self.guild.channels, name="General")
        self.text_channel: discord.TextChannel = discord.utils.get(self.guild.channels, name="general")
        self.logs_channel: discord.TextChannel = discord.utils.get(self.guild.channels, name="logs")
        self.tts_manager = TTSManager()

        for member in self.guild.members:
            self.username_to_id[member.display_name] = member.id

        asyncio.create_task(self.listen_for_config_updates())
        asyncio.create_task(self._audio_player())
        LOGGER.info(f'Logged on as {self.user}!')
        LOGGER.info(f"User id: {self.user.id}")

        await self.get_vc()

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        print(f'Message from {message.author}: {message.content}')
        print(f"Message was sent in {message.channel}")

        #await self.process_commands(message)

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

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None and after.channel is None:
            message = f"{member.display_name} left the vc: {before.channel.name}."
            await self.logs_channel.send(message)
            LOGGER.debug(f"after.channel: {after.channel}")

        update_config = False
        if after.channel is not None and len(after.channel.members) > 1:
            self.config["handle_twitch_events"] = False
            update_config = True
        elif before.channel is not None and len(before.channel.members) < 2:
            self.config["handle_twitch_events"] = True
            update_config = True
        if before.channel is None and after.channel is not None and len(after.channel.members) < 2:
            self.config["handle_twitch_events"] = True
            update_config = True

        # if update_config:
        #     config_json = json.dumps(self.config)
        #     await self.redis_conn.set(BOT_CONFIG_KEY, config_json)
        #     # Publish to the config_updates channel.
        #     await self.redis_conn.publish("config_updates", config_json)
        #     message = f"Updated config: {config_json}"
        #     #await self.logs_channel.send(message)

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
                LOGGER.error(f"Error retrieving user {user_id}: {e}")
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
                self.speaker = display_name
                # Extract the entire content from the BytesIO buffer.
                audio.file.seek(0)
                data = audio.file.read()
                date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

                # Save the data to disk with your desired filename.
                disk_filename = f"{date}-recording_{display_name}.{sink_obj.encoding}"
                self.recording_file_path = os.path.join(recorded_audio_directory, disk_filename)
                with open(self.recording_file_path, "wb") as f:
                    f.write(data)
                LOGGER.info(f"Saved file to disk: {self.recording_file_path}")

                # Create a new BytesIO object for the Discord file,
                # ensuring it starts from the beginning.
                new_file_stream = io.BytesIO(data)
                discord_file = discord.File(new_file_stream, filename=f"{display_name}.{sink_obj.encoding}")
                files.append(discord_file)

            await self.logs_channel.send(
                f"Finished recording audio for: {', '.join(recorded_users)}",
                files=files
            )

            if self.single_speaker:
                transcription = await asyncio.to_thread(
                    self.stt.transcribe_audiofile, self.recording_file_path
                )

                file_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H.%M:%S")
                transcription = f"[{timestamp}] <{self.speaker}>: {transcription}"
                filename = f"simple_transcription_{file_timestamp}.txt"
                file_path = os.path.join(transcriptions_directory, filename)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(transcription)

                await self.transform_transcription(transcription, file_timestamp)
        else:
            LOGGER.info(f"Silence segment, no data recorded.")
        if sink_obj.utterances and not self.single_speaker:
            combined_text = await asyncio.to_thread(self.stt.process_utterances, sink_obj)
            file_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"transcription_{file_timestamp}.txt"
            file_path = os.path.join(transcriptions_directory, filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(combined_text)
            LOGGER.info(f"Saved transcription to file {file_path}")
            await self.transform_transcription(combined_text, file_timestamp)

        self.segment_event.set()  # signal that the segment is done

    async def transform_transcription(self, transcription: str, timestamp: str):
        message = f"Give a response to the following message: {transcription}"
        reply = await self.ollama_client.ollama_chat(message)

        filename = f"output_{timestamp}.txt"
        file_path = os.path.join(llm_output_texts_directory, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(reply)

        try:
            result_dict = json.loads(reply)
            output_path = await asyncio.to_thread(self.tts_manager.text_to_audio_file, result_dict["result"])
            await self.queue_audio(output_path)
        except json.JSONDecodeError as error:
            LOGGER.error(error.msg)
            error_message = "There was an error creating a response."
            output_path = await asyncio.to_thread(self.tts_manager.text_to_audio_file, error_message)
            await self.queue_audio(output_path)

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
async def play(ctx: discord.ApplicationContext):
    await discord_client.play_audio(os.path.join("speech_output", "output.wav"))

@discord_client.command()
async def join(ctx: discord.ApplicationContext):
    vc = await discord_client.get_vc()
    #await ctx.send(f"Connected to voice chat: {vc.channel}")

@discord_client.command()
async def record(ctx: discord.ApplicationContext):
    await discord_client.record()

@discord_client.command(name="stop")
async def stop_recording(ctx: discord.ApplicationContext):
    await discord_client.stop_record()

@discord_client.command(name="hello")
async def hello(ctx: commands.Context):
    await ctx.send(f"Hello @{ctx.author.name}!")

@discord_client.slash_command(name="hello", description="Greets the user")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond(f"Hello {ctx.user.name}!")

@discord_client.command()
async def leave(ctx: discord.ApplicationContext):
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