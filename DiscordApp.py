import discord
import os
import dotenv

dotenv.load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

client = discord.Bot(intents=intents)
connections = {}

@client.event
async def on_ready():
    print(f'Logged on as {client.user}!')

@client.event
async def on_message(message):
    print(f'Message from {message.author}: {message.content}')
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

@client.command()
async def record(ctx):  # If you're using commands.Bot, this will also work.
    voice = ctx.author.voice

    if not voice:
        await ctx.respond("You aren't in a voice channel!")

    print(ctx.guild.id in connections)

    if ctx.guild.id not in connections:
        vc = await voice.channel.connect()  # Connect to the voice channel the author is in.
        connections.update({ctx.guild.id: vc})  # Updating the cache with the guild and channel.
    else:
        vc = connections[ctx.guild.id]

    vc.start_recording(
        discord.sinks.WaveSink(),  # The sink type to use.
        once_done,  # What to do once done.
        ctx.channel  # The channel to disconnect from.
    )
    await ctx.respond("Started recording!")

async def once_done(sink: discord.sinks, channel: discord.TextChannel, *args):  # Our voice client already passes these in.
    recorded_users = [  # A list of recorded users
        f"<@{user_id}>"
        for user_id, audio in sink.audio_data.items()
    ]
    #await sink.vc.disconnect()  # Disconnect from the voice channel.
    files = [discord.File(audio.file, f"{user_id}.{sink.encoding}") for user_id, audio in sink.audio_data.items()]  # List down the files.
    await channel.send(f"finished recording audio for: {', '.join(recorded_users)}.", files=files)

@client.command()
async def stop_recording(ctx):
    if ctx.guild.id in connections:  # Check if the guild is in the cache.
        vc = connections[ctx.guild.id]
        vc.stop_recording()  # Stop recording, and call the callback (once_done).
        #del connections[ctx.guild.id]  # Remove the guild from the cache.
        #await ctx.delete()  # And delete.
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

@client.command()
async def leave(ctx):
    if ctx.guild.id in connections:  # Check if the guild is in the cache.
        del connections[ctx.guild.id]  # Remove the guild from the cache.
        await ctx.delete()  # And delete.
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

#@client.event
#async def on_voice_state_update(member, before, after):
#    if after.channel is not None and before.channel != after.channel and client.user in after.channel.members:
#        if after.channel.guild.voice_client and not after.deaf:
#            voice_client = after.channel.guild.voice_client
#            audio_source = discord.PCMAudio("some_audio_stream")
#            voice_client.play(audio_source)
#            transcript = await transcribe_audio(audio_source)
#            print(transcript)

def start_discord_bot():
    try:
        client.run(os.getenv("DISCORD_TOKEN"))
    finally:
        pass