# services/docker_bot_commands.py
import docker
import asyncio
import logging
import os
from core.state import EXPECTED_CHANGES

# ---------------------------
# Docker client
# ---------------------------
docker_client = docker.from_env()

# ---------------------------
# Logging setup
# ---------------------------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "docker_bot.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------------------
# Async wrapper decorator
# ---------------------------
def docker_command(func):
    async def wrapper(*args, **kwargs):
        def run():
            try:
                docker_client.ping()
            except docker.errors.DockerException:
                return "❌ Docker engine is not running."
            return func(*args, **kwargs)
        return await asyncio.to_thread(run)
    return wrapper

# ---------------------------
# Helpers
# ---------------------------
def format_container(c):
    status_emoji = "🟢" if c.status == "running" else "🔴"

    ports = []
    for port_key, mappings in c.attrs['NetworkSettings']['Ports'].items():
        if mappings:
            host_port = mappings[0]["HostPort"]
            ports.append(host_port)

    port_str = ", ".join(ports) if ports else "No ports"
    return f"{status_emoji} {c.name}: {port_str}"



def format_block(lines):
    return "```\n" + "\n".join(lines) + "\n```"


# ---------------------------
# Docker Commands
# ---------------------------
@docker_command
def list(identifier=None):
    containers = docker_client.containers.list(all=True)
    if not containers:
        return "No containers found."
    lines = [format_container(c) for c in containers]
    return format_block(lines)


@docker_command
def running():
    containers = docker_client.containers.list()
    if not containers:
        return "No running containers."
    lines = [format_container(c) for c in containers]
    return format_block(lines)


@docker_command
def start(identifier):
    try:
        c = docker_client.containers.get(identifier)
        if c.status == "running":
            return f"🟢 Container '{c.name}' is already running."
        c.start()
        logging.info(f"Started {c.name} ({c.id[:12]})")
        return f"✅ Container '{c.name}' started."
    except Exception as e:
        return f"❌ Docker error: {e}"


@docker_command
def restart(identifier):
    try:
        c = docker_client.containers.get(identifier)
        EXPECTED_CHANGES.add(c.name)
        c.restart()
        logging.info(f"Restarted {c.name} ({c.id[:12]})")
        return f"✅ Container '{c.name}' restarted."
    except Exception as e:
        return f"❌ Docker error: {e}"


@docker_command
def kill(identifier):
    try:
        c = docker_client.containers.get(identifier)
        EXPECTED_CHANGES.add(c.name)
        c.kill()
        logging.info(f"Killed {c.name} ({c.id[:12]})")
        return f"⚠ Container '{c.name}' killed."
    except Exception as e:
        return f"❌ Docker error: {e}"


@docker_command
def stop(identifier):
    try:
        c = docker_client.containers.get(identifier)
        EXPECTED_CHANGES.add(c.name)
        c.stop()
        logging.info(f"Stopped {c.name} ({c.id[:12]})")
        return f"⚠ Container '{c.name}' stopped."
    except Exception as e:
        return f"❌ Docker error: {e}"


@docker_command
def deploy(image_name):
    try:
        c = docker_client.containers.run(image_name, detach=True)
        logging.info(f"Deployed {c.name} ({c.id[:12]}) from image {image_name}")
        return f"✅ Container '{c.name}' deployed from image '{image_name}'."
    except Exception as e:
        return f"❌ Docker error: {e}"


@docker_command
def pull(image_name):
    try:
        docker_client.images.pull(image_name)
        logging.info(f"Pulled image {image_name}")
        return f"✅ Image '{image_name}' pulled."
    except Exception as e:
        return f"❌ Docker error: {e}"


@docker_command
def rename(identifier, new_name):
    try:
        c = docker_client.containers.get(identifier)
        old_name = c.name
        c.rename(new_name)
        logging.info(f"Renamed {old_name} ({c.id[:12]}) -> {new_name}")
        return f"✅ Container '{old_name}' renamed to '{new_name}'."
    except Exception as e:
        return f"❌ Docker error: {e}"


@docker_command
def stats(identifier):
    try:
        c = docker_client.containers.get(identifier)
        s = c.stats(stream=False)

        # ✅ CPU percent — same calculation Docker CLI uses
        cpu_delta = (
            s["cpu_stats"]["cpu_usage"]["total_usage"]
            - s["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            s["cpu_stats"]["system_cpu_usage"]
            - s["precpu_stats"]["system_cpu_usage"]
        )
        num_cpus = s["cpu_stats"].get("online_cpus") or len(
            s["cpu_stats"]["cpu_usage"].get("percpu_usage", [1])
        )
        cpu_percent = (
            (cpu_delta / system_delta) * num_cpus * 100.0
            if system_delta > 0
            else 0.0
        )

        # ✅ Memory in MB with percent
        mem_usage = s["memory_stats"]["usage"] / (1024 ** 2)
        mem_limit = s["memory_stats"]["limit"] / (1024 ** 2)
        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0.0

        lines = [
            f"Container: {c.name}",
            f"CPU:    {cpu_percent:.1f}%",
            f"Memory: {mem_usage:.1f} MB / {mem_limit:.1f} MB ({mem_percent:.1f}%)",
        ]
        return format_block(lines)

    except Exception as e:
        return f"❌ Docker error: {e}"


@docker_command
def logs(identifier, tail_lines="20"):
    try:
        c = docker_client.containers.get(identifier)
        logs = c.logs(tail=int(tail_lines)).decode("utf-8")
        lines = logs.splitlines()
        return f"**Logs for {c.name}**\n" + format_block(lines)
    except Exception as e:
        return f"❌ Docker error: {e}"


# ---------------------------
# Exports
# ---------------------------
# ---------------------------
# Exports
# ---------------------------
DOCKER_COMMANDS_LIST = [
    "list", "running", "restart", "kill",
    "deploy", "pull", "rename", "stop",
    "stats", "logs", "start"
]

COMMAND_MAP = {
    "list":    {"func": list,    "help": "Lists all Docker containers.",               "args": "",                "tier": 0},
    "running": {"func": running, "help": "Lists running containers.",                  "args": "",                "tier": 0},
    "start":   {"func": start,   "help": "Starts a stopped container.",                "args": "<name>",          "tier": 0},
    "restart": {"func": restart, "help": "Restarts a container by name.",              "args": "<name>",          "tier": 1},
    "kill":    {"func": kill,    "help": "Kills a container by name.",                 "args": "<name>",          "tier": 1},
    "stop":    {"func": stop,    "help": "Stops a container.",                         "args": "<name>",          "tier": 1},
    "deploy":  {"func": deploy,  "help": "Deploys a new container from an image.",     "args": "<image>",         "tier": 3},
    "pull":    {"func": pull,    "help": "Pulls an image from a registry.",            "args": "<image>",         "tier": 0},
    "rename":  {"func": rename,  "help": "Renames a container.",                       "args": "<id> <new_name>", "tier": 1},
    "stats":   {"func": stats,   "help": "Shows CPU and memory stats of a container.", "args": "<name>",          "tier": 0},
    "logs":    {"func": logs,    "help": "Shows logs of a container.",                 "args": "<id> [lines]",    "tier": 0},
}
