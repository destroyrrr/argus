# core/state.py

# ---------------------------
# Shared Mutable State
# ---------------------------
# Owned here to avoid circular imports between
# docker_bot_commands and monitor.py

EXPECTED_CHANGES: set = set()
PREVIOUS_CONTAINERS: set = set()
