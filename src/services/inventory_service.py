# src/services/inventory_service.py
"""Service untuk manajemen inventory"""

import logging
from typing import Dict, Any, Optional, List

from ..client.rest_client import RestClient

logger = logging.getLogger(__name__)

class InventoryService:
    """Service untuk inventory management"""
    
    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
        self._inventory_cache = None
    
    async def get_inventory(self) -> Dict[str, Any]:
        """Dapatkan inventory dari API"""
        try:
            if self._inventory_cache:
                return self._inventory_cache
            
            inventory = await self.rest.get_inventory()
            self._inventory_cache = inventory
            return inventory
        except Exception as e:
            logger.warning(f"Failed to get inventory: {e}")
            return {}
    
    async def get_healing_items(self) -> List[Dict]:
        """Dapatkan item healing dari inventory"""
        inventory = await self.get_inventory()
        items = inventory.get("items", [])
        healing_items = []
        
        for item in items:
            heal = float(item.get("heal", item.get("healAmount", 0)))
            if heal > 0:
                healing_items.append(item)
        
        return healing_items
    
    async def get_best_equipment(self) -> Dict[str, Optional[Dict]]:
        """Dapatkan equipment terbaik dari inventory"""
        inventory = await self.get_inventory()
        items = inventory.get("items", [])
        
        best_weapon = None
        best_armor = None
        best_relics = []
        
        for item in items:
            item_type = str(item.get("type", item.get("itemType", ""))).lower()
            
            if "weapon" in item_type:
                if not best_weapon or item.get("atk", 0) > best_weapon.get("atk", 0):
                    best_weapon = item
            
            elif "armor" in item_type:
                if not best_armor or item.get("def", 0) > best_armor.get("def", 0):
                    best_armor = item
            
            elif "relic" in item_type:
                best_relics.append(item)
        
        # Sort relics by tier
        best_relics.sort(key=lambda x: x.get("tier", 0), reverse=True)
        
        return {
            "weapon": best_weapon,
            "armor": best_armor,
            "relics": best_relics[:3]  # Max 3 relics
        }
    
    async def auto_equip_best(self) -> Dict[str, Any]:
        """Auto equip item terbaik dari inventory"""
        result = {"changes": [], "errors": []}
        
        try:
            best = await self.get_best_equipment()
            
            # Equip weapon
            if best.get("weapon"):
                try:
                    await self.rest.equip_main_pack(best["weapon"].get("id"))
                    result["changes"].append(f"Weapon: {best['weapon'].get('name', 'unknown')}")
                except Exception as e:
                    result["errors"].append(f"Weapon: {e}")
            
            # Equip armor
            if best.get("armor"):
                try:
                    await self.rest.equip_sub_pack(best["armor"].get("id"))
                    result["changes"].append(f"Armor: {best['armor'].get('name', 'unknown')}")
                except Exception as e:
                    result["errors"].append(f"Armor: {e}")
            
            # Equip relics
            for relic in best.get("relics", []):
                try:
                    await self.rest.equip_relic(relic.get("id"))
                    result["changes"].append(f"Relic: {relic.get('name', 'unknown')}")
                except Exception as e:
                    result["errors"].append(f"Relic: {e}")
            
            # Clear cache
            self._inventory_cache = None
            
        except Exception as e:
            result["errors"].append(f"Auto-equip failed: {e}")
        
        return result
    
    def clear_cache(self):
        """Clear inventory cache"""
        self._inventory_cache = None