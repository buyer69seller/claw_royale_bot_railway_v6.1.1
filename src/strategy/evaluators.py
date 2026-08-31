# src/strategy/evaluators.py
"""Evaluator untuk menghitung skor berbagai jenis objek + Pack Effect Awareness"""

from typing import Dict, List, Any
from ..core.constants import (
    SCORE_HEAL_BASE, SCORE_HEAL_HP_BONUS,
    SCORE_ATTACK_BASE, SCORE_ATTACK_HP_BONUS,
    SCORE_GUARDIAN_PENALTY, SCORE_ATTACK_KILL_BONUS,
    SCORE_SURVIVAL_BONUS,
    SCORE_LOOT_BASE, SCORE_LOOT_BONUS,
    SCORE_INTERACT_BASE,
    SCORE_EXPLORE_BASE,
    SCORE_MOVE_BASE,
    SCORE_CAVE_EXIT,
    PACK_EFFECTS
)

def num(value, default=0):
    """Convert ke float dengan safe default"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def hp(obj: Dict) -> float:
    """Ambil HP dari objek"""
    return num(obj.get("hp", obj.get("currentHp", obj.get("health", 0))))

def max_hp(obj: Dict) -> float:
    """Ambil max HP dari objek"""
    return max(1, num(obj.get("maxHp", obj.get("maxHealth", obj.get("hp", 1)))))

def alive(obj: Dict) -> bool:
    """Cek apakah objek masih hidup - FIXED: default False"""
    return obj.get("isAlive", False) is True and hp(obj) > 0

def heal_score(item: Dict, hp_ratio: float) -> float:
    """Skor untuk item healing"""
    heal_amount = num(item.get("heal", item.get("healAmount", 0)))
    if heal_amount > 0:
        return SCORE_HEAL_BASE + (1 - hp_ratio) * SCORE_HEAL_HP_BONUS
    return 0

def combat_score(enemy: Dict, hp_ratio: float) -> float:
    """Skor untuk menyerang musuh - DISESUAIKAN dengan survival-first"""
    if not alive(enemy):
        return 0
    
    ratio = hp(enemy) / max_hp(enemy)
    
    # Base score untuk attack
    score = SCORE_ATTACK_BASE + (1 - ratio) * SCORE_ATTACK_HP_BONUS
    
    # Survival bonus: jangan ambil risiko jika HP rendah
    if hp_ratio < 0.3:
        score -= (0.3 - hp_ratio) * 500  # Penalti besar jika HP rendah
    
    # Penalti untuk guardian
    if enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian":
        score -= SCORE_GUARDIAN_PENALTY
    
    # Bonus kill hanya jika aman (HP tinggi)
    if hp_ratio > 0.5:
        if hp(enemy) <= num(enemy.get("attack", enemy.get("atk", 0))):
            score += SCORE_ATTACK_KILL_BONUS
    
    # Survival time bonus: bertahan lebih penting dari kills
    score += SCORE_SURVIVAL_BONUS * hp_ratio
    
    return score

def loot_score(item: Dict) -> float:
    """Skor untuk mengambil item/loot"""
    item_type = str(item.get("type", item.get("itemType", ""))).lower()
    value = num(item.get("value", item.get("rarityValue", 0)))
    
    score = SCORE_LOOT_BASE + value
    if any(k in item_type for k in ("weapon", "armor", "relic", "ep", "attack", "def")):
        score += SCORE_LOOT_BONUS
    
    return score

def interact_score(obj: Dict) -> float:
    """Skor untuk berinteraksi dengan objek"""
    obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
    
    if any(k in obj_type for k in ("medical", "supply", "cache", "watchtower")):
        return SCORE_INTERACT_BASE
    
    # Cave exit - high priority
    if obj.get("isExit", False) and "cave" in obj_type:
        return SCORE_CAVE_EXIT
    
    return 0

def explore_score(obj: Dict, region: Dict) -> float:
    """Skor untuk explore ruin"""
    obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
    
    if "ruin" in obj_type:
        alert = num(region.get("alertGauge", 0))
        # Semakin tinggi alert, semakin berbahaya explore
        return SCORE_EXPLORE_BASE - max(0, alert - 6) * 80
    return 0

def move_score(connection: Dict, in_cave: bool = False) -> float:
    """Skor untuk move ke region lain"""
    # JANGAN move jika di dalam cave (akan ditolak server)
    if in_cave:
        return -1000
    
    score = SCORE_MOVE_BASE
    if isinstance(connection, dict):
        score += num(connection.get("safetyScore", connection.get("zoneSafety", 0))) * 100
        if connection.get("insideDeathZone") is True:
            score -= 1000
    return score

def cave_exit_score(obj: Dict) -> float:
    """Skor khusus untuk keluar dari cave"""
    if obj.get("isExit", False) and "cave" in str(obj.get("type", obj.get("kind", ""))).lower():
        return SCORE_CAVE_EXIT
    return 0

# ================================================================
# PACK EFFECT AWARENESS - BARU DITAMBAHKAN
# ================================================================

def get_pack_strategy_modifier(pack_name: str, slot: str = "main") -> Dict[str, Any]:
    """
    Dapatkan modifier strategi berdasarkan pack yang digunakan
    
    Args:
        pack_name: Nama pack (misal: "Thorns", "Berserker")
        slot: "main" atau "sub"
    
    Returns:
        Dict dengan modifier untuk strategi
    """
    effects = PACK_EFFECTS.get(pack_name, {})
    
    if slot == "main":
        effect = effects.get("main", {})
    else:
        effect = effects.get("sub", {})
    
    if not effect:
        return {}
    
    modifiers = {}
    
    # ===== THORNS =====
    if "dmg_reduction" in effect:
        modifiers["defensive"] = True
        modifiers["survival_priority"] = 2.0
        modifiers["reflect_damage"] = effect.get("reflect", 0)
        modifiers["dmg_reduction"] = effect.get("dmg_reduction", 0)
    
    # ===== BERSERKER =====
    if "berserker_dmg" in effect:
        modifiers["aggressive_low_hp"] = True
        modifiers["berserker_dmg_multiplier"] = effect.get("berserker_dmg", 1.0)
        modifiers["berserker_threshold"] = 0.5  # HP < 50%
    
    # ===== HEART OF THE GIANT =====
    if "heal_bonus" in effect:
        modifiers["heal_priority"] = 2.0
        modifiers["heal_bonus"] = effect.get("heal_bonus", 0)
        modifiers["self_heal"] = effect.get("self_heal", 0)
    
    # ===== RANGED =====
    if "range_bonus" in effect:
        modifiers["keep_distance"] = True
        modifiers["range_bonus"] = effect.get("range_bonus", 0)
        modifiers["ranged_dmg"] = effect.get("ranged_dmg", 0)
    
    # ===== SCOUT =====
    if "vision" in effect:
        modifiers["scout_vision"] = effect.get("vision", 0)
        modifiers["move_ep_discount"] = effect.get("move_ep_discount", 0)
    
    # ===== ASSASSIN =====
    if "stealth" in effect:
        modifiers["avoid_detection"] = True
        modifiers["stealth"] = effect.get("stealth", 0)
        modifiers["bonus_dmg"] = effect.get("bonus_dmg", 0)
    
    # ===== DOUBLE ATTACK =====
    if "hit_count" in effect:
        modifiers["double_attack"] = True
        modifiers["hit_multiplier"] = effect.get("hit_multiplier", 0.65)
    
    # ===== GOLIATH =====
    if "aoe_multiplier" in effect:
        modifiers["aoe"] = True
        modifiers["aoe_multiplier"] = effect.get("aoe_multiplier", 0.85)
    
    # ===== LAST STAND =====
    if "survive_lethal" in effect:
        modifiers["last_stand"] = True
        modifiers["berserk_turns"] = effect.get("berserk_turns", 3)
    
    # ===== IRON HEART =====
    if "hp_gain" in effect:
        modifiers["iron_heart"] = True
        modifiers["hp_gain_per_attack"] = effect.get("hp_gain", 5)
        modifiers["def_gain_per_attack"] = effect.get("def_gain", 1)
    
    # ===== ITEM EXPERT =====
    if "item_atk_coef" in effect:
        modifiers["item_expert"] = True
        modifiers["item_atk_coef"] = effect.get("item_atk_coef", 1.0)
    
    # ===== DUELIST =====
    if "solo_atk" in effect:
        modifiers["duelist"] = True
        modifiers["solo_atk_bonus"] = effect.get("solo_atk", 0.9)
        modifiers["solo_def_bonus"] = effect.get("solo_def", 0.9)
    
    # ===== SUNFLAME CLOAK =====
    if "aura_dmg" in effect:
        modifiers["sunflame"] = True
        modifiers["aura_dmg"] = effect.get("aura_dmg", 1.0)
    
    # ===== PICKPOCKET =====
    if "steal_amount" in effect:
        modifiers["pickpocket"] = True
        modifiers["steal_amount"] = effect.get("steal_amount", 3)
    
    return modifiers


def apply_pack_modifiers(decision: Dict, modifiers: Dict, state=None) -> Dict:
    """
    Terapkan modifier pack pada keputusan
    
    Args:
        decision: Keputusan yang akan dimodifikasi
        modifiers: Modifier dari pack
        state: GameState untuk konteks tambahan
    
    Returns:
        Dict keputusan yang sudah dimodifikasi
    """
    if not modifiers or not decision:
        return decision
    
    modified = dict(decision)
    kind = modified.get("kind", "")
    
    # ===== DEFENSIVE (Thorns) =====
    if modifiers.get("defensive"):
        # Kurangi agresivitas
        if kind in ["attack", "explore"]:
            modified["score"] = modified.get("score", 0) * 0.7
            # Tambahkan defensive reasoning
            if "reasoning" in modified:
                modified["reasoning"] += " (Defensive mode)"
    
    # ===== HEAL PRIORITY (Heart of the Giant) =====
    heal_priority = modifiers.get("heal_priority", 1.0)
    if heal_priority > 1.0:
        if kind == "pickup":
            heal_amount = modified.get("obj", {}).get("heal", 0)
            if heal_amount > 0:
                modified["score"] = modified.get("score", 0) * heal_priority
                if "reasoning" in modified:
                    modified["reasoning"] += " (Heal priority)"
    
    # ===== KEEP DISTANCE (Ranged) =====
    if modifiers.get("keep_distance"):
        if kind == "attack":
            # Hanya attack jika jarak aman
            modified["score"] = modified.get("score", 0) * 0.8
        if kind == "move":
            # Prioritaskan move ke arah yang menjauh dari musuh
            pass
    
    # ===== DOUBLE ATTACK =====
    if modifiers.get("double_attack") and kind == "attack":
        # Tidak ada perubahan, double attack akan diproses di action
        if "reasoning" in modified:
            modified["reasoning"] += " (Double Attack)"
    
    # ===== AOE (Goliath) =====
    if modifiers.get("aoe") and kind == "attack":
        if "reasoning" in modified:
            modified["reasoning"] += " (AoE)"
    
    # ===== BERSERKER =====
    if modifiers.get("aggressive_low_hp"):
        # Strategy engine akan menangani ini di decide()
        pass
    
    # ===== AVOID DETECTION (Assassin) =====
    if modifiers.get("avoid_detection"):
        # Hindari area dengan banyak musuh
        if kind == "move":
            # Prioritaskan area yang lebih aman
            pass
    
    return modified


def get_pack_recommendation(current_hp_ratio: float, has_guardian: bool, enemy_count: int) -> Dict[str, str]:
    """
    Rekomendasi pack berdasarkan situasi
    
    Args:
        current_hp_ratio: Rasio HP saat ini (0-1)
        has_guardian: Apakah ada guardian di sekitar
        enemy_count: Jumlah musuh di sekitar
    
    Returns:
        Dict dengan rekomendasi pack dan alasan
    """
    recommendation = {
        "main": "",
        "sub": "",
        "reason": ""
    }
    
    # HP rendah → prioritaskan survival
    if current_hp_ratio < 0.3:
        recommendation["main"] = "Thorns"
        recommendation["sub"] = "Heart of the Giant"
        recommendation["reason"] = f"HP rendah ({current_hp_ratio:.0%}) - survival priority"
    
    # Guardian di sekitar → Thorns + Ranged
    elif has_guardian:
        recommendation["main"] = "Thorns"
        recommendation["sub"] = "Ranged"
        recommendation["reason"] = "Guardian nearby - defensive + ranged"
    
    # Banyak musuh → Goliath + Double Attack
    elif enemy_count > 3:
        recommendation["main"] = "Goliath"
        recommendation["sub"] = "Double Attack"
        recommendation["reason"] = f"Outnumbered ({enemy_count} enemies) - AoE + multi-hit"
    
    # HP tinggi + sedikit musuh → agresif
    elif current_hp_ratio > 0.7 and enemy_count < 2:
        recommendation["main"] = "Berserker"
        recommendation["sub"] = "Assassin"
        recommendation["reason"] = "HP tinggi + sedikit musuh - aggressive"
    
    # Default: balanced
    else:
        recommendation["main"] = "Iron Heart"
        recommendation["sub"] = "Item Expert"
        recommendation["reason"] = "Balanced - steady growth"
    
    return recommendation


def get_pack_synergy_score(pack1_name: str, pack2_name: str) -> float:
    """
    Hitung skor sinergi antara dua pack
    
    Args:
        pack1_name: Nama pack pertama
        pack2_name: Nama pack kedua
    
    Returns:
        Skor sinergi (0-100)
    """
    synergies = {
        ("Thorns", "Heart of the Giant"): 30,  # Survival
        ("Berserker", "Last Stand"): 25,       # Clutch
        ("Item Expert", "Moltz Expert"): 20,   # Economy
        ("Goliath", "Double Attack"): 15,      # Damage
        ("Ranged", "Sword Master"): 10,        # Ranged/Melee
        ("Assassin", "Pickpocket"): 15,        # Stealth
        ("Ruin Expert", "Scout"): 10,          # Exploration
        ("Iron Heart", "Heart of the Giant"): 20,  # Tank
        ("Berserker", "Thorns"): 15,           # Bruiser
        ("Goliath", "Ranged"): 15,             # AoE + Range
    }
    
    # Cek kedua arah
    for (p1, p2), score in synergies.items():
        if (p1 in pack1_name and p2 in pack2_name) or (p1 in pack2_name and p2 in pack1_name):
            return score
    
    return 0


def get_best_pack_for_situation(hp_ratio: float, has_guardian: bool, enemy_count: int, 
                                 has_cave: bool, alert_level: int) -> Dict[str, Any]:
    """
    Dapatkan rekomendasi pack terbaik untuk situasi
    
    Args:
        hp_ratio: Rasio HP (0-1)
        has_guardian: Apakah ada guardian
        enemy_count: Jumlah musuh
        has_cave: Apakah di dalam cave
        alert_level: Level alert (0-10)
    
    Returns:
        Dict dengan rekomendasi
    """
    
    # Prioritas pack berdasarkan situasi
    recommendations = []
    
    # Survival (HP rendah atau guardian)
    if hp_ratio < 0.4 or has_guardian:
        recommendations.append({
            "main": "Thorns",
            "sub": "Heart of the Giant",
            "score": 95 - (hp_ratio * 50),
            "reason": "Survival priority"
        })
    
    # Clutch (HP sangat rendah)
    if hp_ratio < 0.25:
        recommendations.append({
            "main": "Last Stand",
            "sub": "Berserker",
            "score": 90,
            "reason": "Clutch mode - survive lethal"
        })
    
    # Explore (di cave atau alert rendah)
    if has_cave or alert_level < 3:
        recommendations.append({
            "main": "Ruin Expert",
            "sub": "Scout",
            "score": 70,
            "reason": "Exploration focus"
        })
    
    # Combat (banyak musuh)
    if enemy_count > 2:
        recommendations.append({
            "main": "Goliath",
            "sub": "Double Attack",
            "score": 80,
            "reason": "AoE + multi-hit"
        })
    
    # Balanced (default)
    if hp_ratio > 0.5 and enemy_count <= 2 and not has_guardian:
        recommendations.append({
            "main": "Iron Heart",
            "sub": "Item Expert",
            "score": 60,
            "reason": "Balanced growth"
        })
    
    # Sort by score
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    
    if recommendations:
        return recommendations[0]
    
    # Default
    return {
        "main": "Moltz Expert",
        "sub": "Item Expert",
        "score": 50,
        "reason": "Default - economy"
    }
