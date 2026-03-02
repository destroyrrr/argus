# core/auth.py
import hvac
import os
import hashlib
import time
import logging

logger = logging.getLogger("AuthLogger")

VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
ROLE_ID = os.environ.get("VAULT_ROLE_ID")
SECRET_ID = os.environ.get("VAULT_SECRET_ID")
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# ---------------------------
# Vault Connection (retry logic preserved)
# ---------------------------
for attempt in range(MAX_RETRIES):
    try:
        vault_client = hvac.Client(url=VAULT_ADDR)
        vault_client.auth.approle.login(role_id=ROLE_ID, secret_id=SECRET_ID)
        break
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
        else:
            logger.error(f"Vault connection failed: {e}")
            raise RuntimeError("Unable to connect to Vault.")

def get_bot_secrets():
    try:
        secret_data = vault_client.secrets.kv.v2.read_secret_version(
            path="bot", mount_point="discord"
        )["data"]["data"]
        return secret_data
    except Exception as e:
        logger.error(f"Error reading secrets from Vault: {e}")
        raise RuntimeError("Unable to read secrets from Vault.")

# ---------------------------
# Runtime-Injected Auth State
# ---------------------------
PASSWORD_HASH = None
AUTHORIZED_USER_ID = None

def initialize_auth(owner_id: int, bot_password: str):
    global PASSWORD_HASH, AUTHORIZED_USER_ID

    if not bot_password:
        raise RuntimeError("BOT_PASSWORD not provided")

    AUTHORIZED_USER_ID = owner_id
    PASSWORD_HASH = hashlib.sha256(bot_password.encode()).hexdigest()

def verify_user(user_id: int) -> bool:
    if AUTHORIZED_USER_ID is None:
        raise RuntimeError("Auth not initialized")
    return user_id == AUTHORIZED_USER_ID

def verify_password(password: str) -> bool:
    if PASSWORD_HASH is None:
        raise RuntimeError("Auth not initialized")
    return hashlib.sha256(password.encode()).hexdigest() == PASSWORD_HASH