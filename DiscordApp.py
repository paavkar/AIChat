import discord
from discord.ext import commands
import os
import dotenv

dotenv.load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

client = commands.Bot(command_prefix='$', intents=intents)

@client.event
async def on_ready():
    print(f'Logged on as {client.user}!')

@client.event
async def on_message(message):
    print(f'Message from {message.author}: {message.content}')
    if message.author == client.user:
        return

    await client.process_commands(message)

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

@client.command()
async def join(ctx):
    if ctx.author.voice is None:
        await ctx.send("Join a voice channel first.")
        return
    channel = ctx.author.voice.channel
    print(channel)
    if ctx.voice_client is not None:
        return await ctx.voice_client.move_to(channel)

    vc = await channel.connect()
    while True:
        try:
            pass
            #audio_source = await vc.listen() # vc.listen() doesn't exist
        except Exception as e:
            print(e)
            break

@client.event
async def on_voice_state_update(member, before, after):
    if after.channel is not None and before.channel != after.channel and client.user in after.channel.members:
        if after.channel.guild.voice_client and not after.deaf:
            voice_client = after.channel.guild.voice_client
            audio_source = discord.PCMAudio("some_audio_stream")
            voice_client.play(audio_source)
            #transcript = await transcribe_audio(audio_source)
            #print(transcript)

@client.command()
async def leave(ctx):
    await ctx.voice_client.disconnect()

def start_discord_bot():
    client.run(os.getenv('DISCORD_TOKEN'))