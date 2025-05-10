import os
import asyncio
#from TextToSpeech import *
#from AudioPlayer import *
import dotenv
import asyncio
import logging
import sqlite3

import asqlite
import twitchio
from twitchio.ext import commands
from twitchio import eventsub
import json
import redis.asyncio as redis

from constants import BOT_CONFIG_KEY

dotenv.load_dotenv()

LOGGER: logging.Logger = logging.getLogger("TwitchApp")

CLIENT_ID: str = os.getenv("TWITCH_BOT_CLIENT") # The CLIENT ID from the Twitch Dev Console
CLIENT_SECRET: str = os.getenv("TWITCH_BOT_SECRET") # The CLIENT SECRET from the Twitch Dev Console
BOT_ID = os.getenv("TWITCH_BOT_ID")  # The Account ID of the bot user...
OWNER_ID = os.getenv("TWITCH_ACCOUNT_ID")  # Your personal User ID..

class TwitchApp(commands.Bot):
    tts_manager = None
    audio_player = None

    def __init__(self, *, token_database: asqlite.Pool):
        self.token_database = token_database
        super().__init__(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            bot_id=BOT_ID,
            owner_id=OWNER_ID,
            prefix="?")
        #self.tts_manager = TTSManager()
        #self.audio_player = AudioManager()
        self.config = {}
        self.channel = None
        self.redis_conn = redis.Redis(host="localhost", port=6379, db=0)

    async def setup_hook(self) -> None:
        # Add our component which contains our commands...
        await self.add_component(MyComponent(self))

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

        # Subscribe to read chat (event_message) from our channel as the bot...
        # This creates and opens a websocket to Twitch EventSub...
        subscription = eventsub.ChatMessageSubscription(broadcaster_user_id=OWNER_ID, user_id=BOT_ID)
        await self.subscribe_websocket(payload=subscription)

        # Subscribe and listen to when a stream goes live..
        # For this example listen to our own stream...
        subscription = eventsub.StreamOnlineSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelUpdateSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelFollowSubscription(broadcaster_user_id=OWNER_ID, moderator_user_id=BOT_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelBitsUseSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelSubscribeSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelSubscriptionGiftSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelSubscribeMessageSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelCheerSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelRaidSubscription(to_broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelBanSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelUnbanSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelModerateSubscription(broadcaster_user_id=OWNER_ID, moderator_user_id=BOT_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelModeratorAddSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPointsAutoRedeemSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPointsRewardAddSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPointsRewardRemoveSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPointsRedeemAddSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPointsRedeemUpdateSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPollBeginSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPollProgressSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPollEndSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPredictionBeginSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPredictionLockSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPredictionProgressSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelPredictionEndSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.SuspiciousUserMessageSubscription(broadcaster_user_id=OWNER_ID, moderator_user_id=BOT_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelVIPAddSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.ChannelVIPRemoveSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.HypeTrainBeginSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

        subscription = eventsub.HypeTrainEndSubscription(broadcaster_user_id=OWNER_ID)
        await self.subscribe_websocket(payload=subscription)

    async def add_token(self, token: str, refresh: str) -> twitchio.authentication.ValidateTokenPayload:
        # Make sure to call super() as it will add the tokens interally and return us some data...
        resp: twitchio.authentication.ValidateTokenPayload = await super().add_token(token, refresh)

        # Store our tokens in a simple SQLite Database when they are authorized...
        query = """
        INSERT INTO tokens (user_id, token, refresh)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            token = excluded.token,
            refresh = excluded.refresh;
        """

        async with self.token_database.acquire() as connection:
            await connection.execute(query, (resp.user_id, token, refresh))

        LOGGER.info("Added token to the database for user: %s", resp.user_id)
        return resp

    async def load_tokens(self, path: str | None = None) -> None:
        # We don't need to call this manually, it is called in .login() from .start() internally...

        async with self.token_database.acquire() as connection:
            rows: list[sqlite3.Row] = await connection.fetchall("""SELECT * from tokens""")

        for row in rows:
            await self.add_token(row["token"], row["refresh"])

    async def setup_database(self) -> None:
        # Create our token table, if it doesn't exist..
        query = """CREATE TABLE IF NOT EXISTS tokens(user_id TEXT PRIMARY KEY, token TEXT NOT NULL, refresh TEXT NOT NULL)"""
        async with self.token_database.acquire() as connection:
            await connection.execute(query)

    async def event_ready(self):
        print(f'Logged in as | {self.user.display_name}')
        print(f'User id is | {self.user.id}')

        asyncio.create_task(self.listen_for_mod_commands())
        asyncio.create_task(self.listen_for_config_updates())

    async def listen_for_mod_commands(self):
        pubsub = self.redis_conn.pubsub()
        await pubsub.subscribe("mod_commands")
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message and message["data"]:
                try:
                    data = json.loads(message["data"])
                    await self.handle_mod_command(data)
                except Exception as e:
                    print("Failed to process mod command:", e)
            await asyncio.sleep(1)

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
                    print("Configuration updated:", self.config)
                except Exception as e:
                    print("Failed to process config update:", e)
            await asyncio.sleep(1)

    async def handle_mod_command(self, command: dict):
        # Use your local configuration to determine timeouts, etc.
        self.channel = await self.fetch_channel(OWNER_ID)
        if not self.channel:
            print("Channel not available yet.")
            return

        reason = command.get('reason', 'Just \'cause')
        target = command['target']
        partial_user = None

        users = await self.fetch_users(logins=[target])
        if users:
            partial_user = users[0]

        if command["action"] == "timeout":
            await self.timeout_user(command)
        elif command["action"] == "ban":
            cmd = f"/ban {target} {reason}"
            if partial_user is not None:
                ban = await self.channel.user.ban_user(moderator=OWNER_ID, user=partial_user.id, reason=reason)
                print(f"User {ban.user.display_name} was banned {ban.created_at}")
            else:
                await self.channel.user.send_message(cmd)
            print(f"Executed ban command: {cmd}")

    async def timeout_user(self, command: dict):
        reason = command.get('reason', 'Just \'cause')
        target = command['target']
        partial_user = None

        users = await self.fetch_users(logins=[target])
        if users:
            partial_user = users[0]

        # Allow the default timeout duration to come from config if not specified.
        duration = command.get("duration", self.config.get("timeout_duration", 600))
        cmd = f"/timeout {target} {duration} {reason}"
        if partial_user is not None:
            timeout = await self.channel.user.timeout_user(moderator=OWNER_ID, user=partial_user.id,
                                                           duration=duration, reason=reason)
            print(f"User {timeout.user.display_name} was timed out for {timeout.end_time - timeout.created_at}")
        else:
            await self.channel.user.send_message(cmd)
        print(f"Executed timeout command: {cmd}")

class MyComponent(commands.Component):
    def __init__(self, bot: TwitchApp):
        self.bot = bot

    # We use a listener in our Component to display the messages received.
    @commands.Component.listener()
    async def event_message(self, payload: twitchio.ChatMessage) -> None:
        print(f"[{payload.broadcaster.name}] - {payload.chatter.name}: {payload.text}")

    @commands.command(aliases=["hello", "howdy", "hey"])
    async def hi(self, ctx: commands.Context) -> None:
        """Simple command that says hello!

        !hi, !hello, !howdy, !hey
        """
        await ctx.reply(f"Hello {ctx.chatter.mention}!")

    @commands.Component.listener()
    async def event_stream_online(self, payload: twitchio.StreamOnline) -> None:
        # Event dispatched when a user goes live from the subscription we made above...

        # Keep in mind we are assuming this is for ourselves
        # others may not want your bot randomly sending messages...
        await payload.broadcaster.send_message(
            sender=self.bot.bot_id,
            message=f"Hi... {payload.broadcaster}! You are live!",
        )

def main() -> None:
    twitchio.utils.setup_logging(level=logging.INFO)

    async def runner() -> None:
        async with asqlite.create_pool("tokens.db") as tdb, TwitchApp(token_database=tdb) as bot:
            await bot.setup_database()
            await bot.start()

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.warning("Shutting down due to KeyboardInterrupt...")

if __name__ == "__main__":
    main()