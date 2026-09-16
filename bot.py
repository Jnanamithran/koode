import os
import random
import threading
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, jsonify


# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.environ["DISCORD_TOKEN"]

YOUR_USER_ID = 722036964584587284

SERVER_ID = 1180200730854953131
VOICE_CHANNEL_ID = 1496047914575724555

# Original user is watched by default
TARGET_USER_ID = 1159066007508373524

# Set to 0 to allow /msg in any channel
MESSAGE_CHANNEL_ID = 0


# ============================================================
# MUSIC ACTIVITY
# ============================================================

MUSIC_NAMES = [
    "Safarnama",
    "Ilahi",
    "Phir Se Ud Chala",
    "Kun Faya Kun",
    "Aao Milo Chalo",
    "Yun Hi Chala Chal",
    "Khaabon Ke Parinday",
    "Zinda",
    "Arziyan",
    "Iktara",
    "Agar Tum Saath Ho",
    "Patakha Guddi",
    "Journey Song",
    "Midnight Drive",
    "Chill Vibes",
]


# ============================================================
# WATCH / PRESENCE DATA
# ============================================================

# Users currently being watched
watched_users = {
    TARGET_USER_ID
}

# When a watched user became active
online_since = {}

# Last completed online session duration
last_online_duration = {}


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Koode Discord bot is running."


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "bot": str(bot.user) if bot.user else "connecting",
        "watched_users": len(watched_users),
        "time": datetime.now(timezone.utc).isoformat(),
    })


def run_flask():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
    )


# ============================================================
# DISCORD INTENTS
# ============================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.presences = True
intents.voice_states = True
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)

tree = bot.tree


# ============================================================
# HELPERS
# ============================================================

def get_status_text(status: discord.Status) -> str:
    status_names = {
        discord.Status.online: "Online",
        discord.Status.idle: "Idle",
        discord.Status.dnd: "Do Not Disturb",
        discord.Status.offline: "Offline",
        discord.Status.invisible: "Offline",
    }

    return status_names.get(
        status,
        str(status).title(),
    )


def is_active(status: discord.Status) -> bool:
    return status not in (
        discord.Status.offline,
        discord.Status.invisible,
    )


def format_duration(duration) -> str:
    total_seconds = int(duration.total_seconds())

    days, remainder = divmod(
        total_seconds,
        86400,
    )

    hours, remainder = divmod(
        remainder,
        3600,
    )

    minutes, seconds = divmod(
        remainder,
        60,
    )

    parts = []

    if days:
        parts.append(f"{days}d")

    if hours:
        parts.append(f"{hours}h")

    if minutes:
        parts.append(f"{minutes}m")

    if seconds and not parts:
        parts.append(f"{seconds}s")

    if not parts:
        return "0s"

    return " ".join(parts)


# ============================================================
# BOT ACTIVITY
# ============================================================

async def set_bot_activity():
    music_name = random.choice(MUSIC_NAMES)

    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name=music_name,
    )

    await bot.change_presence(
        status=discord.Status.dnd,
        activity=activity,
    )

    print(
        f"Activity set to: Listening to {music_name}"
    )


# ============================================================
# DM NOTIFICATION
# ============================================================

async def send_notification(message: str):
    try:
        user = await bot.fetch_user(
            YOUR_USER_ID
        )

        if user:
            await user.send(message)

            print(
                f"DM sent: {message}"
            )

    except discord.Forbidden:
        print(
            "Could not send DM. "
            "User may have DMs disabled."
        )

    except discord.HTTPException as error:
        print(
            f"Failed to send DM: {error}"
        )


# ============================================================
# VOICE CONNECTION
# ============================================================

async def connect_to_voice():
    guild = bot.get_guild(
        SERVER_ID
    )

    if guild is None:
        print("Server not found.")
        return

    voice_channel = guild.get_channel(
        VOICE_CHANNEL_ID
    )

    if voice_channel is None:
        print("Voice channel not found.")
        return

    if not isinstance(
        voice_channel,
        discord.VoiceChannel,
    ):
        print(
            "Configured channel is not "
            "a normal voice channel."
        )
        return

    current_voice_client = discord.utils.get(
        bot.voice_clients,
        guild=guild,
    )

    if (
        current_voice_client
        and current_voice_client.is_connected()
    ):
        print(
            "Bot is already connected to voice."
        )
        return

    try:
        await voice_channel.connect()

        print(
            f"Connected to voice channel: "
            f"{voice_channel.name}"
        )

    except discord.Forbidden:
        print(
            "Bot does not have permission "
            "to join this voice channel."
        )

    except discord.HTTPException as error:
        print(
            f"Could not connect to voice: {error}"
        )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Connected servers: {len(bot.guilds)}")
    print(
        f"Watching users: {len(watched_users)}"
    )
    print("=" * 50)

    await set_bot_activity()

    try:
        synced_commands = await tree.sync()

        print(
            f"Synced {len(synced_commands)} "
            f"slash commands."
        )

    except Exception as error:
        print(
            f"Failed to sync slash commands: {error}"
        )

    await connect_to_voice()


# ============================================================
# PRESENCE MONITORING
# ============================================================

@bot.event
async def on_presence_update(
    before: discord.Member,
    after: discord.Member,
):
    user_id = after.id

    if user_id not in watched_users:
        return

    before_active = is_active(
        before.status
    )

    after_active = is_active(
        after.status
    )

    before_status = get_status_text(
        before.status
    )

    after_status = get_status_text(
        after.status
    )

    print(
        f"Watched user presence changed: "
        f"{after.display_name}: "
        f"{before_status} -> {after_status}"
    )

    # --------------------------------------------------------
    # Offline -> Active
    # --------------------------------------------------------

    if (
        not before_active
        and after_active
    ):
        online_since[user_id] = (
            datetime.now(timezone.utc)
        )

        await send_notification(
            f"🔔 **{after.display_name} "
            f"is now {after_status}!**\n"
            f"Discord ID: `{user_id}`"
        )

        return

    # --------------------------------------------------------
    # Active -> Offline
    # --------------------------------------------------------

    if (
        before_active
        and not after_active
    ):
        start_time = online_since.get(
            user_id
        )

        if start_time:
            duration = (
                datetime.now(timezone.utc)
                - start_time
            )

            last_online_duration[user_id] = (
                duration
            )

            del online_since[user_id]

            print(
                f"{after.display_name} was "
                f"online for "
                f"{format_duration(duration)}"
            )


# ============================================================
# DISCONNECT / RESUME
# ============================================================

@bot.event
async def on_disconnect():
    print(
        "Bot disconnected from Discord."
    )


@bot.event
async def on_resumed():
    print(
        "Bot connection resumed."
    )

    await set_bot_activity()


# ============================================================
# /msg
# ============================================================

@tree.command(
    name="msg",
    description="Send a message through the bot.",
)
@app_commands.describe(
    message="The message you want to send"
)
async def msg_command(
    interaction: discord.Interaction,
    message: str,
):
    if MESSAGE_CHANNEL_ID != 0:

        if (
            interaction.channel_id
            != MESSAGE_CHANNEL_ID
        ):
            await interaction.response.send_message(
                "❌ This command cannot be "
                "used in this channel.",
                ephemeral=True,
            )

            return

    await interaction.channel.send(
        message
    )

    await interaction.response.send_message(
        "✅ Message sent.",
        ephemeral=True,
    )


# ============================================================
# /status
# ============================================================

@tree.command(
    name="status",
    description="Check a watched user's Discord status.",
)
@app_commands.describe(
    user="The user to check"
)
async def status_command(
    interaction: discord.Interaction,
    user: discord.User | None = None,
):
    if user is None:
        user_id = TARGET_USER_ID
    else:
        user_id = user.id

    if user_id not in watched_users:
        await interaction.response.send_message(
            "❌ That user is not being watched.",
            ephemeral=True,
        )

        return

    guild = bot.get_guild(
        SERVER_ID
    )

    if guild is None:
        await interaction.response.send_message(
            "❌ Server not found.",
            ephemeral=True,
        )

        return

    member = guild.get_member(
        user_id
    )

    if member is None:
        await interaction.response.send_message(
            "❌ User is not found in the server.",
            ephemeral=True,
        )

        return

    status_name = get_status_text(
        member.status
    )

    await interaction.response.send_message(
        f"👤 **{member.display_name}** "
        f"is currently **{status_name}**."
    )


# ============================================================
# /ping
# ============================================================

@tree.command(
    name="ping",
    description="Check the bot's latency.",
)
async def ping_command(
    interaction: discord.Interaction,
):
    latency = round(
        bot.latency * 1000
    )

    await interaction.response.send_message(
        f"🏓 Pong! `{latency}ms`"
    )


# ============================================================
# /info
# ============================================================

@tree.command(
    name="info",
    description="Show bot information.",
)
async def info_command(
    interaction: discord.Interaction,
):
    voice_status = "Not connected"

    for voice_client in bot.voice_clients:

        if (
            voice_client.guild.id
            == SERVER_ID
        ):

            if voice_client.is_connected():
                voice_status = (
                    voice_client.channel.name
                )

    embed = discord.Embed(
        title="🤖 Koode",
        description=(
            "Presence notification "
            "and utility bot"
        ),
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="👀 Watched Users",
        value=str(
            len(watched_users)
        ),
        inline=True,
    )

    embed.add_field(
        name="🔊 Voice",
        value=voice_status,
        inline=True,
    )

    embed.add_field(
        name="⚡ Latency",
        value=f"{round(bot.latency * 1000)}ms",
        inline=True,
    )

    embed.add_field(
        name="🌐 Servers",
        value=str(
            len(bot.guilds)
        ),
        inline=True,
    )

    embed.set_footer(
        text=(
            "Status: Do Not Disturb | "
            "Listening to music"
        )
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /music
# ============================================================

@tree.command(
    name="music",
    description="Change the bot's listening activity.",
)
@app_commands.describe(
    name="Music name to display"
)
async def music_command(
    interaction: discord.Interaction,
    name: str,
):
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name=name,
    )

    await bot.change_presence(
        status=discord.Status.dnd,
        activity=activity,
    )

    await interaction.response.send_message(
        f"🎧 Now listening to **{name}**.",
        ephemeral=True,
    )


# ============================================================
# /vc
# ============================================================

@tree.command(
    name="vc",
    description="Connect the bot to the configured voice channel.",
)
async def vc_command(
    interaction: discord.Interaction,
):
    await connect_to_voice()

    await interaction.response.send_message(
        "🔊 Connecting to the configured "
        "voice channel.",
        ephemeral=True,
    )


# ============================================================
# /leave
# ============================================================

@tree.command(
    name="leave",
    description="Disconnect the bot from the current voice channel.",
)
async def leave_command(
    interaction: discord.Interaction,
):
    disconnected = False

    for voice_client in bot.voice_clients:

        if (
            voice_client.guild.id
            == interaction.guild_id
        ):
            await voice_client.disconnect()

            disconnected = True

    if disconnected:

        await interaction.response.send_message(
            "👋 Disconnected from "
            "the voice channel.",
            ephemeral=True,
        )

    else:

        await interaction.response.send_message(
            "❌ I am not connected "
            "to a voice channel.",
            ephemeral=True,
        )


# ============================================================
# /watch
# ============================================================

@tree.command(
    name="watch",
    description="Add, remove, or list watched users.",
)
@app_commands.describe(
    action="Choose add, remove, or list",
    user="Discord user to add or remove",
)
@app_commands.choices(
    action=[
        app_commands.Choice(
            name="add",
            value="add",
        ),
        app_commands.Choice(
            name="remove",
            value="remove",
        ),
        app_commands.Choice(
            name="list",
            value="list",
        ),
    ]
)
async def watch_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    user: discord.User | None = None,
):
    # Only bot owner can manage watches
    if interaction.user.id != YOUR_USER_ID:

        await interaction.response.send_message(
            "❌ You are not allowed to "
            "manage the watch list.",
            ephemeral=True,
        )

        return

    # --------------------------------------------------------
    # LIST
    # --------------------------------------------------------

    if action.value == "list":

        if not watched_users:

            await interaction.response.send_message(
                "👀 No users are currently "
                "being watched.",
                ephemeral=True,
            )

            return

        lines = []

        for user_id in watched_users:

            watched_user = bot.get_user(
                user_id
            )

            if watched_user:

                lines.append(
                    f"• {watched_user.mention} "
                    f"(`{user_id}`)"
                )

            else:

                lines.append(
                    f"• <@{user_id}> "
                    f"(`{user_id}`)"
                )

        await interaction.response.send_message(
            "👀 **Watched Users**\n\n"
            + "\n".join(lines)
        )

        return

    # --------------------------------------------------------
    # ADD / REMOVE REQUIRE USER
    # --------------------------------------------------------

    if user is None:

        await interaction.response.send_message(
            f"❌ Please specify a user.\n"
            f"Example: `/watch "
            f"{action.value} @username`",
            ephemeral=True,
        )

        return

    # --------------------------------------------------------
    # ADD
    # --------------------------------------------------------

    if action.value == "add":

        if user.id in watched_users:

            await interaction.response.send_message(
                f"👀 **{user.display_name}** "
                f"is already being watched.",
                ephemeral=True,
            )

            return

        watched_users.add(
            user.id
        )

        await interaction.response.send_message(
            f"✅ Now watching "
            f"**{user.display_name}**."
        )

        return

    # --------------------------------------------------------
    # REMOVE
    # --------------------------------------------------------

    if action.value == "remove":

        if user.id not in watched_users:

            await interaction.response.send_message(
                f"❌ **{user.display_name}** "
                f"is not being watched.",
                ephemeral=True,
            )

            return

        watched_users.remove(
            user.id
        )

        online_since.pop(
            user.id,
            None,
        )

        last_online_duration.pop(
            user.id,
            None,
        )

        await interaction.response.send_message(
            f"✅ Stopped watching "
            f"**{user.display_name}**."
        )


# ============================================================
# /duration
# ============================================================

@tree.command(
    name="duration",
    description="Check how long a watched user has been online.",
)
@app_commands.describe(
    user="The watched user"
)
async def duration_command(
    interaction: discord.Interaction,
    user: discord.User,
):
    if user.id not in watched_users:

        await interaction.response.send_message(
            f"❌ **{user.display_name}** "
            f"is not currently being watched.",
            ephemeral=True,
        )

        return

    # Currently online
    if user.id in online_since:

        duration = (
            datetime.now(timezone.utc)
            - online_since[user.id]
        )

        await interaction.response.send_message(
            f"🟢 **{user.display_name}** "
            f"has been online for "
            f"**{format_duration(duration)}**."
        )

        return

    # Currently offline but has history
    if user.id in last_online_duration:

        duration = last_online_duration[
            user.id
        ]

        await interaction.response.send_message(
            f"🔴 **{user.display_name}** "
            f"is currently offline.\n"
            f"Last online duration: "
            f"**{format_duration(duration)}**"
        )

        return

    # No history
    await interaction.response.send_message(
        f"ℹ️ I don't have enough presence "
        f"history for **{user.display_name}** yet."
    )


# ============================================================
# START BOT
# ============================================================

if __name__ == "__main__":

    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True,
    )

    flask_thread.start()

    bot.run(TOKEN)