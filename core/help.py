# core/help.py
from core.registry import COMMAND_GROUPS  # ✅ replaces local definition

# ---------------------------
# Get Help Function
# ---------------------------
def get_help(service: str = None, command: str = None) -> str:
    # No service — list available services
    if not service:
        services = ", ".join(COMMAND_GROUPS.keys())
        return f"Available services: {services}\nUsage: `!help <service>` or `!help <service> <command>`"

    service = service.lower()
    module = COMMAND_GROUPS.get(service)
    if not module:
        return f"❌ Unknown service `{service}`. Available: {', '.join(COMMAND_GROUPS.keys())}"

    command_map = module.COMMAND_MAP

    # Service only — list all commands
    if not command:
        lines = [f"**{service.upper()} Commands:**"]
        for cmd, meta in command_map.items():
            args = meta.get("args", "")
            desc = meta.get("help", "No description.")
            entry = f"  `!{service} {cmd}"
            if args:
                entry += f" {args}"
            entry += f"` — {desc}"
            lines.append(entry)
        return "\n".join(lines)

    # Service + command — show specific help
    command = command.lower()
    meta = command_map.get(command)
    if not meta:
        return f"❌ No help found for `{command}` in `{service}`."

    args = meta.get("args", "")
    desc = meta.get("help", "No description.")
    usage = f"`!{service} {command}"
    if args:
        usage += f" {args}"
    usage += "`"
    return f"**{usage}**\n{desc}"
