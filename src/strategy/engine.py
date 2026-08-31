# src/strategy/engine.py
"""Strategy engine dengan Pack Effects Integration (Pre-Season 1)"""

import logging
from typing import Dict, List, Optional

from ..game.state import GameState
from ..game.actions import ActionBuilder
from .evaluators import (
    heal_score, combat_score, loot_score, 
    interact_score, explore_score, move_score,
    alive, get_pack_strategy_modifier, apply_pack_modifiers
)
from ..core.constants import SCORE_CAVE_EXIT

logger = logging.getLogger(__name__)

class StrategyEngine:
    """Engine untuk mengambil keputusan dengan Pack Effects"""
    
    def __init__(self):
        self.turn = 0
        self.action_builder = ActionBuilder()
        self._last_action = None
        self._consecutive_rejections = 0
        self._used_interactables = set()
        self._attack_cooldown = 0
        self._pack_modifiers = {}  # Pack effects modifiers
        
        # Pre-Season 1 specific
        self._has_thorns = False
        self._has_berserker = False
        self._has_heart_of_giant = False
        self._has_last_stand = False
        self._has_item_expert = False
    
    def set_pack_modifiers(self, main_pack: Dict, sub_pack: Dict):
        """
        Set pack modifiers dari loadout
        Berdasarkan Pre-Season 1 pack data
        """
        self._pack_modifiers = {}
        
        # Reset flags
        self._has_thorns = False
        self._has_berserker = False
        self._has_heart_of_giant = False
        self._has_last_stand = False
        self._has_item_expert = False
        
        # Process Main Pack
        if main_pack:
            main_name = main_pack.get("name", "")
            modifiers = get_pack_strategy_modifier(main_name, "main")
            self._pack_modifiers.update(modifiers)
            
            # Track specific packs
            if "Thorns" in main_name:
                self._has_thorns = True
            if "Berserker" in main_name:
                self._has_berserker = True
            if "Heart of the Giant" in main_name:
                self._has_heart_of_giant = True
            if "Last Stand" in main_name:
                self._has_last_stand = True
            if "Item Expert" in main_name:
                self._has_item_expert = True
            
            logger.info(f"📦 Main Pack: {main_name}")
        
        # Process Sub Pack (attenuated)
        if sub_pack:
            sub_name = sub_pack.get("name", "")
            modifiers = get_pack_strategy_modifier(sub_name, "sub")
            
            # Sub pack effects attenuated (×0.5)
            for key, value in modifiers.items():
                if isinstance(value, (int, float)):
                    self._pack_modifiers[key] = value * 0.5
                elif isinstance(value, bool):
                    self._pack_modifiers[key] = value
                else:
                    self._pack_modifiers[key] = value
            
            # Track specific packs (attenuated)
            if "Thorns" in sub_name:
                self._has_thorns = True
            if "Berserker" in sub_name:
                self._has_berserker = True
            if "Heart of the Giant" in sub_name:
                self._has_heart_of_giant = True
            if "Last Stand" in sub_name:
                self._has_last_stand = True
            if "Item Expert" in sub_name:
                self._has_item_expert = True
            
            logger.info(f"📦 Sub Pack: {sub_name}")
        
        logger.info(f"📊 Pack modifiers: {self._pack_modifiers}")
        logger.info(f"📊 Pack flags: Thorns={self._has_thorns}, Berserker={self._has_berserker}, Heart={self._has_heart_of_giant}, LastStand={self._has_last_stand}")
    
    def decide(self, state: GameState) -> Dict:
        """
        Ambil keputusan dengan mempertimbangkan pack effects
        Berdasarkan Pre-Season 1
        """
        self.turn += 1
        
        # Decrease attack cooldown
        if self._attack_cooldown > 0:
            self._attack_cooldown -= 1
        
        if not state.is_alive:
            return {"kind": "dead", "score": -1e9}
        
        # PRIORITAS: Keluar dari cave
        if state.in_cave:
            cave_exit = state.get_cave_exit()
            if cave_exit:
                return {"kind": "interact", "obj": cave_exit, "score": SCORE_CAVE_EXIT}
            return {"kind": "wait", "score": 0}
        
        candidates = []
        hp_ratio = state.hp_ratio()
        me = state.get_self()
        my_atk = float(me.get("attack", me.get("atk", 0)))
        
        # ===== ADAPTIVE: Pack Effects Based Strategy =====
        
        # === 1. HEALING (PRIORITAS TERTINGGI) ===
        # Heart of the Giant: bonus healing
        heal_bonus = self._pack_modifiers.get("heal_priority", 1.0)
        
        if hp_ratio < 0.4:
            for item in state.get_items():
                item_id = item.get("instanceId") or item.get("id")
                if not state.is_item_valid(item_id):
                    continue
                
                heal = float(item.get("heal", item.get("healAmount", 0)))
                if heal > 0:
                    score = heal_score(item, hp_ratio)
                    
                    # Heart of the Giant: bonus untuk healing
                    if self._has_heart_of_giant:
                        score *= 1.5  # +50% healing priority
                    
                    # Bonus jika item dalam jangkauan
                    distance = state._calculate_distance(me, item)
                    if distance < 2:
                        score += 200
                    elif distance < 4:
                        score += 100
                    
                    candidates.append({"kind": "pickup", "obj": item, "score": score})
        
        # === 2. RETREAT (Jika HP sangat rendah) ===
        # Berserker: lebih agresif saat HP rendah, jangan retreat
        if hp_ratio < 0.15 and not self._has_berserker:
            for conn in state.get_connections():
                if not conn.get("insideDeathZone", False):
                    candidates.append({"kind": "move", "obj": conn, "score": 600})
        
        # === 3. COMBAT ===
        # Thorns: defensive, hanya attack jika aman
        # Berserker: lebih agresif saat HP rendah
        # Last Stand: clutch saat HP rendah
        
        should_attack = False
        attack_threshold = 0.4  # Default
        
        if self._has_berserker:
            # Berserker: attack lebih agresif, bahkan saat HP rendah
            attack_threshold = 0.3
            if hp_ratio < 0.5 and hp_ratio > 0.2:
                should_attack = True
        
        if self._has_thorns:
            # Thorns: hanya attack jika HP > 50%
            if hp_ratio > 0.5:
                should_attack = True
        else:
            if hp_ratio > attack_threshold and self._attack_cooldown == 0:
                should_attack = True
        
        # Last Stand: clutch saat HP kritis
        if self._has_last_stand and hp_ratio < 0.2:
            should_attack = True
        
        if should_attack:
            enemies = state.get_enemies()
            
            # Sort enemies by priority
            # Prioritaskan yang HP rendah dan dekat
            priority_enemies = sorted(
                [e for e in enemies if alive(e)],
                key=lambda e: (
                    float(e.get("hp", 0)),  # HP rendah dulu
                    state._calculate_distance(me, e)  # Jarak dekat dulu
                )
            )
            
            for enemy in priority_enemies:
                enemy_hp = float(enemy.get("hp", 0))
                enemy_max_hp = float(enemy.get("maxHp", 1))
                enemy_ratio = enemy_hp / max(enemy_max_hp, 1)
                
                is_guardian = enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian"
                
                # Guardian avoidance (kecuali Last Stand)
                if is_guardian and not self._has_last_stand:
                    continue
                
                # Thorns: jangan serang guardian
                if is_guardian and self._has_thorns:
                    continue
                
                # Berserker: bonus damage saat HP rendah
                dmg_bonus = 1.0
                if self._has_berserker and hp_ratio < 0.5:
                    dmg_bonus = self._pack_modifiers.get("berserker_dmg", 1.7)
                
                # Hitung kill probability dengan bonus
                kill_prob = (my_atk * dmg_bonus) / max(enemy_hp, 1)
                
                if kill_prob > 0.4:  # 40% chance to kill
                    score = combat_score(enemy, hp_ratio)
                    
                    # Berserker: bonus attack saat HP rendah
                    if self._has_berserker and hp_ratio < 0.5:
                        score *= 1.5
                    
                    # Thorns: bonus karena reflect damage
                    if self._has_thorns:
                        score *= 1.2
                    
                    candidates.append({"kind": "attack", "obj": enemy, "score": score})
        
        # === 4. LOOT ===
        # Item Expert: prioritaskan Moltz
        for item in state.get_items():
            item_id = item.get("instanceId") or item.get("id")
            if not state.is_item_valid(item_id):
                continue
            
            score = loot_score(item)
            item_type = str(item.get("type", item.get("itemType", ""))).lower()
            
            # Item Expert: Moltz lebih berharga
            if self._has_item_expert and "moltz" in item_type:
                score *= 2.0
            
            if score > 0:
                # Bonus jika item dalam jangkauan
                distance = state._calculate_distance(me, item)
                if distance < 2:
                    score += 100
                elif distance < 4:
                    score += 50
                
                candidates.append({"kind": "pickup", "obj": item, "score": score})
        
        # === 5. INTERACT ===
        for obj in state.get_interactables():
            obj_id = obj.get("id") or obj.get("interactableId")
            if obj_id in self._used_interactables:
                continue
            
            score = interact_score(obj)
            if score > 0:
                candidates.append({"kind": "interact", "obj": obj, "score": score})
        
        # === 6. EXPLORE ===
        if hp_ratio > 0.5:  # Hanya explore jika HP cukup
            for obj in state.get_interactables():
                obj_id = obj.get("id") or obj.get("interactableId")
                if obj_id in self._used_interactables:
                    continue
                
                score = explore_score(obj, state.get_region())
                if score > 0:
                    candidates.append({"kind": "explore", "obj": obj, "score": score})
        
        # === 7. MOVE (FALLBACK) ===
        for conn in state.get_connections():
            score = move_score(conn, state.in_cave)
            if score > 0:
                candidates.append({"kind": "move", "obj": conn, "score": score})
        
        # === 8. WAIT (LAST RESORT) ===
        if not candidates:
            return {"kind": "wait", "score": 0}
        
        # Pilih yang terbaik
        best = max(candidates, key=lambda x: x["score"])
        
        # === APPLY PACK MODIFIERS ===
        best = apply_pack_modifiers(best, self._pack_modifiers)
        
        # Set attack cooldown
        if best["kind"] == "attack":
            self._attack_cooldown = 2
        
        # Track used interactables
        if best["kind"] in ("interact", "explore"):
            obj_id = best["obj"].get("id") or best["obj"].get("interactableId")
            if obj_id:
                self._used_interactables.add(obj_id)
        
        # Track item yang dipilih
        if best["kind"] == "pickup":
            item_id = best["obj"].get("instanceId") or best["obj"].get("id")
            if item_id:
                state.mark_item_attempted(item_id)
        
        # Log decision dengan pack info
        if self._pack_modifiers:
            logger.debug(f"📦 Pack modifier applied to {best['kind']}")
        
        return best
    
    def execute(self, state: GameState, decision: Dict):
        """Eksekusi keputusan"""
        kind = decision.get("kind")
        obj = decision.get("obj", {})
        
        if kind == "dead" or kind == "wait":
            return None
        
        if kind == "pickup":
            return self.action_builder.pickup(obj)
        elif kind == "attack":
            return self.action_builder.attack(obj)
        elif kind == "interact":
            return self.action_builder.interact(obj)
        elif kind == "explore":
            return self.action_builder.explore(obj)
        elif kind == "move":
            return self.action_builder.move(obj)
        
        return None
    
    def reset_rejection_counter(self):
        """Reset counter untuk infinite loop prevention"""
        self._consecutive_rejections = 0
    
    def reset(self):
        """Reset semua tracking"""
        self._used_interactables.clear()
        self._attack_cooldown = 0
        self._consecutive_rejections = 0
        self._last_action = None
        self._pack_modifiers = {}
        
        # Reset flags
        self._has_thorns = False
        self._has_berserker = False
        self._has_heart_of_giant = False
        self._has_last_stand = False
        self._has_item_expert = False
    
    def get_pack_info(self) -> Dict:
        """Dapatkan informasi pack saat ini"""
        return {
            "modifiers": self._pack_modifiers,
            "flags": {
                "thorns": self._has_thorns,
                "berserker": self._has_berserker,
                "heart_of_giant": self._has_heart_of_giant,
                "last_stand": self._has_last_stand,
                "item_expert": self._has_item_expert
            }
        }
