import os
import random
import threading
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, jsonify

# =========================================================
# CONFIGURATION
# =========================================================

TOKEN = os.environ["DISCORD_TOKEN"]

TARGET_USER_ID = 1159066007508373524
YOUR_USER_ID = 722036964584587284

SERVER_ID = 1180200730854953131
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
            "time": datetime.utcnow().isoformat(),
        }
    )


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


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

# Stores the previous active/offline state.
previous_active_state = None


# =========================================================
# HELPER FUNCTIONS
# =========================================================

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
        print("Could not send DM. User may have DMs disabled.")

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
        print("Configured channel is not a normal voice channel.")
        return

    current_voice_client = discord.utils.get(
        bot.voice_clients,
        guild=guild,
    )

    if current_voice_client and current_voice_client.is_connected():
        print("Bot is already connected to voice.")
        return

    try:
        await voice_channel.connect()
        print(f"Connected to voice channel: {voice_channel.name}")

    except discord.Forbidden:
        print("Bot does not have permission to join this voice channel.")

    except discord.HTTPException as error:
        print(f"Could not connect to voice channel: {error}")


def get_status_text(status: discord.Status) -> str:
    """Convert Discord status to readable text."""

    status_names = {
        discord.Status.online: "Online",
        discord.Status.idle: "Idle",
        discord.Status.dnd: "Do Not Disturb",
        discord.Status.offline: "Offline",
        discord.Status.invisible: "Offline",
    }

    return status_names.get(status, str(status).title())


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

    await set_bot_activity()

    try:
        synced_commands = await tree.sync()
        print(f"Synced {len(synced_commands)} slash commands.")

    except Exception as error:
        print(f"Failed to sync slash commands: {error}")

    await connect_to_voice()


@bot.event
async def on_presence_update(
    before: discord.Member,
    after: discord.Member,
):
    """
    Notify only when the target changes from Offline
    to Online, Idle, or Do Not Disturb.

    Examples:
    Offline -> Online  = Notify
    Offline -> Idle    = Notify
    Offline -> DND     = Notify

    Online -> Idle      = Ignore
    Idle -> DND         = Ignore
    DND -> Online       = Ignore
    """

    global previous_active_state

    if after.id != TARGET_USER_ID:
        return

    before_active = before.status not in (
        discord.Status.offline,
        discord.Status.invisible,
    )

    after_active = after.status not in (
        discord.Status.offline,
        discord.Status.invisible,
    )

    print(
        f"Target presence changed: "
        f"{get_status_text(before.status)} -> "
        f"{get_status_text(after.status)}"
    )

    # Ignore active-to-active changes.
    if before_active and after_active:
        previous_active_state = True
        return

    # Notify only when Offline -> Active.
    if not before_active and after_active:
        status_name = get_status_text(after.status)

        await send_notification(
            f"🔔 **{after.display_name} is now {status_name}!**\n"
            f"Discord ID: `{after.id}`"
        )

    previous_active_state = after_active


@bot.event
async def on_disconnect():
    print("Bot disconnected from Discord.")


@bot.event
async def on_resumed():
    print("Bot connection resumed.")
    await set_bot_activity()


# =========================================================
# SLASH COMMANDS
# =========================================================

@tree.command(
    name="msg",
    description="Send a message through the bot.",
)
@app_commands.describe(message="The message you want to send")
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
async def status_command(interaction: discord.Interaction):
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
        f"👤 **{member.display_name}** is currently **{status_name}**."
    )


@tree.command(
    name="ping",
    description="Check the bot's latency.",
)
async def ping_command(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"🏓 Pong! `{latency}ms`"
    )


@tree.command(
    name="info",
    description="Show bot information.",
)
async def info_command(interaction: discord.Interaction):
    voice_status = "Not connected"

    for voice_client in bot.voice_clients:
        if voice_client.guild.id == SERVER_ID:
            if voice_client.is_connected():
                voice_status = voice_client.channel.name

    embed = discord.Embed(
        title="🤖 Discord Bot Information",
        description="Presence notification and utility bot",
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="Monitored User",
        value=f"<@{TARGET_USER_ID}>",
        inline=False,
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
        text="Status: Do Not Disturb | Listening to music"
    )

    await interaction.response.send_message(embed=embed)


@tree.command(
    name="music",
    description="Change the bot's listening activity.",
)
@app_commands.describe(name="Music name to display")
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
    description="Connect the bot to the configured voice channel.",
)
async def vc_command(interaction: discord.Interaction):
    await connect_to_voice()

    await interaction.response.send_message(
        "🔊 Connecting to the configured voice channel.",
        ephemeral=True,
    )


@tree.command(
    name="leave",
    description="Disconnect the bot from the current voice channel.",
)
async def leave_command(interaction: discord.Interaction):
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
# START BOT
# =========================================================

if __name__ == "__main__":
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True,
    )

    flask_thread.start()

    bot.run(TOKEN)