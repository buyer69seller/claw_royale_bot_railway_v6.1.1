# src/ai/risk.py
"""Risk Assessment - Menilai risiko setiap action"""

import logging
from typing import Dict, Any, List, Optional

from .perception import PerceivedState

logger = logging.getLogger(__name__)


class RiskAssessor:
    """Menilai risiko setiap keputusan dan situasi"""
    
    def __init__(self):
        self.risk_threshold = 0.7
        self.last_risk_assessment = None
    
    def assess_action_risk(self, action: Optional[Dict], state: PerceivedState) -> Dict[str, Any]:
        """
        Menilai risiko untuk action tertentu
        
        Args:
            action: Dictionary action dengan keys: type, target
            state: PerceivedState dari game
            
        Returns:
            Dict dengan risk_score, is_safe, risk_level, factors, recommendation
        """
        
        # ===== FIX 1: Handle None action =====
        if action is None:
            return {
                "risk_score": 0.5,
                "is_safe": False,
                "risk_level": "medium",
                "factors": [{"factor": "no_action", "weight": 0.5, "description": "No action provided"}],
                "recommendation": "Reconsider - no action"
            }
        
        # ===== FIX 2: Handle jika action bukan dict =====
        if not isinstance(action, dict):
            return {
                "risk_score": 0.5,
                "is_safe": False,
                "risk_level": "medium",
                "factors": [{"factor": "invalid_action", "weight": 0.5, "description": "Invalid action format"}],
                "recommendation": "Reconsider - invalid action"
            }
        
        action_type = action.get("type")
        
        # ===== FIX 3: Handle jika action_type None =====
        if action_type is None:
            return {
                "risk_score": 0.3,
                "is_safe": True,
                "risk_level": "low",
                "factors": [],
                "recommendation": "Proceed - unknown action type"
            }
        
        # ===== FIX 4: Safe target extraction =====
        target = action.get("target")
        target_id = None
        if target and isinstance(target, dict):
            target_id = target.get("id")
        elif target and isinstance(target, str):
            target_id = target
        
        risk_factors = []
        
        # Assess based on action type
        if action_type == "attack":
            risk_factors = self._assess_attack_risk(target_id, state)
        elif action_type == "pickup":
            risk_factors = self._assess_pickup_risk(target_id, state)
        elif action_type in ("interact", "explore"):
            risk_factors = self._assess_interact_risk(target_id, state)
        elif action_type == "move":
            risk_factors = self._assess_move_risk(target_id, state)
        elif action_type == "use":
            risk_factors = self._assess_use_risk(target_id, state)
        elif action_type == "wait":
            risk_factors = [{"factor": "waiting", "weight": 0.1, "description": "Waiting - low risk"}]
        else:
            risk_factors = [{"factor": "unknown_action", "weight": 0.5, "description": f"Unknown action type: {action_type}"}]
        
        # Calculate total risk
        total_risk = sum(f["weight"] for f in risk_factors)
        max_risk = len(risk_factors) * 1.0 if risk_factors else 1.0
        risk_score = min(total_risk / max_risk if max_risk > 0 else 0, 1.0)
        is_safe = risk_score < self.risk_threshold
        
        # Determine risk level
        if risk_score < 0.3:
            risk_level = "low"
        elif risk_score < 0.6:
            risk_level = "medium"
        elif risk_score < 0.8:
            risk_level = "high"
        else:
            risk_level = "critical"
        
        return {
            "risk_score": risk_score,
            "is_safe": is_safe,
            "risk_level": risk_level,
            "factors": risk_factors,
            "recommendation": "Proceed" if is_safe else f"Reconsider - {risk_level} risk action"
        }
    
    def _assess_attack_risk(self, target_id: Optional[str], state: PerceivedState) -> List[Dict]:
        """Risiko menyerang target"""
        risks = []
        
        # ===== FIX: Handle jika target_id None =====
        if not target_id:
            risks.append({"factor": "no_target", "weight": 0.5, "description": "No target specified"})
            return risks
        
        # Find target
        target = None
        for enemy in state.enemies:
            if enemy.id == target_id:
                target = enemy
                break
        
        if not target:
            risks.append({"factor": "target_not_found", "weight": 0.8, "description": "Target not found"})
            return risks
        
        # HP ratio risk
        hp_ratio = state.hp_ratio
        if hp_ratio < 0.3:
            risks.append({"factor": "critical_hp", "weight": 0.9, "description": "Critical HP - high risk"})
        elif hp_ratio < 0.5:
            risks.append({"factor": "low_hp", "weight": 0.6, "description": "Low HP - moderate risk"})
        
        # Target threat
        if target.is_guardian:
            risks.append({"factor": "guardian_target", "weight": 0.9, "description": "Guardian is very dangerous"})
        elif target.threat_score > 30:
            risks.append({"factor": "high_threat_target", "weight": 0.7, "description": "Target is threatening"})
        
        # Target HP
        target_hp_ratio = target.hp / max(target.max_hp, 1)
        if target_hp_ratio < 0.2:
            risks.append({"factor": "target_almost_dead", "weight": 0.1, "description": "Target almost dead - low risk"})
        elif target_hp_ratio > 0.7:
            risks.append({"factor": "target_healthy", "weight": 0.5, "description": "Target is healthy"})
        
        # Nearby enemies
        nearby_enemies = len([e for e in state.enemies if e.id != target_id and e.distance < 10])
        if nearby_enemies > 2:
            risks.append({"factor": "outnumbered", "weight": 0.8, "description": f"Outnumbered by {nearby_enemies} enemies"})
        elif nearby_enemies > 0:
            risks.append({"factor": "other_enemies", "weight": 0.4, "description": f"{nearby_enemies} other enemies nearby"})
        
        return risks
    
    def _assess_pickup_risk(self, target_id: Optional[str], state: PerceivedState) -> List[Dict]:
        """Risiko mengambil item"""
        risks = []
        
        if not target_id:
            risks.append({"factor": "no_item", "weight": 0.3, "description": "No item specified"})
            return risks
        
        # Find item
        item = None
        for i in state.items:
            if i.id == target_id:
                item = i
                break
        
        if not item:
            risks.append({"factor": "item_not_found", "weight": 0.5, "description": "Item not found"})
            return risks
        
        # Enemies nearby
        nearby_enemies = len([e for e in state.enemies if e.distance < 8])
        if nearby_enemies > 0:
            risks.append({"factor": "enemies_nearby", "weight": 0.6, "description": f"{nearby_enemies} enemies nearby"})
        
        # Danger level
        if state.danger_level > 40:
            risks.append({"factor": "dangerous_area", "weight": 0.7, "description": "Area is dangerous"})
        
        # Item value vs risk
        if item.value_score > 50:
            risks.append({"factor": "high_value_item", "weight": 0.1, "description": "High value - worth some risk"})
        
        # Distance risk
        if item.distance > 5:
            risks.append({"factor": "item_far", "weight": 0.3, "description": f"Item is far ({item.distance:.1f}m)"})
        
        return risks
    
    def _assess_interact_risk(self, target_id: Optional[str], state: PerceivedState) -> List[Dict]:
        """Risiko interaksi dengan objek"""
        risks = []
        
        if not target_id:
            risks.append({"factor": "no_object", "weight": 0.3, "description": "No object specified"})
            return risks
        
        # Find interactable
        interactable = None
        for i in state.interactables:
            if i.id == target_id:
                interactable = i
                break
        
        if not interactable:
            risks.append({"factor": "object_not_found", "weight": 0.5, "description": "Object not found"})
            return risks
        
        kind = str(interactable.metadata.get("kind", ""))
        
        # Ruin risk
        if "ruin" in kind:
            alert = state.region.get("alertGauge", 0)
            if alert > 8:
                risks.append({"factor": "high_alert", "weight": 0.8, "description": f"High alert level: {alert}"})
            elif alert > 5:
                risks.append({"factor": "medium_alert", "weight": 0.5, "description": f"Alert level: {alert}"})
        
        # Cave exit - low risk
        if interactable.metadata.get("is_exit"):
            risks.append({"factor": "exiting_cave", "weight": 0.1, "description": "Exit cave - low risk"})
        
        # Enemies nearby
        nearby_enemies = len([e for e in state.enemies if e.distance < 10])
        if nearby_enemies > 0:
            risks.append({"factor": "enemies_nearby", "weight": 0.5, "description": f"{nearby_enemies} enemies nearby"})
        
        # Distance risk
        if interactable.distance > 5:
            risks.append({"factor": "object_far", "weight": 0.3, "description": f"Object is far ({interactable.distance:.1f}m)"})
        
        return risks
    
    def _assess_move_risk(self, target_id: Optional[str], state: PerceivedState) -> List[Dict]:
        """Risiko pindah ke region lain"""
        risks = []
        
        if not target_id:
            risks.append({"factor": "no_connection", "weight": 0.3, "description": "No connection specified"})
            return risks
        
        # Find connection
        conn = None
        for c in state.connections:
            if c.id == target_id:
                conn = c
                break
        
        if not conn:
            risks.append({"factor": "connection_not_found", "weight": 0.5, "description": "Connection not found"})
            return risks
        
        # Death zone
        if conn.metadata.get("insideDeathZone", False):
            risks.append({"factor": "death_zone", "weight": 0.9, "description": "Death zone - high risk"})
        
        # Safety score
        safety = float(conn.metadata.get("safetyScore", conn.metadata.get("zoneSafety", 0)))
        if safety < 0.3:
            risks.append({"factor": "unsafe_zone", "weight": 0.7, "description": "Unsafe zone"})
        elif safety > 0.7:
            risks.append({"factor": "safe_zone", "weight": 0.1, "description": "Safe zone - low risk"})
        
        return risks
    
    def _assess_use_risk(self, target_id: Optional[str], state: PerceivedState) -> List[Dict]:
        """Risiko menggunakan item (heal)"""
        risks = []
        
        if not target_id:
            risks.append({"factor": "no_item", "weight": 0.3, "description": "No item specified"})
            return risks
        
        # Using item is generally safe
        risks.append({"factor": "using_item", "weight": 0.2, "description": "Using item - generally safe"})
        
        # HP check
        if state.hp_ratio > 0.8:
            risks.append({"factor": "high_hp", "weight": 0.3, "description": "HP is already high - may waste item"})
        
        # Enemies nearby
        nearby_enemies = len([e for e in state.enemies if e.distance < 8])
        if nearby_enemies > 0:
            risks.append({"factor": "enemies_nearby", "weight": 0.4, "description": f"{nearby_enemies} enemies nearby"})
        
        return risks
    
    def assess_current_situation(self, state: PerceivedState) -> Dict[str, Any]:
        """
        Menilai situasi secara keseluruhan
        
        Returns:
            Dict dengan risk_score, risk_level, factors, should_flee, should_heal
        """
        risk_factors = []
        
        # HP risk
        if state.hp_ratio < 0.3:
            risk_factors.append({"factor": "critical_hp", "weight": 0.9})
        elif state.hp_ratio < 0.5:
            risk_factors.append({"factor": "low_hp", "weight": 0.6})
        
        # Enemy count
        enemy_count = len(state.enemies)
        if enemy_count > 3:
            risk_factors.append({"factor": "many_enemies", "weight": 0.8})
        elif enemy_count > 1:
            risk_factors.append({"factor": "multiple_enemies", "weight": 0.5})
        
        # Guardian
        if any(e.is_guardian for e in state.enemies):
            risk_factors.append({"factor": "guardian_present", "weight": 0.8})
        
        # Cave
        if state.in_cave:
            risk_factors.append({"factor": "in_cave", "weight": 0.4})
        
        # Alert
        alert = state.region.get("alertGauge", 0)
        if alert > 8:
            risk_factors.append({"factor": "high_alert", "weight": 0.7})
        elif alert > 5:
            risk_factors.append({"factor": "medium_alert", "weight": 0.4})
        
        # Danger level from state
        if state.danger_level > 50:
            risk_factors.append({"factor": "high_danger", "weight": 0.7})
        elif state.danger_level > 30:
            risk_factors.append({"factor": "medium_danger", "weight": 0.4})
        
        # Calculate total risk
        total_weight = sum(f["weight"] for f in risk_factors)
        max_weight = len(risk_factors) * 1.0 if risk_factors else 1.0
        risk_score = min(total_weight / max_weight if max_weight > 0 else 0, 1.0)
        
        # Determine risk level
        if risk_score < 0.3:
            risk_level = "low"
        elif risk_score < 0.6:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "factors": risk_factors,
            "should_flee": risk_score > 0.7,
            "should_heal": state.hp_ratio < 0.4,
            "is_safe": risk_score < 0.4,
            "recommendation": "Proceed" if risk_score < 0.4 else "Be cautious" if risk_score < 0.7 else "Flee or heal"
        }
