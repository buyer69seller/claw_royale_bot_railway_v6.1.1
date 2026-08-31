# src/core/__init__.py
"""Core module - config, constants, and exceptions"""

from .config import API_KEY, ENTRY_TYPE, PREFERRED_MODE, LOG_LEVEL
from .constants import (
    # API & Network
    BASE_API,
    JOIN_WS,
    AGENT_WS,
    API_VERSION_URL,
    
    # Default values
    DEFAULT_ENTRY_TYPE,
    DEFAULT_PREFERRED_MODE,
    DEFAULT_ACTION_INTERVAL,
    ACTION_INTERVAL_SECONDS,
    
    # Retry configuration
    MIN_RETRY_DELAY,
    MAX_RETRY_DELAY,
    RETRY_BACKOFF_MULTIPLIER,
    RECONNECT_RESET_THRESHOLD,
    
    # Strategy scoring
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
    
    # Runtime directories
    CACHE_DIR,
    LOG_DIR,
    KNOWLEDGE_PATH,
    DOCS_TO_CACHE,
    ensure_directories,
    
    # AI Constants
    AI_LEARNING_RATE,
    AI_CONFIDENCE_THRESHOLD,
    AI_RISK_THRESHOLD,
    AI_STRATEGY_SWITCH_INTERVAL,
    
    # ===== PRE-SEASON 1 PACK DATA =====
    MAIN_ONLY_PACKS,
    SUB_CAPABLE_PACKS,
    PACK_EFFECTS,
    RELIC_AFFIX_PRIORITY,
    get_pack_by_name,
    get_pack_effect,
    is_main_only_pack,
    is_sub_capable_pack,
)
from .exceptions import *

__all__ = [
    # Config
    "API_KEY",
    "ENTRY_TYPE",
    "PREFERRED_MODE",
    "LOG_LEVEL",
    
    # API & Network
    "BASE_API",
    "JOIN_WS",
    "AGENT_WS",
    "API_VERSION_URL",
    
    # Default values
    "DEFAULT_ENTRY_TYPE",
    "DEFAULT_PREFERRED_MODE",
    "DEFAULT_ACTION_INTERVAL",
    "ACTION_INTERVAL_SECONDS",
    
    # Retry configuration
    "MIN_RETRY_DELAY",
    "MAX_RETRY_DELAY",
    "RETRY_BACKOFF_MULTIPLIER",
    "RECONNECT_RESET_THRESHOLD",
    
    # Strategy scoring
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
    
    # Runtime directories
    "CACHE_DIR",
    "LOG_DIR",
    "KNOWLEDGE_PATH",
    "DOCS_TO_CACHE",
    "ensure_directories",
    
    # AI Constants
    "AI_LEARNING_RATE",
    "AI_CONFIDENCE_THRESHOLD",
    "AI_RISK_THRESHOLD",
    "AI_STRATEGY_SWITCH_INTERVAL",
    
    # ===== PRE-SEASON 1 PACK DATA =====
    "MAIN_ONLY_PACKS",
    "SUB_CAPABLE_PACKS",
    "PACK_EFFECTS",
    "RELIC_AFFIX_PRIORITY",
    "get_pack_by_name",
    "get_pack_effect",
    "is_main_only_pack",
    "is_sub_capable_pack",
    
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
