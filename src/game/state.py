# src/game/state.py
"""Manajemen state game"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

@dataclass
class GameState:
    """State dari game yang sedang berjalan"""
    
    # Game info
    game_id: Optional[str] = None
    entry_type: str = "free"
    
    # Agent info
    agent_id: Optional[str] = None
    self_token: Optional[str] = None
    is_alive: bool = True
    can_act: bool = True
    in_cave: bool = False
    
    # View data terakhir
    view: Dict[str, Any] = field(default_factory=dict)
    turn: int = 0
    last_view_hash: int = 0
    
    # Status
    is_finished: bool = False
    is_dead: bool = False
    
    # Metadata
    survival_time: int = 0
    kills: int = 0
    hp: float = 0
    max_hp: float = 1
    
    # Rejected action tracking
    rejected_count: int = 0
    last_rejected_action: Optional[str] = None
    
    def update_view(self, view_data: Dict, reason: str = "sync"):
        """Update view dari game"""
        import hashlib
        import json
        
        # Hash view untuk deteksi perubahan
        view_str = json.dumps(view_data, sort_keys=True)
        new_hash = hash(view_str)
        
        if new_hash == self.last_view_hash and reason == "action_rejected":
            self.rejected_count += 1
        else:
            self.rejected_count = 0
            self.last_view_hash = new_hash
        
        self.view = view_data
        self.turn += 1
        
        # Update self info
        self_data = view_data.get("self", {})
        self.is_alive = self_data.get("isAlive", True)
        self.self_token = self_data.get("id")
        self.in_cave = self_data.get("inCave", False)
        
        # Update HP
        self.hp = float(self_data.get("hp", self_data.get("currentHp", self_data.get("health", 0))))
        self.max_hp = float(self_data.get("maxHp", self_data.get("maxHealth", self_data.get("hp", 1))))
        
        # Track stats
        if "survivalTime" in self_data:
            self.survival_time = self_data.get("survivalTime", 0)
        if "kills" in self_data:
            self.kills = self_data.get("kills", 0)
    
    def mark_dead(self):
        """Tandai agent sudah mati"""
        self.is_dead = True
        self.is_alive = False
        self.is_finished = True
        logger.info(f"💀 YOU DIED! Survival: {self.survival_time}, Kills: {self.kills}")
    
    def mark_finished(self):
        """Tandai game selesai"""
        self.is_finished = True
        logger.info(f"🏆 Game finished. Survival: {self.survival_time}, Kills: {self.kills}")
    
    def get_self(self) -> Dict:
        return self.view.get("self", {})
    
    def get_region(self) -> Dict:
        return self.view.get("currentRegion", {})
    
    def get_enemies(self) -> List[Dict]:
        enemies = []
        for enemy in self.view.get("visibleAgents", []):
            if self._is_alive(enemy):
                enemies.append(enemy)
        for monster in self.view.get("visibleMonsters", []):
            if self._is_alive(monster):
                enemies.append(monster)
        return enemies
    
    def get_items(self) -> List[Dict]:
        region = self.get_region()
        return region.get("items", [])
    
    def get_interactables(self) -> List[Dict]:
        region = self.get_region()
        return region.get("interactables", [])
    
    def get_connections(self) -> List[Dict]:
        region = self.get_region()
        return region.get("connections", [])
    
    def get_cave_exit(self) -> Optional[Dict]:
        if not self.in_cave:
            return None
        for obj in self.get_interactables():
            obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
            if "cave" in obj_type and obj.get("isExit", False):
                return obj
        return None
    
    def hp_ratio(self) -> float:
        return self.hp / max(self.max_hp, 1)
    
    def is_low_hp(self, threshold: float = 0.25) -> bool:
        return self.hp_ratio() < threshold
    
    def is_very_low_hp(self, threshold: float = 0.15) -> bool:
        return self.hp_ratio() < threshold
    
    @staticmethod
    def _is_alive(obj: Dict) -> bool:
        return obj.get("isAlive", False) is True and obj.get("hp", 0) > 0