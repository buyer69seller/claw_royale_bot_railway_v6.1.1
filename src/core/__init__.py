# src/core/__init__.py
"""Core module - Config, Constants, Exceptions"""

from .config import (
    API_KEY,
    ENTRY_TYPE,
    PREFERRED_MODE,
    ACTION_INTERVAL_SECONDS,
    LOG_LEVEL,
    STRATEGY_MODE
)
from .constants import (
    # Base
    BASE_DIR,
    # API
    BASE_API,
    JOIN_WS,
    AGENT_WS,
    API_VERSION_URL,
    # Defaults
    DEFAULT_ENTRY_TYPE,
    DEFAULT_PREFERRED_MODE,
    DEFAULT_ACTION_INTERVAL,
    # Runtime
    ACTION_INTERVAL_SECONDS as CONST_ACTION_INTERVAL_SECONDS,
    MIN_RETRY_DELAY,
    MAX_RETRY_DELAY,
    RETRY_BACKOFF_MULTIPLIER,
    RECONNECT_RESET_THRESHOLD,
    # Directories
    CACHE_DIR,
    LOG_DIR,
    KNOWLEDGE_PATH,
    ensure_directories,
    # Strategy Scoring
    SCORE_HEAL_BASE,
    SCORE_HEAL_HP_BONUS,
    SCORE_ATTACK_BASE,
    SCORE_ATTACK_HP_BONUS,
    SCORE_GUARDIAN_PENALTY,
    SCORE_ATTACK_KILL_BONUS,
    SCORE_SURVIVAL_BONUS,
    SCORE_LOOT_BASE,
    SCORE_LOOT_BONUS,
    SCORE_INTERACT_BASE,
    SCORE_EXPLORE_BASE,
    SCORE_MOVE_BASE,
    SCORE_CAVE_EXIT,
    # Docs
    DOCS_TO_CACHE,
    # AI
    AI_LEARNING_RATE,
    AI_CONFIDENCE_THRESHOLD,
    AI_RISK_THRESHOLD,
    AI_STRATEGY_SWITCH_INTERVAL,
    # Auto-Equip
    AUTO_EQUIP_ENABLED,
    AUTO_EQUIP_INTERVAL_GAMES,
    AUTO_EQUIP_ON_STARTUP,
    # Pre-Season 1 - Packs
    MAIN_ONLY_PACKS,
    SUB_CAPABLE_PACKS,
    PACK_EFFECTS,
    PACK_ATTENUATION,
    SUB_ATTENUATION_MODES,
    # Pre-Season 1 - Relics
    RELIC_SLOTS,
    RELIC_AFFIXES,
    RELIC_AFFIX_PRIORITY,
    # Inventory
    INVENTORY_CAPS,
    # Pack Helper Functions
    get_pack_by_name,
    get_pack_effect,
    is_main_only_pack,
    is_sub_capable_pack,
    get_pack_tier_effect,
    get_pack_recommendation,
)
from .exceptions import (
    ClawRoyaleError,
    ConfigurationError,
    VersionMismatchError,
    AgentDeadError,
    TargetDeadError,
    ResumeTargetDeadError,
    AuthenticationError,
    RateLimitError,
    NotSelectedError,
    GameError,
    AgentTokenRequiredError,
    AccountBlockedError,
)

__all__ = [
    # Config
    "API_KEY",
    "ENTRY_TYPE",
    "PREFERRED_MODE",
    "ACTION_INTERVAL_SECONDS",
    "LOG_LEVEL",
    "STRATEGY_MODE",
    # Base
    "BASE_DIR",
    # API
    "BASE_API",
    "JOIN_WS",
    "AGENT_WS",
    "API_VERSION_URL",
    # Defaults
    "DEFAULT_ENTRY_TYPE",
    "DEFAULT_PREFERRED_MODE",
    "DEFAULT_ACTION_INTERVAL",
    # Runtime
    "CONST_ACTION_INTERVAL_SECONDS",
    "MIN_RETRY_DELAY",
    "MAX_RETRY_DELAY",
    "RETRY_BACKOFF_MULTIPLIER",
    "RECONNECT_RESET_THRESHOLD",
    # Directories
    "CACHE_DIR",
    "LOG_DIR",
    "KNOWLEDGE_PATH",
    "ensure_directories",
    # Strategy Scoring
    "SCORE_HEAL_BASE",
    "SCORE_HEAL_HP_BONUS",
    "SCORE_ATTACK_BASE",
    "SCORE_ATTACK_HP_BONUS",
    "SCORE_GUARDIAN_PENALTY",
    "SCORE_ATTACK_KILL_BONUS",
    "SCORE_SURVIVAL_BONUS",
    "SCORE_LOOT_BASE",
    "SCORE_LOOT_BONUS",
    "SCORE_INTERACT_BASE",
    "SCORE_EXPLORE_BASE",
    "SCORE_MOVE_BASE",
    "SCORE_CAVE_EXIT",
    # Docs
    "DOCS_TO_CACHE",
    # AI
    "AI_LEARNING_RATE",
    "AI_CONFIDENCE_THRESHOLD",
    "AI_RISK_THRESHOLD",
    "AI_STRATEGY_SWITCH_INTERVAL",
    # Auto-Equip
    "AUTO_EQUIP_ENABLED",
    "AUTO_EQUIP_INTERVAL_GAMES",
    "AUTO_EQUIP_ON_STARTUP",
    # Pre-Season 1 - Packs
    "MAIN_ONLY_PACKS",
    "SUB_CAPABLE_PACKS",
    "PACK_EFFECTS",
    "PACK_ATTENUATION",
    "SUB_ATTENUATION_MODES",
    # Pre-Season 1 - Relics
    "RELIC_SLOTS",
    "RELIC_AFFIXES",
    "RELIC_AFFIX_PRIORITY",
    # Inventory
    "INVENTORY_CAPS",
    # Pack Helper Functions
    "get_pack_by_name",
    "get_pack_effect",
    "is_main_only_pack",
    "is_sub_capable_pack",
    "get_pack_tier_effect",
    "get_pack_recommendation",
    # Exceptions
    "ClawRoyaleError",
    "ConfigurationError",
    "VersionMismatchError",
    "AgentDeadError",
    "TargetDeadError",
    "ResumeTargetDeadError",
    "AuthenticationError",
    "RateLimitError",
    "NotSelectedError",
    "GameError",
    "AgentTokenRequiredError",
    "AccountBlockedError",
]
