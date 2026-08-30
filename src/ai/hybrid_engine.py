# src/ai/hybrid_engine.py
"""Hybrid AI Engine - Gabungan AI Auto-Pilot + Competitive v7"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .perception import PerceivedState
from .decision import AIDecision
from .risk import RiskAssessor
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
    """
    
    def __init__(self):
        self.ai = DecisionEngine()
        self.risk = RiskAssessor()
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
        3. Priority-based selection (v7)
        4. Final decision (AI + Heuristic)
        """
        self.turn += 1
        
        # Step 1: AI Perception
        perceived = self.ai.perception.perceive(state)
        
        # Step 2: Threat Assessment (v7)
        threat = await self._assess_threat(perceived, state)
        
        # Step 3: Priority Decision (v7)
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
        
        logger.info(
            f"🧠 Hybrid AI: {final_decision.action_type} "
            f"(Priority: {priority_decision.priority}, "
            f"Conf: {final_decision.confidence:.2f}, "
            f"Threat: {threat.risk_score:.2f})"
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
        
        # Get self stats
        me = state.get_self()
        my_hp = float(me.get("hp", 0))
        my_max_hp = float(me.get("maxHp", 1))
        my_atk = float(me.get("attack", me.get("atk", 0)))
        my_def = float(me.get("defense", me.get("def", 0)))
        hp_ratio = my_hp / max(my_max_hp, 1)
        
        # Enemy assessment
        enemies = state.get_enemies()
        if enemies:
            # Find closest enemy
            closest = min(enemies, key=lambda e: self._distance(me, e))
            target_hp = float(closest.get("hp", 0))
            target_max_hp = float(closest.get("maxHp", 1))
            target_atk = float(closest.get("attack", closest.get("atk", 0)))
            target_def = float(closest.get("defense", closest.get("def", 0)))
            
            # Kill probability
            target_hp_ratio = target_hp / max(target_max_hp, 1)
            threat["kill_probability"] = max(0, min(1, (my_atk - target_def) / max(target_hp, 1)))
            
            # Damage received
            turns_to_kill = target_hp / max(my_atk - target_def, 1)
            threat["damage_received"] = (target_atk - my_def) * turns_to_kill
            
            # Survival chance
            threat["survival_chance"] = max(0, min(1, 1 - (threat["damage_received"] / max(my_hp, 1))))
            
            # Escape chance
            enemy_density = len(enemies)
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
        if region.get("insideDeathZone", False):
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
        
        return threat
    
    async def _priority_decision(self, perceived: PerceivedState, state: GameState, threat: Dict) -> PriorityDecision:
        """v7 Priority-based decision"""
        
        # Get self
        me = state.get_self()
        my_hp = float(me.get("hp", 0))
        my_max_hp = float(me.get("maxHp", 1))
        hp_ratio = my_hp / max(my_max_hp, 1)
        alert = state.get_region().get("alertGauge", 0)
        
        # === PRIORITY 1: SURVIVAL ===
        
        # HP < 30% → HEAL
        if hp_ratio < 0.3:
            # Cari healing item
            for item in state.get_items():
                heal = float(item.get("heal", item.get("healAmount", 0)))
                if heal > 0:
                    self.stats["survival_priority"] += 1
                    return PriorityDecision(
                        priority=1,
                        action_type="pickup",
                        target_id=item.get("instanceId") or item.get("id"),
                        reasoning=f"Critical HP ({hp_ratio:.0%}) - healing",
                        confidence=0.95
                    )
        
        # HP < 20% → RETREAT
        if hp_ratio < 0.2:
            self.stats["survival_priority"] += 1
            # Move away from enemies
            enemies = state.get_enemies()
            if enemies:
                # Move to safe region
                for conn in state.get_connections():
                    if not conn.get("insideDeathZone", False):
                        return PriorityDecision(
                            priority=1,
                            action_type="move",
                            target_id=conn.get("regionId"),
                            reasoning=f"Critical HP ({hp_ratio:.0%}) - retreating",
                            confidence=0.9
                        )
        
        # In Cave → EXIT
        if state.in_cave:
            for obj in state.get_interactables():
                if obj.get("isExit", False) and "cave" in str(obj.get("type", "")):
                    self.stats["survival_priority"] += 1
                    return PriorityDecision(
                        priority=1,
                        action_type="interact",
                        target_id=obj.get("interactableId") or obj.get("id"),
                        reasoning="Exiting cave",
                        confidence=0.95
                    )
        
        # In Death Zone → MOVE TO CENTER
        if state.get_region().get("insideDeathZone", False):
            self.stats["survival_priority"] += 1
            for conn in state.get_connections():
                if not conn.get("insideDeathZone", False):
                    return PriorityDecision(
                        priority=1,
                        action_type="move",
                        target_id=conn.get("regionId"),
                        reasoning="Escaping death zone",
                        confidence=0.9
                    )
        
        # Alert > 7 → HIDE / RETREAT
        if alert > 7:
            self.stats["survival_priority"] += 1
            # Move to less dangerous region
            for conn in state.get_connections():
                if conn.get("safetyScore", 0) > 0.5:
                    return PriorityDecision(
                        priority=1,
                        action_type="move",
                        target_id=conn.get("regionId"),
                        reasoning=f"High alert ({alert}) - moving to safety",
                        confidence=0.85
                    )
        
        # === PRIORITY 2: LOOT ===
        
        # Collect items in range
        for item in state.get_items():
            distance = self._distance(me, item)
            if distance < 3:
                item_type = str(item.get("type", item.get("itemType", ""))).lower()
                value = float(item.get("value", item.get("rarityValue", 0)))
                
                # Prioritaskan: Relic > Pack > Potion > sMoltz
                priority_score = 0
                if "relic" in item_type:
                    priority_score = 4
                elif "pack" in item_type:
                    priority_score = 3
                elif "potion" in item_type or "herb" in item_type:
                    priority_score = 2
                else:
                    priority_score = 1
                
                # Only loot if safe enough
                if threat["risk_score"] < 0.5 or priority_score > 2:
                    self.stats["loot_priority"] += 1
                    return PriorityDecision(
                        priority=2,
                        action_type="pickup",
                        target_id=item.get("instanceId") or item.get("id"),
                        reasoning=f"Collecting {item_type} (value: {value})",
                        confidence=0.8
                    )
        
        # Move to items in range (distance < 5)
        for item in state.get_items():
            distance = self._distance(me, item)
            if distance < 5 and threat["risk_score"] < 0.4:
                self.stats["loot_priority"] += 1
                return PriorityDecision(
                    priority=2,
                    action_type="move",
                    target_id=item.get("regionId"),
                    reasoning=f"Moving to collect item",
                    confidence=0.7
                )
        
        # === PRIORITY 3: KILL ===
        
        # Only if HP > 50%
        if hp_ratio > 0.5 and threat["should_fight"]:
            enemies = state.get_enemies()
            if enemies:
                # Target: HP terendah dalam range
                targetable = [
                    e for e in enemies 
                    if self._distance(me, e) < 10
                ]
                if targetable:
                    # Sort by HP (lowest first)
                    targetable.sort(key=lambda e: float(e.get("hp", 0)))
                    target = targetable[0]
                    
                    # Check kill probability
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
        
        # === PRIORITY 4: EXPLORE ===
        
        # Ruin in range (distance < 2)
        for obj in state.get_interactables():
            distance = self._distance(me, obj)
            if distance < 2 and "ruin" in str(obj.get("type", obj.get("kind", ""))):
                self.stats["explore_priority"] += 1
                return PriorityDecision(
                    priority=4,
                    action_type="explore",
                    target_id=obj.get("interactableId") or obj.get("id"),
                    reasoning="Exploring ruin",
                    confidence=0.75
                )
        
        # Ruin in range (distance < 5)
        for obj in state.get_interactables():
            distance = self._distance(me, obj)
            if distance < 5 and "ruin" in str(obj.get("type", obj.get("kind", ""))):
                self.stats["explore_priority"] += 1
                return PriorityDecision(
                    priority=4,
                    action_type="move",
                    target_id=obj.get("regionId"),
                    reasoning="Moving to ruin",
                    confidence=0.6
                )
        
        # === FALLBACK: MOVE TOWARDS CENTER ===
        
        # Move to center (safer)
        for conn in state.get_connections():
            if conn.get("safetyScore", 0) > 0.5:
                return PriorityDecision(
                    priority=4,
                    action_type="move",
                    target_id=conn.get("regionId"),
                    reasoning="Moving to safer area",
                    confidence=0.5
                )
        
        # Last resort: move to any connection
        for conn in state.get_connections():
            if not conn.get("insideDeathZone", False):
                return PriorityDecision(
                    priority=4,
                    action_type="move",
                    target_id=conn.get("regionId"),
                    reasoning="Moving randomly",
                    confidence=0.3
                )
        
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
                risk_score=threat["risk_score"],
                expected_value=1 - threat["risk_score"]
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
                risk_score=threat["risk_score"],
                expected_value=1 - threat["risk_score"]
            )
        
        # Default: AI decision
        return ai
    
    def _distance(self, obj1: Dict, obj2: Dict) -> float:
        """Hitung distance antara dua object"""
        import math
        x1 = float(obj1.get("x", obj1.get("position", {}).get("x", 0)))
        y1 = float(obj1.get("y", obj1.get("position", {}).get("y", 0)))
        x2 = float(obj2.get("x", obj2.get("position", {}).get("x", 0)))
        y2 = float(obj2.get("y", obj2.get("position", {}).get("y", 0)))
        return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
    
    def get_stats(self) -> Dict:
        """Dapatkan statistik decision"""
        return self.stats