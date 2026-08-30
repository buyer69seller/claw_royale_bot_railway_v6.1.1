# src/strategy/engine.py
"""Strategy engine (fallback untuk AI)"""

import logging
from typing import Dict

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
    
    def decide(self, state: GameState) -> Dict:
        self.turn += 1
        
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
        
        # Healing
        for item in state.get_items():
            score = heal_score(item, hp_ratio)
            if score > 0:
                candidates.append({"kind": "pickup", "obj": item, "score": score})
        
        # Combat
        for enemy in state.get_enemies():
            score = combat_score(enemy, hp_ratio)
            if score > 0:
                candidates.append({"kind": "attack", "obj": enemy, "score": score})
        
        # Loot
        for item in state.get_items():
            score = loot_score(item)
            if score > 0:
                candidates.append({"kind": "pickup", "obj": item, "score": score})
        
        # Interact
        for obj in state.get_interactables():
            score = interact_score(obj)
            if score > 0:
                candidates.append({"kind": "interact", "obj": obj, "score": score})
        
        # Explore
        for obj in state.get_interactables():
            score = explore_score(obj, state.get_region())
            if score > 0:
                candidates.append({"kind": "explore", "obj": obj, "score": score})
        
        # Move
        for conn in state.get_connections():
            score = move_score(conn, state.in_cave)
            if score > 0:
                candidates.append({"kind": "move", "obj": conn, "score": score})
        
        if not candidates:
            return {"kind": "wait", "score": 0}
        
        # HP priority
        if state.is_low_hp(0.25):
            heals = [c for c in candidates if c["kind"] == "pickup"]
            if heals:
                return max(heals, key=lambda x: x["score"])
        
        if state.is_very_low_hp(0.15):
            heals = [c for c in candidates if c["kind"] == "pickup"]
            if heals:
                return max(heals, key=lambda x: x["score"])
        
        # Best option
        best = max(candidates, key=lambda x: x["score"])
        
        # Prevent loop
        if self._last_action == best["kind"]:
            self._consecutive_rejections += 1
            if self._consecutive_rejections > 5:
                candidates = [c for c in candidates if c["kind"] != best["kind"]]
                if candidates:
                    best = max(candidates, key=lambda x: x["score"])
                else:
                    return {"kind": "wait", "score": 0}
        else:
            self._consecutive_rejections = 0
            self._last_action = best["kind"]
        
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