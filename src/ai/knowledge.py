# src/ai/knowledge.py
"""Knowledge Base - Belajar dari pengalaman dengan memory limit"""

import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import deque

logger = logging.getLogger(__name__)

class KnowledgeBase:
    """Knowledge base dengan memory limit untuk mencegah memory leak"""
    
    # ===== MEMORY LIMITS =====
    MAX_HISTORY = 500          # Maksimum history entries
    MAX_PATTERNS = 100         # Maksimum patterns per category
    MAX_SESSION_HISTORY = 50   # Maksimum per session
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size
    
    def __init__(self, storage_path: str = "knowledge.json"):
        self.storage_path = Path(storage_path)
        self.data = self._load()
        self.session_id = datetime.datetime.now().isoformat()
        self._session_count = 0
        
        # Memory tracking
        self._memory_usage = {
            "history": len(self.data.get("history", [])),
            "patterns": sum(len(v) for v in self.data.get("patterns", {}).values()),
            "session_history": 0
        }
        logger.debug(f"📊 Memory usage: {self._memory_usage}")
    
    def _load(self) -> Dict[str, Any]:
        """Load knowledge dari file dengan limit dan validasi"""
        if self.storage_path.exists():
            try:
                # Cek file size
                file_size = self.storage_path.stat().st_size
                if file_size > self.MAX_FILE_SIZE:
                    logger.warning(f"⚠️ Knowledge file too large ({file_size} bytes), creating new...")
                    return self._default_knowledge()
                
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    
                    # Validasi dan limit history
                    if len(data.get("history", [])) > self.MAX_HISTORY:
                        removed = len(data["history"]) - self.MAX_HISTORY
                        data["history"] = data["history"][-self.MAX_HISTORY:]
                        logger.debug(f"🧹 Removed {removed} old history entries on load")
                    
                    # Validasi patterns
                    for key in data.get("patterns", {}):
                        if len(data["patterns"][key]) > self.MAX_PATTERNS:
                            removed = len(data["patterns"][key]) - self.MAX_PATTERNS
                            data["patterns"][key] = data["patterns"][key][-self.MAX_PATTERNS:]
                            logger.debug(f"🧹 Removed {removed} old {key} patterns on load")
                    
                    return data
            except json.JSONDecodeError:
                logger.warning("⚠️ Knowledge file corrupted, creating new...")
                return self._default_knowledge()
            except Exception as e:
                logger.warning(f"Failed to load knowledge: {e}")
                return self._default_knowledge()
        return self._default_knowledge()
    
    def _default_knowledge(self) -> Dict[str, Any]:
        """Default knowledge structure dengan limit"""
        return {
            "patterns": {
                "dangerous_situations": [],
                "good_opportunities": [],
                "failed_actions": [],
                "successful_actions": []
            },
            "stats": {
                "total_games": 0,
                "games_won": 0,
                "total_actions": 0,
                "successful_actions": 0,
                "kills": 0,
                "deaths": 0,
                "avg_survival": 0,
                "max_survival": 0,
                "total_kills": 0
            },
            "learned_weights": {
                "heal_value": 1.0,
                "attack_value": 1.0,
                "loot_value": 1.0,
                "explore_value": 1.0,
                "move_value": 1.0
            },
            "history": [],
            "created_at": datetime.datetime.now().isoformat(),
            "last_updated": datetime.datetime.now().isoformat()
        }
    
    def save(self):
        """Save knowledge dengan cleanup sebelum save"""
        self._cleanup()
        try:
            compact_data = self._compact_data()
            
            # Create backup before overwriting
            if self.storage_path.exists():
                backup_path = self.storage_path.with_suffix(".json.bak")
                try:
                    self.storage_path.rename(backup_path)
                except Exception:
                    pass
            
            with open(self.storage_path, 'w') as f:
                json.dump(compact_data, f, indent=2)
            
            # Update file info
            self.data["last_updated"] = datetime.datetime.now().isoformat()
            logger.debug(f"💾 Knowledge saved ({len(compact_data['history'])} entries)")
            
        except Exception as e:
            logger.error(f"Failed to save knowledge: {e}")
    
    def _cleanup(self):
        """Cleanup data untuk mencegah memory leak"""
        # ===== LIMIT HISTORY =====
        if len(self.data.get("history", [])) > self.MAX_HISTORY:
            removed = len(self.data["history"]) - self.MAX_HISTORY
            self.data["history"] = self.data["history"][-self.MAX_HISTORY:]
            logger.debug(f"🧹 Removed {removed} old history entries")
        
        # ===== LIMIT PATTERNS =====
        for key in self.data.get("patterns", {}):
            if len(self.data["patterns"][key]) > self.MAX_PATTERNS:
                removed = len(self.data["patterns"][key]) - self.MAX_PATTERNS
                self.data["patterns"][key] = self.data["patterns"][key][-self.MAX_PATTERNS:]
                logger.debug(f"🧹 Removed {removed} old {key} patterns")
        
        # ===== UPDATE MEMORY USAGE =====
        self._memory_usage = {
            "history": len(self.data.get("history", [])),
            "patterns": sum(len(v) for v in self.data.get("patterns", {}).values()),
            "session_history": self._session_count
        }
        
        # ===== CHECK FILE SIZE =====
        if self.storage_path.exists():
            file_size = self.storage_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                logger.warning(f"⚠️ Knowledge file too large ({file_size} bytes), compacting...")
                # Keep only last 100 entries
                if len(self.data.get("history", [])) > 100:
                    self.data["history"] = self.data["history"][-100:]
                    self.save()
    
    def _compact_data(self) -> Dict[str, Any]:
        """Compact data untuk save"""
        return {
            "patterns": self.data.get("patterns", {}),
            "stats": self.data.get("stats", {}),
            "learned_weights": self.data.get("learned_weights", {}),
            "history": self.data.get("history", [])[-self.MAX_HISTORY:],
            "created_at": self.data.get("created_at", datetime.datetime.now().isoformat()),
            "last_updated": datetime.datetime.now().isoformat(),
            "total_entries": len(self.data.get("history", [])),
            "version": "2.0"
        }
    
    async def record_decision(self, decision, perceived, analysis):
        """Rekam keputusan dengan limit"""
        
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "session": self.session_id,
            "decision": {
                "action_type": decision.action_type,
                "target_id": decision.target_id,
                "confidence": decision.confidence,
                "expected_value": decision.expected_value
            },
            "context": {
                "hp_ratio": perceived.hp_ratio,
                "in_cave": perceived.in_cave,
                "enemy_count": len(perceived.enemies),
                "danger_level": perceived.danger_level,
                "opportunity_score": perceived.opportunity_score,
                "turn": perceived.turn
            },
            "analysis": {
                "threat_level": analysis["threat_level"]["level"],
                "battle_potential": analysis["battle_potential"]["potential"],
                "strategy": analysis["survival_strategy"]["primary"]
            },
            "outcome": None  # Akan diisi nanti
        }
        
        self.data["history"].append(entry)
        self.data["stats"]["total_actions"] += 1
        self._session_count += 1
        
        # ===== AUTO CLEANUP =====
        if len(self.data["history"]) % 50 == 0:
            self._cleanup()
            self.save()
        
        # ===== UPDATE MEMORY USAGE =====
        self._memory_usage["history"] = len(self.data["history"])
        self._memory_usage["session_history"] = self._session_count
    
    def record_outcome(self, outcome: str, details: Dict = None):
        """Rekam outcome dari game"""
        self.data["stats"]["total_games"] += 1
        
        if outcome == "win":
            self.data["stats"]["games_won"] += 1
        elif outcome == "death":
            self.data["stats"]["deaths"] += 1
        
        if details:
            kills = details.get("kills", 0)
            survival = details.get("survival_time", 0)
            
            self.data["stats"]["total_kills"] += kills
            self.data["stats"]["kills"] = self.data["stats"]["total_kills"] / max(self.data["stats"]["total_games"], 1)
            
            total_games = self.data["stats"]["total_games"]
            avg = self.data["stats"]["avg_survival"]
            self.data["stats"]["avg_survival"] = (avg * (total_games - 1) + survival) / total_games
            
            if survival > self.data["stats"]["max_survival"]:
                self.data["stats"]["max_survival"] = survival
        
        # ===== UPDATE HISTORY WITH OUTCOME =====
        if self.data["history"]:
            last_entry = self.data["history"][-1]
            last_entry["outcome"] = outcome
        
        # ===== CLEANUP AFTER OUTCOME =====
        self._cleanup()
        self.save()
    
    def record_pattern(self, pattern_type: str, pattern_data: Dict):
        """Rekam pattern dengan limit"""
        if pattern_type in self.data["patterns"]:
            self.data["patterns"][pattern_type].append({
                "timestamp": datetime.datetime.now().isoformat(),
                "data": pattern_data
            })
            # ===== CLEANUP PATTERNS =====
            if len(self.data["patterns"][pattern_type]) > self.MAX_PATTERNS:
                self.data["patterns"][pattern_type] = self.data["patterns"][pattern_type][-self.MAX_PATTERNS:]
            self.save()
    
    def get_learned_weight(self, action_type: str) -> float:
        """Dapatkan bobot yang telah dipelajari"""
        return self.data["learned_weights"].get(action_type + "_value", 1.0)
    
    def update_learned_weight(self, action_type: str, adjustment: float):
        """Update bobot yang dipelajari"""
        key = action_type + "_value"
        if key in self.data["learned_weights"]:
            current = self.data["learned_weights"][key]
            new_value = current + adjustment
            self.data["learned_weights"][key] = max(min(new_value, 2.0), 0.5)
            self.save()
    
    def get_insights(self) -> Dict[str, Any]:
        """Dapatkan insights dari knowledge"""
        stats = self.data["stats"]
        total_games = max(stats["total_games"], 1)
        
        return {
            "performance": {
                "win_rate": stats["games_won"] / total_games,
                "avg_survival": stats["avg_survival"],
                "max_survival": stats["max_survival"],
                "kills_per_game": stats["kills"],
                "success_rate": stats["successful_actions"] / max(stats["total_actions"], 1)
            },
            "weights": self.data["learned_weights"],
            "pattern_count": {
                k: len(v) for k, v in self.data["patterns"].items()
            },
            "total_games": stats["total_games"],
            "total_actions": stats["total_actions"],
            "memory": {
                "history_entries": len(self.data.get("history", [])),
                "max_history": self.MAX_HISTORY,
                "usage_percent": (len(self.data.get("history", [])) / self.MAX_HISTORY) * 100,
                "patterns_total": sum(len(v) for v in self.data.get("patterns", {}).values()),
                "session_entries": self._session_count
            },
            "created_at": self.data.get("created_at", "unknown"),
            "last_updated": self.data.get("last_updated", "unknown")
        }
    
    def clear_old_data(self, days: int = 30) -> int:
        """Hapus data lebih dari N hari"""
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        original_count = len(self.data.get("history", []))
        self.data["history"] = [
            h for h in self.data.get("history", [])
            if h.get("timestamp", "") > cutoff_str
        ]
        removed = original_count - len(self.data["history"])
        
        if removed > 0:
            logger.info(f"🧹 Cleared {removed} entries older than {days} days")
            self.save()
        
        return removed
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Dapatkan statistik memory"""
        file_size = 0
        if self.storage_path.exists():
            file_size = self.storage_path.stat().st_size
        
        return {
            "history_count": len(self.data.get("history", [])),
            "history_limit": self.MAX_HISTORY,
            "history_usage": f"{len(self.data.get('history', [])) / self.MAX_HISTORY * 100:.1f}%",
            "patterns_count": sum(len(v) for v in self.data.get("patterns", {}).values()),
            "patterns_limit": self.MAX_PATTERNS,
            "session_entries": self._session_count,
            "file_size_bytes": file_size,
            "file_size_kb": file_size / 1024,
            "file_size_mb": file_size / (1024 * 1024)
        }
    
    def get_recent_history(self, limit: int = 10) -> List[Dict]:
        """Dapatkan history terakhir"""
        return self.data.get("history", [])[-limit:]
    
    def get_summary(self) -> Dict[str, Any]:
        """Dapatkan summary knowledge"""
        stats = self.data["stats"]
        total_games = max(stats["total_games"], 1)
        
        return {
            "games": {
                "total": stats["total_games"],
                "wins": stats["games_won"],
                "losses": stats["deaths"],
                "win_rate": f"{stats['games_won'] / total_games * 100:.1f}%"
            },
            "combat": {
                "kills": stats["kills"],
                "avg_kills": stats["kills"],
                "survival": {
                    "avg": stats["avg_survival"],
                    "max": stats["max_survival"]
                }
            },
            "actions": {
                "total": stats["total_actions"],
                "successful": stats["successful_actions"],
                "success_rate": f"{stats['successful_actions'] / max(stats['total_actions'], 1) * 100:.1f}%"
            },
            "memory": self.get_memory_stats(),
            "weights": self.data["learned_weights"]
        }
