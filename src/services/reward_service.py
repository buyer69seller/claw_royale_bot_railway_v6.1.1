# src/services/reward_service.py
import logging
from typing import Dict, Any

from ..client.rest_client import RestClient
from ..core.exceptions import ClawRoyaleError

logger = logging.getLogger(__name__)

class RewardService:
    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
        self._redeemed_codes = set()
    
    async def redeem_welcome_bundle(self) -> bool:
        try:
            if "WELCOME" in self._redeemed_codes:
                return False
            
            # PERBAIKI: redeem code dengan path yang benar
            result = await self.rest.redeem_code("WELCOME")
            logger.info(f"🎁 Welcome bundle claimed!")
            self._redeemed_codes.add("WELCOME")
            return True
            
        except ClawRoyaleError as e:
            if "already redeemed" in str(e).lower() or "already claimed" in str(e).lower():
                self._redeemed_codes.add("WELCOME")
                logger.info("Welcome bundle already claimed")
                return False
            logger.error(f"Failed to redeem WELCOME: {e}")
            return False
        except Exception as e:
            logger.warning(f"Welcome bundle not available: {e}")
            return False
    
    async def check_and_claim_rewards(self) -> Dict[str, Any]:
        results = {"claimed": [], "failed": [], "total": 0}
        
        try:
            overview = await self.rest.get_dashboard_overview()
            
            for quest in overview.get("quests", []):
                if quest.get("canClaim"):
                    try:
                        await self.rest.claim_quest(quest.get("key"), quest.get("tier"))
                        results["claimed"].append(f"Quest: {quest.get('key')}")
                        results["total"] += 1
                        logger.info(f"Claimed quest: {quest.get('key')}")
                    except Exception as e:
                        results["failed"].append(f"Quest: {quest.get('key')} - {e}")
            
            daily = overview.get("daily", {})
            if daily.get("canClaim"):
                try:
                    await self.rest.claim_daily()
                    results["claimed"].append("Daily reward")
                    results["total"] += 1
                    logger.info("Claimed daily reward")
                except Exception as e:
                    results["failed"].append(f"Daily reward - {e}")
            
            return results
            
        except Exception as e:
            logger.warning(f"Failed to check rewards: {e}")
            return results
    
    async def get_available_rewards(self) -> Dict[str, Any]:
        try:
            overview = await self.rest.get_dashboard_overview()
            available = {"quests": [], "daily": False, "season": False}
            
            for quest in overview.get("quests", []):
                if quest.get("canClaim"):
                    available["quests"].append({"key": quest.get("key"), "tier": quest.get("tier")})
            
            available["daily"] = overview.get("daily", {}).get("canClaim", False)
            available["season"] = overview.get("season", {}).get("canClaim", False)
            
            return available
            
        except Exception as e:
            logger.warning(f"Failed to get available rewards: {e}")
            return {"quests": [], "daily": False, "season": False}
