# src/services/loadout_service.py
"""Service untuk manajemen loadout dengan Pre-Season 1 support"""

import logging
from typing import Dict, Any, Optional, List

from ..client.rest_client import RestClient
from ..core.constants import (
    MAIN_ONLY_PACKS,
    SUB_CAPABLE_PACKS,
    PACK_EFFECTS,
    RELIC_AFFIX_PRIORITY,
    RELIC_SLOTS,
    INVENTORY_CAPS
)

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
    
    def is_main_only(self, pack_name: str) -> bool:
        return pack_name in MAIN_ONLY_PACKS
    
    def is_sub_capable(self, pack_name: str) -> bool:
        return pack_name in SUB_CAPABLE_PACKS
    
    def get_pack_effect(self, pack_name: str, slot: str = "main") -> Optional[Dict]:
        effects = PACK_EFFECTS.get(pack_name)
        if not effects:
            return None
        if slot == "main":
            return effects.get("main")
        else:
            return effects.get("sub")
    
    async def get_best_pack_combo(self) -> Dict[str, Any]:
        inventory = await self.rest.get_inventory()
        packs = inventory.get("packs", [])
        
        main_packs = [p for p in packs if self.is_sub_capable(p.get("name", "")) or self.is_main_only(p.get("name", ""))]
        sub_packs = [p for p in packs if self.is_sub_capable(p.get("name", ""))]
        
        best_combo = {
            "main": None,
            "sub": None,
            "score": 0,
            "relics": []
        }
        
        for main in main_packs:
            for sub in sub_packs:
                if main.get("name") == sub.get("name"):
                    continue
                score = self._evaluate_synergy(main, sub)
                if score > best_combo["score"]:
                    best_combo["main"] = main
                    best_combo["sub"] = sub
                    best_combo["score"] = score
        
        relics = inventory.get("relics", [])
        best_relics = await self.get_best_relics(3)
        best_combo["relics"] = best_relics
        
        return best_combo
    
    def _evaluate_synergy(self, main: Dict, sub: Dict) -> float:
        main_name = main.get("name", "")
        sub_name = sub.get("name", "")
        score = 0
        
        score += main.get("tier", 0) * 20
        score += sub.get("tier", 0) * 15
        
        synergies = [
            ("Thorns", "Heart of the Giant", 30),
            ("Berserker", "Last Stand", 25),
            ("Item Expert", "Moltz Expert", 20),
            ("Goliath", "Double Attack", 15),
            ("Ranged", "Sword Master", 10),
            ("Assassin", "Pickpocket", 15),
            ("Ruin Expert", "Scout", 10),
        ]
        
        for pack1, pack2, bonus in synergies:
            if (pack1 in main_name and pack2 in sub_name) or (pack1 in sub_name and pack2 in main_name):
                score += bonus
        
        return score
    
    # ===== RELIC SELECTION (BARU) =====
    
    async def get_best_relics(self, count: int = 3) -> List[Dict]:
        """
        Dapatkan relic terbaik dari inventory
        Berdasarkan Pre-S1 relic system
        """
        inventory = await self.rest.get_inventory()
        relics = inventory.get("relics", [])
        
        if not relics:
            logger.info("📭 No relics found in inventory")
            return []
        
        # Skor setiap relic
        scored_relics = []
        for relic in relics:
            score = self._score_relic(relic)
            slot = self._get_relic_slot(relic)
            scored_relics.append({
                "relic": relic,
                "score": score,
                "slot": slot,
                "affix_count": len(relic.get("affixes", []))
            })
        
        # Sort by score (descending)
        scored_relics.sort(key=lambda x: (x["score"], x["affix_count"]), reverse=True)
        
        # Ambil top N
        best = scored_relics[:count]
        
        # Log selected relics
        for i, r in enumerate(best):
            relic = r["relic"]
            affixes = relic.get("affixes", [])
            affix_names = [a.get("stat", "") for a in affixes]
            logger.info(f"🔮 Relic {i+1}: {relic.get('name', 'unknown')} "
                       f"(score: {r['score']:.0f}, affixes: {affix_names})")
        
        return [r["relic"] for r in best]
    
    def _score_relic(self, relic: Dict) -> float:
        """
        Skor relic berdasarkan affixes
        Pre-S1: 0-3 affixes, same stat can stack
        """
        affixes = relic.get("affixes", [])
        tier = relic.get("tier", 0)
        
        # Tier bonus (T1 > T2 > T3)
        score = tier * 10
        
        # Affix scoring
        for affix in affixes:
            stat = affix.get("stat", "")
            value = affix.get("value", 0)
            
            # Prioritaskan positive affixes
            priority = RELIC_AFFIX_PRIORITY.get(stat, 1)
            
            # Value multiplier
            if value > 0:
                score += value * priority * 1.5  # Bonus untuk positive
            else:
                score += value * priority * 0.5  # Penalti untuk negative
        
        # Bonus untuk relic dengan banyak affixes
        affix_count = len(affixes)
        if affix_count >= 3:
            score *= 1.3
        elif affix_count >= 2:
            score *= 1.15
        
        return max(score, -100)  # Minimum score -100
    
    def _get_relic_slot(self, relic: Dict) -> int:
        """
        Dapatkan slot relic berdasarkan tipe
        Ruby → slot 0, Emerald → slot 1, Sapphire → slot 2
        """
        name = relic.get("name", "")
        for gem_name, slot in RELIC_SLOTS.items():
            if gem_name in name:
                return slot
        return 0  # Default slot 0
    
    def _get_relic_display_name(self, relic: Dict) -> str:
        """
        Dapatkan display name relic
        Format: Ferocious Sturdy Ruby (affixes + gem name)
        """
        name = relic.get("name", "Unknown")
        affixes = relic.get("affixes", [])
        
        if not affixes:
            return name
        
        # Get positive affix names
        affix_names = []
        for affix in affixes:
            stat = affix.get("stat", "")
            value = affix.get("value", 0)
            
            # Cari display name dari constants
            from ..core.constants import RELIC_AFFIXES
            affix_data = RELIC_AFFIXES.get(stat)
            if affix_data:
                if value >= 0:
                    affix_names.append(affix_data["positive"]["name"])
                else:
                    affix_names.append(affix_data["negative"]["name"])
        
        return " ".join(affix_names + [name])
    
    # ===== RELIC FARMING STRATEGY =====
    
    def get_relic_farming_priority(self, current_relics: List[Dict]) -> Dict[str, Any]:
        """
        Dapatkan prioritas farming relic
        Berdasarkan relic yang sudah dimiliki
        """
        if not current_relics:
            return {
                "priority": "high",
                "reason": "No relics equipped",
                "target_slots": [0, 1, 2]
            }
        
        # Cek slot yang kosong
        equipped_slots = set()
        for relic in current_relics:
            slot = self._get_relic_slot(relic)
            equipped_slots.add(slot)
        
        missing_slots = [s for s in range(3) if s not in equipped_slots]
        
        if missing_slots:
            return {
                "priority": "high",
                "reason": f"Missing slots: {missing_slots}",
                "target_slots": missing_slots
            }
        
        # Cek kualitas relic
        avg_score = sum(self._score_relic(r) for r in current_relics) / max(len(current_relics), 1)
        
        if avg_score < 30:
            return {
                "priority": "medium",
                "reason": f"Low quality relics (avg score: {avg_score:.0f})",
                "target_slots": [0, 1, 2]
            }
        
        return {
            "priority": "low",
            "reason": f"Good relics equipped (avg score: {avg_score:.0f})",
            "target_slots": []
        }
    
    # ===== INVENTORY MANAGEMENT =====
    
    async def get_inventory_status(self) -> Dict[str, Any]:
        """
        Dapatkan status inventory
        Termasuk caps dan usage
        """
        inventory = await self.rest.get_inventory()
        
        relics = inventory.get("relics", [])
        packs = inventory.get("packs", [])
        items = inventory.get("items", [])
        
        return {
            "relics": {
                "count": len(relics),
                "cap": INVENTORY_CAPS["lobby_relics"],
                "remaining": INVENTORY_CAPS["lobby_relics"] - len(relics),
                "items": relics
            },
            "packs": {
                "count": len(packs),
                "cap": INVENTORY_CAPS["lobby_packs"],
                "remaining": INVENTORY_CAPS["lobby_packs"] - len(packs),
                "items": packs
            },
            "items": {
                "count": len(items),
                "cap": INVENTORY_CAPS["items"],
                "remaining": INVENTORY_CAPS["items"] - len(items),
                "items": items
            }
        }
    
    async def optimize_loadout(self) -> Dict[str, Any]:
        """Optimasi loadout dengan Pre-Season 1 logic"""
        try:
            best = await self.get_best_pack_combo()
            current = await self.get_current_loadout()
            
            result = {"changes": [], "current": current, "suggested": best}
            
            # Equip main pack
            if best["main"] and best["main"].get("id") != current.get("mainPack", {}).get("id"):
                await self.rest.equip_main_pack(best["main"]["id"])
                result["changes"].append(f"Main: {best['main'].get('name')} (T{best['main'].get('tier', 0)})")
            
            # Equip sub pack
            if best["sub"] and best["sub"].get("id") != current.get("subPack", {}).get("id"):
                await self.rest.equip_sub_pack(best["sub"]["id"])
                result["changes"].append(f"Sub: {best['sub'].get('name')} (T{best['sub'].get('tier', 0)})")
            
            # Equip relics
            current_relic_ids = [r.get("id") for r in current.get("relics", [])]
            for relic in best["relics"]:
                if relic.get("id") not in current_relic_ids:
                    # Cek slot
                    slot = self._get_relic_slot(relic)
                    await self.rest.equip_relic(relic["id"])
                    display_name = self._get_relic_display_name(relic)
                    result["changes"].append(f"Relic slot {slot}: {display_name}")
            
            self._current_loadout = None
            await self.get_current_loadout()
            
            logger.info(f"📊 Pack synergy score: {best['score']:.0f}")
            
            # Log relic summary
            relic_scores = [self._score_relic(r) for r in best.get("relics", [])]
            if relic_scores:
                logger.info(f"🔮 Relic scores: {relic_scores}")
            
            return result
            
        except Exception as e:
            logger.debug(f"Loadout optimization skipped: {e}")
            return {"error": str(e), "changes": []}
