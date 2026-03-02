# services/system_bot_commands.py
import asyncio
import subprocess
import os

# ---------------------------
# Async subprocess wrapper
# ---------------------------
async def _run(cmd: list) -> subprocess.CompletedProcess:
    return await asyncio.to_thread(
        subprocess.run, cmd, capture_output=True, text=True
    )

# ---------------------------
# System Commands
# ---------------------------
async def uptime(*args):
    result = await _run(["uptime"])
    return result.stdout.strip()

async def load(*args):
    result = await _run(["uptime"])
    try:
        loads = result.stdout.strip().split("load averages:")[-1].strip()
        return f"Load averages: {loads}"
    except Exception:
        return result.stdout.strip()

async def mem(*args):
    vm_result  = await _run(["vm_stat"])
    mem_result = await _run(["sysctl", "-n", "hw.memsize"])

    # Total RAM from sysctl
    total_mb = int(mem_result.stdout.strip()) / (1024 ** 2)

    # Page breakdown from vm_stat
    mem_info = {}
    page_size = 4096
    for line in vm_result.stdout.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        try:
            mem_info[key.strip()] = int(val.strip().replace(".", "")) * page_size / (1024 ** 2)
        except ValueError:
            continue

    wired      = mem_info.get("Pages wired down", 0)
    active     = mem_info.get("Pages active", 0)
    inactive   = mem_info.get("Pages inactive", 0)
    compressed = mem_info.get("Pages occupied by compressor", 0)
    free       = mem_info.get("Pages free", 0)
    speculative = mem_info.get("Pages speculative", 0)

    accounted  = wired + active + inactive + compressed + free + speculative
    other      = total_mb - accounted  # file cache, mapped memory, etc.
    used       = total_mb - free - speculative

    return (
        f"Memory: {used:.0f} MB used / {total_mb:.0f} MB total\n"
        f"  Wired:      {wired:.0f} MB\n"
        f"  Active:     {active:.0f} MB\n"
        f"  Inactive:   {inactive:.0f} MB\n"
        f"  Compressed: {compressed:.0f} MB\n"
        f"  Other:      {other:.0f} MB\n"
        f"  Free:       {free:.0f} MB"
    )



async def processes(*args):
    result = await _run(["ps", "aux"])
    return f"```\n{result.stdout.strip()[:1900]}\n```"

async def users(*args):
    result = await _run(["who"])
    return result.stdout.strip()

async def ps(*args):
    if not args:
        return "Usage: !system ps <name>"
    result = await _run(["pgrep", "-fl", args[0]])
    return result.stdout.strip() or f"No process matching '{args[0]}' found"

async def kill(*args):
    if not args:
        return "Usage: !system kill <pid/name>"
    pid_or_name = args[0]
    result = await _run(["kill", "-9", pid_or_name])
    if result.returncode == 0:
        return f"Process {pid_or_name} killed"
    result = await _run(["pkill", "-f", pid_or_name])
    if result.returncode == 0:
        return f"Processes matching '{pid_or_name}' killed"
    return f"No matching process found for '{pid_or_name}'"

async def start(*args):
    if not args:
        return "Usage: !system start <service>"
    result = await _run(["sudo", "launchctl", "load", f"/Library/LaunchDaemons/{args[0]}.plist"])
    return result.stdout.strip() or f"Service '{args[0]}' started"

async def stop(*args):
    if not args:
        return "Usage: !system stop <service>"
    result = await _run(["sudo", "launchctl", "unload", f"/Library/LaunchDaemons/{args[0]}.plist"])
    return result.stdout.strip() or f"Service '{args[0]}' stopped"

async def restart(*args):
    if not args:
        return "Usage: !system restart <service>"
    await stop(args[0])
    await asyncio.sleep(1)
    await start(args[0])
    return f"Service '{args[0]}' restarted"

async def ls(*args):
    if not args:
        return "Usage: !system ls <path>"
    result = await _run(["ls", "-lha", args[0]])
    return f"```\n{result.stdout.strip()[:1900]}\n```"

async def cat(*args):
    if not args:
        return "Usage: !system cat <file>"
    result = await _run(["cat", args[0]])
    return f"```\n{result.stdout.strip()[:1900]}\n```"

async def tail(*args):
    if not args:
        return "Usage: !system tail <file> [lines]"
    lines = args[1] if len(args) > 1 else "10"
    result = await _run(["tail", "-n", lines, args[0]])
    return f"```\n{result.stdout.strip()[:1900]}\n```"

async def mounts(*args):
    result = await _run(["mount"])
    return f"```\n{result.stdout.strip()[:1900]}\n```"

async def checkmount(*args):
    if not args:
        return "Usage: !system checkmount <name>"
    name = args[0]
    result = await _run(["mount"])
    for line in result.stdout.splitlines():
        if name in line:
            return f"✅ Mount '{name}' exists: {line}"
    return f"❌ Mount '{name}' not found"

async def mount(*args):
    if not args:
        return "Usage: !system mount <name>"
    mount_point = f"/Volumes/{args[0]}"
    is_mounted = await asyncio.to_thread(os.path.ismount, mount_point)
    if is_mounted:
        return f"Mount '{args[0]}' already mounted at {mount_point}"
    result = await _run(["open", mount_point])
    if result.returncode == 0:
        return f"Mount '{args[0]}' mounted successfully"
    return f"Failed to mount '{args[0]}'"

async def eject(*args):
    if not args:
        return "Usage: !system eject <name>"
    mount_point = f"/Volumes/{args[0]}"
    is_mounted = await asyncio.to_thread(os.path.ismount, mount_point)
    if not is_mounted:
        return f"Mount '{args[0]}' not found"
    result = await _run(["diskutil", "unmount", mount_point])
    if result.returncode == 0:
        return f"Mount '{args[0]}' ejected successfully"
    return f"Failed to eject '{args[0]}': {result.stderr.strip()}"

async def launch(*args):
    if not args:
        return "Usage: !system launch <app_path>"
    path = args[0]
    exists = await asyncio.to_thread(os.path.exists, path)
    if not exists:
        return f"App path '{path}' does not exist"
    result = await _run(["open", path])
    if result.returncode == 0:
        return f"App '{path}' launched successfully"
    return f"Failed to launch '{path}': {result.stderr.strip()}"

# ---------------------------
# Exports
# ---------------------------
SYSTEM_COMMANDS_LIST = [
    "uptime", "load", "mem", "processes", "users", "ps", "kill",
    "start", "stop", "restart", "ls", "cat", "tail",
    "mounts", "checkmount", "mount", "eject", "launch"
]

COMMAND_MAP = {
    "uptime":     {"func": uptime,     "help": "Shows how long the system has been running.",        "args": ""},
    "load":       {"func": load,       "help": "Shows current system load averages.",                "args": ""},
    "mem":        {"func": mem,        "help": "Shows memory usage.",                                "args": ""},
    "processes":  {"func": processes,  "help": "Lists all running processes.",                       "args": ""},
    "users":      {"func": users,      "help": "Lists logged in users.",                             "args": ""},
    "ps":         {"func": ps,         "help": "Finds processes by name.",                           "args": "<name>"},
    "kill":       {"func": kill,       "help": "Kills a process by PID or name.",                   "args": "<pid/name>"},
    "start":      {"func": start,      "help": "Starts a system service.",                           "args": "<service>"},
    "stop":       {"func": stop,       "help": "Stops a system service.",                            "args": "<service>"},
    "restart":    {"func": restart,    "help": "Restarts a system service.",                         "args": "<service>"},
    "ls":         {"func": ls,         "help": "Lists files in the given path.",                     "args": "<path>"},
    "cat":        {"func": cat,        "help": "Displays the contents of a file.",                   "args": "<file>"},
    "tail":       {"func": tail,       "help": "Shows the last N lines of a file.",                  "args": "<file> [lines]"},
    "mounts":     {"func": mounts,     "help": "Lists all mounted drives.",                          "args": ""},
    "checkmount": {"func": checkmount, "help": "Checks if a specific drive is mounted.",             "args": "<name>"},
    "mount":      {"func": mount,      "help": "Mounts a drive by name.",                            "args": "<name>"},
    "eject":      {"func": eject,      "help": "Ejects a drive by name.",                            "args": "<name>"},
    "launch":     {"func": launch,     "help": "Launches a macOS .app application.",                 "args": "<app_path>"},
}
