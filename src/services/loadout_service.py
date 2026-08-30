# src/services/loadout_service.py
"""Service untuk manajemen loadout dan auto-equip"""

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
            logger.warning(f"Could not get loadout: {e}")
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
            logger.debug(f"Loadout optimization skipped: {e}")
            return {"error": str(e), "changes": []}
    
    # ===== AUTO-EQUIP (BARU) =====
    
    async def auto_equip_best_items(self) -> Dict[str, Any]:
        """
        Auto-equip item terbaik dari inventory
        - Equip weapon terbaik
        - Equip armor terbaik
        - Equip relic terbaik
        - Equip pack terbaik
        """
        try:
            inventory = await self.rest.get_inventory()
            current = await self.get_current_loadout()
            
            result = {
                "changes": [],
                "equipped": [],
                "failed": [],
                "current": current
            }
            
            # 1. Equip weapon terbaik
            best_weapon = self._find_best_weapon(inventory)
            current_weapon = current.get("weapon")
            if best_weapon and best_weapon.get("id") != current_weapon.get("id"):
                try:
                    await self.rest.equip_weapon(best_weapon["id"])
                    result["changes"].append(f"Weapon: {best_weapon.get('name', 'unknown')}")
                    result["equipped"].append(f"Weapon: {best_weapon.get('name', 'unknown')}")
                    logger.info(f"🔧 Equipped weapon: {best_weapon.get('name', 'unknown')}")
                except Exception as e:
                    result["failed"].append(f"Weapon: {e}")
                    logger.warning(f"Failed to equip weapon: {e}")
            
            # 2. Equip armor terbaik
            best_armor = self._find_best_armor(inventory)
            current_armor = current.get("armor")
            if best_armor and best_armor.get("id") != current_armor.get("id"):
                try:
                    await self.rest.equip_armor(best_armor["id"])
                    result["changes"].append(f"Armor: {best_armor.get('name', 'unknown')}")
                    result["equipped"].append(f"Armor: {best_armor.get('name', 'unknown')}")
                    logger.info(f"🔧 Equipped armor: {best_armor.get('name', 'unknown')}")
                except Exception as e:
                    result["failed"].append(f"Armor: {e}")
                    logger.warning(f"Failed to equip armor: {e}")
            
            # 3. Equip relic terbaik (3 slot)
            best_relics = self._find_best_relics(inventory, 3)
            current_relic_ids = [r.get("id") for r in current.get("relics", [])]
            for relic in best_relics:
                if relic.get("id") not in current_relic_ids:
                    try:
                        await self.rest.equip_relic(relic["id"])
                        result["changes"].append(f"Relic: {relic.get('name', 'unknown')}")
                        result["equipped"].append(f"Relic: {relic.get('name', 'unknown')}")
                        logger.info(f"🔧 Equipped relic: {relic.get('name', 'unknown')}")
                    except Exception as e:
                        result["failed"].append(f"Relic: {e}")
                        logger.warning(f"Failed to equip relic: {e}")
            
            # 4. Equip pack (Main + Sub)
            best_main = self._find_best_pack(inventory, "main")
            best_sub = self._find_best_pack(inventory, "sub")
            
            if best_main and best_main.get("id") != current.get("mainPack", {}).get("id"):
                try:
                    await self.rest.equip_main_pack(best_main["id"])
                    result["changes"].append(f"Main Pack: {best_main.get('name', 'unknown')}")
                    result["equipped"].append(f"Main Pack: {best_main.get('name', 'unknown')}")
                    logger.info(f"🔧 Equipped main pack: {best_main.get('name', 'unknown')}")
                except Exception as e:
                    result["failed"].append(f"Main Pack: {e}")
                    logger.warning(f"Failed to equip main pack: {e}")
            
            if best_sub and best_sub.get("id") != current.get("subPack", {}).get("id"):
                try:
                    await self.rest.equip_sub_pack(best_sub["id"])
                    result["changes"].append(f"Sub Pack: {best_sub.get('name', 'unknown')}")
                    result["equipped"].append(f"Sub Pack: {best_sub.get('name', 'unknown')}")
                    logger.info(f"🔧 Equipped sub pack: {best_sub.get('name', 'unknown')}")
                except Exception as e:
                    result["failed"].append(f"Sub Pack: {e}")
                    logger.warning(f"Failed to equip sub pack: {e}")
            
            self._current_loadout = None
            await self.get_current_loadout()
            
            if result["changes"]:
                logger.info(f"✅ Auto-equipped: {', '.join(result['changes'])}")
            else:
                logger.info("✅ All items already optimal")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to auto-equip: {e}")
            return {"error": str(e), "changes": []}
    
    def _find_best_weapon(self, inventory: Dict) -> Optional[Dict]:
        """Cari weapon terbaik dari inventory"""
        items = inventory.get("items", [])
        weapons = []
        
        for item in items:
            item_type = str(item.get("type", item.get("itemType", ""))).lower()
            # Cek apakah item adalah weapon
            if any(k in item_type for k in ["weapon", "sword", "bow", "dagger", "axe", "staff", "gun"]):
                # Hitung score berdasarkan stats
                score = 0
                stats = item.get("stats", {})
                score += stats.get("atk", 0) * 2
                score += stats.get("crit", 0) * 3
                score += stats.get("range", 0) * 1.5
                score += stats.get("attack", 0) * 2
                score += item.get("tier", 0) * 10
                score += item.get("rarity", 0) * 5
                
                weapons.append({
                    "item": item,
                    "score": score,
                    "name": item.get("name", item.get("type", "unknown"))
                })
        
        if not weapons:
            return None
        
        weapons.sort(key=lambda x: x["score"], reverse=True)
        logger.debug(f"Best weapon: {weapons[0]['name']} (score: {weapons[0]['score']})")
        return weapons[0]["item"]
    
    def _find_best_armor(self, inventory: Dict) -> Optional[Dict]:
        """Cari armor terbaik dari inventory"""
        items = inventory.get("items", [])
        armors = []
        
        for item in items:
            item_type = str(item.get("type", item.get("itemType", ""))).lower()
            # Cek apakah item adalah armor
            if any(k in item_type for k in ["armor", "shield", "helmet", "chest", "boots", "gloves", "cloak"]):
                # Hitung score berdasarkan stats
                score = 0
                stats = item.get("stats", {})
                score += stats.get("def", 0) * 2
                score += stats.get("hp", 0) * 0.5
                score += stats.get("defense", 0) * 2
                score += stats.get("maxHp", 0) * 0.5
                score += item.get("tier", 0) * 10
                score += item.get("rarity", 0) * 5
                
                armors.append({
                    "item": item,
                    "score": score,
                    "name": item.get("name", item.get("type", "unknown"))
                })
        
        if not armors:
            return None
        
        armors.sort(key=lambda x: x["score"], reverse=True)
        logger.debug(f"Best armor: {armors[0]['name']} (score: {armors[0]['score']})")
        return armors[0]["item"]
    
    def _find_best_pack(self, inventory: Dict, slot: str) -> Optional[Dict]:
        """Cari pack terbaik untuk slot tertentu"""
        packs = inventory.get("packs", [])
        slot_packs = []
        
        for p in packs:
            # Cek apakah pack bisa di slot ini
            if p.get("slot") == slot or slot in p.get("canEquipIn", []):
                # Hitung score
                score = 0
                score += p.get("tier", 0) * 100
                stats = p.get("stats", {})
                score += stats.get("atk", 0) * 2
                score += stats.get("def", 0) * 1.5
                score += stats.get("maxHp", 0) * 0.5
                score += stats.get("attack", 0) * 2
                score += stats.get("defense", 0) * 1.5
                score += p.get("rarity", 0) * 10
                
                slot_packs.append({
                    "item": p,
                    "score": score,
                    "name": p.get("name", p.get("type", "unknown"))
                })
        
        if not slot_packs:
            return None
        
        slot_packs.sort(key=lambda x: x["score"], reverse=True)
        logger.debug(f"Best {slot} pack: {slot_packs[0]['name']} (score: {slot_packs[0]['score']})")
        return slot_packs[0]["item"]
    
    def _find_best_relics(self, inventory: Dict, count: int) -> List[Dict]:
        """Cari relic terbaik dari inventory"""
        relics = inventory.get("relics", [])
        relic_scores = []
        
        for r in relics:
            score = 0
            score += r.get("tier", 0) * 100
            score += r.get("rarity", 0) * 10
            
            # Hitung affixes
            affixes = r.get("affixes", [])
            for affix in affixes:
                value = affix.get("value", 0)
                affix_type = str(affix.get("type", "")).upper()
                
                # Bobot berdasarkan tipe affix
                if affix_type in ["ATK", "ATTACK", "DMG", "DAMAGE"]:
                    score += value * 2
                elif affix_type in ["DEF", "DEFENSE", "ARMOR"]:
                    score += value * 1.5
                elif affix_type in ["HP", "MAXHP", "HEALTH"]:
                    score += value * 0.5
                elif affix_type in ["CRIT", "CRITICAL"]:
                    score += value * 3
                elif affix_type in ["SPEED", "MOVEMENT"]:
                    score += value * 1
                else:
                    score += value * 0.5
            
            relic_scores.append({
                "item": r,
                "score": score,
                "name": r.get("name", r.get("type", "unknown"))
            })
        
        relic_scores.sort(key=lambda x: x["score"], reverse=True)
        best_relics = [r["item"] for r in relic_scores[:count]]
        
        if best_relics:
            logger.debug(f"Best relics: {[r.get('name', 'unknown') for r in best_relics]}")
        
        return best_relics
    
    # ===== GET INVENTORY =====
    
    async def get_best_weapon(self) -> Optional[Dict]:
        """Dapatkan weapon terbaik di inventory"""
        try:
            inventory = await self.rest.get_inventory()
            return self._find_best_weapon(inventory)
        except Exception as e:
            logger.warning(f"Failed to get best weapon: {e}")
            return None
    
    async def get_best_armor(self) -> Optional[Dict]:
        """Dapatkan armor terbaik di inventory"""
        try:
            inventory = await self.rest.get_inventory()
            return self._find_best_armor(inventory)
        except Exception as e:
            logger.warning(f"Failed to get best armor: {e}")
            return None
    
    async def get_best_relics(self, count: int = 3) -> List[Dict]:
        """Dapatkan relic terbaik di inventory"""
        try:
            inventory = await self.rest.get_inventory()
            return self._find_best_relics(inventory, count)
        except Exception as e:
            logger.warning(f"Failed to get best relics: {e}")
            return []
    
    async def get_best_pack(self, slot: str = "main") -> Optional[Dict]:
        """Dapatkan pack terbaik untuk slot tertentu"""
        try:
            inventory = await self.rest.get_inventory()
            return self._find_best_pack(inventory, slot)
        except Exception as e:
            logger.warning(f"Failed to get best pack for {slot}: {e}")
            return None
    
    async def get_inventory_summary(self) -> Dict[str, Any]:
        """Dapatkan summary inventory"""
        try:
            inventory = await self.rest.get_inventory()
            
            return {
                "total_items": len(inventory.get("items", [])),
                "total_packs": len(inventory.get("packs", [])),
                "total_relics": len(inventory.get("relics", [])),
                "best_weapon": await self.get_best_weapon(),
                "best_armor": await self.get_best_armor(),
                "best_relics": await self.get_best_relics(3),
                "best_main_pack": await self.get_best_pack("main"),
                "best_sub_pack": await self.get_best_pack("sub")
            }
        except Exception as e:
            logger.warning(f"Failed to get inventory summary: {e}")
            return {}
