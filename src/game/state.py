# src/game/state.py
"""Manajemen state game - dengan Item Tracking, Ruin & Alert Tracking"""

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
    
    # ===== ITEM TRACKING =====
    attempted_items: Set[str] = field(default_factory=set)
    collected_items: Set[str] = field(default_factory=set)
    item_cache: Dict[str, Dict] = field(default_factory=dict)
    last_item_scan_turn: int = 0
    
    # ===== INVENTORY TRACKING =====
    inventory_items: Dict[str, Dict] = field(default_factory=dict)
    equipped_items: Dict[str, str] = field(default_factory=dict)
    
    # ===== RUIN & ALERT TRACKING (BARU) =====
    alert_gauge: int = 0
    alert_active: bool = False
    ruin_cache: Dict[str, Dict] = field(default_factory=dict)
    explored_ruins: Set[str] = field(default_factory=set)
    ruin_explore_count: int = 0
    last_ruin_explore_turn: int = 0
    
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
        
        # ===== RUIN CACHE UPDATE (BARU) =====
        self._update_ruin_cache(view_data)
    
    def _update_item_cache(self, view_data: Dict):
        """Update item cache dari view"""
        region = view_data.get("currentRegion", {})
        items = region.get("items", [])
        
        # Reset cache jika view baru (game baru)
        if self.turn == 1:
            self.item_cache.clear()
            self.attempted_items.clear()
            self.collected_items.clear()
        
        # Update cache dengan item baru
        current_item_ids = set()
        for item in items:
            item_id = item.get("instanceId") or item.get("id")
            if item_id:
                current_item_ids.add(item_id)
                if item_id not in self.item_cache or self.item_cache.get(item_id) != item:
                    self.item_cache[item_id] = item
                    logger.debug(f"📦 Item cached: {item_id[:8]} - {item.get('type', 'unknown')}")
        
        # Hapus item yang sudah tidak ada di view
        removed_items = []
        for cached_id in list(self.item_cache.keys()):
            if cached_id not in current_item_ids:
                if cached_id not in self.collected_items:
                    self.collected_items.add(cached_id)
                removed_items.append(cached_id)
                del self.item_cache[cached_id]
        
        if removed_items:
            logger.debug(f"🗑️ Items removed from cache: {len(removed_items)}")
        
        # Bersihkan attempted_items yang sudah dikoleksi
        self.attempted_items = self.attempted_items - self.collected_items
    
    def _update_ruin_cache(self, view_data: Dict):
        """Update ruin cache dari view (BARU)"""
        region = view_data.get("currentRegion", {})
        interactables = region.get("interactables", [])
        
        for obj in interactables:
            obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
            if "ruin" in obj_type:
                ruin_id = obj.get("id") or obj.get("interactableId")
                if ruin_id:
                    # Update cache
                    self.ruin_cache[ruin_id] = {
                        "id": ruin_id,
                        "gauge": obj.get("gauge", 0),
                        "maxGauge": obj.get("maxGauge", 3),
                        "occupiedBy": obj.get("occupiedBy"),
                        "isEmpty": obj.get("isEmpty", False),
                        "contentType": obj.get("contentType", "unknown"),
                        "position": {"x": obj.get("x", 0), "y": obj.get("y", 0)}
                    }
                    
                    # Jika ruin kosong, tandai sudah diexplore
                    if obj.get("isEmpty", False):
                        self.explored_ruins.add(ruin_id)
                        logger.debug(f"🗺️ Ruin {ruin_id[:8]} cleared")
    
    # ===== ITEM VALIDATION METHODS =====
    
    def get_valid_items(self) -> List[Dict]:
        """Dapatkan item yang VALID dan BELUM DICOBA"""
        items = self.get_items()
        valid_items = []
        me = self.get_self()
        
        if not items:
            logger.debug("📭 No items in current view")
            return []
        
        logger.debug(f"📦 Total items in view: {len(items)}")
        
        for item in items:
            item_id = item.get("instanceId") or item.get("id")
            if not item_id:
                continue
            
            item_type = item.get("type", item.get("itemType", "unknown"))
            logger.debug(f"🔍 Found item: {item_id[:8]} - {item_type}")
            
            if item_id in self.attempted_items:
                logger.debug(f"⏭️ Item {item_id[:8]} already attempted")
                continue
            
            if item_id in self.collected_items:
                logger.debug(f"⏭️ Item {item_id[:8]} already collected")
                continue
            
            distance = self._calculate_distance(me, item)
            
            if distance < 5:
                valid_items.append(item)
                logger.debug(f"✅ Item {item_id[:8]} valid (distance: {distance:.1f})")
            else:
                logger.debug(f"📏 Item {item_id[:8]} too far (distance: {distance:.1f})")
        
        logger.debug(f"📦 Valid items: {len(valid_items)}")
        return valid_items
    
    def get_nearby_items(self, max_distance: float = 3.0) -> List[Dict]:
        """Dapatkan semua item dalam jarak tertentu"""
        items = self.get_items()
        nearby = []
        me = self.get_self()
        
        for item in items:
            item_id = item.get("instanceId") or item.get("id")
            if not item_id:
                continue
            
            distance = self._calculate_distance(me, item)
            if distance <= max_distance:
                nearby.append(item)
                logger.debug(f"📦 Nearby item: {item_id[:8]} - {distance:.1f}m")
        
        return nearby
    
    def get_healing_items(self) -> List[Dict]:
        """Dapatkan item healing dari ground"""
        items = []
        for item in self.get_items():
            heal = float(item.get("heal", item.get("healAmount", 0)))
            if heal > 0:
                items.append(item)
        return items
    
    def get_loot_items(self) -> List[Dict]:
        """Dapatkan item loot (non-healing)"""
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
    
    # ===== INVENTORY METHODS =====
    
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
        items.sort(key=lambda x: float(x.get("heal", x.get("healAmount", 0))), reverse=True)
        return items[0]
    
    def has_healing_items(self) -> bool:
        """Cek apakah ada item healing di inventory"""
        return len(self.get_healing_items_inventory()) > 0
    
    # ===== RUIN & ALERT METHODS (BARU) =====
    
    def update_ruin_state(self, ruin_data: Dict):
        """Update ruin state dari event"""
        ruin_id = ruin_data.get("ruinId")
        if not ruin_id:
            return
        
        self.ruin_cache[ruin_id] = {
            "id": ruin_id,
            "gauge": ruin_data.get("gauge", 0),
            "maxGauge": ruin_data.get("maxGauge", 3),
            "occupiedBy": ruin_data.get("occupiedBy"),
            "isEmpty": ruin_data.get("isEmpty", False),
            "contentType": ruin_data.get("contentType", "unknown")
        }
        
        # Jika ruin kosong, tandai sudah diexplore
        if ruin_data.get("isEmpty", False):
            self.explored_ruins.add(ruin_id)
            logger.debug(f"🗺️ Ruin {ruin_id[:8]} cleared")
    
    def update_alert_gauge(self, alert_data: Dict):
        """Update alert gauge dari event"""
        self.alert_gauge = alert_data.get("alertGauge", 0)
        self.alert_active = alert_data.get("alertActive", False)
        
        if self.alert_active:
            logger.warning(f"⚠️ ALERT ACTIVE! Gauge: {self.alert_gauge}")
        else:
            logger.debug(f"📊 Alert gauge: {self.alert_gauge}")
    
    def get_available_ruins(self) -> List[Dict]:
        """Dapatkan ruins yang tersedia (tidak kosong dan tidak dioccupied)"""
        available = []
        for ruin_id, ruin in self.ruin_cache.items():
            if not ruin.get("isEmpty", True) and not ruin.get("occupiedBy"):
                available.append(ruin)
        return available
    
    def get_best_ruin_to_explore(self) -> Optional[Dict]:
        """Dapatkan ruin terbaik untuk diexplore"""
        available = self.get_available_ruins()
        
        if not available:
            return None
        
        # Prioritaskan relic ruins
        relic_ruins = [r for r in available if r.get("contentType") == "relic"]
        pack_ruins = [r for r in available if r.get("contentType") == "pack"]
        
        # Urutkan berdasarkan gauge (yang sudah tinggi lebih baik)
        relic_ruins.sort(key=lambda r: r.get("gauge", 0), reverse=True)
        pack_ruins.sort(key=lambda r: r.get("gauge", 0), reverse=True)
        
        # Prioritaskan relic ruins
        if relic_ruins:
            logger.debug(f"🗺️ Best ruin: {relic_ruins[0].get('id', 'unknown')[:8]} (relic, gauge: {relic_ruins[0].get('gauge', 0)}/3)")
            return relic_ruins[0]
        elif pack_ruins:
            logger.debug(f"🗺️ Best ruin: {pack_ruins[0].get('id', 'unknown')[:8]} (pack, gauge: {pack_ruins[0].get('gauge', 0)}/3)")
            return pack_ruins[0]
        
        return None
    
    def can_explore_ruin(self) -> bool:
        """Cek apakah aman untuk explore (alert < 8)"""
        safe = self.alert_gauge < 8
        if not safe:
            logger.warning(f"⚠️ Cannot explore: alert gauge too high ({self.alert_gauge})")
        return safe
    
    def can_explore_more(self) -> bool:
        """Cek apakah masih bisa explore tanpa trigger alert"""
        # Explore +2, jika gauge + 2 >= 10 maka akan trigger alert
        return self.alert_gauge + 2 < 10
    
    def get_ruin_explore_count(self, ruin_id: str) -> int:
        """Dapatkan jumlah explore yang sudah dilakukan di ruin"""
        ruin = self.ruin_cache.get(ruin_id, {})
        return ruin.get("gauge", 0)
    
    def get_ruin_by_id(self, ruin_id: str) -> Optional[Dict]:
        """Dapatkan ruin berdasarkan ID"""
        return self.ruin_cache.get(ruin_id)
    
    def get_ruin_position(self, ruin_id: str) -> Dict[str, float]:
        """Dapatkan posisi ruin"""
        ruin = self.ruin_cache.get(ruin_id, {})
        return ruin.get("position", {"x": 0, "y": 0})
    
    def get_ruin_content_type(self, ruin_id: str) -> str:
        """Dapatkan tipe konten ruin"""
        ruin = self.ruin_cache.get(ruin_id, {})
        return ruin.get("contentType", "unknown")
    
    def get_ruin_status(self) -> Dict[str, Any]:
        """Dapatkan status semua ruin"""
        total = len(self.ruin_cache)
        explored = len(self.explored_ruins)
        available = len(self.get_available_ruins())
        
        return {
            "total_ruins": total,
            "explored_ruins": explored,
            "available_ruins": available,
            "relic_ruins": len([r for r in self.ruin_cache.values() if r.get("contentType") == "relic"]),
            "pack_ruins": len([r for r in self.ruin_cache.values() if r.get("contentType") == "pack"]),
            "alert_gauge": self.alert_gauge,
            "alert_active": self.alert_active
        }
    
    # ===== EXISTING METHODS =====
    
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
