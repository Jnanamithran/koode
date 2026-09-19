import os
import random
import threading
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, jsonify


# =========================================================
# CONFIGURATION
# =========================================================

TOKEN = os.environ["DISCORD_TOKEN"]

# Default monitored user
TARGET_USER_ID = 1159066007508373524

# Bot owner
YOUR_USER_ID = 722036964584587284

# Discord server
SERVER_ID = 1180200730854953131

# Voice channel
VOICE_CHANNEL_ID = 1496047914575724555

# Set to a text channel ID if /msg should work only there.
# Keep 0 to allow /msg in any channel.
MESSAGE_CHANNEL_ID = 0


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


# =========================================================
# WATCH / DURATION DATA
# =========================================================

# Users currently being monitored.
# The original target user is watched by default.
watched_users = {
    TARGET_USER_ID
}

# When a watched user became active.
#
# Example:
# {
#     123456789: datetime(...)
# }
online_since = {}

# Last completed active duration.
#
# Example:
# {
#     123456789: 3600
# }
last_online_duration = {}


# =========================================================
# FLASK SERVER FOR RENDER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Discord bot is running."


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "online",
            "bot": str(bot.user) if bot.user else "connecting",
            "time": datetime.now(timezone.utc).isoformat(),
        }
    )


def run_flask():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
    )


# =========================================================
# DISCORD BOT SETUP
# =========================================================

intents = discord.Intents.default()

intents.presences = True
intents.members = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)

tree = bot.tree


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_status_text(status: discord.Status) -> str:
    """Convert Discord status to readable text."""

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


def is_active_status(status: discord.Status) -> bool:
    """Return True if the Discord status is considered active."""

    return status not in (
        discord.Status.offline,
        discord.Status.invisible,
    )


def format_duration(seconds: float) -> str:
    """Convert seconds into a readable duration."""

    seconds = int(seconds)

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []

    if days:
        parts.append(f"{days}d")

    if hours:
        parts.append(f"{hours}h")

    if minutes:
        parts.append(f"{minutes}m")

    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


async def set_bot_activity():
    """Set bot status to DND and show Listening to a random song."""

    music_name = random.choice(MUSIC_NAMES)

    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name=music_name,
    )

    await bot.change_presence(
        status=discord.Status.dnd,
        activity=activity,
    )

    print(f"Activity set to: Listening to {music_name}")


async def send_notification(message: str):
    """Send a DM to the bot owner."""

    try:
        user = await bot.fetch_user(YOUR_USER_ID)

        if user:
            await user.send(message)
            print(f"DM sent: {message}")

    except discord.Forbidden:
        print(
            "Could not send DM. "
            "User may have DMs disabled."
        )

    except discord.HTTPException as error:
        print(f"Failed to send DM: {error}")


async def connect_to_voice():
    """Connect to the configured voice channel."""

    guild = bot.get_guild(SERVER_ID)

    if guild is None:
        print("Server not found.")
        return

    voice_channel = guild.get_channel(VOICE_CHANNEL_ID)

    if voice_channel is None:
        print("Voice channel not found.")
        return

    if not isinstance(voice_channel, discord.VoiceChannel):
        print(
            "Configured channel is not a normal voice channel."
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
        print("Bot is already connected to voice.")
        return

    try:
        await voice_channel.connect()

        print(
            f"Connected to voice channel: "
            f"{voice_channel.name}"
        )

    except discord.Forbidden:
        print(
            "Bot does not have permission to "
            "join this voice channel."
        )

    except discord.HTTPException as error:
        print(
            f"Could not connect to voice channel: {error}"
        )


def get_member_from_server(user_id: int):
    """Get a member from the configured server."""

    guild = bot.get_guild(SERVER_ID)

    if guild is None:
        return None

    return guild.get_member(user_id)


def is_owner(interaction: discord.Interaction) -> bool:
    """Check whether the interaction was made by the bot owner."""

    return interaction.user.id == YOUR_USER_ID


# =========================================================
# BOT EVENTS
# =========================================================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Connected servers: {len(bot.guilds)}")
    print("=" * 50)

    # Initialize active times for watched users.
    guild = bot.get_guild(SERVER_ID)

    if guild:
        for user_id in watched_users:
            member = guild.get_member(user_id)

            if member and is_active_status(member.status):
                if user_id not in online_since:
                    online_since[user_id] = datetime.now(
                        timezone.utc
                    )

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

    # IMPORTANT:
    # Keep the original voice connection behavior.
    await connect_to_voice()


@bot.event
async def on_presence_update(
    before: discord.Member,
    after: discord.Member,
):
    """
    Monitor all users in watched_users.

    Offline -> Online/Idle/DND:
        - Start duration timer
        - Send DM notification

    Online/Idle/DND -> Offline:
        - Stop duration timer
        - Save duration

    Online -> Idle:
        Ignore

    Idle -> DND:
        Ignore

    DND -> Online:
        Ignore
    """

    user_id = after.id

    # Ignore users that are not being watched.
    if user_id not in watched_users:
        return

    before_active = is_active_status(before.status)
    after_active = is_active_status(after.status)

    before_text = get_status_text(before.status)
    after_text = get_status_text(after.status)

    print(
        f"Watched user presence changed: "
        f"{after.display_name}: "
        f"{before_text} -> {after_text}"
    )

    # -----------------------------------------------------
    # ACTIVE -> ACTIVE
    # -----------------------------------------------------
    #
    # Online -> Idle
    # Idle -> DND
    # DND -> Online
    #
    # Nothing happens.
    #
    if before_active and after_active:

        # Safety: make sure a timer exists.
        if user_id not in online_since:
            online_since[user_id] = datetime.now(
                timezone.utc
            )

        return

    # -----------------------------------------------------
    # OFFLINE -> ACTIVE
    # -----------------------------------------------------

    if not before_active and after_active:

        # Start timer.
        online_since[user_id] = datetime.now(
            timezone.utc
        )

        status_name = get_status_text(after.status)

        await send_notification(
            f"🔔 **{after.display_name} is now "
            f"{status_name}!**\n"
            f"Discord ID: `{after.id}`"
        )

        print(
            f"Started timer for "
            f"{after.display_name}"
        )

        return

    # -----------------------------------------------------
    # ACTIVE -> OFFLINE
    # -----------------------------------------------------

    if before_active and not after_active:

        start_time = online_since.pop(
            user_id,
            None,
        )

        if start_time is None:
            print(
                f"No start time found for "
                f"{after.display_name}."
            )
            return

        duration = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()

        last_online_duration[user_id] = duration

        print(
            f"{after.display_name} went offline. "
            f"Active duration: "
            f"{format_duration(duration)}"
        )


@bot.event
async def on_disconnect():
    # Keep original behavior.
    print("Bot disconnected from Discord.")


@bot.event
async def on_resumed():
    # Keep original behavior.
    print("Bot connection resumed.")

    await set_bot_activity()


# =========================================================
# SLASH COMMANDS
# =========================================================

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
        if interaction.channel_id != MESSAGE_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ This command cannot be used in this channel.",
                ephemeral=True,
            )
            return

    await interaction.channel.send(message)

    await interaction.response.send_message(
        "✅ Message sent.",
        ephemeral=True,
    )


@tree.command(
    name="status",
    description="Check the monitored user's Discord status.",
)
async def status_command(
    interaction: discord.Interaction,
):
    guild = bot.get_guild(SERVER_ID)

    if guild is None:
        await interaction.response.send_message(
            "❌ Server not found.",
            ephemeral=True,
        )
        return

    member = guild.get_member(TARGET_USER_ID)

    if member is None:
        await interaction.response.send_message(
            "❌ Target user is not found in the server.",
            ephemeral=True,
        )
        return

    status_name = get_status_text(member.status)

    await interaction.response.send_message(
        f"👤 **{member.display_name}** is currently "
        f"**{status_name}**."
    )


@tree.command(
    name="ping",
    description="Check the bot's latency.",
)
async def ping_command(
    interaction: discord.Interaction,
):
    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"🏓 Pong! `{latency}ms`"
    )


@tree.command(
    name="info",
    description="Show bot information.",
)
async def info_command(
    interaction: discord.Interaction,
):
    voice_status = "Not connected"

    for voice_client in bot.voice_clients:
        if voice_client.guild.id == SERVER_ID:
            if voice_client.is_connected():
                voice_status = voice_client.channel.name

    embed = discord.Embed(
        title="🤖 Discord Bot Information",
        description=(
            "Presence notification and utility bot"
        ),
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="Watched Users",
        value=str(len(watched_users)),
        inline=True,
    )

    embed.add_field(
        name="Server ID",
        value=str(SERVER_ID),
        inline=False,
    )

    embed.add_field(
        name="Voice Channel",
        value=voice_status,
        inline=False,
    )

    embed.add_field(
        name="Latency",
        value=f"{round(bot.latency * 1000)}ms",
        inline=True,
    )

    embed.add_field(
        name="Servers",
        value=str(len(bot.guilds)),
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


@tree.command(
    name="vc",
    description=(
        "Connect the bot to the configured "
        "voice channel."
    ),
)
async def vc_command(
    interaction: discord.Interaction,
):
    await connect_to_voice()

    await interaction.response.send_message(
        "🔊 Connecting to the configured voice channel.",
        ephemeral=True,
    )


@tree.command(
    name="leave",
    description=(
        "Disconnect the bot from the current "
        "voice channel."
    ),
)
async def leave_command(
    interaction: discord.Interaction,
):
    disconnected = False

    for voice_client in bot.voice_clients:
        if voice_client.guild.id == interaction.guild_id:
            await voice_client.disconnect()
            disconnected = True

    if disconnected:
        await interaction.response.send_message(
            "👋 Disconnected from the voice channel.",
            ephemeral=True,
        )

    else:
        await interaction.response.send_message(
            "❌ I am not connected to a voice channel.",
            ephemeral=True,
        )


# =========================================================
# WATCH COMMAND GROUP
# =========================================================

watch_group = app_commands.Group(
    name="watch",
    description="Manage users being monitored.",
)


@watch_group.command(
    name="add",
    description="Add a user to the watch list.",
)
@app_commands.describe(
    user="The Discord user you want to monitor"
)
async def watch_add(
    interaction: discord.Interaction,
    user: discord.Member,
):
    if not is_owner(interaction):
        await interaction.response.send_message(
            "❌ You do not have permission to use this.",
            ephemeral=True,
        )
        return

    if user.id in watched_users:
        await interaction.response.send_message(
            f"👀 **{user.display_name}** is already "
            f"being watched.",
            ephemeral=True,
        )
        return

    watched_users.add(user.id)

    # If the user is currently active,
    # start tracking immediately.
    if is_active_status(user.status):
        online_since[user.id] = datetime.now(
            timezone.utc
        )

    await interaction.response.send_message(
        f"✅ Now watching **{user.display_name}**.\n"
        f"ID: `{user.id}`",
        ephemeral=True,
    )

    print(
        f"Added watched user: "
        f"{user.display_name} ({user.id})"
    )


@watch_group.command(
    name="remove",
    description="Remove a user from the watch list.",
)
@app_commands.describe(
    user="The Discord user you want to stop monitoring"
)
async def watch_remove(
    interaction: discord.Interaction,
    user: discord.Member,
):
    if not is_owner(interaction):
        await interaction.response.send_message(
            "❌ You do not have permission to use this.",
            ephemeral=True,
        )
        return

    # Prevent removing the default user accidentally.
    if user.id == TARGET_USER_ID:
        await interaction.response.send_message(
            "❌ The default monitored user cannot "
            "be removed.",
            ephemeral=True,
        )
        return

    if user.id not in watched_users:
        await interaction.response.send_message(
            f"❌ **{user.display_name}** is not "
            f"being watched.",
            ephemeral=True,
        )
        return

    watched_users.remove(user.id)

    # Remove active tracking data.
    online_since.pop(user.id, None)
    last_online_duration.pop(user.id, None)

    await interaction.response.send_message(
        f"🗑️ Stopped watching "
        f"**{user.display_name}**.",
        ephemeral=True,
    )

    print(
        f"Removed watched user: "
        f"{user.display_name} ({user.id})"
    )


@watch_group.command(
    name="list",
    description="Show all users currently being watched.",
)
async def watch_list(
    interaction: discord.Interaction,
):
    if not watched_users:
        await interaction.response.send_message(
            "👀 No users are currently being watched.",
            ephemeral=True,
        )
        return

    lines = []

    for index, user_id in enumerate(
        watched_users,
        start=1,
    ):
        member = get_member_from_server(user_id)

        if member:
            status = get_status_text(member.status)

            lines.append(
                f"**{index}.** "
                f"{member.display_name} "
                f"— `{status}`\n"
                f"   ID: `{user_id}`"
            )

        else:
            lines.append(
                f"**{index}.** "
                f"<@{user_id}>\n"
                f"   ID: `{user_id}`"
            )

    embed = discord.Embed(
        title="👀 Watched Users",
        description="\n\n".join(lines),
        color=discord.Color.blurple(),
    )

    embed.set_footer(
        text=f"Total watched: {len(watched_users)}"
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True,
    )


tree.add_command(watch_group)


# =========================================================
# DURATION COMMAND
# =========================================================

@tree.command(
    name="duration",
    description="Show a user's current or last active duration.",
)
@app_commands.describe(
    user="The Discord user"
)
async def duration_command(
    interaction: discord.Interaction,
    user: discord.Member,
):
    if user.id not in watched_users:
        await interaction.response.send_message(
            f"❌ **{user.display_name}** is not "
            f"being watched.",
            ephemeral=True,
        )
        return

    # -----------------------------------------------------
    # USER IS CURRENTLY ACTIVE
    # -----------------------------------------------------

    if user.id in online_since:
        start_time = online_since[user.id]

        current_duration = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()

        status_name = get_status_text(user.status)

        await interaction.response.send_message(
            f"👤 **{user.display_name}** is currently "
            f"**{status_name}**.\n\n"
            f"⏱️ Active for: "
            f"**{format_duration(current_duration)}**",
            ephemeral=True,
        )

        return

    # -----------------------------------------------------
    # USER IS OFFLINE
    # -----------------------------------------------------

    if user.id in last_online_duration:
        duration = last_online_duration[user.id]

        await interaction.response.send_message(
            f"👤 **{user.display_name}** is currently "
            f"**Offline**.\n\n"
            f"⏱️ Last active duration: "
            f"**{format_duration(duration)}**",
            ephemeral=True,
        )

        return

    # -----------------------------------------------------
    # NO DATA YET
    # -----------------------------------------------------

    await interaction.response.send_message(
        f"👤 **{user.display_name}** has no recorded "
        f"active duration yet.",
        ephemeral=True,
    )


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":

    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True,
    )

    flask_thread.start()

    bot.run(TOKEN)