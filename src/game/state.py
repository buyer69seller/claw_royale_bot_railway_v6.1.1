# src/game/state.py
"""Manajemen state game - dengan Item Tracking"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set
import logging
import math

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
    # src/game/state.py - tambahkan di GameState

    # ===== INVENTORY TRACKING (BARU) =====
    inventory_items: Dict[str, Dict] = field(default_factory=dict)  # Item yang dimiliki
    equipped_items: Dict[str, str] = field(default_factory=dict)   # slot -> item_id
    
    def add_to_inventory(self, item: Dict):
        """Tambahkan item ke inventory"""
        item_id = item.get("instanceId") or item.get("id")
        if item_id:
            self.inventory_items[item_id] = item
            logger.debug(f"📦 Added to inventory: {item_id[:8]}")
    
    def remove_from_inventory(self, item_id: str):
        """Hapus item dari inventory"""
        if item_id in self.inventory_items:
            del self.inventory_items[item_id]
            logger.debug(f"🗑️ Removed from inventory: {item_id[:8]}")
    
    def get_healing_items_inventory(self) -> List[Dict]:
        """Dapatkan item healing dari inventory"""
        healing_items = []
        for item in self.inventory_items.values():
            heal = float(item.get("heal", item.get("healAmount", 0)))
            if heal > 0:
                healing_items.append(item)
        return healing_items
    
    def get_best_healing_item(self) -> Optional[Dict]:
        """Dapatkan item healing terbaik dari inventory"""
        items = self.get_healing_items_inventory()
        if not items:
            return None
        # Sort by heal amount (terbesar dulu)
        items.sort(key=lambda x: float(x.get("heal", x.get("healAmount", 0))), reverse=True)
        return items[0]
    
    def has_healing_items(self) -> bool:
        """Cek apakah ada item healing di inventory"""
        return len(self.get_healing_items_inventory()) > 0
        
    # ===== ITEM TRACKING (BARU) =====
    attempted_items: Set[str] = field(default_factory=set)
    collected_items: Set[str] = field(default_factory=set)
    item_cache: Dict[str, Dict] = field(default_factory=dict)
    last_item_scan_turn: int = 0
    
    def update_view(self, view_data: Dict, reason: str = "sync"):
        """Update view dari game - dengan item cache update"""
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
        
        # ===== ITEM CACHE UPDATE =====
        self._update_item_cache(view_data)
    
    def _update_item_cache(self, view_data: Dict):
        """Update item cache dari view"""
        region = view_data.get("currentRegion", {})
        items = region.get("items", [])
        
        # Update cache dengan item baru
        current_item_ids = set()
        for item in items:
            item_id = item.get("instanceId") or item.get("id")
            if item_id:
                current_item_ids.add(item_id)
                if item_id not in self.item_cache or self.item_cache.get(item_id) != item:
                    self.item_cache[item_id] = item
        
        # Hapus item yang sudah tidak ada di view
        removed_items = []
        for cached_id in list(self.item_cache.keys()):
            if cached_id not in current_item_ids:
                self.collected_items.add(cached_id)
                removed_items.append(cached_id)
                del self.item_cache[cached_id]
        
        if removed_items:
            logger.debug(f"🗑️ Items removed from cache: {len(removed_items)}")
        
        # Bersihkan attempted_items yang sudah dikoleksi
        self.attempted_items = self.attempted_items - self.collected_items
    
    # ===== ITEM VALIDATION METHODS =====
    
    def get_valid_items(self) -> List[Dict]:
        """
        Dapatkan item yang VALID dan BELUM DICOBA
        - Item dalam jangkauan (distance < 5)
        - Item belum dicoba/dikoleksi
        - Item masih ada di cache
        - Item masih ada di view
        """
        items = self.get_items()
        valid_items = []
        me = self.get_self()
        
        if not items:
            logger.debug("📭 No items in current view")
            return []
        
        for item in items:
            item_id = item.get("instanceId") or item.get("id")
            if not item_id:
                continue
            
            # Skip jika sudah dicoba atau sudah dikoleksi
            if item_id in self.attempted_items:
                logger.debug(f"⏭️ Item {item_id[:8]} already attempted")
                continue
            
            if item_id in self.collected_items:
                logger.debug(f"⏭️ Item {item_id[:8]} already collected")
                continue
            
            # Cek jarak
            distance = self._calculate_distance(me, item)
            
            # Hanya ambil item dalam jangkauan (distance < 5)
            if distance < 5:
                valid_items.append(item)
                logger.debug(f"✅ Item {item_id[:8]} valid (distance: {distance:.1f})")
            else:
                logger.debug(f"📏 Item {item_id[:8]} too far (distance: {distance:.1f})")
        
        return valid_items
    
    def get_healing_items(self, hp_threshold: float = 0.4) -> List[Dict]:
        """Dapatkan item healing yang valid"""
        valid_items = self.get_valid_items()
        healing_items = []
        
        for item in valid_items:
            heal = float(item.get("heal", item.get("healAmount", 0)))
            if heal > 0:
                me = self.get_self()
                distance = self._calculate_distance(me, item)
                healing_items.append({
                    "item": item,
                    "heal": heal,
                    "distance": distance,
                    "score": heal / max(distance, 1)
                })
        
        healing_items.sort(key=lambda x: x["score"], reverse=True)
        return [h["item"] for h in healing_items]
    
    def get_loot_items(self) -> List[Dict]:
        """Dapatkan item loot yang valid (non-healing)"""
        valid_items = self.get_valid_items()
        loot_items = []
        
        for item in valid_items:
            heal = float(item.get("heal", item.get("healAmount", 0)))
            if heal == 0:
                value = float(item.get("value", item.get("rarityValue", 0)))
                item_type = str(item.get("type", item.get("itemType", ""))).lower()
                
                priority = 0
                if "relic" in item_type:
                    priority = 4
                elif "pack" in item_type:
                    priority = 3
                elif "weapon" in item_type or "armor" in item_type:
                    priority = 2
                else:
                    priority = 1
                
                loot_items.append({
                    "item": item,
                    "value": value,
                    "priority": priority,
                    "item_type": item_type
                })
        
        loot_items.sort(key=lambda x: (x["priority"], x["value"]), reverse=True)
        return [l["item"] for l in loot_items]
    
    def mark_item_attempted(self, item_id: str):
        """Tandai item sudah dicoba"""
        if item_id:
            self.attempted_items.add(item_id)
            logger.debug(f"📝 Item {item_id[:8]} marked as attempted")
    
    def mark_item_collected(self, item_id: str):
        """Tandai item sudah dikoleksi"""
        if item_id:
            self.collected_items.add(item_id)
            self.attempted_items.add(item_id)
            if item_id in self.item_cache:
                del self.item_cache[item_id]
            logger.debug(f"✅ Item {item_id[:8]} marked as collected")
    
    def is_item_valid(self, item_id: str) -> bool:
        """Cek apakah item masih valid"""
        if not item_id:
            return False
        return item_id not in self.attempted_items and item_id not in self.collected_items
    
    def _calculate_distance(self, obj1: Dict, obj2: Dict) -> float:
        """Hitung jarak antara dua objek"""
        try:
            x1 = float(obj1.get("x", obj1.get("position", {}).get("x", 0)))
            y1 = float(obj1.get("y", obj1.get("position", {}).get("y", 0)))
            x2 = float(obj2.get("x", obj2.get("position", {}).get("x", 0)))
            y2 = float(obj2.get("y", obj2.get("position", {}).get("y", 0)))
            return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
        except:
            return 999.0
    
    def get_item_stats(self) -> Dict[str, Any]:
        """Dapatkan statistik item tracking"""
        return {
            "total_items_in_cache": len(self.item_cache),
            "attempted_items": len(self.attempted_items),
            "collected_items": len(self.collected_items),
            "valid_items_available": len(self.get_valid_items())
        }
    
    # ===== EXISTING METHODS (TIDAK DIUBAH) =====
    
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
