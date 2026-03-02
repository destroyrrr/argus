# monitoring/monitor.py
import asyncio
import psutil
from datetime import datetime
from core.logger import log_failure
from core.state import EXPECTED_CHANGES, PREVIOUS_CONTAINERS  # ✅ no longer owns this state
from services import docker_bot_commands
from services import system_bot_commands
from services import tailscale_bot_commands

# ---------------------------
# Poll Intervals
# ---------------------------
DOCKER_POLL_INTERVAL = 10
SYSTEM_POLL_INTERVAL = 30
MOUNT_POLL_INTERVAL = 30
TAILSCALE_POLL_INTERVAL = 60

# ---------------------------
# Thresholds
# ---------------------------
CPU_THRESHOLD = 80.0   # percent
MEM_THRESHOLD = 90.0   # percent

# ---------------------------
# Alert Cooldown
# ---------------------------
ALERT_COOLDOWN = 300
_last_alert_times = {}

def _should_alert(key: str) -> bool:
    now = datetime.utcnow()
    last = _last_alert_times.get(key)
    if last is None or (now - last).total_seconds() > ALERT_COOLDOWN:
        _last_alert_times[key] = now
        return True
    return False

# ---------------------------
# Expected Mounts / Devices
# ---------------------------
EXPECTED_MOUNTS = [
    "TV", "Movies", "Books",
    "Destroyer of Movies", "Destroyer of Television", "Destroyer of Content"
]
TAILSCALE_DEVICES = []  # populate with known device hostnames to monitor

# ---------------------------
# Docker Monitor
# ---------------------------
async def monitor_docker(bot, channel_id):
    """Alert only on unexpected container stops."""
    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)

    while True:
        try:
            containers = docker_bot_commands.docker_client.containers.list()
            running = set(c.name for c in containers)

            if not PREVIOUS_CONTAINERS:
                # First run — establish baseline, no alerts
                PREVIOUS_CONTAINERS.update(running)
            else:
                stopped = PREVIOUS_CONTAINERS - running
                unexpected = [c for c in stopped if c not in EXPECTED_CHANGES]

                for c in unexpected:
                    if _should_alert(f"docker:{c}"):
                        await channel.send(f"🚨 **Unexpected Docker Stop**\n❌ `{c}`")

                # Reset expected changes after evaluation
                EXPECTED_CHANGES.clear()
                PREVIOUS_CONTAINERS.clear()
                PREVIOUS_CONTAINERS.update(running)

        except Exception as e:
            log_failure("monitor", "monitor_docker", 0, error=e)

        await asyncio.sleep(DOCKER_POLL_INTERVAL)

# ---------------------------
# System Monitor
# ---------------------------
async def monitor_system(bot, channel_id):
    """Monitor CPU and memory against defined thresholds."""
    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)

    while True:
        try:
            # ✅ psutil runs in thread — doesn't block event loop
            cpu = await asyncio.to_thread(psutil.cpu_percent, interval=1)
            mem = await asyncio.to_thread(lambda: psutil.virtual_memory().percent)

            if cpu > CPU_THRESHOLD and _should_alert("system:cpu"):
                await channel.send(f"⚠ High CPU usage: `{cpu:.1f}%`")

            if mem > MEM_THRESHOLD and _should_alert("system:mem"):
                await channel.send(f"⚠ High memory usage: `{mem:.1f}%`")

        except Exception as e:
            log_failure("monitor", "monitor_system", 0, error=e)

        await asyncio.sleep(SYSTEM_POLL_INTERVAL)

# ---------------------------
# Mount Monitor
# ---------------------------
async def monitor_mounts(bot, channel_id):
    """Alert when expected mounts go missing."""
    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)

    known_missing = set()

    while True:
        try:
            mounts_output = await system_bot_commands.mounts()

            current_mounts = set()
            for line in mounts_output.splitlines():
                if "/Volumes/" in line:
                    parts = line.split("/Volumes/")
                    if len(parts) > 1:
                        name = parts[1].split(" ")[0]
                        current_mounts.add(name)

            missing = set(EXPECTED_MOUNTS) - current_mounts
            new_missing = missing - known_missing

            for m in new_missing:
                if _should_alert(f"mount:{m}"):
                    await channel.send(f"⚠ Mount missing: `{m}`")

            known_missing = missing

        except Exception as e:
            log_failure("monitor", "monitor_mounts", 0, error=e)

        await asyncio.sleep(MOUNT_POLL_INTERVAL)

# ---------------------------
# Tailscale Monitor
# ---------------------------
async def monitor_tailscale(bot, channel_id):
    """Monitor Tailscale devices using structured data, not string scraping."""
    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)

    known_offline = set()

    while True:
        try:
            # ✅ structured data — no string parsing of formatted output
            devices_list = await tailscale_bot_commands.get_devices_structured()
            online = {d["name"] for d in devices_list if d.get("online")}

            offline = set(TAILSCALE_DEVICES) - online
            new_offline = offline - known_offline

            for d in new_offline:
                if _should_alert(f"tailscale:{d}"):
                    await channel.send(f"⚠ Tailscale device offline: `{d}`")

            known_offline = offline

        except Exception as e:
            log_failure("monitor", "monitor_tailscale", 0, error=e)

        await asyncio.sleep(TAILSCALE_POLL_INTERVAL)

# ---------------------------
# Start Monitoring
# ---------------------------
async def start_monitoring(bot, channel_id):
    asyncio.create_task(monitor_docker(bot, channel_id))
    asyncio.create_task(monitor_system(bot, channel_id))
    asyncio.create_task(monitor_mounts(bot, channel_id))
    asyncio.create_task(monitor_tailscale(bot, channel_id))
