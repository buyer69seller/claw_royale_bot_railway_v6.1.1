# src/ai/hybrid_engine.py
"""Hybrid AI Engine - Gabungan AI Auto-Pilot + Competitive v7 dengan Item Tracking"""

import logging
import math
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from .perception import PerceivedState, PerceptionEngine
from .analyzer import GameAnalyzer
from .decision import DecisionEngine, AIDecision
from .risk import RiskAssessor
from .knowledge import KnowledgeBase
from ..game.state import GameState
from ..core.constants import ACTION_INTERVAL_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class ThreatAssessment:
    """Hasil threat assessment"""
    kill_probability: float
    damage_received: float
    survival_chance: float
    escape_chance: float
    zone_threat: float
    risk_score: float
    is_safe: bool
    should_fight: bool
    should_flee: bool


@dataclass
class PriorityDecision:
    """Keputusan berdasarkan priority"""
    priority: int  # 1=survival, 2=loot, 3=kill, 4=explore
    action_type: str
    target_id: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.0


class HybridAIEngine:
    """
    Hybrid AI Engine - Menggabungkan:
    1. AI Auto-Pilot (ML/Neural)
    2. Competitive v7 (Heuristic/Priority)
    3. Item Tracking & Validation
    """
    
    def __init__(self):
        self.ai = DecisionEngine()
        self.perception = PerceptionEngine()
        self.analyzer = GameAnalyzer()
        self.risk = RiskAssessor()
        self.knowledge = KnowledgeBase()
        self.turn = 0
        self.kills = 0
        self.survival_time = 0
        
        # Stats tracking
        self.stats = {
            "decisions_made": 0,
            "ai_decisions": 0,
            "heuristic_decisions": 0,
            "survival_priority": 0,
            "kill_priority": 0,
            "loot_priority": 0,
            "explore_priority": 0
        }
    
    async def decide(self, state: GameState) -> AIDecision:
        """
        Hybrid decision making:
        1. AI Analysis (ML-based)
        2. Threat Assessment (v7)
        3. Priority-based selection (v7) dengan Item Tracking
        4. Final decision (AI + Heuristic)
        """
        self.turn += 1
        
        # Step 1: AI Perception
        perceived = self.perception.perceive(state)
        
        # Step 2: Threat Assessment (v7)
        threat = await self._assess_threat(perceived, state)
        
        # Step 3: Priority Decision (v7) dengan Item Tracking
        priority_decision = await self._priority_decision(perceived, state, threat)
        
        # Step 4: AI Decision (ML)
        ai_decision = await self.ai._make_decision(
            perceived, 
            self.ai.analyzer.analyze(perceived),
            self.risk.assess_current_situation(perceived)
        )
        
        # Step 5: Hybrid Selection
        final_decision = await self._hybrid_selection(
            priority_decision, 
            ai_decision, 
            perceived, 
            threat
        )
        
        # Update stats
        self.stats["decisions_made"] += 1
        if final_decision.confidence > 0.6:
            self.stats["ai_decisions"] += 1
        else:
            self.stats["heuristic_decisions"] += 1
        
        # Log item stats periodically
        if self.turn % 10 == 0:
            try:
                item_stats = state.get_item_stats()
                logger.debug(f"📊 Item Stats: {item_stats}")
            except Exception as e:
                logger.debug(f"Item stats error: {e}")
        
        logger.info(
            f"🧠 Hybrid AI: {final_decision.action_type} "
            f"(Priority: {priority_decision.priority}, "
            f"Conf: {final_decision.confidence:.2f}, "
            f"Risk: {threat['risk_score']:.2f})"
        )
        
        return final_decision
    
    async def _assess_threat(self, perceived: PerceivedState, state: GameState) -> Dict[str, Any]:
        """v7 Threat Assessment"""
        threat = {
            "kill_probability": 0.0,
            "damage_received": 0.0,
            "survival_chance": 1.0,
            "escape_chance": 1.0,
            "zone_threat": 0.0,
            "risk_score": 0.0,
            "is_safe": True,
            "should_fight": False,
            "should_flee": False
        }
        
        try:
            # Get self stats
            me = state.get_self()
            if not isinstance(me, dict):
                return threat
            
            my_hp = float(me.get("hp", 0))
            my_max_hp = float(me.get("maxHp", 1))
            my_atk = float(me.get("attack", me.get("atk", 0)))
            my_def = float(me.get("defense", me.get("def", 0)))
            hp_ratio = my_hp / max(my_max_hp, 1)
            
            # Enemy assessment
            enemies = state.get_enemies()
            if enemies:
                # Filter enemies yang valid
                valid_enemies = [e for e in enemies if isinstance(e, dict)]
                if valid_enemies:
                    # Find closest enemy
                    closest = min(valid_enemies, key=lambda e: self._distance(me, e))
                    target_hp = float(closest.get("hp", 0))
                    target_max_hp = float(closest.get("maxHp", 1))
                    target_atk = float(closest.get("attack", closest.get("atk", 0)))
                    target_def = float(closest.get("defense", closest.get("def", 0)))
                    
                    # Kill probability
                    threat["kill_probability"] = max(0, min(1, (my_atk - target_def) / max(target_hp, 1)))
                    
                    # Damage received
                    turns_to_kill = target_hp / max(my_atk - target_def, 1)
                    threat["damage_received"] = (target_atk - my_def) * turns_to_kill
                    
                    # Survival chance
                    threat["survival_chance"] = max(0, min(1, 1 - (threat["damage_received"] / max(my_hp, 1))))
                    
                    # Escape chance
                    enemy_density = len(valid_enemies)
                    threat["escape_chance"] = max(0, min(1, 1 - (enemy_density / 10)))
                    
                    # Should fight?
                    threat["should_fight"] = (
                        hp_ratio > 0.5 and 
                        threat["kill_probability"] > 0.6 and
                        threat["survival_chance"] > 0.7
                    )
                    
                    # Should flee?
                    threat["should_flee"] = (
                        hp_ratio < 0.3 or
                        threat["survival_chance"] < 0.5 or
                        threat["kill_probability"] < 0.3
                    )
            
            # Zone threat (death zone)
            region = state.get_region()
            if isinstance(region, dict) and region.get("insideDeathZone", False):
                threat["zone_threat"] = 0.8
            else:
                threat["zone_threat"] = 0.0
            
            # Overall risk
            threat["risk_score"] = (
                (1 - hp_ratio) * 0.4 +
                (1 - threat["survival_chance"]) * 0.3 +
                threat["zone_threat"] * 0.2 +
                (1 - threat["escape_chance"]) * 0.1
            )
            
            threat["is_safe"] = threat["risk_score"] < 0.4
            
        except Exception as e:
            logger.debug(f"Threat assessment error: {e}")
        
        return threat
    
    async def _priority_decision(self, perceived: PerceivedState, state: GameState, threat: Dict) -> PriorityDecision:
        """
        v7 Priority-based decision dengan Item Tracking
        """
        
        try:
            # Get self
            me = state.get_self()
            if not isinstance(me, dict):
                return PriorityDecision(priority=5, action_type="wait", reasoning="No self data", confidence=0.1)
            
            my_hp = float(me.get("hp", 0))
            my_max_hp = float(me.get("maxHp", 1))
            hp_ratio = my_hp / max(my_max_hp, 1)
            alert = state.get_region().get("alertGauge", 0)
            my_atk = float(me.get("attack", me.get("atk", 0)))
            
            # === PRIORITY 1: SURVIVAL ===
            # src/ai/hybrid_engine.py - di _priority_decision
        # src/ai/hybrid_engine.py - di _priority_decision, bagian PRIORITY 1: SURVIVAL

        # === PRIORITY 1: SURVIVAL ===
        
        # ===== USE ITEM DARI INVENTORY (BARU) =====
        # HP < 50% dan ada item healing di inventory → USE
        if hp_ratio < 0.5 and state.has_healing_items():
            best_heal = state.get_best_healing_item()
            if best_heal:
                heal_amount = float(best_heal.get("heal", best_heal.get("healAmount", 0)))
                if heal_amount > 0:
                    self.stats["survival_priority"] += 1
                    item_id = best_heal.get("instanceId") or best_heal.get("id")
                    if item_id:
                        logger.info(f"💚 Using healing item: {heal_amount} HP (HP: {hp_ratio:.0%})")
                        state.remove_from_inventory(item_id)
                        return PriorityDecision(
                            priority=1,
                            action_type="use",
                            target_id=item_id,
                            reasoning=f"Using healing item ({heal_amount} HP)",
                            confidence=0.98
                        )
        
        # HP < 40% → CARI HEALING ITEM DI GROUND
        if hp_ratio < 0.4:
            healing_items = state.get_healing_items()
            for item in healing_items:
                heal = float(item.get("heal", item.get("healAmount", 0)))
                if heal > 0:
                    distance = state._calculate_distance(state.get_self(), item)
                    if distance < 3:
                        self.stats["survival_priority"] += 1
                        item_id = item.get("instanceId") or item.get("id")
                        state.mark_item_attempted(item_id)
                        return PriorityDecision(
                            priority=1,
                            action_type="pickup",
                            target_id=item_id,
                            reasoning=f"Pickup healing ({heal} HP) - HP: {hp_ratio:.0%}",
                            confidence=0.95
                        )
        # === PRIORITY 1: SURVIVAL ===
        
        # HP < 40% → CARI HEALING ITEM DAN USE
        if hp_ratio < 0.4:
            # Cari healing item di inventory terlebih dahulu
            # Note: inventory tidak ada di agent_view, perlu REST API
            # Untuk sekarang, cari item healing di ground
            
            healing_items = state.get_healing_items()
            for item in healing_items:
                heal = float(item.get("heal", item.get("healAmount", 0)))
                if heal > 0:
                    distance = state._calculate_distance(state.get_self(), item)
                    if distance < 3:
                        self.stats["survival_priority"] += 1
                        item_id = item.get("instanceId") or item.get("id")
                        state.mark_item_attempted(item_id)
                        
                        # Jika item healing, ambil dulu
                        return PriorityDecision(
                            priority=1,
                            action_type="pickup",
                            target_id=item_id,
                            reasoning=f"Pickup healing ({heal} HP) - HP: {hp_ratio:.0%}",
                            confidence=0.95
                        )
            
            # HP < 40% → CARI HEALING ITEM
            if hp_ratio < 0.4:
                try:
                    healing_items = state.get_healing_items()
                    for item in healing_items:
                        if not isinstance(item, dict):
                            continue
                        heal = float(item.get("heal", item.get("healAmount", 0)))
                        if heal > 0:
                            distance = state._calculate_distance(state.get_self(), item)
                            if distance < 3:
                                self.stats["survival_priority"] += 1
                                item_id = item.get("instanceId") or item.get("id")
                                if item_id:
                                    state.mark_item_attempted(item_id)
                                    return PriorityDecision(
                                        priority=1,
                                        action_type="pickup",
                                        target_id=item_id,
                                        reasoning=f"Need healing ({heal} HP) - HP: {hp_ratio:.0%}",
                                        confidence=0.95
                                    )
                except Exception as e:
                    logger.debug(f"Healing items error: {e}")
            
            # HP < 25% → URGENT HEAL
            if hp_ratio < 0.25:
                try:
                    for item in state.get_nearby_items(max_distance=5.0):
                        if not isinstance(item, dict):
                            continue
                        heal = float(item.get("heal", item.get("healAmount", 0)))
                        if heal > 0:
                            self.stats["survival_priority"] += 1
                            item_id = item.get("instanceId") or item.get("id")
                            if item_id:
                                state.mark_item_attempted(item_id)
                                return PriorityDecision(
                                    priority=1,
                                    action_type="pickup",
                                    target_id=item_id,
                                    reasoning=f"URGENT: Need healing! HP: {hp_ratio:.0%}",
                                    confidence=0.98
                                )
                except Exception as e:
                    logger.debug(f"Urgent heal error: {e}")
            
            # HP < 20% → RETREAT
            if hp_ratio < 0.2:
                self.stats["survival_priority"] += 1
                try:
                    for conn in state.get_connections():
                        if isinstance(conn, dict) and not conn.get("insideDeathZone", False):
                            return PriorityDecision(
                                priority=1,
                                action_type="move",
                                target_id=conn.get("regionId"),
                                reasoning=f"Critical HP ({hp_ratio:.0%}) - retreating",
                                confidence=0.9
                            )
                except Exception as e:
                    logger.debug(f"Retreat error: {e}")
            
            # In Cave → EXIT
            if state.in_cave:
                try:
                    for obj in state.get_interactables():
                        if isinstance(obj, dict) and obj.get("isExit", False) and "cave" in str(obj.get("type", "")):
                            self.stats["survival_priority"] += 1
                            return PriorityDecision(
                                priority=1,
                                action_type="interact",
                                target_id=obj.get("interactableId") or obj.get("id"),
                                reasoning="Exiting cave",
                                confidence=0.95
                            )
                except Exception as e:
                    logger.debug(f"Cave exit error: {e}")
            
            # In Death Zone → MOVE TO CENTER
            try:
                region = state.get_region()
                if isinstance(region, dict) and region.get("insideDeathZone", False):
                    self.stats["survival_priority"] += 1
                    for conn in state.get_connections():
                        if isinstance(conn, dict) and not conn.get("insideDeathZone", False):
                            return PriorityDecision(
                                priority=1,
                                action_type="move",
                                target_id=conn.get("regionId"),
                                reasoning="Escaping death zone",
                                confidence=0.9
                            )
            except Exception as e:
                logger.debug(f"Death zone error: {e}")
            
            # Alert > 7 → HIDE / RETREAT
            if alert > 7:
                self.stats["survival_priority"] += 1
                try:
                    for conn in state.get_connections():
                        if isinstance(conn, dict) and conn.get("safetyScore", 0) > 0.5:
                            return PriorityDecision(
                                priority=1,
                                action_type="move",
                                target_id=conn.get("regionId"),
                                reasoning=f"High alert ({alert}) - moving to safety",
                                confidence=0.85
                            )
                except Exception as e:
                    logger.debug(f"Alert retreat error: {e}")
            
            # === PRIORITY 2: LOOT ===
            
            try:
                loot_items = state.get_loot_items()
                for item in loot_items:
                    if not isinstance(item, dict):
                        continue
                    distance = self._distance(state.get_self(), item)
                    if distance < 3:
                        self.stats["loot_priority"] += 1
                        item_id = item.get("instanceId") or item.get("id")
                        if item_id:
                            state.mark_item_attempted(item_id)
                            return PriorityDecision(
                                priority=2,
                                action_type="pickup",
                                target_id=item_id,
                                reasoning="Collecting loot",
                                confidence=0.8
                            )
            except Exception as e:
                logger.debug(f"Loot items error: {e}")
            
            # === PRIORITY 3: KILL ===
            
            if hp_ratio > 0.5 and threat.get("should_fight", False):
                try:
                    enemies = state.get_enemies()
                    if enemies:
                        targetable = []
                        for e in enemies:
                            if not isinstance(e, dict):
                                continue
                            dist = self._distance(state.get_self(), e)
                            if dist < 10:
                                targetable.append(e)
                        
                        if targetable:
                            targetable.sort(key=lambda e: float(e.get("hp", 0)))
                            target = targetable[0]
                            
                            target_hp = float(target.get("hp", 0))
                            target_def = float(target.get("defense", target.get("def", 0)))
                            kill_prob = (my_atk - target_def) / max(target_hp, 1)
                            
                            if kill_prob > 0.6:
                                self.stats["kill_priority"] += 1
                                return PriorityDecision(
                                    priority=3,
                                    action_type="attack",
                                    target_id=target.get("agentId") or target.get("monsterId") or target.get("id"),
                                    reasoning=f"Kill opportunity (HP: {target_hp:.0f})",
                                    confidence=min(kill_prob, 0.9)
                                )
                except Exception as e:
                    logger.debug(f"Kill decision error: {e}")
            
            # === PRIORITY 4: EXPLORE ===
            
            try:
                for obj in state.get_interactables():
                    if not isinstance(obj, dict):
                        continue
                    distance = self._distance(state.get_self(), obj)
                    if distance < 2 and "ruin" in str(obj.get("type", obj.get("kind", ""))):
                        self.stats["explore_priority"] += 1
                        return PriorityDecision(
                            priority=4,
                            action_type="explore",
                            target_id=obj.get("interactableId") or obj.get("id"),
                            reasoning="Exploring ruin",
                            confidence=0.75
                        )
                
                for obj in state.get_interactables():
                    if not isinstance(obj, dict):
                        continue
                    distance = self._distance(state.get_self(), obj)
                    if distance < 5 and "ruin" in str(obj.get("type", obj.get("kind", ""))):
                        self.stats["explore_priority"] += 1
                        return PriorityDecision(
                            priority=4,
                            action_type="move",
                            target_id=obj.get("regionId"),
                            reasoning="Moving to ruin",
                            confidence=0.6
                        )
            except Exception as e:
                logger.debug(f"Explore error: {e}")
            
            # === FALLBACK: MOVE TOWARDS CENTER ===
            
            try:
                for conn in state.get_connections():
                    if isinstance(conn, dict) and conn.get("safetyScore", 0) > 0.5:
                        return PriorityDecision(
                            priority=4,
                            action_type="move",
                            target_id=conn.get("regionId"),
                            reasoning="Moving to safer area",
                            confidence=0.5
                        )
                
                for conn in state.get_connections():
                    if isinstance(conn, dict) and not conn.get("insideDeathZone", False):
                        return PriorityDecision(
                            priority=4,
                            action_type="move",
                            target_id=conn.get("regionId"),
                            reasoning="Moving randomly",
                            confidence=0.3
                        )
            except Exception as e:
                logger.debug(f"Fallback move error: {e}")
            
        except Exception as e:
            logger.debug(f"Priority decision error: {e}")
        
        # No action
        return PriorityDecision(
            priority=5,
            action_type="wait",
            reasoning="No action available",
            confidence=0.1
        )
    
    async def _hybrid_selection(self, priority: PriorityDecision, ai: AIDecision, perceived: PerceivedState, threat: Dict) -> AIDecision:
        """Memilih antara AI dan Priority decision"""
        
        # Jika priority confidence tinggi, pakai priority
        if priority.confidence > 0.8:
            return AIDecision(
                action_type=priority.action_type,
                target_id=priority.target_id,
                confidence=priority.confidence,
                reasoning=[priority.reasoning, "Priority-based"],
                risk_score=threat.get("risk_score", 0.5),
                expected_value=1 - threat.get("risk_score", 0.5)
            )
        
        # Jika AI confidence tinggi dan priority tidak urgent, pakai AI
        if ai.confidence > 0.7 and priority.priority > 2:
            return ai
        
        # Critical priority (1-2) override AI
        if priority.priority <= 2:
            return AIDecision(
                action_type=priority.action_type,
                target_id=priority.target_id,
                confidence=priority.confidence,
                reasoning=[priority.reasoning, "Emergency priority"],
                risk_score=threat.get("risk_score", 0.5),
                expected_value=1 - threat.get("risk_score", 0.5)
            )
        
        # Default: AI decision
        return ai
    
    def _distance(self, obj1, obj2) -> float:
        """Hitung distance antara dua object"""
        try:
            # Handle berbagai tipe data
            if obj1 is None or obj2 is None:
                return 999.0
            
            # Jika objek adalah string (ID), return large distance
            if isinstance(obj1, str) or isinstance(obj2, str):
                return 999.0
            
            # Jika objek adalah list, ambil elemen pertama jika ada
            if isinstance(obj1, list):
                obj1 = obj1[0] if obj1 else {}
            if isinstance(obj2, list):
                obj2 = obj2[0] if obj2 else {}
            
            # Jika objek adalah tuple atau set, convert ke list
            if isinstance(obj1, (tuple, set)):
                obj1 = list(obj1)[0] if obj1 else {}
            if isinstance(obj2, (tuple, set)):
                obj2 = list(obj2)[0] if obj2 else {}
            
            # Jika bukan dictionary, return large distance
            if not isinstance(obj1, dict) or not isinstance(obj2, dict):
                return 999.0
            
            # Ambil posisi
            x1 = float(obj1.get("x", obj1.get("position", {}).get("x", 0)))
            y1 = float(obj1.get("y", obj1.get("position", {}).get("y", 0)))
            x2 = float(obj2.get("x", obj2.get("position", {}).get("x", 0)))
            y2 = float(obj2.get("y", obj2.get("position", {}).get("y", 0)))
            
            return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
        except Exception as e:
            logger.debug(f"Distance calculation error: {e}")
            return 999.0
    
    def get_stats(self) -> Dict:
        """Dapatkan statistik decision"""
        return self.stats
