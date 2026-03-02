# core/registry.py
from services import docker_bot_commands
from services import tailscale_bot_commands
from services import system_bot_commands
from services import sql_bot_commands   

# ---------------------------
# Single source of truth for all command groups
# Add new services here — no other file needs to change
# ---------------------------
COMMAND_GROUPS = {
    "docker":    docker_bot_commands,
    "tailscale": tailscale_bot_commands,
    "system":    system_bot_commands,
    "media":     sql_bot_commands,
}
