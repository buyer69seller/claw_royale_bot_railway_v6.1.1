# src/strategy/engine.py
"""Strategy engine (fallback untuk AI) - dengan Item Validation"""

import logging
from typing import Dict, List

from ..game.state import GameState
from ..game.actions import ActionBuilder
from .evaluators import (
    heal_score, combat_score, loot_score, 
    interact_score, explore_score, move_score,
    alive
)
from ..core.constants import SCORE_CAVE_EXIT

logger = logging.getLogger(__name__)

class StrategyEngine:
    """Engine untuk mengambil keputusan (fallback)"""
    
    def __init__(self):
        self.turn = 0
        self.action_builder = ActionBuilder()
        self._last_action = None
        self._consecutive_rejections = 0
        self._used_interactables = set()
        self._attack_cooldown = 0
    
    def decide(self, state: GameState) -> Dict:
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
        
        # === 1. HEALING (PRIORITAS TERTINGGI) ===
        if hp_ratio < 0.4:
            for item in state.get_items():
                # TAMBAHKAN: cek validasi item
                item_id = item.get("instanceId") or item.get("id")
                if not state.is_item_valid(item_id):
                    continue
                
                heal = float(item.get("heal", item.get("healAmount", 0)))
                if heal > 0:
                    score = heal_score(item, hp_ratio)
                    # Bonus jika item dalam jangkauan
                    me = state.get_self()
                    distance = state._calculate_distance(me, item)
                    if distance < 3:
                        score += 100
                    candidates.append({"kind": "pickup", "obj": item, "score": score})
        
        # === 2. RETREAT (Jika HP sangat rendah) ===
        if hp_ratio < 0.2:
            for conn in state.get_connections():
                if not conn.get("insideDeathZone", False):
                    candidates.append({"kind": "move", "obj": conn, "score": 500})
        
        # === 3. COMBAT (HANYA JIKA HP > 40%) ===
        if hp_ratio > 0.4 and self._attack_cooldown == 0:
            for enemy in state.get_enemies():
                enemy_hp = float(enemy.get("hp", 0))
                enemy_max_hp = float(enemy.get("maxHp", 1))
                enemy_ratio = enemy_hp / max(enemy_max_hp, 1)
                
                is_guardian = enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian"
                if is_guardian and hp_ratio < 0.6:
                    continue
                
                if enemy_ratio < 0.5 or (hp_ratio > 0.7 and enemy_ratio < 0.7):
                    score = combat_score(enemy, hp_ratio)
                    if score > 0:
                        candidates.append({"kind": "attack", "obj": enemy, "score": score})
        
        # === 4. LOOT ===
        for item in state.get_items():
            # TAMBAHKAN: cek validasi item
            item_id = item.get("instanceId") or item.get("id")
            if not state.is_item_valid(item_id):
                continue
            
            score = loot_score(item)
            if score > 0:
                # Bonus jika item dalam jangkauan
                me = state.get_self()
                distance = state._calculate_distance(me, item)
                if distance < 3:
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
        if hp_ratio > 0.6:
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
        
        # Set attack cooldown
        if best["kind"] == "attack":
            self._attack_cooldown = 2
        
        # Track used interactables
        if best["kind"] in ("interact", "explore"):
            obj_id = best["obj"].get("id") or best["obj"].get("interactableId")
            if obj_id:
                self._used_interactables.add(obj_id)
        
        # TAMBAHKAN: track item yang dipilih
        if best["kind"] == "pickup":
            item_id = best["obj"].get("instanceId") or best["obj"].get("id")
            if item_id:
                state.mark_item_attempted(item_id)
        
        return best
    
    def execute(self, state: GameState, decision: Dict):
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
        self._consecutive_rejections = 0
    
    def reset(self):
        """Reset semua tracking"""
        self._used_interactables.clear()
        self._attack_cooldown = 0
        self._consecutive_rejections = 0
        self._last_action = None
