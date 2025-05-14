# AI Chat program

## Introduction

The goal of this program was to create something that could respond to various Twitch events (raids, subscriptions,
bits usage, etc.) and to have capabilities so that you could talk with it.

Currently only the talking to it part is working.

## Requirements for running locally

Install the requirements with ``pip install -r requirements.txt``.

The program requires you to have Redis installed for example like [these](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/docker/)
instructions:

``docker run -d --name redis -p 6379:6379 redis:<version>``

For the Discord bot, you need to follow the instructions found [here](https://guide.pycord.dev/getting-started/creating-your-first-bot).

For the Twitch bot, you need to follow the instructions found [here](https://twitchio.dev/en/latest/getting-started/quickstart.html).

You need [Ollama](https://ollama.com/) installed and running to get the LLM capabilities. You can start the app
or run the command ``ollama serve`` to use an LLM.

Python version 3.12 is the latest supported.

Once you have these installed and running, make sure that your Discord server has a text channel called ``logs``
to which the bot has access to, and a voice channel called ``AIChat``, the bot uses these two channels.

You can run only the DiscordApp.py file for the Discord interactions.

## Functionality

Currently, when you start the DiscordApp.py, the bot gets in voice channel specified and starts listening for
speech. Every 2-second intervals, it checks the last activity and if it's over that, it starts processing the
recorded speech. In plain English, you need to have 2 seconds of silence so that the bot can respond to you.

The processing starts with transcribing the recorded speech with [Whisper](https://openai.com/index/whisper/), 
which is done two different ways. 
If there was a single speaker, a plain audio file transcribing is done. If there were multiple speakers,
a more sophisticated effort is done to ensure that the audio transcription includes all the speakers.

Once the transcribing is done, the transcription is given to [Ollama](https://ollama.com/) to get a response from it, this response
is then given to the TTS service, [Coqui TTS](https://coqui-tts.readthedocs.io/en/latest/), to synthesize
speech.

And finally, when the Ollama response is transformed into a playable audio file, it is queued to be played
in the voice channel for all to hear. Then you can respond to that and so forth.