# src/core/constants.py
"""Konstanta global untuk bot Claw Royale"""

# API Endpoints
BASE_API = "https://cdn.clawroyale.ai/api"
JOIN_WS = "wss://cdn.clawroyale.ai/ws/join"
AGENT_WS = "wss://cdn.clawroyale.ai/ws/agent"
API_VERSION_URL = f"{BASE_API}/version"

# Default values
DEFAULT_ENTRY_TYPE = "free"
DEFAULT_PREFERRED_MODE = "offchain"
DEFAULT_ACTION_INTERVAL = 0.25

# Retry configuration
MIN_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0
RETRY_BACKOFF_MULTIPLIER = 2.0
RECONNECT_RESET_THRESHOLD = 10.0

# Strategy scoring - Survival-first
SCORE_HEAL_BASE = 900
SCORE_HEAL_HP_BONUS = 700
SCORE_ATTACK_BASE = 550
SCORE_ATTACK_HP_BONUS = 600
SCORE_GUARDIAN_PENALTY = 300
SCORE_ATTACK_KILL_BONUS = 150
SCORE_SURVIVAL_BONUS = 200

# Loot scoring
SCORE_LOOT_BASE = 300
SCORE_LOOT_BONUS = 250
SCORE_INTERACT_BASE = 520
SCORE_EXPLORE_BASE = 380
SCORE_MOVE_BASE = 250

# Cave escape priority
SCORE_CAVE_EXIT = 1000

# Document cache paths
CACHE_DIR = "runtime_cache"
DOCS_TO_CACHE = [
    "/skill.md",
    "/openapi.yaml", 
    "/references/actions.md",
    "/references/game-loop.md",
    "/references/combat-items.md",
    "/references/game-systems.md",
    "/references/api-summary.md",
    "/references/errors.md",
]

# AI Constants
AI_LEARNING_RATE = 0.1
AI_CONFIDENCE_THRESHOLD = 0.6
AI_RISK_THRESHOLD = 0.7
AI_STRATEGY_SWITCH_INTERVAL = 10