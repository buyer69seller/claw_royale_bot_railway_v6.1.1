# src/lifecycle/router.py
import logging
from typing import Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)

class GameState(str, Enum):
    NO_ACCOUNT = "NO_ACCOUNT"
    READY_FREE = "READY_FREE"
    READY_PAID = "READY_PAID"
    IN_GAME_FREE = "IN_GAME_FREE"
    IN_GAME_PAID = "IN_GAME_PAID"
    ERROR = "ERROR"
    IDLE = "IDLE"

class StateRouter:
    def __init__(self, rest_client):
        self.rest = rest_client
        self.current_state = GameState.IDLE
        self.live_games: Dict[str, Dict] = {}
    
    async def determine_state(self) -> GameState:
        try:
            account = await self.rest.get_account()
            
            readiness = account.get("readiness", {})
            current_games = account.get("currentGames", [])
            
            # Log readiness issues
            if not readiness.get("agentToken"):
                logger.info("ℹ️ No agent token - will try to join via WebSocket")
            if not readiness.get("sMoltzSufficient"):
                logger.info("ℹ️ Insufficient sMoltz - will try free games")
            
            self.live_games = {}
            for game in current_games:
                entry_type = game.get("entryType")
                if entry_type and game.get("isAlive") and game.get("gameStatus") != "finished":
                    self.live_games[entry_type] = game
            
            # Cek game live
            if "free" in self.live_games:
                logger.info("✅ Free game live, resuming...")
                return GameState.IN_GAME_FREE
            if "paid" in self.live_games:
                logger.info("✅ Paid game live, resuming...")
                return GameState.IN_GAME_PAID
            
            # Cek readiness
            free_ready = readiness.get("free", {}).get("ready", False)
            paid_ready = readiness.get("paid", {}).get("ready", False)
            
            # Jika tidak ready, tetap coba join via WebSocket
            if not free_ready and not paid_ready:
                logger.info("🔄 No readiness - attempting direct WebSocket join...")
                # Coba join free game via WebSocket
                return GameState.READY_FREE
            
            if free_ready:
                logger.info("✅ Free game ready, starting...")
                return GameState.READY_FREE
            if paid_ready:
                logger.info("✅ Paid game ready, starting...")
                return GameState.READY_PAID
            
            logger.info("⏳ No game available, idle...")
            return GameState.IDLE
            
        except Exception as e:
            logger.error(f"❌ Failed to determine state: {e}")
            return GameState.ERROR
    
    async def resolve_state(self) -> Dict[str, Any]:
        state = await self.determine_state()
        self.current_state = state
        
        # Default ke free jika tidak ada state
        if state in [GameState.READY_FREE, GameState.IN_GAME_FREE]:
            entry_type = "free"
        elif state in [GameState.READY_PAID, GameState.IN_GAME_PAID]:
            entry_type = "paid"
        else:
            # Default ke free
            entry_type = "free"
            if state == GameState.IDLE:
                logger.info("🔄 Forcing join attempt for free game...")
                state = GameState.READY_FREE
        
        return {
            "state": state,
            "entry_type": entry_type,
            "action": self._get_action_for_state(state),
            "game": self.live_games.get(entry_type)
        }
    
    def _get_action_for_state(self, state: GameState) -> str:
        action_map = {
            GameState.READY_FREE: "start_free",
            GameState.READY_PAID: "start_paid",
            GameState.IN_GAME_FREE: "resume_free",
            GameState.IN_GAME_PAID: "resume_paid",
            GameState.IDLE: "idle",
            GameState.ERROR: "error",
            GameState.NO_ACCOUNT: "setup_account"
        }
        return action_map.get(state, "idle")
