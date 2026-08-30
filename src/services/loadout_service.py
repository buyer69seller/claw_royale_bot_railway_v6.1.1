# src/services/loadout_service.py
"""Service untuk manajemen loadout"""

import logging
from typing import Dict, Any, Optional, List

from ..client.rest_client import RestClient

logger = logging.getLogger(__name__)

class LoadoutService:
    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
        self._current_loadout = None
    
    async def get_current_loadout(self) -> Dict[str, Any]:
        if self._current_loadout:
            return self._current_loadout
        try:
            loadout = await self.rest.get_loadout()
            self._current_loadout = loadout
            return loadout
        except Exception as e:
            logger.error(f"Failed to get loadout: {e}")
            return {}
    
    async def is_full_set(self) -> bool:
        loadout = await self.get_current_loadout()
        has_main = bool(loadout.get("mainPack"))
        has_sub = bool(loadout.get("subPack"))
        relics = loadout.get("relics", [])
        return has_main and has_sub and len(relics) >= 3
    
    async def optimize_loadout(self) -> Dict[str, Any]:
        try:
            inventory = await self.rest.get_inventory()
            current = await self.get_current_loadout()
            
            best_main = self._find_best_pack(inventory, "main")
            best_sub = self._find_best_pack(inventory, "sub")
            best_relics = self._find_best_relics(inventory, 3)
            
            result = {"changes": [], "current": current, "suggested": {
                "mainPack": best_main, "subPack": best_sub, "relics": best_relics
            }}
            
            if best_main and best_main.get("id") != current.get("mainPack", {}).get("id"):
                await self.rest.equip_main_pack(best_main["id"])
                result["changes"].append(f"Main: {best_main.get('name')}")
            
            if best_sub and best_sub.get("id") != current.get("subPack", {}).get("id"):
                await self.rest.equip_sub_pack(best_sub["id"])
                result["changes"].append(f"Sub: {best_sub.get('name')}")
            
            current_relic_ids = [r.get("id") for r in current.get("relics", [])]
            for relic in best_relics:
                if relic.get("id") not in current_relic_ids:
                    await self.rest.equip_relic(relic["id"])
                    result["changes"].append(f"Relic: {relic.get('name')}")
            
            self._current_loadout = None
            await self.get_current_loadout()
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to optimize loadout: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def _find_best_pack(inventory: Dict, slot: str) -> Optional[Dict]:
        packs = inventory.get("packs", [])
        slot_packs = [p for p in packs if p.get("slot") == slot or slot in p.get("canEquipIn", [])]
        if not slot_packs:
            return None
        return max(slot_packs, key=lambda p: p.get("tier", 0) * 100 + sum(p.get("stats", {}).values()) * 2)
    
    @staticmethod
    def _find_best_relics(inventory: Dict, count: int) -> List[Dict]:
        relics = inventory.get("relics", [])
        sorted_relics = sorted(relics, key=lambda r: r.get("tier", 0) * 100 + sum(a.get("value", 0) for a in r.get("affixes", [])), reverse=True)
        return sorted_relics[:count]