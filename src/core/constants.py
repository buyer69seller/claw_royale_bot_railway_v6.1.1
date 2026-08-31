# src/core/constants.py
"""Konstanta global untuk bot Claw Royale"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent

# Runtime directories
CACHE_DIR = os.getenv("CACHE_DIR", str(BASE_DIR / "runtime_cache"))
LOG_DIR = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
KNOWLEDGE_PATH = os.getenv("KNOWLEDGE_PATH", str(BASE_DIR / "knowledge.json"))

def ensure_directories():
    """Buat semua direktori yang dibutuhkan"""
    for d in [CACHE_DIR, LOG_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)

# API Endpoints
BASE_API = "https://cdn.clawroyale.ai/api"
JOIN_WS = "wss://cdn.clawroyale.ai/ws/join"
AGENT_WS = "wss://cdn.clawroyale.ai/ws/agent"
API_VERSION_URL = f"{BASE_API}/version"

# Default values
DEFAULT_ENTRY_TYPE = "free"
DEFAULT_PREFERRED_MODE = "offchain"
DEFAULT_ACTION_INTERVAL = 0.25

# ACTION_INTERVAL_SECONDS
ACTION_INTERVAL_SECONDS = float(os.getenv("ACTION_INTERVAL_SECONDS", str(DEFAULT_ACTION_INTERVAL)))

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
DOCS_TO_CACHE = [
    "/skill.md",
    "/openapi.yaml", 
    "/references/actions.md",
    "/references/game-loop.md",
    "/references/combat-items.md",
    "/references/game-systems.md",
    "/references/api-summary.md",
    "/references/errors.md",
    "/references/changelog.md",
    "/references/economy.md",
    "/references/free-games.md",
    "/references/paid-games.md",
]

# ===== AI Constants =====
AI_LEARNING_RATE = 0.1
AI_CONFIDENCE_THRESHOLD = 0.6
AI_RISK_THRESHOLD = 0.7
AI_STRATEGY_SWITCH_INTERVAL = 10

# ===== AUTO-EQUIP Constants (TAMBAHKAN INI) =====
AUTO_EQUIP_ENABLED = True
AUTO_EQUIP_INTERVAL_GAMES = 3  # Auto-equip setiap 3 game
AUTO_EQUIP_ON_STARTUP = True

# ===== PRE-SEASON 1 PACK DATA =====

MAIN_ONLY_PACKS = ["Scout", "Assassin"]

SUB_CAPABLE_PACKS = [
    "Moltz Expert", "Item Expert", "Goliath", "Thorns",
    "Ruin Expert", "Berserker", "Double Attack",
    "Heart of the Giant", "Bomber", "Trail Ward",
    "Ranged", "Sword Master", "Duelist", "Raider",
    "Last Stand", "Iron Heart", "Sunflame Cloak", "Pickpocket"
]

PACK_EFFECTS: Dict[str, Dict] = {
    "Moltz Expert": {
        "description": "Convert weapons/armor to Moltz",
        "main": {"moltz_convert": 1.0},
        "sub": {"moltz_convert": 0.5}
    },
    "Item Expert": {
        "description": "Moltz → Item ATK",
        "main": {"item_atk_coef": 1.0},
        "sub": {"item_atk_coef": 0.5}
    },
    "Goliath": {
        "description": "AoE attack",
        "main": {"aoe_multiplier": 0.85},
        "sub": {"aoe_multiplier": 0.425}
    },
    "Thorns": {
        "description": "Damage reduction + reflect",
        "main": {"dmg_reduction": 0.50, "reflect": 1.0},
        "sub": {"dmg_reduction": 0.25, "reflect": 0.5}
    },
    "Scout": {
        "description": "Vision +2, move -2 EP",
        "main": {"vision": 2, "move_ep_discount": 2},
        "sub": None
    },
    "Ruin Expert": {
        "description": "Instant relics, max alert",
        "main": {"instant_relics": True, "alert_max": True},
        "sub": {"instant_relics": True, "alert_max": True}
    },
    "Berserker": {
        "description": "DMG boost when HP < 50%",
        "main": {"berserker_dmg": 1.7},
        "sub": {"berserker_dmg": 1.3}
    },
    "Double Attack": {
        "description": "Attack twice",
        "main": {"hit_count": 2, "hit_multiplier": 0.65},
        "sub": {"hit_count": 2, "hit_multiplier": 0.55}
    },
    "Heart of the Giant": {
        "description": "Healing bonus + self-heal",
        "main": {"heal_bonus": 0.75, "self_heal": 0.03},
        "sub": {"heal_bonus": 0.375, "self_heal": 0.015}
    },
    "Bomber": {
        "description": "Convert items to bombs",
        "main": {"bomb_count": 3, "bomb_dmg": 0.2},
        "sub": {"bomb_count": 3, "bomb_dmg": 0.1}
    },
    "Trail Ward": {
        "description": "Start with vision wards",
        "main": {"wards": 3},
        "sub": {"wards": 2}
    },
    "Ranged": {
        "description": "Range +1, ranged damage +15%",
        "main": {"range_bonus": 1, "ranged_dmg": 0.15},
        "sub": {"range_bonus": 1, "ranged_dmg": 0.15, "ep_cost": 1}
    },
    "Sword Master": {
        "description": "No ranged, ignore ranged damage",
        "main": {"item_atk_multiplier": 1.0},
        "sub": {"item_atk_multiplier": 0.5}
    },
    "Duelist": {
        "description": "Alone → ATK/DEF boost",
        "main": {"solo_atk": 0.9, "solo_def": 0.9},
        "sub": {"solo_atk": 0.45, "solo_def": 0.45}
    },
    "Raider": {
        "description": "Steal inventory slot",
        "main": {"steal_slot": True},
        "sub": {"steal_slot": True, "ep_cost": 1}
    },
    "Last Stand": {
        "description": "Survive lethal, berserk",
        "main": {"survive_lethal": True, "berserk_turns": 3},
        "sub": {"survive_lethal": True, "berserk_turns": 1}
    },
    "Iron Heart": {
        "description": "On attack gain max-HP, DEF",
        "main": {"hp_gain": 5, "def_gain": 1},
        "sub": {"hp_gain": 2.5, "def_gain": 0.5}
    },
    "Sunflame Cloak": {
        "description": "Aura damage",
        "main": {"aura_dmg": 1.0},
        "sub": {"aura_dmg": 0.5}
    },
    "Assassin": {
        "description": "Stealth, bonus damage",
        "main": {"stealth": 3, "bonus_dmg": 0.6},
        "sub": None
    },
    "Pickpocket": {
        "description": "Steal sMoltz",
        "main": {"steal_amount": 3},
        "sub": {"steal_amount": 3, "ep_cost": 1}
    }
}

# Relic affix priorities
RELIC_AFFIX_PRIORITY = {
    "ATK": 5,
    "DMG": 5,
    "HP": 4,
    "DEF": 4,
    "Item ATK": 3,
    "Explore": 2,
    "Heal": 2
}

# ===== PACK HELPER FUNCTIONS =====

def get_pack_by_name(name: str) -> Optional[Dict]:
    """Dapatkan data pack berdasarkan nama"""
    return PACK_EFFECTS.get(name)

def get_pack_effect(name: str, slot: str = "main") -> Optional[Dict]:
    """Dapatkan efek pack berdasarkan slot"""
    pack = get_pack_by_name(name)
    if not pack:
        return None
    return pack.get(slot)

def is_main_only_pack(name: str) -> bool:
    """Cek apakah pack hanya bisa di Main slot"""
    return name in MAIN_ONLY_PACKS

def is_sub_capable_pack(name: str) -> bool:
    """Cek apakah pack bisa di Sub slot"""
    return name in SUB_CAPABLE_PACKS

def get_pack_tier_effect(pack_name: str, tier: int, slot: str = "main") -> Dict:
    """Dapatkan efek pack berdasarkan tier"""
    base_effect = get_pack_effect(pack_name, slot)
    if not base_effect:
        return {}
    
    # Tier multiplier (T1 = 1.0, T2 = 0.8, T3 = 0.6)
    tier_multiplier = {1: 1.0, 2: 0.8, 3: 0.6}.get(tier, 1.0)
    
    # Apply tier multiplier to numeric values
    result = {}
    for key, value in base_effect.items():
        if isinstance(value, (int, float)):
            result[key] = value * tier_multiplier
        else:
            result[key] = value
    
    return result

def get_pack_recommendation(strategy_type: str = "balanced") -> Dict[str, str]:
    """
    Dapatkan rekomendasi pack berdasarkan strategi
    
    Args:
        strategy_type: "survival", "damage", "stealth", "balanced", "economy"
    
    Returns:
        Dict dengan main_pack dan sub_pack
    """
    recommendations = {
        "survival": {
            "main": "Thorns",
            "sub": "Heart of the Giant",
            "description": "Focus on survival and healing"
        },
        "damage": {
            "main": "Berserker",
            "sub": "Double Attack",
            "description": "Focus on dealing damage"
        },
        "stealth": {
            "main": "Assassin",
            "sub": "Pickpocket",
            "description": "Focus on stealth and stealing"
        },
        "balanced": {
            "main": "Goliath",
            "sub": "Iron Heart",
            "description": "Balanced approach"
        },
        "economy": {
            "main": "Item Expert",
            "sub": "Moltz Expert",
            "description": "Focus on economy and item ATK"
        },
        "ranged": {
            "main": "Ranged",
            "sub": "Sword Master",
            "description": "Focus on ranged combat"
        },
        "explore": {
            "main": "Ruin Expert",
            "sub": "Scout",
            "description": "Focus on exploration and ruin farming"
        }
    }
    
    return recommendations.get(strategy_type, recommendations["balanced"])
