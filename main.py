# main.py
import asyncio
import discord
from core.auth import get_bot_secrets, initialize_auth
from core.confirmation import request_confirmation, handle_password, handle_confirm, handle_cancel, _cleanup_expired
from core.logger import log_failure, query_logs, format_log_entries
from core.help import get_help
from core.utils import chunk_message
from core.registry import COMMAND_GROUPS
from monitoring.monitor import start_monitoring

# ---------------------------
# Vault Setup
# ---------------------------
secrets = get_bot_secrets()
DISCORD_TOKEN = secrets["DISCORD_TOKEN"]
PRIVATE_CHANNEL_ID = int(secrets["PRIVATE_CHANNEL_ID"])
AUTHORIZED_USER_ID = int(secrets["DISCORD_OWNER_ID"])

initialize_auth(AUTHORIZED_USER_ID, secrets["BOT_PASSWORD"])

# ---------------------------
# Discord Setup
# ---------------------------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = discord.Client(intents=intents)

# ---------------------------
# Running Commands Lock
# ---------------------------
RUNNING_COMMANDS = set()
RUNNING_LOCK = asyncio.Lock()

# ---------------------------cat 
# Helpers
# ---------------------------
def _is_authorized(message) -> bool:
    return (
        message.channel.id == PRIVATE_CHANNEL_ID
        and message.author.id == AUTHORIZED_USER_ID
    )

async def send_reply(channel, text: str):
    """Send a reply, chunking if it exceeds Discord's 2000 char limit."""
    is_code_block = text.strip().startswith("```")
    chunks = chunk_message(text, code_block=is_code_block)
    for chunk in chunks:
        await channel.send(chunk)

# ---------------------------
# Handlers
# ---------------------------
async def _handle_confirm(message):
    reply = await handle_confirm(message.author.id)
    await send_reply(message.channel, reply)

async def _handle_cancel(message):
    reply = await handle_cancel(message.author.id)
    await send_reply(message.channel, reply)

async def _handle_password(message):
    parts = message.content.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send("Usage: !password <your_password>")
        return
    reply = await handle_password(message.author.id, parts[1])
    await send_reply(message.channel, reply)

async def _handle_help(message):
    parts = message.content.strip().split(maxsplit=2)
    service = parts[1] if len(parts) > 1 else None
    command = parts[2] if len(parts) > 2 else None
    reply = get_help(service, command)
    await send_reply(message.channel, reply)
{}
async def _handle_logs(message):
    """
    !logs                            → last 20 entries
    !logs 50                         → last 50 entries
    !logs command <name>             → filter by command name
    !logs level <INFO|WARNING|ERROR> → filter by level
    !logs type <command|monitor|confirmation|system_action>
    """
    parts = message.content.strip().split()
    last_n         = 20
    filter_command = None
    filter_level   = None
    filter_type    = None

    i = 1
    while i < len(parts):
        token = parts[i].lower()
        if token.isdigit():
            last_n = int(token)
        elif token == "command" and i + 1 < len(parts):
            filter_command = parts[i + 1].lower()
            i += 1
        elif token == "level" and i + 1 < len(parts):
            filter_level = parts[i + 1].upper()
            i += 1
        elif token == "type" and i + 1 < len(parts):
            filter_type = parts[i + 1].lower()
            i += 1
        i += 1

    entries = query_logs(
        last_n=last_n,
        filter_command=filter_command,
        filter_level=filter_level,
        filter_type=filter_type
    )
    reply = format_log_entries(entries)
    await send_reply(message.channel, reply)

async def _handle_command(message):
    parts = message.content.strip()[1:].split()
    cmd_group_key = parts[0]
    cmd_key = parts[1] if len(parts) > 1 else None
    args = parts[2:] if len(parts) > 2 else []

    # ---------------------------
    # !<service> help → delegate to help handler
    # ---------------------------
    if cmd_key and cmd_key.lower() == "help":
        reply = get_help(cmd_group_key, args[0] if args else None)
        await send_reply(message.channel, reply)
        return

    module = COMMAND_GROUPS.get(cmd_group_key)
    if not module or not cmd_key:
        await message.channel.send(
            f"❌ Unknown command group `{cmd_group_key}`. Try `!help` to see available services."
        )
        return

    meta = module.COMMAND_MAP.get(cmd_key)
    if not meta:
        await message.channel.send(
            f"❌ Unknown command `{cmd_key}` in `{cmd_group_key}`. Try `!help {cmd_group_key}` to see available commands."
        )
        return

    func = meta["func"]
    tier = meta.get("tier", 0)

    async with RUNNING_LOCK:
        if cmd_key in RUNNING_COMMANDS:
            await message.channel.send(f"❌ `{cmd_key}` is already running.")
            return
        RUNNING_COMMANDS.add(cmd_key)

    if meta.get("slow"):
        ack = await message.channel.send(f"⏳ `{cmd_group_key} {cmd_key}` is running, please wait...")
    else:
        ack = await message.channel.send(f"🔄 `{cmd_group_key} {cmd_key}`...")

    async def wrapped():
        try:
            await asyncio.sleep(.5)
            if asyncio.iscoroutinefunction(func):
                return await func(*args)
            else:
                return func(*args)
        except Exception as e:
            log_failure(cmd_key, tier, str(e))
            return f"❌ Error executing `{cmd_key}`: {e}"
        finally:
            async with RUNNING_LOCK:
                RUNNING_COMMANDS.discard(cmd_key)

    # ---------------------------
    # Fix: name the closure for confirmation logging
    # ---------------------------
    wrapped.__name__ = f"{cmd_group_key}_{cmd_key}"

    if tier == 0:
        reply = await wrapped()
    else:
        reply = await request_confirmation(message.author.id, wrapped, tier)

    try:
        await ack.delete()
    except discord.NotFound:
        pass

    await send_reply(message.channel, reply)


# ---------------------------
# Event Handlers
# ---------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Listening in channel ID: {PRIVATE_CHANNEL_ID}")
    asyncio.create_task(start_monitoring(bot, PRIVATE_CHANNEL_ID))
    asyncio.create_task(_cleanup_expired())

@bot.event
async def on_message(message):
    if not _is_authorized(message):
        return

    lower = message.content.strip().lower()

    try:
        if lower.startswith("!confirm"):
            await _handle_confirm(message)
        elif lower.startswith("!cancel"):
            await _handle_cancel(message)
        elif lower.startswith("!password"):
            await _handle_password(message)
        elif lower.startswith("!ping"):
            await message.channel.send("pong")
        elif lower.startswith("!help"):
            await _handle_help(message)
        elif lower.startswith("!logs"):
            await _handle_logs(message)
        elif lower.startswith("!"):
            await _handle_command(message)
    except Exception as e:
        log_failure("main", "on_message", 0, error=e)
        await message.channel.send(f"❌ Unexpected error: `{e}`")

# ---------------------------
# Run Bot
# ---------------------------
bot.run(DISCORD_TOKEN)
