# services/tailscale_bot_commands.py
import asyncio
import subprocess
import json

# ---------------------------
# Core CLI Runner
# ---------------------------
async def run_tailscale_cmd(*args):
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["tailscale", *args],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"❌ CLI error: {e.stderr or e}"
    except Exception as e:
        return f"❌ Error: {e}"

# ---------------------------
# JSON Parser
# ---------------------------
def parse_status_json(raw_json):
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return None, "❌ Failed to parse Tailscale JSON output."

    devices = []

    self_info = data.get("Self", {})
    devices.append({
        "name":      self_info.get("HostName", "Unknown"),
        "online":    self_info.get("Online", False),
        "addresses": self_info.get("TailscaleIPs", []),
        "dnsName":   self_info.get("DNSName", ""),
        "os":        self_info.get("OS", ""),
        "user":      self_info.get("UserID", "")
    })

    peers = data.get("Peer", {})
    for peer_name, peer_info in peers.items():
        devices.append({
            "name":      peer_info.get("HostName", "Unknown"),
            "online":    peer_info.get("Online", False),
            "addresses": peer_info.get("TailscaleIPs", []),
            "dnsName":   peer_info.get("DNSName", ""),
            "os":        peer_info.get("OS", ""),
            "user":      peer_info.get("UserID", "")
        })

    return devices, None


# ---------------------------
# Structured data for monitor.py
# ---------------------------
async def get_devices_structured() -> list:
    """Returns raw device dicts. Used by monitor — not for Discord display."""
    raw = await run_tailscale_cmd("status", "--json")
    devices_list, error = parse_status_json(raw)
    if error:
        raise RuntimeError(error)
    return devices_list or []

# ---------------------------
# Discord-Facing Commands
# ---------------------------
async def devices(*args):
    raw = await run_tailscale_cmd("status", "--json")
    devices_list, error = parse_status_json(raw)
    if error:
        return error
    lines = []
    for d in devices_list:
        status = "🟢" if d.get("online") else "🔴"
        hostname = d.get("name") or "Unknown"
        lines.append(f"{status} {hostname}")
    return "```\n" + "\n".join(lines) + "\n```"


async def online(*args):
    raw = await run_tailscale_cmd("status", "--json")
    devices_list, error = parse_status_json(raw)
    if error:
        return error
    lines = []
    for d in devices_list:
        if d.get("online"):
            hostname = d.get("name") or "Unknown"
            lines.append(f"🟢 {hostname}")
    return "No devices online." if not lines else "```\n" + "\n".join(lines) + "\n```"



async def ips(*args):
    if not args:
        return "Usage: !tailscale ips <device_name>"
    device_name = " ".join(args).lower()
    raw = await run_tailscale_cmd("status", "--json")
    devices_list, error = parse_status_json(raw)
    if error:
        return error
    for d in devices_list:
        if d.get("name", "").lower() == device_name:
            status = "🟢" if d.get("online") else "🔴"
            hostname = d.get("name") or "Unknown"
            addresses = [ip for ip in d.get("addresses", []) if ip]
            ips_str = ", ".join(addresses) if addresses else "N/A"
            lines = [
                f"Device info: {status} {hostname}",
                f"Tailnet IPs: {ips_str}",
            ]
            return "```\n" + "\n".join(lines) + "\n```"
    return f"❌ Device `{device_name}` not found."

async def dns(*args):
    if not args:
        return "Usage: !tailscale dns <device_name>"
    device_name = " ".join(args).lower()
    raw = await run_tailscale_cmd("status", "--json")
    devices_list, error = parse_status_json(raw)
    if error:
        return error
    for d in devices_list:
        if d.get("name", "").lower() == device_name:
            status = "🟢" if d.get("online") else "🔴"
            hostname = d.get("name") or "Unknown"
            dns_name = d.get("dnsName") or "N/A"
            lines = [
                f"Device info: {status} {hostname}",
                f"DNS Name: {dns_name}",
            ]
            return "```\n" + "\n".join(lines) + "\n```"
    return f"❌ Device `{device_name}` not found."


async def toggle(*args):
    try:
        raw = await run_tailscale_cmd("status")
        connected = "100." in raw
        if connected:
            await run_tailscale_cmd("down")
            await asyncio.sleep(2)
            return "⚠ Tailscale disconnected."
        else:
            await run_tailscale_cmd("up")
            await asyncio.sleep(2)
            return "✅ Tailscale connected."
    except Exception as e:
        return f"❌ Error toggling connection: {e}"


# ---------------------------
# Exports
# ---------------------------
TAILSCALE_COMMANDS_LIST = ["devices", "online", "ips", "dns", "toggle"]

COMMAND_MAP = {
    "devices": {"func": devices, "help": "Lists all devices on the tailnet.",        "args": ""},
    "online":  {"func": online,  "help": "Lists online devices.",                    "args": ""},
    "ips":     {"func": ips,     "help": "Shows IPs and info for a device.",         "args": "<device>"},
    "dns":     {"func": dns,     "help": "Shows the DNS name of a device.",          "args": "<device>"},
    "toggle":  {"func": toggle,  "help": "Toggles the Tailscale connection on/off.", "args": ""},
}
