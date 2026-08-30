# src/services/auth_service.py
"""Service untuk authentication dan login"""

import logging
from typing import Dict, Any, Optional

from ..client.rest_client import RestClient
from ..client.ws_client import WSClient
from ..core.constants import JOIN_WS
from ..core.exceptions import AuthenticationError, AgentTokenRequiredError

logger = logging.getLogger(__name__)

class AuthService:
    """Service untuk authentication"""
    
    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
        self._account: Optional[Dict] = None
        self._agent_token: Optional[str] = None
    
    async def login(self) -> Dict[str, Any]:
        """
        Login ke Claw Royale
        Berdasarkan skill.md: Gunakan API key untuk autentikasi
        """
        logger.info("🔐 Logging in to Claw Royale...")
        
        # 1. Get account info
        self._account = await self.rest.get_account()
        
        if not self._account:
            raise AuthenticationError("Failed to get account info")
        
        logger.info(f"✅ Logged in as: {self._account.get('name')}")
        logger.info(f"   Account ID: {self._account.get('id')}")
        logger.info(f"   Wallet: {self._account.get('walletAddress')}")
        
        # 2. Check readiness
        readiness = self._account.get("readiness", {})
        logger.info(f"📊 Readiness:")
        logger.info(f"   - Wallet: {readiness.get('walletAddress')}")
        logger.info(f"   - Whitelist: {readiness.get('whitelistApproved')}")
        logger.info(f"   - Agent Token: {readiness.get('agentToken')}")
        logger.info(f"   - sMoltz: {readiness.get('sMoltzSufficient')}")
        
        # 3. Ensure agent token
        if not readiness.get("agentToken"):
            logger.info("🔑 Agent token missing, registering...")
            await self.rest.ensure_agent_token()
            # Re-fetch account
            self._account = await self.rest.get_account()
        
        return self._account
    
    async def get_websocket_auth(self) -> Dict[str, str]:
        """
        Dapatkan headers untuk WebSocket authentication
        Berdasarkan skill.md: Authorization: mr-auth <APIKey>
        """
        return {
            "Authorization": f"mr-auth {self.rest.api_key}",
            "X-Version": self.rest.version or "1.15.0"
        }
    
    async def join_game_websocket(self, entry_type: str = "free") -> WSClient:
        """
        Join game via WebSocket
        Berdasarkan skill.md: wss://cdn.clawroyale.ai/ws/join
        """
        logger.info(f"🎮 Joining {entry_type} game via WebSocket...")
        
        headers = await self.get_websocket_auth()
        
        try:
            # Connect dengan auth headers
            ws = WSClient(self.rest.api_key, self.rest.version)
            
            # Connect manual dengan headers
            import websockets
            connection = await websockets.connect(
                JOIN_WS,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5
            )
            ws._ws = connection
            
            # Baca welcome frame
            import json
            welcome = json.loads(await connection.recv())
            decision = welcome.get("decision")
            logger.info(f"📨 Welcome decision: {decision}")
            
            # Kirim hello frame
            hello = {"type": "hello", "entryType": entry_type}
            if entry_type == "paid":
                hello["mode"] = "offchain"
            
            await connection.send(json.dumps(hello))
            logger.info(f"📤 Sent hello: {entry_type}")
            
            return ws
            
        except Exception as e:
            logger.error(f"❌ Failed to join game: {e}")
            raise
    
    async def wait_for_game_assignment(self, ws: WSClient, entry_type: str = "free") -> Optional[Dict]:
        """
        Tunggu assignment game
        Berdasarkan skill.md: queued → assigned/joined
        """
        import json
        
        while True:
            try:
                msg = json.loads(await ws.recv())
                msg_type = msg.get("type")
                
                if msg_type in ("assigned", "joined"):
                    logger.info(f"✅ {msg_type} to game {msg.get('gameId')}")
                    return msg
                
                elif msg_type == "not_selected":
                    logger.warning("❌ Not selected for game")
                    return None
                
                elif msg_type == "queued":
                    logger.info("⏳ Queued, waiting for match...")
                    continue
                
                elif msg_type == "waiting":
                    logger.info("⏳ Waiting for game...")
                    continue
                
                elif msg_type == "error":
                    error = msg.get("error", {})
                    code = error.get("code")
                    message = error.get("message", "")
                    logger.error(f"❌ Server error: {code} - {message}")
                    
                    if code == "AGENT_TOKEN_REQUIRED":
                        raise AgentTokenRequiredError("Agent token required!")
                    if code == "BLOCKED":
                        logger.warning("⛔ Account blocked")
                    
                    return None
                
                else:
                    logger.debug(f"📨 Unknown message: {msg_type}")
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Error waiting for assignment: {e}")
                return None
    
    def get_account(self) -> Optional[Dict]:
        """Dapatkan data akun yang sedang login"""
        return self._account
    
    def is_logged_in(self) -> bool:
        """Cek apakah sudah login"""
        return self._account is not None