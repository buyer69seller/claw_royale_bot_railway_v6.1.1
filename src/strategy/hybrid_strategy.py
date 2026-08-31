# src/strategy/hybrid_strategy.py
"""Hybrid Strategy v7 - 3 Mode Strategy Selector"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

from ..game.state import GameState
from ..game.actions import ActionBuilder
from .evaluators import (
    heal_score, combat_score, loot_score, 
    interact_score, explore_score, move_score,
    alive
)
from ..core.constants import SCORE_CAVE_EXIT

logger = logging.getLogger(__name__)


class StrategyMode(Enum):
    """Mode strategi yang tersedia"""
    AI_AUTO_PILOT = "ai_auto_pilot"
    COMPETITIVE_V7 = "competitive_v7"
    HYBRID_V7 = "hybrid_v7"


class HybridStrategyV7:
    """
    Hybrid Strategy v7 - 3 Mode Strategy Selector
    
    Mode 1: AI Auto-Pilot (ML-Based)
    Mode 2: Competitive v7 (Heuristic Priority)
    Mode 3: Hybrid v7 (AI + Heuristic + Priority)
    """
    
    def __init__(self):
        self.action_builder = ActionBuilder()
        self.turn = 0
        
        # Mode tracking
        self.current_mode = StrategyMode.HYBRID_V7
        self.mode_history = []
        
        # Stats per mode
        self.stats = {
            StrategyMode.AI_AUTO_PILOT: {"used": 0, "success": 0},
            StrategyMode.COMPETITIVE_V7: {"used": 0, "success": 0},
            StrategyMode.HYBRID_V7: {"used": 0, "success": 0}
        }
        
        # Tracking
        self._used_interactables = set()
        self._attack_cooldown = 0
        self._pack_modifiers = {}
        self._consecutive_rejections = 0
        self._last_action = None
        
    def set_pack_modifiers(self, main_pack: Dict, sub_pack: Dict):
        """Set pack modifiers dari loadout"""
        self._pack_modifiers = {}
        
        if main_pack:
            main_name = main_pack.get("name", "")
            from .evaluators import get_pack_strategy_modifier
            modifiers = get_pack_strategy_modifier(main_name, "main")
            self._pack_modifiers.update(modifiers)
        
        if sub_pack:
            sub_name = sub_pack.get("name", "")
            from .evaluators import get_pack_strategy_modifier
            modifiers = get_pack_strategy_modifier(sub_name, "sub")
            for key, value in modifiers.items():
                if isinstance(value, (int, float)):
                    self._pack_modifiers[key] = value * 0.5
                else:
                    self._pack_modifiers[key] = value
        
        logger.debug(f"📦 Pack modifiers: {self._pack_modifiers}")
    
    def decide(self, state: GameState, ai_decision: Optional[Dict] = None) -> Dict:
        """
        Ambil keputusan berdasarkan mode yang dipilih
        
        Args:
            state: GameState
            ai_decision: Hasil dari AI Auto-Pilot (opsional)
        
        Returns:
            Dict dengan keputusan
        """
        self.turn += 1
        
        # ===== STRATEGY SELECTOR =====
        mode = self._select_mode(state)
        self.current_mode = mode
        self.mode_history.append(mode)
        
        # ===== EXECUTE SELECTED MODE =====
        if mode == StrategyMode.AI_AUTO_PILOT:
            decision = self._ai_mode(state, ai_decision)
        elif mode == StrategyMode.COMPETITIVE_V7:
            decision = self._competitive_mode(state)
        else:  # HYBRID_V7
            decision = self._hybrid_mode(state, ai_decision)
        
        # ===== TRACK STATS =====
        self.stats[mode]["used"] += 1
        
        return decision
    
    def _select_mode(self, state: GameState) -> StrategyMode:
        """
        Pilih mode berdasarkan situasi
        
        Kriteria:
        - Survival (HP < 30%) → Competitive v7 (lebih cepat)
        - Banyak enemy → Hybrid v7 (lebih akurat)
        - HP tinggi & aman → AI Auto-Pilot (lebih eksploratif)
        """
        hp_ratio = state.hp_ratio()
        enemy_count = len(state.get_enemies())
        danger = state.alert_gauge
        
        # ===== SURVIVAL PRIORITY =====
        if hp_ratio < 0.25:
            # Prioritaskan survival → Competitive v7 (lebih cepat)
            return StrategyMode.COMPETITIVE_V7
        
        if hp_ratio < 0.40:
            # HP rendah → Hybrid v7
            return StrategyMode.HYBRID_V7
        
        # ===== SITUATIONAL SELECTION =====
        if enemy_count > 3:
            # Banyak musuh → Hybrid v7 (lebih akurat)
            return StrategyMode.HYBRID_V7
        
        if enemy_count == 0 and hp_ratio > 0.7:
            # Aman & HP tinggi → AI Auto-Pilot (eksplorasi)
            return StrategyMode.AI_AUTO_PILOT
        
        if danger > 7:
            # Alert tinggi → Competitive v7 (defensif)
            return StrategyMode.COMPETITIVE_V7
        
        # ===== DEFAULT =====
        return StrategyMode.HYBRID_V7
    
    def _ai_mode(self, state: GameState, ai_decision: Optional[Dict]) -> Dict:
        """
        MODE 1: AI Auto-Pilot (ML-Based)
        Mengandalkan keputusan dari AI/ML
        """
        logger.debug("🧠 Using AI Auto-Pilot Mode")
        
        # Jika ada AI decision, gunakan
        if ai_decision:
            return ai_decision
        
        # Fallback ke heuristic
        return self._competitive_mode(state)
    
    def _competitive_mode(self, state: GameState) -> Dict:
        """
        MODE 2: Competitive v7 (Heuristic Priority)
        Mengandalkan aturan dan prioritas
        """
        logger.debug("⚡ Using Competitive v7 Mode")
        
        # Gunakan priority-based decision
        return self._priority_decision(state)
    
    def _hybrid_mode(self, state: GameState, ai_decision: Optional[Dict]) -> Dict:
        """
        MODE 3: Hybrid v7 (AI + Heuristic + Priority)
        Menggabungkan semua pendekatan
        """
        logger.debug("🔄 Using Hybrid v7 Mode")
        
        # ===== STEP 1: Get AI Decision =====
        ai_dec = ai_decision or self._get_ai_decision(state)
        
        # ===== STEP 2: Get Priority Decision =====
        priority_dec = self._priority_decision(state)
        
        # ===== STEP 3: Hybrid Selection =====
        # Jika priority adalah survival (priority 1-2), gunakan priority
        if priority_dec.get("priority", 5) <= 2:
            logger.debug("🔄 Hybrid: Using Priority (Survival)")
            return priority_dec
        
        # Jika AI confidence tinggi, gunakan AI
        if ai_dec and ai_dec.get("confidence", 0) > 0.7:
            logger.debug("🔄 Hybrid: Using AI (High Confidence)")
            return ai_dec
        
        # Default: Priority
        logger.debug("🔄 Hybrid: Using Priority (Default)")
        return priority_dec
    
    def _get_ai_decision(self, state: GameState) -> Optional[Dict]:
        """
        Dapatkan keputusan dari AI (simulasi)
        Sebenarnya ini akan terhubung ke DecisionEngine
        """
        # Sementara, gunakan heuristic sebagai simulasi AI
        return None
    
    def _priority_decision(self, state: GameState) -> Dict:
        """
        Priority-based decision (Competitive v7)
        """
        # Decrease attack cooldown
        if self._attack_cooldown > 0:
            self._attack_cooldown -= 1
        
        if not state.is_alive:
            return {"kind": "dead", "score": -1e9, "priority": 5}
        
        # Cave exit priority
        if state.in_cave:
            cave_exit = state.get_cave_exit()
            if cave_exit:
                return {"kind": "interact", "obj": cave_exit, "score": SCORE_CAVE_EXIT, "priority": 1}
            return {"kind": "wait", "score": 0, "priority": 5}
        
        candidates = []
        hp_ratio = state.hp_ratio()
        
        # ===== PRIORITY 1: SURVIVAL =====
        if hp_ratio < 0.4:
            for item in state.get_items():
                if not isinstance(item, dict):
                    continue
                item_id = item.get("instanceId") or item.get("id")
                if not state.is_item_valid(item_id):
                    continue
                heal = float(item.get("heal", item.get("healAmount", 0)))
                if heal > 0:
                    score = heal_score(item, hp_ratio)
                    me = state.get_self()
                    distance = state._calculate_distance(me, item)
                    if distance < 3:
                        score += 100
                    candidates.append({"kind": "pickup", "obj": item, "score": score, "priority": 1})
        
        # ===== PRIORITY 2: RETREAT =====
        if hp_ratio < 0.2:
            for conn in state.get_connections():
                if isinstance(conn, str):
                    conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
                elif not isinstance(conn, dict):
                    continue
                if not conn.get("insideDeathZone", False):
                    candidates.append({"kind": "move", "obj": conn, "score": 500, "priority": 2})
        
        # ===== PRIORITY 3: COMBAT =====
        if hp_ratio > 0.4 and self._attack_cooldown == 0:
            for enemy in state.get_enemies():
                if not isinstance(enemy, dict):
                    continue
                enemy_hp = float(enemy.get("hp", 0))
                enemy_max_hp = float(enemy.get("maxHp", 1))
                enemy_ratio = enemy_hp / max(enemy_max_hp, 1)
                is_guardian = enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian"
                if is_guardian and hp_ratio < 0.6:
                    continue
                if enemy_ratio < 0.5 or (hp_ratio > 0.7 and enemy_ratio < 0.7):
                    score = combat_score(enemy, hp_ratio)
                    if score > 0:
                        candidates.append({"kind": "attack", "obj": enemy, "score": score, "priority": 3})
        
        # ===== PRIORITY 4: LOOT =====
        for item in state.get_items():
            if not isinstance(item, dict):
                continue
            item_id = item.get("instanceId") or item.get("id")
            if not state.is_item_valid(item_id):
                continue
            score = loot_score(item)
            if score > 0:
                me = state.get_self()
                distance = state._calculate_distance(me, item)
                if distance < 3:
                    score += 50
                candidates.append({"kind": "pickup", "obj": item, "score": score, "priority": 4})
        
        # ===== PRIORITY 5: INTERACT =====
        for obj in state.get_interactables():
            if not isinstance(obj, dict):
                continue
            obj_id = obj.get("id") or obj.get("interactableId")
            if obj_id in self._used_interactables:
                continue
            score = interact_score(obj)
            if score > 0:
                candidates.append({"kind": "interact", "obj": obj, "score": score, "priority": 5})
        
        # ===== PRIORITY 6: EXPLORE =====
        if hp_ratio > 0.6:
            for obj in state.get_interactables():
                if not isinstance(obj, dict):
                    continue
                obj_id = obj.get("id") or obj.get("interactableId")
                if obj_id in self._used_interactables:
                    continue
                score = explore_score(obj, state.get_region())
                if score > 0:
                    candidates.append({"kind": "explore", "obj": obj, "score": score, "priority": 6})
        
        # ===== PRIORITY 7: MOVE =====
        for conn in state.get_connections():
            if isinstance(conn, str):
                conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
            elif not isinstance(conn, dict):
                continue
            score = move_score(conn, state.in_cave)
            if score > 0:
                candidates.append({"kind": "move", "obj": conn, "score": score, "priority": 7})
        
        # ===== PRIORITY 8: WAIT =====
        if not candidates:
            return {"kind": "wait", "score": 0, "priority": 8}
        
        # ===== SELECT BEST =====
        best = max(candidates, key=lambda x: (x["priority"], x["score"]))
        
        # ===== TRACKING =====
        if best["kind"] == "attack":
            self._attack_cooldown = 2
        
        if best["kind"] in ("interact", "explore"):
            obj_id = best["obj"].get("id") or best["obj"].get("interactableId")
            if obj_id:
                self._used_interactables.add(obj_id)
        
        if best["kind"] == "pickup":
            item_id = best["obj"].get("instanceId") or best["obj"].get("id")
            if item_id:
                state.mark_item_attempted(item_id)
        
        return best
    
    def execute(self, decision: Dict) -> Optional[Dict]:
        """Eksekusi keputusan menjadi action"""
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
            if isinstance(obj, str):
                return self.action_builder.move({"regionId": obj})
            return self.action_builder.move(obj)
        
        return None
    
    def reset(self):
        """Reset semua tracking"""
        self._used_interactables.clear()
        self._attack_cooldown = 0
        self._consecutive_rejections = 0
        self._last_action = None
        self.turn = 0
        self.mode_history = []
    
    def get_stats(self) -> Dict:
        """Dapatkan statistik mode"""
        total = sum(s["used"] for s in self.stats.values())
        
        return {
            "mode_stats": {
                mode.value: {
                    "used": data["used"],
                    "percentage": (data["used"] / total * 100) if total > 0 else 0
                }
                for mode, data in self.stats.items()
            },
            "current_mode": self.current_mode.value,
            "mode_history": self.mode_history[-10:]  # Last 10
        }