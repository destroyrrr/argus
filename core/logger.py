# core/logger.py
import logging
import json
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_FILE = "logs/argus.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logger = logging.getLogger("ArgusLogger")
logger.setLevel(logging.DEBUG)

try:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
except Exception as e:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    logger.error(f"Failed to initialize file logger: {e}")

# ---------------------------
# Internal Writer
# ---------------------------
def _write(level: str, entry: dict):
    entry["level"] = level
    line = json.dumps(entry)
    if level == "ERROR":
        logger.error(line)
    elif level == "WARNING":
        logger.warning(line)
    else:
        logger.info(line)

# ---------------------------
# Command Logging
# ---------------------------
def log_command(user_id, command, tier, args=None, success=True, error=None):
    level = "INFO" if success else "ERROR"
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type":      "command",
        "user_id":   user_id,
        "command":   command,
        "tier":      tier,
        "args":      args or [],
        "success":   success,
        "error":     str(error) if error else None
    }
    _write(level, entry)

def log_success(user_id, command, tier, args=None):
    log_command(user_id, command, tier, args=args, success=True)

def log_failure(user_id, command, tier, args=None, error=None):
    log_command(user_id, command, tier, args=args, success=False, error=error)

# ---------------------------
# System Action Logging
# ---------------------------
def log_system_action(user_id, action_name, target=None, tier=0, success=True, error=None):
    level = "INFO" if success else "ERROR"
    entry = {
        "timestamp":     datetime.utcnow().isoformat(),
        "type":          "system_action",
        "user_id":       user_id,
        "system_action": action_name,
        "target":        target,
        "tier":          tier,
        "success":       success,
        "error":         str(error) if error else None
    }
    _write(level, entry)

# ---------------------------
# Monitor Event Logging
# ---------------------------
def log_monitor_event(event_type: str, target: str, detail: str = None, level: str = "WARNING"):
    """
    event_type: 'docker_stop', 'high_cpu', 'mount_missing', 'tailscale_offline', etc.
    level:      'INFO', 'WARNING', 'ERROR'
    """
    entry = {
        "timestamp":  datetime.utcnow().isoformat(),
        "type":       "monitor",
        "event_type": event_type,
        "target":     target,
        "detail":     detail,
    }
    _write(level, entry)

# ---------------------------
# Confirmation Event Logging
# ---------------------------
def log_confirmation(user_id: int, command: str, tier: int, outcome: str):
    """
    outcome: 'requested', 'approved', 'denied', 'expired', 'cancelled'
    """
    level = "WARNING" if outcome in ("denied", "expired") else "INFO"
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type":      "confirmation",
        "user_id":   user_id,
        "command":   command,
        "tier":      tier,
        "outcome":   outcome,
    }
    _write(level, entry)

# ---------------------------
# Query Logs — used by !logs command
# ---------------------------
def query_logs(
    last_n: int = 20,
    filter_command: str = None,
    filter_level: str = None,
    filter_type: str = None
) -> list[dict]:
    """
    Reads log file in reverse, returns up to last_n matching entries.

    filter_command : match entries where 'command' == value
    filter_level   : 'INFO', 'WARNING', 'ERROR'
    filter_type    : 'command', 'monitor', 'confirmation', 'system_action'
    """
    if not os.path.exists(LOG_FILE):
        return []

    results = []

    with open(LOG_FILE, "r") as f:
        lines = f.readlines()

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if filter_level and entry.get("level") != filter_level.upper():
            continue
        if filter_type and entry.get("type") != filter_type.lower():
            continue
        if filter_command and entry.get("command") != filter_command.lower():
            continue

        results.append(entry)
        if len(results) >= last_n:
            break

    return results

# ---------------------------
# Format Log Entries — used by !logs command
# ---------------------------
def format_log_entries(entries: list[dict]) -> str:
    """Formats query results into a Discord-safe code block."""
    if not entries:
        return "No log entries found."

    lines = []
    for e in entries:
        ts      = e.get("timestamp", "")[:19].replace("T", " ")
        level   = e.get("level", "INFO").ljust(7)
        etype   = e.get("type", "unknown").ljust(13)
        command = e.get("command") or e.get("event_type") or e.get("system_action") or "—"
        target  = e.get("target") or e.get("args") or ""
        error   = e.get("error")

        line = f"{ts} [{level}] [{etype}] {command}"
        if target:
            line += f" | {target}"
        if error:
            line += f" | ❌ {error}"

        lines.append(line)

    return "```\n" + "\n".join(lines) + "\n```"
