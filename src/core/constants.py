# src/core/constants.py
"""Konstanta global untuk bot Claw Royale"""

import os
from pathlib import Path

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

# AI Constants
AI_LEARNING_RATE = 0.1
AI_CONFIDENCE_THRESHOLD = 0.6
AI_RISK_THRESHOLD = 0.7
AI_STRATEGY_SWITCH_INTERVAL = 10


# ============================================================
# ===== PRE-SEASON 1 PACK DATA =====
# ============================================================

MAIN_ONLY_PACKS = ["Scout", "Assassin"]

SUB_CAPABLE_PACKS = [
    "Moltz Expert",
    "Item Expert",
    "Goliath",
    "Thorns",
    "Ruin Expert",
    "Berserker",
    "Double Attack",
    "Heart of the Giant",
    "Bomber",
    "Trail Ward",
    "Ranged",
    "Sword Master",
    "Duelist",
    "Raider",
    "Last Stand",
    "Iron Heart",
    "Sunflame Cloak",
    "Pickpocket"
]

PACK_EFFECTS = {
    "Moltz Expert": {
        "description": "Converts acquired weapons and armor into Moltz by grade",
        "main": {"moltz_convert": 1.0},
        "sub": {"moltz_convert": 0.5}
    },
    "Item Expert": {
        "description": "Moltz picked up is instantly added to item ATK",
        "main": {"item_atk_coef": 1.0},
        "sub": {"item_atk_coef": 0.5}
    },
    "Goliath": {
        "description": "Area-of-effect attack that hits every targeted tile",
        "main": {"aoe_multiplier": 0.85},
        "sub": {"aoe_multiplier": 0.425}
    },
    "Thorns": {
        "description": "Reduces incoming combat damage and reflects absorbed damage",
        "main": {"dmg_reduction": 0.50, "reflect": 1.0},
        "sub": {"dmg_reduction": 0.25, "reflect": 0.5}
    },
    "Scout": {
        "description": "Vision +2 and move costs 2 less EP. Main slot only.",
        "main": {"vision": 2, "move_ep_discount": 2},
        "sub": None  # Main only
    },
    "Ruin Expert": {
        "description": "Grants collected relics and packs immediately, fills alert gauge",
        "main": {"instant_relics": True, "alert_max": True, "guardian_dmg": 1.5},
        "sub": {"instant_relics": True, "alert_max": True, "guardian_dmg": 1.5}
    },
    "Berserker": {
        "description": "When HP drops below 50, damage dealt is multiplied",
        "main": {"berserker_dmg": 1.7},
        "sub": {"berserker_dmg": 1.3}
    },
    "Double Attack": {
        "description": "Attack resolves twice",
        "main": {"hit_count": 2, "hit_multiplier": 0.65},
        "sub": {"hit_count": 2, "hit_multiplier": 0.55}
    },
    "Heart of the Giant": {
        "description": "Healing items restore bonus max-HP, self-heal per turn",
        "main": {"heal_bonus": 0.75, "self_heal": 0.03},
        "sub": {"heal_bonus": 0.375, "self_heal": 0.015}
    },
    "Bomber": {
        "description": "Convert passed-tile items into bombs",
        "main": {"bomb_count": 3, "bomb_dmg": 0.2},
        "sub": {"bomb_count": 3, "bomb_dmg": 0.1}
    },
    "Trail Ward": {
        "description": "Start with vision wards that grant vision around them",
        "main": {"wards": 3},
        "sub": {"wards": 2}
    },
    "Ranged": {
        "description": "Ranged weapon range +1, ranged damage +15%",
        "main": {"range_bonus": 1, "ranged_dmg": 0.15},
        "sub": {"range_bonus": 1, "ranged_dmg": 0.15, "ep_cost": 1}
    },
    "Sword Master": {
        "description": "No ranged, ignore ranged damage, relic Item ATK bonus",
        "main": {"item_atk_multiplier": 1.0, "ignore_ranged": True},
        "sub": {"item_atk_multiplier": 0.5, "ignore_ranged": True}
    },
    "Duelist": {
        "description": "When alone with one other target, gain relic ATK and DEF",
        "main": {"solo_atk": 0.9, "solo_def": 0.9},
        "sub": {"solo_atk": 0.45, "solo_def": 0.45}
    },
    "Raider": {
        "description": "Attack steals inventory slot from target",
        "main": {"steal_slot": True},
        "sub": {"steal_slot": True, "ep_cost": 1}
    },
    "Last Stand": {
        "description": "Survive lethal at HP1, then berserk",
        "main": {"survive_lethal": True, "berserk_turns": 3, "hp_regen": 5.0},
        "sub": {"survive_lethal": True, "berserk_turns": 1, "hp_regen": 2.5}
    },
    "Iron Heart": {
        "description": "On attack, gain max-HP and DEF (stack cap 10)",
        "main": {"hp_gain": 5, "def_gain": 1},
        "sub": {"hp_gain": 2.5, "def_gain": 0.5}
    },
    "Sunflame Cloak": {
        "description": "Aura radius deals per-turn damage",
        "main": {"aura_dmg": 1.0, "aura_radius": 1},
        "sub": {"aura_dmg": 0.5, "aura_radius": 1}
    },
    "Assassin": {
        "description": "Stealth: harder to detect. Bonus damage on hit. Main slot only.",
        "main": {"stealth": 3, "bonus_dmg": 0.6},
        "sub": None  # Main only
    },
    "Pickpocket": {
        "description": "Steal sMoltz from same-region agent",
        "main": {"steal_amount": 3},
        "sub": {"steal_amount": 3, "ep_cost": 1}
    }
}

# Pack tier ranges (T1, T2, T3)
PACK_TIER_RANGES = {
    "Moltz Expert": {
        "T1": {"moltz_convert_high": (11, 13)},
        "T2": {"moltz_convert_high": (8, 10)},
        "T3": {"moltz_convert_high": (5, 7)}
    },
    "Item Expert": {
        "T1": {"coef": (1.75, 2.25)},
        "T2": {"coef": (1.25, 1.75)},
        "T3": {"coef": (0.75, 1.25)}
    },
    "Goliath": {
        "T1": {"atk_multiplier": (0.8, 0.9)},
        "T2": {"atk_multiplier": (0.7, 0.8)},
        "T3": {"atk_multiplier": (0.6, 0.7)}
    },
    "Thorns": {
        "T1": {"dmg_reduction": (0.475, 0.525)},
        "T2": {"dmg_reduction": (0.425, 0.475)},
        "T3": {"dmg_reduction": (0.375, 0.425)}
    },
    "Scout": {
        "T1": {"dmg_multiplier": (0.75, 0.85)},
        "T2": {"dmg_multiplier": (0.65, 0.75)},
        "T3": {"dmg_multiplier": (0.55, 0.65)}
    },
    "Ruin Expert": {
        "T1": {"guardian_dmg": (1.25, 1.75)},
        "T2": {"guardian_dmg": (1.75, 2.25)},
        "T3": {"guardian_dmg": (2.25, 2.75)}
    },
    "Berserker": {
        "T1": {"dmg_multiplier": (1.6, 1.8)},
        "T2": {"dmg_multiplier": (1.4, 1.6)},
        "T3": {"dmg_multiplier": (1.2, 1.4)}
    },
    "Double Attack": {
        "T1": {"hit_multiplier": (0.6, 0.7)},
        "T2": {"hit_multiplier": (0.525, 0.6)},
        "T3": {"hit_multiplier": (0.475, 0.525)}
    },
    "Heart of the Giant": {
        "T1": {"heal_bonus": (0.625, 0.875)},
        "T2": {"heal_bonus": (0.375, 0.625)},
        "T3": {"heal_bonus": (0.125, 0.375)}
    },
    "Bomber": {
        "T1": {"atk_multiplier": (0.175, 0.225)},
        "T2": {"atk_multiplier": (0.125, 0.175)},
        "T3": {"atk_multiplier": (0.075, 0.125)}
    },
    "Trail Ward": {
        "T1": {"wards": 3},
        "T2": {"wards": 2},
        "T3": {"wards": 1}
    },
    "Ranged": {
        "T1": {"dmg_increase": (0.125, 0.175)},
        "T2": {"dmg_increase": (0.075, 0.125)},
        "T3": {"dmg_increase": (0.025, 0.075)}
    },
    "Sword Master": {
        "T1": {"item_atk_multiplier": (0.875, 1.125)},
        "T2": {"item_atk_multiplier": (0.625, 0.875)},
        "T3": {"item_atk_multiplier": (0.375, 0.625)}
    },
    "Duelist": {
        "T1": {"solo_atk": (0.8, 1.0), "solo_def": (0.8, 1.0)},
        "T2": {"solo_atk": (0.6, 0.8), "solo_def": (0.6, 0.8)},
        "T3": {"solo_atk": (0.4, 0.6), "solo_def": (0.4, 0.6)}
    },
    "Last Stand": {
        "T1": {"hp_regen": (4.5, 5.5)},
        "T2": {"hp_regen": (3.5, 4.5)},
        "T3": {"hp_regen": (2.5, 3.5)}
    },
    "Iron Heart": {
        "T1": {"dmg_multiplier": (0.85, 0.95)},
        "T2": {"dmg_multiplier": (0.75, 0.85)},
        "T3": {"dmg_multiplier": (0.65, 0.75)}
    },
    "Sunflame Cloak": {
        "T1": {"dmg_multiplier": (0.8, 1.0)},
        "T2": {"dmg_multiplier": (0.6, 0.8)},
        "T3": {"dmg_multiplier": (0.4, 0.6)}
    },
    "Assassin": {
        "T1": {"bonus_dmg": (0.55, 0.65)},
        "T2": {"bonus_dmg": (0.45, 0.55)},
        "T3": {"bonus_dmg": (0.35, 0.45)}
    }
}

# Synergy pairs and their bonus scores
PACK_SYNERGIES = [
    ("Thorns", "Heart of the Giant", 30, "Survival - damage reduction + healing"),
    ("Berserker", "Last Stand", 25, "Clutch - low HP damage + survive lethal"),
    ("Item Expert", "Moltz Expert", 20, "Economy - convert Moltz to ATK"),
    ("Goliath", "Double Attack", 15, "Damage - AoE + double hit"),
    ("Ranged", "Sword Master", 10, "Ranged/Melee - versatile combat"),
    ("Assassin", "Pickpocket", 15, "Stealth - steal + bonus damage"),
    ("Ruin Expert", "Scout", 10, "Exploration - vision + ruin rewards"),
    ("Thorns", "Iron Heart", 20, "Tank - damage reduction + stack DEF"),
    ("Berserker", "Double Attack", 15, "Burst - low HP damage + double hit"),
    ("Heart of the Giant", "Last Stand", 25, "Immortal - healing + survive lethal")
]

# Relic affix priority weights
RELIC_AFFIX_PRIORITY = {
    "ATK": 5,
    "DMG": 5,
    "HP": 4,
    "DEF": 4,
    "Item ATK": 3,
    "Explore": 2,
    "Heal": 2,
    "Speed": 1,
    "Vision": 1
}

def get_pack_by_name(name: str) -> Dict:
    """Dapatkan data pack berdasarkan nama"""
    return PACK_EFFECTS.get(name, {})

def get_pack_tier_effect(pack_name: str, tier: int) -> Dict:
    """Dapatkan efek pack berdasarkan tier"""
    tier_key = f"T{tier}"
    return PACK_TIER_RANGES.get(pack_name, {}).get(tier_key, {})

def is_pack_main_only(pack_name: str) -> bool:
    """Cek apakah pack hanya bisa di Main slot"""
    return pack_name in MAIN_ONLY_PACKS

def is_pack_sub_capable(pack_name: str) -> bool:
    """Cek apakah pack bisa di Sub slot"""
    return pack_name in SUB_CAPABLE_PACKS

def get_pack_synergy_score(pack1: str, pack2: str) -> tuple:
    """Dapatkan skor sinergi antara dua pack"""
    for p1, p2, score, desc in PACK_SYNERGIES:
        if (p1 == pack1 and p2 == pack2) or (p1 == pack2 and p2 == pack1):
            return score, desc
    return 0, None
