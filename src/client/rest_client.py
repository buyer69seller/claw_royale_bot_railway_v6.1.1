# src/client/rest_client.py
import aiohttp
import json
import logging
from typing import Optional, Dict, Any

from ..core.constants import BASE_API
from ..core.exceptions import AuthenticationError, VersionMismatchError, ClawRoyaleError

logger = logging.getLogger(__name__)

class RestClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._version: Optional[str] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
    
    @property
    def version(self) -> str:
        return self._version or "1.15.0"  # Default version
    
    async def get_version(self) -> str:
        """Dapatkan versi API terbaru"""
        async with self._get("/version") as resp:
            data = await resp.json()
            self._version = data.get("version") or data.get("data", {}).get("version")
            return self._version
    
    # src/client/rest_client.py - tambahkan logging di get_account

async def get_account(self) -> Dict[str, Any]:
    """Dapatkan data akun"""
    logger.info("📡 Fetching account data...")
    try:
        result = await self._request("GET", "/accounts/me")
        logger.info(f"✅ Account data received: {result.keys() if result else 'empty'}")
        return result
    except Exception as e:
        logger.error(f"❌ Failed to get account: {e}")
        return {}
    
    async def get_dashboard_games(self, limit: int = 10, cursor: Optional[str] = None) -> Dict:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/accounts/me/dashboard/games", params=params)
    
    async def redeem_code(self, code: str) -> Dict:
        return await self._request("POST", "/redeem", json={"code": code})
    
    # ===== LOADOUT =====
    
    async def get_loadout(self) -> Dict[str, Any]:
        return await self._request("GET", "/accounts/me/loadout")
    
    async def equip_main_pack(self, pack_id: str) -> Dict:
        return await self._request("POST", "/accounts/me/loadout/main", json={"packId": pack_id})
    
    async def equip_sub_pack(self, pack_id: str) -> Dict:
        return await self._request("POST", "/accounts/me/loadout/sub", json={"packId": pack_id})
    
    async def equip_relic(self, relic_id: str) -> Dict:
        return await self._request("POST", "/accounts/me/loadout/relics", json={"relicId": relic_id})
    
    async def unequip_relic(self, relic_id: str) -> Dict:
        return await self._request("DELETE", f"/accounts/me/loadout/relics/{relic_id}")
    
    async def get_inventory(self) -> Dict[str, Any]:
        return await self._request("GET", "/accounts/me/inventory")
    
    # ===== REWARD =====
    
    async def get_dashboard_overview(self) -> Dict[str, Any]:
        return await self._request("GET", "/accounts/me/dashboard/overview")
    
    async def claim_quest(self, quest_key: str, tier: int) -> Dict:
        return await self._request("POST", f"/api/quests/{quest_key}/claim/{tier}")
    
    async def claim_daily(self) -> Dict:
        return await self._request("POST", "/api/daily-quests/claim")
    
    # ===== MARKETPLACE =====
    
    async def get_marketplace_listings(self, filters: Dict = None) -> Dict[str, Any]:
        params = filters or {}
        return await self._request("GET", "/api/marketplace/listings", params=params)
    
    async def buy_marketplace_listing(self, listing_id: str) -> Dict:
        return await self._request("POST", f"/api/marketplace/listings/{listing_id}/buy")
    
    async def _request(self, method: str, path: str, **kwargs) -> Dict:
        if not self._session:
            raise RuntimeError("Session not initialized.")
        
        url = f"{BASE_API}{path}"
        headers = {
            "Authorization": f"mr-auth {self.api_key}",
            "X-Version": self._version or "1.15.0"  # <-- Kirim version
        }
        
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        
        try:
            async with self._session.request(method, url, headers=headers, **kwargs) as resp:
                if resp.status == 426:
                    error_data = await resp.text()
                    logger.error(f"Version mismatch: {error_data}")
                    raise VersionMismatchError(f"Version mismatch: {error_data}")
                if resp.status == 401:
                    raise AuthenticationError("Invalid API key")
                if resp.status == 404:
                    logger.debug(f"Endpoint not found: {path}")
                    return {}
                
                resp.raise_for_status()
                data = await resp.json()
                
                if not data.get("success", True):
                    error = data.get("error", {})
                    raise ClawRoyaleError(f"API Error: {error.get('code')} - {error.get('message')}")
                
                return data.get("data", {})
        except aiohttp.ClientError as e:
            logger.warning(f"Request failed: {e}")
            return {}
    
    def _get(self, path: str, **kwargs):
        return self._session.get(f"{BASE_API}{path}", headers=self._default_headers, **kwargs)
    
    @property
    def _default_headers(self) -> Dict:
        return {
            "Authorization": f"mr-auth {self.api_key}",
            "X-Version": self._version or "1.15.0"
        }
