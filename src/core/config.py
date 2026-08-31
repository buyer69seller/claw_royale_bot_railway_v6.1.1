# src/core/config.py
"""Konfigurasi dari environment dengan Strategy Mode Selection"""

import os
import logging
from dotenv import load_dotenv
from .constants import (
    DEFAULT_ENTRY_TYPE,
    DEFAULT_PREFERRED_MODE,
    DEFAULT_ACTION_INTERVAL
)
from .exceptions import ConfigurationError

# Setup logger
logger = logging.getLogger(__name__)

# Load .env
load_dotenv()


# ===== REQUIRED =====
API_KEY = os.getenv("CLAW_API_KEY", "").strip()
if not API_KEY:
    raise ConfigurationError(
        "❌ CLAW_API_KEY is required. Please set it in .env file.\n"
        "   Example: CLAW_API_KEY=mr_live_xxxxxxxxxxxx"
    )


# ===== STRATEGY MODE =====
STRATEGY_MODE = os.getenv("STRATEGY_MODE", "hybrid").lower()
VALID_STRATEGIES = ["hybrid", "scan_clear"]

if STRATEGY_MODE not in VALID_STRATEGIES:
    print(f"⚠️ Unknown STRATEGY_MODE: '{STRATEGY_MODE}', using default: hybrid")
    STRATEGY_MODE = "hybrid"

# Strategy description
STRATEGY_DESCRIPTIONS = {
    "hybrid": "AI Auto-Pilot + Reinforcement Learning (Adaptive)",
    "scan_clear": "Scan semua item, clear semua musuh, pindah region (Aggressive)"
}


# ===== GAME CONFIG =====
ENTRY_TYPE = os.getenv("ENTRY_TYPE", DEFAULT_ENTRY_TYPE).lower()
if ENTRY_TYPE not in ["free", "paid"]:
    raise ConfigurationError(
        f"❌ Invalid ENTRY_TYPE: '{ENTRY_TYPE}'. Must be 'free' or 'paid'"
    )

PREFERRED_MODE = os.getenv("PREFERRED_MODE", DEFAULT_PREFERRED_MODE).lower()
if PREFERRED_MODE not in ["offchain", "onchain"]:
    raise ConfigurationError(
        f"❌ Invalid PREFERRED_MODE: '{PREFERRED_MODE}'. Must be 'offchain' or 'onchain'"
    )

ACTION_INTERVAL_SECONDS = float(
    os.getenv("ACTION_INTERVAL_SECONDS", str(DEFAULT_ACTION_INTERVAL))
)
if ACTION_INTERVAL_SECONDS < 0.1 or ACTION_INTERVAL_SECONDS > 2.0:
    print(f"⚠️ ACTION_INTERVAL_SECONDS: {ACTION_INTERVAL_SECONDS} outside recommended range (0.1-1.0)")


# ===== LOGGING =====
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if LOG_LEVEL not in VALID_LOG_LEVELS:
    print(f"⚠️ Unknown LOG_LEVEL: '{LOG_LEVEL}', using default: INFO")
    LOG_LEVEL = "INFO"


# ===== REINFORCEMENT LEARNING =====
RL_ENABLED = os.getenv("RL_ENABLED", "true").lower() in ["true", "1", "yes", "on"]
RL_LEARNING_RATE = float(os.getenv("RL_LEARNING_RATE", "0.1"))
RL_EPSILON_START = float(os.getenv("RL_EPSILON_START", "1.0"))
RL_EPSILON_END = float(os.getenv("RL_EPSILON_END", "0.05"))

# Validate RL params
if RL_LEARNING_RATE < 0.01 or RL_LEARNING_RATE > 1.0:
    print(f"⚠️ RL_LEARNING_RATE: {RL_LEARNING_RATE} outside range (0.01-1.0), using 0.1")
    RL_LEARNING_RATE = 0.1

if RL_EPSILON_START < 0.0 or RL_EPSILON_START > 1.0:
    print(f"⚠️ RL_EPSILON_START: {RL_EPSILON_START} outside range (0.0-1.0), using 1.0")
    RL_EPSILON_START = 1.0

if RL_EPSILON_END < 0.0 or RL_EPSILON_END > 1.0:
    print(f"⚠️ RL_EPSILON_END: {RL_EPSILON_END} outside range (0.0-1.0), using 0.05")
    RL_EPSILON_END = 0.05


# ===== MEMORY =====
MAX_KNOWLEDGE_HISTORY = int(os.getenv("MAX_KNOWLEDGE_HISTORY", "500"))
MAX_RL_MEMORY = int(os.getenv("MAX_RL_MEMORY", "1000"))

if MAX_KNOWLEDGE_HISTORY < 100:
    print(f"⚠️ MAX_KNOWLEDGE_HISTORY: {MAX_KNOWLEDGE_HISTORY} too low, using 100")
    MAX_KNOWLEDGE_HISTORY = 100

if MAX_RL_MEMORY < 100:
    print(f"⚠️ MAX_RL_MEMORY: {MAX_RL_MEMORY} too low, using 100")
    MAX_RL_MEMORY = 100


# ===== SCAN & CLEAR CONFIG =====
SCAN_CLEAR_MAX_TURNS_PER_REGION = int(os.getenv("SCAN_CLEAR_MAX_TURNS_PER_REGION", "10"))
SCAN_CLEAR_MAX_ITEM_DISTANCE = float(os.getenv("SCAN_CLEAR_MAX_ITEM_DISTANCE", "5.0"))
SCAN_CLEAR_MIN_HP_TO_FIGHT = float(os.getenv("SCAN_CLEAR_MIN_HP_TO_FIGHT", "0.4"))

if SCAN_CLEAR_MAX_TURNS_PER_REGION < 3:
    print(f"⚠️ SCAN_CLEAR_MAX_TURNS_PER_REGION: {SCAN_CLEAR_MAX_TURNS_PER_REGION} too low, using 3")
    SCAN_CLEAR_MAX_TURNS_PER_REGION = 3


# ===== VALIDATION SUMMARY =====
def validate_config() -> bool:
    """Validasi semua konfigurasi"""
    errors = []
    warnings = []
    
    # API Key
    if not API_KEY:
        errors.append("CLAW_API_KEY is empty")
    elif len(API_KEY) < 10:
        warnings.append("CLAW_API_KEY seems too short (min 10 chars)")
    
    # Strategy
    if STRATEGY_MODE not in VALID_STRATEGIES:
        errors.append(f"Invalid STRATEGY_MODE: {STRATEGY_MODE}")
    
    # Entry Type
    if ENTRY_TYPE not in ["free", "paid"]:
        errors.append(f"Invalid ENTRY_TYPE: {ENTRY_TYPE}")
    
    # Log Level
    if LOG_LEVEL not in VALID_LOG_LEVELS:
        warnings.append(f"Invalid LOG_LEVEL: {LOG_LEVEL}")
    
    # RL
    if RL_LEARNING_RATE < 0.01 or RL_LEARNING_RATE > 1.0:
        warnings.append(f"RL_LEARNING_RATE: {RL_LEARNING_RATE} outside range")
    
    if errors:
        for error in errors:
            logger.error(f"❌ Config error: {error}")
        return False
    
    if warnings:
        for warning in warnings:
            logger.warning(f"⚠️ Config warning: {warning}")
    
    return True


def print_config():
    """Print konfigurasi yang digunakan"""
    print("=" * 60)
    print("📋 CONFIGURATION SUMMARY")
    print("=" * 60)
    print(f"  🔑 API Key: {API_KEY[:10]}...{API_KEY[-5:] if len(API_KEY) > 15 else ''}")
    print(f"  🧠 Strategy Mode: {STRATEGY_MODE.upper()} - {STRATEGY_DESCRIPTIONS.get(STRATEGY_MODE, 'Unknown')}")
    print(f"  🎮 Entry Type: {ENTRY_TYPE}")
    print(f"  ⚡ Action Interval: {ACTION_INTERVAL_SECONDS}s")
    print(f"  📊 Log Level: {LOG_LEVEL}")
    print("-" * 60)
    print(f"  🧠 RL Enabled: {RL_ENABLED}")
    if RL_ENABLED:
        print(f"     - Learning Rate: {RL_LEARNING_RATE}")
        print(f"     - Epsilon Start: {RL_EPSILON_START}")
        print(f"     - Epsilon End: {RL_EPSILON_END}")
    print("-" * 60)
    print(f"  💾 Knowledge History: {MAX_KNOWLEDGE_HISTORY}")
    print(f"  💾 RL Memory: {MAX_RL_MEMORY}")
    print("-" * 60)
    if STRATEGY_MODE == "scan_clear":
        print(f"  📋 Scan & Clear Config:")
        print(f"     - Max Turns/Region: {SCAN_CLEAR_MAX_TURNS_PER_REGION}")
        print(f"     - Max Item Distance: {SCAN_CLEAR_MAX_ITEM_DISTANCE}")
        print(f"     - Min HP to Fight: {SCAN_CLEAR_MIN_HP_TO_FIGHT}")
    print("=" * 60)


# ===== EXPORTS =====
__all__ = [
    # Required
    "API_KEY",
    # Strategy
    "STRATEGY_MODE",
    "STRATEGY_DESCRIPTIONS",
    "VALID_STRATEGIES",
    # Game
    "ENTRY_TYPE",
    "PREFERRED_MODE",
    "ACTION_INTERVAL_SECONDS",
    # Logging
    "LOG_LEVEL",
    # RL
    "RL_ENABLED",
    "RL_LEARNING_RATE",
    "RL_EPSILON_START",
    "RL_EPSILON_END",
    # Memory
    "MAX_KNOWLEDGE_HISTORY",
    "MAX_RL_MEMORY",
    # Scan & Clear
    "SCAN_CLEAR_MAX_TURNS_PER_REGION",
    "SCAN_CLEAR_MAX_ITEM_DISTANCE",
    "SCAN_CLEAR_MIN_HP_TO_FIGHT",
    # Functions
    "validate_config",
    "print_config"
]


# ===== AUTO-VALIDATE ON IMPORT =====
if __name__ != "__main__":
    # Auto-validate config
    valid = validate_config()
    if not valid:
        print("\n❌ Configuration validation failed. Please fix errors and restart.")
        # Don't exit, let it fail gracefully
