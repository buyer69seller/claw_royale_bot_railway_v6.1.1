# src/strategy/engine.py
"""Strategy engine (fallback untuk AI) - dengan visited region tracking"""

import logging
from typing import Dict, List, Any, Optional

from ..game.state import GameState
from ..game.actions import ActionBuilder
from .evaluators import (
    heal_score, combat_score, loot_score, 
    interact_score, explore_score, move_score,
    alive, get_pack_strategy_modifier, apply_pack_modifiers
)
from ..core.constants import SCORE_CAVE_EXIT
from ..core.exceptions import ClawRoyaleError

logger = logging.getLogger(__name__)


class StrategyEngine:
    """Engine untuk mengambil keputusan (fallback) dengan visited region tracking"""
    
    def __init__(self):
        self.turn = 0
        self.action_builder = ActionBuilder()
        self._last_action = None
        self._consecutive_rejections = 0
        self._used_interactables = set()
        self._attack_cooldown = 0
        self._pack_modifiers = {}
    
    def set_pack_modifiers(self, main_pack: Dict, sub_pack: Dict):
        """Set pack modifiers dari loadout"""
        self._pack_modifiers = {}
        
        if main_pack:
            main_name = main_pack.get("name", "")
            modifiers = get_pack_strategy_modifier(main_name, "main")
            self._pack_modifiers.update(modifiers)
        
        if sub_pack:
            sub_name = sub_pack.get("name", "")
            modifiers = get_pack_strategy_modifier(sub_name, "sub")
            for key, value in modifiers.items():
                if isinstance(value, (int, float)):
                    self._pack_modifiers[key] = value * 0.5
                else:
                    self._pack_modifiers[key] = value
        
        if self._pack_modifiers:
            logger.debug(f"📦 Pack modifiers: {self._pack_modifiers}")
    
    def decide_move(self, state: GameState) -> Optional[Dict]:
        """
        Pilih region tujuan dengan mempertimbangkan:
        1. Hindari death zone
        2. Prioritaskan region belum dikunjungi
        3. Hindari region yang sudah terlalu sering dikunjungi
        4. Pilih safety tertinggi
        """
        connections = state.get_connections()
        
        if not connections:
            logger.debug("📭 No connections available")
            return None
        
        # Log semua connections
        logger.info(f"🗺️ Found {len(connections)} connections:")
        for i, conn in enumerate(connections, 1):
            if isinstance(conn, str):
                conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
            elif not isinstance(conn, dict):
                continue
            
            region_id = conn.get("regionId", "unknown")
            safety = conn.get("safetyScore", 0)
            death = "⚠️ DEATH ZONE" if conn.get("insideDeathZone", False) else "✅ Safe"
            visited = "🔁 Visited" if state.is_region_visited(region_id) else "🆕 New"
            count = state.get_region_visit_count(region_id)
            logger.info(f"   {i}. {region_id[:8]} - safety:{safety:.2f} {death} {visited} (x{count})")
        
        # Filter: Hindari death zone
        safe_connections = []
        for conn in connections:
            if isinstance(conn, str):
                conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
            elif not isinstance(conn, dict):
                continue
            
            if not conn.get("insideDeathZone", False):
                safe_connections.append(conn)
        
        if not safe_connections:
            logger.warning("⚠️ All connections are death zones!")
            return None
        
        # ===== PRIORITAS 1: UNVISITED REGION =====
        unvisited = []
        for conn in safe_connections:
            region_id = conn.get("regionId")
            if region_id and not state.is_region_visited(region_id):
                unvisited.append(conn)
        
        if unvisited:
            logger.info(f"🎯 Found {len(unvisited)} unvisited regions")
            # Pilih unvisited dengan safety tertinggi
            best = max(unvisited, key=lambda c: c.get("safetyScore", 0))
            region_id = best.get("regionId", "unknown")
            safety = best.get("safetyScore", 0)
            logger.info(f"✅ Moving to unvisited region: {region_id[:8]} (safety: {safety:.2f})")
            return best
        
        # ===== PRIORITAS 2: LOW VISIT COUNT (< 2) =====
        low_visit = []
        for conn in safe_connections:
            region_id = conn.get("regionId")
            if region_id and state.get_region_visit_count(region_id) < 2:
                low_visit.append(conn)
        
        if low_visit:
            logger.info(f"🎯 Found {len(low_visit)} low-visit regions")
            best = max(low_visit, key=lambda c: c.get("safetyScore", 0))
            region_id = best.get("regionId", "unknown")
            safety = best.get("safetyScore", 0)
            logger.info(f"✅ Moving to low-visit region: {region_id[:8]} (safety: {safety:.2f})")
            return best
        
        # ===== PRIORITAS 3: HIGHEST SAFETY =====
        logger.info("🎯 All regions visited, choosing highest safety")
        best = max(safe_connections, key=lambda c: c.get("safetyScore", 0))
        region_id = best.get("regionId", "unknown")
        safety = best.get("safetyScore", 0)
        visit_count = state.get_region_visit_count(region_id)
        logger.info(f"✅ Moving to safest region: {region_id[:8]} (safety: {safety:.2f}, visited: {visit_count}x)")
        return best
    
    def decide(self, state: GameState) -> Dict:
        """
        Ambil keputusan berdasarkan state game
        Dengan visited region tracking
        """
        self.turn += 1
        
        # Decrease attack cooldown
        if self._attack_cooldown > 0:
            self._attack_cooldown -= 1
        
        # Cek apakah agent mati
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
            try:
                for item in state.get_items():
                    # Validasi item
                    if not isinstance(item, dict):
                        continue
                    
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
            except Exception as e:
                logger.debug(f"Healing items error: {e}")
        
        # === 2. RETREAT (Jika HP sangat rendah) ===
        if hp_ratio < 0.2:
            try:
                for conn in state.get_connections():
                    if isinstance(conn, str):
                        conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
                    elif not isinstance(conn, dict):
                        continue
                    
                    if not conn.get("insideDeathZone", False):
                        candidates.append({"kind": "move", "obj": conn, "score": 500})
            except Exception as e:
                logger.debug(f"Retreat error: {e}")
        
        # === 3. COMBAT (HANYA JIKA HP > 40%) ===
        if hp_ratio > 0.4 and self._attack_cooldown == 0:
            try:
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
                            candidates.append({"kind": "attack", "obj": enemy, "score": score})
            except Exception as e:
                logger.debug(f"Combat error: {e}")
        
        # === 4. LOOT ===
        try:
            for item in state.get_items():
                if not isinstance(item, dict):
                    continue
                
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
        except Exception as e:
            logger.debug(f"Loot error: {e}")
        
        # === 5. INTERACT ===
        try:
            for obj in state.get_interactables():
                if not isinstance(obj, dict):
                    continue
                
                obj_id = obj.get("id") or obj.get("interactableId")
                if obj_id in self._used_interactables:
                    continue
                
                score = interact_score(obj)
                if score > 0:
                    candidates.append({"kind": "interact", "obj": obj, "score": score})
        except Exception as e:
            logger.debug(f"Interact error: {e}")
        
        # === 6. EXPLORE ===
        if hp_ratio > 0.6:
            try:
                for obj in state.get_interactables():
                    if not isinstance(obj, dict):
                        continue
                    
                    obj_id = obj.get("id") or obj.get("interactableId")
                    if obj_id in self._used_interactables:
                        continue
                    
                    score = explore_score(obj, state.get_region())
                    if score > 0:
                        candidates.append({"kind": "explore", "obj": obj, "score": score})
            except Exception as e:
                logger.debug(f"Explore error: {e}")
        
        # === 7. MOVE (FALLBACK) - DENGAN VISITED TRACKING ===
        try:
            best_connection = self.decide_move(state)
            if best_connection:
                score = move_score(best_connection, state.in_cave)
                if score > 0:
                    candidates.append({"kind": "move", "obj": best_connection, "score": score})
        except Exception as e:
            logger.debug(f"Move error: {e}")
        
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
        
        # Track item yang dipilih
        if best["kind"] == "pickup":
            item_id = best["obj"].get("instanceId") or best["obj"].get("id")
            if item_id:
                state.mark_item_attempted(item_id)
        
        # ===== Apply pack modifiers =====
        if self._pack_modifiers:
            best = self._apply_pack_modifiers(best)
        
        # Log keputusan
        logger.info(f"📊 Turn {self.turn}: {best['kind']} (score: {best['score']:.0f})")
        
        return best
    
    def _apply_pack_modifiers(self, decision: Dict) -> Dict:
        """Terapkan pack modifiers pada keputusan"""
        modifiers = self._pack_modifiers
        if not modifiers:
            return decision
        
        modified = dict(decision)
        
        # Defensive: prioritaskan survival
        if modifiers.get("defensive"):
            if modified.get("kind") in ["attack", "explore"]:
                modified["score"] *= 0.7
        
        # Heal priority
        if modifiers.get("heal_priority", 1.0) > 1.0:
            if modified.get("kind") == "pickup":
                heal = modified.get("obj", {}).get("heal", 0)
                if heal > 0:
                    modified["score"] *= modifiers["heal_priority"]
        
        # Keep distance
        if modifiers.get("keep_distance"):
            if modified.get("kind") == "attack":
                modified["score"] *= 0.8
        
        return modified
    
    def execute(self, state: GameState, decision: Dict):
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
        self.turn = 0
