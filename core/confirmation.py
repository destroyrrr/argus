# core/confirmation.py
import asyncio
from typing import Callable
from core.auth import verify_password
from core.logger import log_success, log_failure, log_confirmation

# ---------------------------
# Awaiting Confirmation
# ---------------------------
AWAITING_CONFIRMATION = {}
AWAITING_LOCK = asyncio.Lock()
CONFIRM_EXPIRY = 300

# ---------------------------
# Background Cleanup
# ---------------------------
async def _cleanup_expired():
    """Runs forever. Purges confirmations that passed their expiry without action."""
    while True:
        await asyncio.sleep(60)
        now = asyncio.get_event_loop().time()
        async with AWAITING_LOCK:
            expired = [
                uid for uid, entry in AWAITING_CONFIRMATION.items()
                if now > entry["expiry"]
            ]
            for uid in expired:
                entry = AWAITING_CONFIRMATION.pop(uid)
                log_confirmation(uid, entry["func"].__name__, entry["tier"], "expired")

# ---------------------------
# Request Confirmation
# Tier 0 is handled directly in _handle_command — never reaches here
# ---------------------------
async def request_confirmation(user_id: int, func: Callable, tier: int = 1, *args):
    """
    Tier levels:
      1 - requires !confirm
      2 - requires !password
      3 - requires !password (confirm alone not sufficient)
    """
    async with AWAITING_LOCK:
        if user_id in AWAITING_CONFIRMATION:
            return "⚠ You already have a pending command. Confirm it or wait for it to expire."

        expiry = asyncio.get_event_loop().time() + CONFIRM_EXPIRY
        AWAITING_CONFIRMATION[user_id] = {
            "func":   func,
            "args":   args,
            "tier":   tier,
            "expiry": expiry
        }

    log_confirmation(user_id, func.__name__, tier, "requested")

    if tier == 1:
        return "⚠ Confirm with `!confirm` within 5 minutes. Use `!cancel` to abort."
    if tier in [2, 3]:
        return "⚠ Authorize with `!password <password>` within 5 minutes. Use `!cancel` to abort."
    return "⚠ Pending confirmation. Use `!cancel` to abort."

# ---------------------------
# Handle !confirm
# ---------------------------
async def handle_confirm(user_id: int):
    async with AWAITING_LOCK:
        entry = AWAITING_CONFIRMATION.get(user_id)
        if not entry:
            return "No pending commands."

        if entry["tier"] in [2, 3]:
            return "❌ This command requires `!password <password>`, not `!confirm`."

        AWAITING_CONFIRMATION.pop(user_id)

    if asyncio.get_event_loop().time() > entry["expiry"]:
        log_confirmation(user_id, entry["func"].__name__, entry["tier"], "expired")
        return "⏱ Pending command expired."

    func, args, tier = entry["func"], entry["args"], entry["tier"]

    try:
        result = func(*args)
        if asyncio.iscoroutine(result):
            result = await result
        log_success(user_id, func.__name__, tier, args)
        log_confirmation(user_id, func.__name__, tier, "approved")
        return f"✅ Command executed:\n{result}"
    except Exception as e:
        log_failure(user_id, func.__name__, tier, args, error=e)
        log_confirmation(user_id, func.__name__, tier, "denied")
        return f"❌ Command failed: {e}"

# ---------------------------
# Handle !password
# ---------------------------
async def handle_password(user_id: int, password: str):
    async with AWAITING_LOCK:
        entry = AWAITING_CONFIRMATION.get(user_id)
        if not entry:
            return "No pending commands."

        if entry["tier"] == 1:
            return "❌ This command requires `!confirm`, not `!password`."

        AWAITING_CONFIRMATION.pop(user_id)

    if asyncio.get_event_loop().time() > entry["expiry"]:
        log_confirmation(user_id, entry["func"].__name__, entry["tier"], "expired")
        return "⏱ Pending command expired."

    if not verify_password(password):
        log_failure(user_id, entry["func"].__name__, entry["tier"], entry["args"], error="Incorrect password")
        log_confirmation(user_id, entry["func"].__name__, entry["tier"], "denied")
        return "❌ Incorrect password. Command not executed."

    func, args, tier = entry["func"], entry["args"], entry["tier"]

    try:
        result = func(*args)
        if asyncio.iscoroutine(result):
            result = await result
        log_success(user_id, func.__name__, tier, args)
        log_confirmation(user_id, func.__name__, tier, "approved")
        return f"✅ Command executed:\n{result}"
    except Exception as e:
        log_failure(user_id, func.__name__, tier, args, error=e)
        log_confirmation(user_id, func.__name__, tier, "denied")
        return f"❌ Command failed: {e}"

# ---------------------------
# Handle !cancel
# ---------------------------
async def handle_cancel(user_id: int):
    async with AWAITING_LOCK:
        entry = AWAITING_CONFIRMATION.pop(user_id, None)

    if not entry:
        return "No pending commands to cancel."

    log_confirmation(user_id, entry["func"].__name__, entry["tier"], "cancelled")
    return f"🚫 Pending command `{entry['func'].__name__}` cancelled."
