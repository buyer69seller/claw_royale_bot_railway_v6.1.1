# src/services/loadout_service.py
"""Service untuk manajemen loadout dengan Pre-Season 1 support"""

import logging
from typing import Dict, Any, Optional, List

from ..client.rest_client import RestClient
from ..core.constants import MAIN_ONLY_PACKS, SUB_CAPABLE_PACKS, PACK_EFFECTS

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
    
    # ===== PACK VALIDATION =====
    
    def is_main_only(self, pack_name: str) -> bool:
        """Cek apakah pack hanya bisa di Main slot"""
        if not pack_name:
            return False
        return pack_name in MAIN_ONLY_PACKS
    
    def is_sub_capable(self, pack_name: str) -> bool:
        """Cek apakah pack bisa di Sub slot"""
        if not pack_name:
            return False
        return pack_name in SUB_CAPABLE_PACKS
    
    def can_equip_in_slot(self, pack_name: str, slot: str) -> bool:
        """Cek apakah pack bisa di-equip di slot tertentu"""
        if slot == "main":
            return True  # Semua pack bisa di Main
        elif slot == "sub":
            return self.is_sub_capable(pack_name)
        return False
    
    def get_pack_effect(self, pack_name: str, slot: str = "main") -> Optional[Dict]:
        """Dapatkan efek pack berdasarkan slot"""
        effects = PACK_EFFECTS.get(pack_name)
        if not effects:
            return None
        
        if slot == "main":
            return effects.get("main")
        else:  # sub
            return effects.get("sub")
    
    def get_pack_tier_effect(self, pack_name: str, tier: int, slot: str = "main") -> Optional[Dict]:
        """Dapatkan efek pack berdasarkan tier dan slot"""
        # Tier-specific effects based on Pre-Season 1 doc
        tier_effects = {
            "Moltz Expert": {
                1: {"high": 12, "middle": 8, "low": 4},
                2: {"high": 9, "middle": 6, "low": 3},
                3: {"high": 6, "middle": 4, "low": 2}
            },
            "Item Expert": {
                1: {"coef": 2.0},
                2: {"coef": 1.5},
                3: {"coef": 1.0}
            },
            "Goliath": {
                1: {"atkMultiplier": 0.85},
                2: {"atkMultiplier": 0.75},
                3: {"atkMultiplier": 0.65}
            },
            "Thorns": {
                1: {"dmgTakenReduction": 0.50, "reflect": 1.0},
                2: {"dmgTakenReduction": 0.45, "reflect": 0.95},
                3: {"dmgTakenReduction": 0.40, "reflect": 0.90}
            },
            "Scout": {
                1: {"vision": 2, "move_ep_discount": 2, "dmgMultiplier": 0.8},
                2: {"vision": 2, "move_ep_discount": 1, "dmgMultiplier": 0.7},
                3: {"vision": 1, "move_ep_discount": 0, "dmgMultiplier": 0.6}
            },
            "Ruin Expert": {
                1: {"guardianDmgMultiplier": 1.5},
                2: {"guardianDmgMultiplier": 2.0},
                3: {"guardianDmgMultiplier": 2.5}
            },
            "Berserker": {
                1: {"dmgMultiplier": 1.7},
                2: {"dmgMultiplier": 1.5},
                3: {"dmgMultiplier": 1.3}
            },
            "Double Attack": {
                1: {"hitMultiplier": 0.65},
                2: {"hitMultiplier": 0.55},
                3: {"hitMultiplier": 0.5}
            },
            "Heart of the Giant": {
                1: {"healBonusFromMaxHp": 0.75, "selfHeal": 0.03},
                2: {"healBonusFromMaxHp": 0.50, "selfHeal": 0.02},
                3: {"healBonusFromMaxHp": 0.25, "selfHeal": 0.01}
            },
            "Bomber": {
                1: {"bombCount": 3, "atkMultiplier": 0.2},
                2: {"bombCount": 2, "atkMultiplier": 0.15},
                3: {"bombCount": 1, "atkMultiplier": 0.10}
            },
            "Trail Ward": {
                1: {"wards": 3},
                2: {"wards": 2},
                3: {"wards": 1}
            },
            "Ranged": {
                1: {"dmgIncrease": 0.15},
                2: {"dmgIncrease": 0.10},
                3: {"dmgIncrease": 0.05}
            },
            "Sword Master": {
                1: {"itemAtkMultiplier": 1.0},
                2: {"itemAtkMultiplier": 0.75},
                3: {"itemAtkMultiplier": 0.5}
            },
            "Duelist": {
                1: {"soloAtkBonus": 0.9, "soloDefBonus": 0.9},
                2: {"soloAtkBonus": 0.7, "soloDefBonus": 0.7},
                3: {"soloAtkBonus": 0.5, "soloDefBonus": 0.5}
            },
            "Last Stand": {
                1: {"hpRegenBonus": 5.0, "berserkTurns": 3},
                2: {"hpRegenBonus": 4.0, "berserkTurns": 2},
                3: {"hpRegenBonus": 3.0, "berserkTurns": 1}
            },
            "Iron Heart": {
                1: {"dmgMultiplier": 0.90},
                2: {"dmgMultiplier": 0.80},
                3: {"dmgMultiplier": 0.70}
            },
            "Sunflame Cloak": {
                1: {"auraDmg": 1.0},
                2: {"auraDmg": 0.8},
                3: {"auraDmg": 0.6}
            },
            "Assassin": {
                1: {"bonusDmgMultiplier": 0.6},
                2: {"bonusDmgMultiplier": 0.5},
                3: {"bonusDmgMultiplier": 0.4}
            },
            "Pickpocket": {
                1: {"stealAmount": 3},
                2: {"stealAmount": 2},
                3: {"stealAmount": 1}
            }
        }
        
        pack_tiers = tier_effects.get(pack_name, {})
        return pack_tiers.get(tier)
    
    def get_pack_description(self, pack_name: str) -> str:
        """Dapatkan deskripsi pack"""
        effects = PACK_EFFECTS.get(pack_name, {})
        return effects.get("description", f"{pack_name} pack")
    
    # ===== PACK EVALUATION =====
    
    def evaluate_pack(self, pack: Dict, slot: str = "main") -> float:
        """Evaluasi nilai pack untuk slot tertentu"""
        pack_name = pack.get("name", "")
        tier = pack.get("tier", 0)
        
        # Base score dari tier
        score = tier * 30
        
        # Slot compatibility
        if slot == "sub" and not self.is_sub_capable(pack_name):
            return -999  # Tidak bisa di Sub
        
        # Bonus untuk pack yang bagus di slot
        if slot == "main":
            if pack_name in ["Thorns", "Berserker", "Assassin", "Scout"]:
                score += 20
        else:  # sub
            if pack_name in ["Item Expert", "Heart of the Giant", "Ruin Expert"]:
                score += 15
        
        # Sub attenuation penalty
        if slot == "sub":
            score *= 0.7
        
        return score
    
    def evaluate_pack_synergy(self, main_pack: Dict, sub_pack: Dict) -> float:
        """Evaluasi sinergi antara main dan sub pack"""
        main_name = main_pack.get("name", "")
        sub_name = sub_pack.get("name", "")
        
        if not main_name or not sub_name:
            return 0
        
        if main_name == sub_name:
            return -100  # Tidak boleh sama
        
        score = 0
        
        # Synergy pairs berdasarkan Pre-Season 1
        synergies = [
            # (pack1, pack2, bonus, description)
            ("Thorns", "Heart of the Giant", 35, "Thorns + Heart = Ultimate Survival"),
            ("Berserker", "Last Stand", 30, "Berserker + Last Stand = Clutch King"),
            ("Item Expert", "Moltz Expert", 25, "Item Expert + Moltz Expert = Economy"),
            ("Goliath", "Double Attack", 20, "Goliath + Double Attack = AoE Damage"),
            ("Ranged", "Sword Master", 15, "Ranged + Sword Master = Versatile"),
            ("Assassin", "Pickpocket", 20, "Assassin + Pickpocket = Stealth Thief"),
            ("Ruin Expert", "Scout", 15, "Ruin Expert + Scout = Explorer"),
            ("Sunflame Cloak", "Thorns", 15, "Sunflame + Thorns = Defensive Aura"),
            ("Iron Heart", "Heart of the Giant", 20, "Iron Heart + Heart = Tank"),
            ("Duelist", "Berserker", 15, "Duelist + Berserker = 1v1 Monster"),
        ]
        
        for pack1, pack2, bonus, desc in synergies:
            if (pack1 in main_name and pack2 in sub_name) or (pack1 in sub_name and pack2 in main_name):
                score += bonus
                logger.debug(f"🔗 Synergy found: {desc}")
        
        # Tier match bonus
        main_tier = main_pack.get("tier", 0)
        sub_tier = sub_pack.get("tier", 0)
        if main_tier == sub_tier:
            score += 10  # Same tier bonus
        
        return score
    
    def get_pack_recommendation(self, pack_name: str, slot: str = "main") -> str:
        """Dapatkan rekomendasi penggunaan pack"""
        recommendations = {
            "Thorns": "Best defensive pack - use Main for max damage reduction",
            "Heart of the Giant": "Best healing pack - use Main for max heal bonus",
            "Berserker": "Best damage pack - use Main for max damage boost",
            "Last Stand": "Best clutch pack - use Main for 3-turn berserk",
            "Assassin": "Best stealth pack - Main only",
            "Scout": "Best vision pack - Main only",
            "Item Expert": "Best economy pack - use Sub for economy",
            "Moltz Expert": "Best Moltz conversion - use Sub for conversion",
            "Ruin Expert": "Best ruin farming - Main or Sub same effect",
            "Double Attack": "Best multi-hit - Main for max damage",
            "Goliath": "Best AoE - Main for max AoE damage",
            "Ranged": "Best ranged - Main for max damage",
            "Sword Master": "Best melee - Main for max item ATK"
        }
        
        return recommendations.get(pack_name, "Balanced pack - use according to strategy")
    
    # ===== LOADOUT OPTIMIZATION =====
    
    async def get_best_pack_combo(self) -> Dict[str, Any]:
        """Dapatkan kombinasi pack terbaik berdasarkan sinergi"""
        try:
            inventory = await self.rest.get_inventory()
            packs = inventory.get("packs", [])
            
            if not packs:
                logger.warning("No packs available in inventory")
                return {"main": None, "sub": None, "score": 0, "relics": []}
            
            # Filter pack berdasarkan kategori
            main_candidates = []
            sub_candidates = []
            
            for pack in packs:
                pack_name = pack.get("name", "")
                # Semua pack bisa di Main
                main_candidates.append(pack)
                
                # Cek apakah bisa di Sub
                if self.is_sub_capable(pack_name):
                    sub_candidates.append(pack)
            
            # Evaluasi semua kombinasi
            best_combo = {
                "main": None,
                "sub": None,
                "score": -999,
                "relics": [],
                "synergy_details": ""
            }
            
            for main in main_candidates:
                for sub in sub_candidates:
                    if main.get("id") == sub.get("id"):
                        continue  # Tidak bisa sama
                    
                    # Evaluasi
                    main_score = self.evaluate_pack(main, "main")
                    sub_score = self.evaluate_pack(sub, "sub")
                    synergy_score = self.evaluate_pack_synergy(main, sub)
                    
                    total_score = main_score + sub_score + synergy_score
                    
                    if total_score > best_combo["score"]:
                        best_combo["main"] = main
                        best_combo["sub"] = sub
                        best_combo["score"] = total_score
                        best_combo["synergy_details"] = f"{main.get('name')} + {sub.get('name')} = {synergy_score:.0f} synergy"
            
            # Dapatkan relics terbaik
            relics = inventory.get("relics", [])
            best_relics = sorted(relics, key=lambda r: self._relic_score(r), reverse=True)[:3]
            best_combo["relics"] = best_relics
            
            return best_combo
            
        except Exception as e:
            logger.error(f"Failed to get best pack combo: {e}")
            return {"main": None, "sub": None, "score": 0, "relics": []}
    
    def _relic_score(self, relic: Dict) -> float:
        """Skor untuk relic"""
        try:
            tier = relic.get("tier", 0)
            affixes = relic.get("affixes", [])
            
            score = tier * 50
            
            # Affix bonus
            for affix in affixes:
                affix_type = affix.get("type", "")
                value = affix.get("value", 0)
                
                if affix_type in ["ATK", "DMG"]:
                    score += value * 3
                elif affix_type in ["HP", "DEF"]:
                    score += value * 2
                elif affix_type == "Item ATK":
                    score += value * 2.5
                elif affix_type == "Explore":
                    score += value * 1.5
                elif affix_type == "Heal":
                    score += value * 2
            
            return score
        except Exception as e:
            logger.debug(f"Relic score error: {e}")
            return 0
    
    async def optimize_loadout(self) -> Dict[str, Any]:
        """Optimasi loadout dengan Pre-Season 1 logic"""
        try:
            # Dapatkan kombinasi terbaik
            best = await self.get_best_pack_combo()
            current = await self.get_current_loadout()
            
            result = {
                "changes": [],
                "errors": [],
                "current": current,
                "suggested": best,
                "synergy": best.get("synergy_details", "")
            }
            
            # Equip main pack
            if best["main"]:
                main_id = best["main"].get("id")
                main_name = best["main"].get("name", "unknown")
                main_tier = best["main"].get("tier", 0)
                
                if main_id and main_id != current.get("mainPack", {}).get("id"):
                    await self.rest.equip_main_pack(main_id)
                    result["changes"].append(f"Main: {main_name} (T{main_tier})")
            
            # Equip sub pack
            if best["sub"]:
                sub_id = best["sub"].get("id")
                sub_name = best["sub"].get("name", "unknown")
                sub_tier = best["sub"].get("tier", 0)
                
                if sub_id and sub_id != current.get("subPack", {}).get("id"):
                    await self.rest.equip_sub_pack(sub_id)
                    result["changes"].append(f"Sub: {sub_name} (T{sub_tier})")
            
            # Equip relics
            current_relic_ids = [r.get("id") for r in current.get("relics", [])]
            for relic in best["relics"]:
                relic_id = relic.get("id")
                relic_tier = relic.get("tier", 0)
                relic_name = relic.get("name", "unknown")
                
                if relic_id and relic_id not in current_relic_ids:
                    await self.rest.equip_relic(relic_id)
                    result["changes"].append(f"Relic: T{relic_tier} ({relic_name})")
            
            # Clear cache
            self._current_loadout = None
            await self.get_current_loadout()
            
            # Log synergy score
            logger.info(f"📊 Pack synergy score: {best['score']:.0f}")
            if best.get("synergy_details"):
                logger.info(f"🔗 {best['synergy_details']}")
            
            return result
            
        except Exception as e:
            logger.warning(f"Loadout optimization skipped: {e}")
            return {"error": str(e), "changes": []}
