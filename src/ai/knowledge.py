# src/ai/knowledge.py
"""Knowledge Base - Belajar dari pengalaman"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import datetime

logger = logging.getLogger(__name__)

class KnowledgeBase:
    def __init__(self, storage_path: str = "knowledge.json"):
        self.storage_path = Path(storage_path)
        self.data = self._load()
        self.session_id = datetime.datetime.now().isoformat()
        
    def _load(self) -> Dict[str, Any]:
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load knowledge: {e}")
        return self._default_knowledge()
    
    def _default_knowledge(self) -> Dict[str, Any]:
        return {
            "patterns": {"dangerous_situations": [], "good_opportunities": [], "failed_actions": [], "successful_actions": []},
            "stats": {"total_games": 0, "games_won": 0, "total_actions": 0, "successful_actions": 0, "kills": 0, "deaths": 0, "avg_survival": 0},
            "learned_weights": {"heal_value": 1.0, "attack_value": 1.0, "loot_value": 1.0, "explore_value": 1.0, "move_value": 1.0},
            "history": []
        }
    
    def save(self):
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save knowledge: {e}")
    
    async def record_decision(self, decision, perceived, analysis):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "session": self.session_id,
            "decision": {"action_type": decision.action_type, "target_id": decision.target_id, "confidence": decision.confidence, "expected_value": decision.expected_value},
            "context": {"hp_ratio": perceived.hp_ratio, "in_cave": perceived.in_cave, "enemy_count": len(perceived.enemies), "danger_level": perceived.danger_level, "opportunity_score": perceived.opportunity_score, "turn": perceived.turn},
            "analysis": {"threat_level": analysis["threat_level"]["level"], "battle_potential": analysis["battle_potential"]["potential"], "strategy": analysis["survival_strategy"]["primary"]}
        }
        self.data["history"].append(entry)
        self.data["stats"]["total_actions"] += 1
        if len(self.data["history"]) % 10 == 0:
            self.save()
    
    def record_outcome(self, outcome: str, details: Dict = None):
        self.data["stats"]["total_games"] += 1
        if outcome == "win":
            self.data["stats"]["games_won"] += 1
        elif outcome == "death":
            self.data["stats"]["deaths"] += 1
        if details:
            self.data["stats"]["kills"] += details.get("kills", 0)
            self.data["stats"]["avg_survival"] = (self.data["stats"]["avg_survival"] * (self.data["stats"]["total_games"] - 1) + details.get("survival_time", 0)) / self.data["stats"]["total_games"]
        self.save()
    
    def get_insights(self) -> Dict[str, Any]:
        stats = self.data["stats"]
        return {
            "performance": {
                "win_rate": stats["games_won"] / max(stats["total_games"], 1),
                "avg_survival": stats["avg_survival"],
                "kills_per_game": stats["kills"] / max(stats["total_games"], 1),
                "success_rate": stats["successful_actions"] / max(stats["total_actions"], 1)
            },
            "weights": self.data["learned_weights"],
            "pattern_count": {k: len(v) for k, v in self.data["patterns"].items()},
            "total_games": stats["total_games"]
        }