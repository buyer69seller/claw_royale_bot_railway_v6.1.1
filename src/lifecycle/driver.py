# src/lifecycle/driver.py
"""Driver utama dengan Hybrid AI (AI Auto-Pilot + Competitive v7) + RL + Region Tracking"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any, Set

from websockets.exceptions import ConnectionClosed

from ..client.rest_client import RestClient
from ..client.ws_client import WSClient
from ..game.state import GameState
from ..game.actions import ActionBuilder
from ..strategy.engine import StrategyEngine
from .router import StateRouter
from .version_manager import VersionManager
from ..core.exceptions import (
    AgentDeadError,
    ResumeTargetDeadError,
    NotSelectedError,
    AgentTokenRequiredError
)
from ..core.constants import (
    MIN_RETRY_DELAY,
    MAX_RETRY_DELAY,
    RETRY_BACKOFF_MULTIPLIER,
    JOIN_WS,
    ACTION_INTERVAL_SECONDS
)
from ..ai.hybrid_engine import HybridAIEngine
from ..ai.knowledge import KnowledgeBase

logger = logging.getLogger(__name__)


class Driver:
    """Driver utama bot dengan Hybrid AI + RL + Region Tracking"""

    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
        self.router = StateRouter(rest_client)
        self.version_mgr = VersionManager(rest_client.api_key)

        # Hybrid AI Engine
        self.ai = HybridAIEngine()
        self.knowledge: Optional[KnowledgeBase] = None
        self.auth_service = None

        # Fallback strategy (heuristic)
        self.strategy = StrategyEngine()
        self._pack_modifiers_loaded = False

        # ===== STRATEGY MODE =====
        self.strategy_mode = "hybrid"
        self.scan_clear = None

        # Game state
        self.current_game: Optional[GameState] = None
        self.delay = MIN_RETRY_DELAY
        self.game_count = 0
        self.ai_enabled = True

        # Performance tracking
        self.start_time = None
        self.total_actions = 0
        self.successful_actions = 0
        
        # Rate limit tracking
        self._last_action_time = 0
        
        # ===== RL TRACKING =====
        self._rl_action_tracking: Dict[str, Any] = {
            "action": None,
            "state": None,
            "timestamp": 0,
            "success": False
        }
        self._rl_reward_buffer = []
        
        # ===== REGION TRACKING =====
        self._visited_regions: Set[str] = set()
        self._region_visit_count: Dict[str, int] = {}
        self._current_region_id: Optional[str] = None
        self._region_loop_detected: bool = False

    def set_strategy_mode(self, mode: str):
        """Set strategy mode: 'hybrid' atau 'scan_clear'"""
        if mode in ["hybrid", "scan_clear"]:
            self.strategy_mode = mode
            logger.info(f"🔄 Strategy mode changed to: {mode}")
            if mode == "scan_clear":
                from ..strategy.scan_clear import ScanClearStrategy
                self.scan_clear = ScanClearStrategy()
                self.scan_clear.reset()
            else:
                self.scan_clear = None
        else:
            logger.warning(f"⚠️ Unknown strategy mode: {mode}, keeping current")

    async def run(self):
        """Loop utama driver"""
        logger.info("🚀 Driver run() started!")
        self.delay = MIN_RETRY_DELAY
        self.start_time = __import__('time').time()
        logger.info(f"⏰ Start time: {self.start_time}")

        loop_count = 0

        while True:
            loop_count += 1
            logger.info(f"🔄 Driver loop iteration #{loop_count}")

            try:
                # Update version
                logger.info("📥 Checking version...")
                await self.version_mgr.ensure_current(self.rest._session)
                logger.info(f"✅ Version: {self.version_mgr.version}")

                # Determine state
                logger.info("🔍 Determining game state...")
                state_info = await self.router.resolve_state()
                logger.info(f"📊 State: {state_info['state']} -> {state_info['action']}")

                # Execute based on state
                if state_info["action"] in ["start_free", "start_paid"]:
                    logger.info(f"🎮 Attempting to join game: {state_info['action']}")
                    await self._start_game(state_info["entry_type"])
                elif state_info["action"] in ["resume_free", "resume_paid"]:
                    logger.info(f"🔄 Attempting to resume game: {state_info['action']}")
                    await self._resume_game(state_info["entry_type"])
                elif state_info["action"] == "idle":
                    logger.info("⏳ Idle, waiting for game...")
                    await asyncio.sleep(5)
                elif state_info["action"] == "error":
                    logger.warning("⚠️ Error state, waiting...")
                    await asyncio.sleep(10)
                else:
                    logger.warning(f"⚠️ Unknown action: {state_info['action']}")
                    await asyncio.sleep(2)

                self.delay = MIN_RETRY_DELAY

            except ResumeTargetDeadError as e:
                logger.warning(f"🔄 Resume target dead: {e}, re-dialing...")
                await asyncio.sleep(1)
                self.delay = MIN_RETRY_DELAY
                continue

            except ConnectionClosed as e:
                logger.warning(f"🔌 WebSocket closed: {e.code} - {e.reason}")
                
                if e.code == 1013:
                    logger.info("🔄 Resume target dead, starting new game...")
                    self.current_game = None
                    self._reset_region_tracking()
                    await asyncio.sleep(2)
                    continue
                elif e.code == 4008:
                    logger.warning("⏳ Rate limited, waiting 10s...")
                    await asyncio.sleep(10)
                    self.delay = MIN_RETRY_DELAY
                    continue
                elif e.code in (4030, 4031):
                    logger.info("🔄 Agent in game or game full, retrying...")
                    await asyncio.sleep(3)
                    continue
                elif e.code == 4032:
                    logger.info("💀 Agent dead (from close code), restarting...")
                    self.current_game = None
                    self._reset_region_tracking()
                    await asyncio.sleep(2)
                    continue
                else:
                    if e.code in (1013, 4008, 4030, 4031):
                        await asyncio.sleep(3)
                    else:
                        await asyncio.sleep(self.delay)
                        self.delay = min(self.delay * RETRY_BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)

            except AgentDeadError:
                logger.info("💀 Agent died, restarting...")
                if self.current_game and self.knowledge:
                    self.knowledge.record_outcome("death", {
                        "kills": self.current_game.kills,
                        "survival_time": self.current_game.survival_time
                    })
                self.current_game = None
                self.strategy.reset_rejection_counter()
                self.ai.stats = {
                    "decisions_made": 0,
                    "ai_decisions": 0,
                    "heuristic_decisions": 0,
                    "survival_priority": 0,
                    "kill_priority": 0,
                    "loot_priority": 0,
                    "explore_priority": 0
                }
                self._stuck_counter = 0
                self._last_hp = 0
                self._last_turn = 0
                self._reset_region_tracking()
                await asyncio.sleep(1)
                self.delay = MIN_RETRY_DELAY
                logger.info("🔄 Rejoining new game...")
                continue

            except NotSelectedError:
                logger.info("❌ Not selected, retrying...")
                await asyncio.sleep(2)
                self.delay = MIN_RETRY_DELAY

            except AgentTokenRequiredError:
                logger.warning("🔑 Agent token required! Trying to register...")
                if self.auth_service:
                    await self.auth_service.rest.ensure_agent_token()
                await asyncio.sleep(2)
                self.delay = MIN_RETRY_DELAY

            except Exception as e:
                logger.exception(f"💥 Driver error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(self.delay)
                self.delay = min(self.delay * RETRY_BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)

    def _reset_region_tracking(self):
        """Reset region tracking untuk game baru"""
        self._visited_regions.clear()
        self._region_visit_count.clear()
        self._current_region_id = None
        self._region_loop_detected = False
        logger.debug("🗺️ Region tracking reset for new game")

    def _track_region(self, region_id: str):
        """Track region yang dikunjungi"""
        if not region_id:
            return
        
        self._visited_regions.add(region_id)
        self._region_visit_count[region_id] = self._region_visit_count.get(region_id, 0) + 1
        self._current_region_id = region_id
        
        visit_count = self._region_visit_count[region_id]
        if visit_count > 3:
            self._region_loop_detected = True
            logger.warning(f"⚠️ Region {region_id[:8]} visited {visit_count}x - possible loop!")
        else:
            self._region_loop_detected = False

    async def _load_pack_modifiers(self):
        """Load pack modifiers dari loadout untuk strategy"""
        try:
            loadout = await self.rest.get_loadout()
            main_pack = loadout.get("mainPack", {})
            sub_pack = loadout.get("subPack", {})
            
            self.strategy.set_pack_modifiers(main_pack, sub_pack)
            self._pack_modifiers_loaded = True
            
            if main_pack:
                logger.info(f"📦 Main Pack: {main_pack.get('name', 'unknown')} (T{main_pack.get('tier', 0)})")
            if sub_pack:
                logger.info(f"📦 Sub Pack: {sub_pack.get('name', 'unknown')} (T{sub_pack.get('tier', 0)})")
            
            relics = loadout.get("relics", [])
            logger.info(f"📦 Relics: {len(relics)} equipped")
            
            return True
            
        except Exception as e:
            logger.debug(f"Failed to load pack modifiers: {e}")
            self._pack_modifiers_loaded = False
            return False

    async def _start_game(self, entry_type: str):
        """Mulai game baru - reset semua tracking"""
        logger.info(f"🎮 Joining {entry_type} game...")
        logger.info(f"🔑 API Key: {self.rest.api_key[:10]}...")
        
        self._reset_region_tracking()
        logger.info("🗺️ Region tracking reset for new game")

        try:
            await self._load_pack_modifiers()
            
            if not self.auth_service:
                from ..services.auth_service import AuthService
                self.auth_service = AuthService(self.rest)
                logger.info("✅ Auth service initialized")

            headers = await self.auth_service.get_websocket_auth()
            logger.info(f"📨 Headers: {headers}")

            import websockets
            import json
            from ..core.constants import JOIN_WS

            logger.info(f"🔗 Connecting to {JOIN_WS}...")

            connection = await websockets.connect(
                JOIN_WS,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5
            )
            logger.info("✅ WebSocket connected!")

            welcome = json.loads(await connection.recv())
            decision = welcome.get("decision")
            logger.info(f"📨 Welcome decision: {decision}")

            hello = {"type": "hello", "entryType": entry_type}
            if entry_type == "paid":
                hello["mode"] = "offchain"
            await connection.send(json.dumps(hello))
            logger.info(f"📤 Sent hello: {entry_type}")

            while True:
                msg = json.loads(await connection.recv())
                msg_type = msg.get("type")
                logger.info(f"📨 Received: {msg_type}")

                if msg_type in ("assigned", "joined"):
                    self.current_game = GameState(entry_type=entry_type)
                    self.current_game.game_id = msg.get("gameId")
                    self.game_count += 1
                    logger.info(f"✅ {msg_type} to game {self.current_game.game_id}")

                    ws = WSClient(self.rest.api_key, self.rest.version)
                    ws._ws = connection

                    await self._play_game(ws)
                    return

                elif msg_type == "not_selected":
                    logger.warning("❌ Not selected for game")
                    await asyncio.sleep(2)
                    return

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
                        logger.warning("⛔ Account blocked - check API key")
                        await asyncio.sleep(5)
                        return

                    raise RuntimeError(f"Error from server: {msg}")

                else:
                    logger.debug(f"📨 Unknown message: {msg_type}")

        except Exception as e:
            logger.error(f"❌ Failed to join game: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def _resume_game(self, entry_type: str):
        """Resume game yang sedang berjalan"""
        logger.info(f"🔄 Resuming {entry_type} game...")
        
        try:
            await self._load_pack_modifiers()
        except Exception as e:
            logger.debug(f"Failed to load pack modifiers: {e}")
        
        try:
            await self._start_game(entry_type)
        except ResumeTargetDeadError:
            logger.info(f"{entry_type} resume target dead, re-dialing...")
            raise
        except Exception as e:
            logger.error(f"Failed to resume game: {e}")
            raise

    async def _rejoin_game(self, entry_type: str):
        """REJOIN: Kembali ke game yang sedang berjalan"""
        logger.info(f"🔄 Attempting to REJOIN {entry_type} game...")
        
        try:
            await self._load_pack_modifiers()
        except Exception as e:
            logger.debug(f"Failed to load pack modifiers: {e}")
        
        try:
            account = await self.rest.get_account()
            current_games = account.get("currentGames", [])
            
            live_game = None
            for game in current_games:
                if game.get("entryType") == entry_type and game.get("isAlive") and game.get("gameStatus") != "finished":
                    live_game = game
                    break
            
            if not live_game:
                logger.info("ℹ️ No live game found, starting new game...")
                await self._start_game(entry_type)
                return
            
            logger.info(f"✅ Found live game: {live_game.get('gameId')}")
            logger.info(f"   - Entry Type: {live_game.get('entryType')}")
            logger.info(f"   - Is Alive: {live_game.get('isAlive')}")
            logger.info(f"   - Status: {live_game.get('gameStatus')}")
            
            if not self.auth_service:
                from ..services.auth_service import AuthService
                self.auth_service = AuthService(self.rest)
            
            headers = await self.auth_service.get_websocket_auth()
            
            import websockets
            import json
            from ..core.constants import JOIN_WS
            
            logger.info(f"🔗 Reconnecting to {JOIN_WS}...")
            
            connection = await websockets.connect(
                JOIN_WS,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5
            )
            logger.info("✅ WebSocket reconnected!")
            
            welcome = json.loads(await connection.recv())
            decision = welcome.get("decision")
            logger.info(f"📨 Welcome decision: {decision}")
            
            hello = {"type": "hello", "entryType": entry_type}
            if entry_type == "paid":
                hello["mode"] = "offchain"
            await connection.send(json.dumps(hello))
            logger.info(f"📤 Sent hello: {entry_type}")
            
            while True:
                msg = json.loads(await connection.recv())
                msg_type = msg.get("type")
                logger.info(f"📨 Received: {msg_type}")
                
                if msg_type in ("assigned", "joined"):
                    self.current_game = GameState(entry_type=entry_type)
                    self.current_game.game_id = msg.get("gameId")
                    logger.info(f"✅ REJOIN success! {msg_type} to game {self.current_game.game_id}")
                    
                    ws = WSClient(self.rest.api_key, self.rest.version)
                    ws._ws = connection
                    
                    await self._play_game(ws)
                    return
                    
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
                    
                    if code == "GAME_NOT_FOUND":
                        logger.info("ℹ️ Game not found, starting new game...")
                        await self._start_game(entry_type)
                        return
                    
                    raise RuntimeError(f"Error from server: {msg}")
                    
                else:
                    logger.debug(f"📨 Unknown message: {msg_type}")
                    
        except Exception as e:
            logger.error(f"❌ Failed to rejoin game: {e}")
            logger.info("🔄 Falling back to new game...")
            await self._start_game(entry_type)

    async def _play_game(self, ws: WSClient):
        """Loop gameplay - Fokus deteksi kematian via meta.youDied"""
        logger.info("🎮 Starting Hybrid AI-powered gameplay loop...")
        logger.info("🧠 Hybrid AI = AI Auto-Pilot + Competitive v7")
        logger.info("👻 Only detecting OWN death via meta.youDied")
        logger.info("💀 When you died → restart → join new game")

        last_action_time = __import__('time').time()
        no_action_timeout = 120
        last_view_time = __import__('time').time()
        view_timeout = 90
        stuck_counter = 0
        last_hp = 0
        last_turn = 0
        
        last_ping_time = __import__('time').time()
        ping_interval = 30

        while True:
            try:
                current_time = __import__('time').time()
                if current_time - last_ping_time > ping_interval:
                    try:
                        await ws.send({"type": "ping"})
                        last_ping_time = current_time
                        logger.debug("📤 Sent ping")
                    except Exception as e:
                        logger.debug(f"Ping failed: {e}")

                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                msg_type = msg.get("type")

                if msg_type in ("agent_view", "turn_advanced", "action_sync"):
                    last_view_time = __import__('time').time()

                current_time = __import__('time').time()
                if current_time - last_view_time > view_timeout:
                    logger.warning(f"⏰ No view for {view_timeout}s, attempting REJOIN...")
                    try:
                        if self.current_game:
                            entry_type = self.current_game.entry_type
                            await self._rejoin_game(entry_type)
                            return
                        else:
                            await self._start_game("free")
                            return
                    except Exception as e:
                        logger.error(f"❌ Rejoin failed: {e}")
                        raise AgentDeadError(f"View timeout - rejoin failed: {e}")

                # =============================================================
                # DETEKSI KEMATIAN DIRI SENDIRI
                # =============================================================
                if msg_type == "agent_died":
                    if msg.get("meta", {}).get("youDied") is True:
                        self.current_game.mark_dead()
                        if self.knowledge:
                            self.knowledge.record_outcome("death", {
                                "kills": self.current_game.kills,
                                "survival_time": self.current_game.survival_time
                            })
                        logger.info(f"💀 YOU DIED! Survival: {self.current_game.survival_time}, Kills: {self.current_game.kills}")
                        logger.info("🔄 Restarting and joining new game...")
                        raise AgentDeadError("You died!")
                    continue

                # =============================================================
                # GAME SELESAI
                # =============================================================
                if msg_type == "game_settled":
                    self.current_game.mark_finished()
                    winners = msg.get("winners", [])
                    logger.info(f"🏆 Game settled! Winners: {len(winners)}")
                    if self.knowledge:
                        self.knowledge.record_outcome("win", {
                            "kills": self.current_game.kills,
                            "survival_time": self.current_game.survival_time
                        })
                    self._log_hybrid_stats()
                    break

                if msg_type == "game_ended":
                    self.current_game.mark_finished()
                    placement = msg.get("placement")
                    logger.info(f"🏆 Game ended! Placement: {placement}")
                    if self.knowledge and placement and placement <= 5:
                        self.knowledge.record_outcome("win", {
                            "kills": self.current_game.kills,
                            "survival_time": self.current_game.survival_time
                        })
                    self._log_hybrid_stats()
                    break

                # ===== CAN_ACT =====
                if msg_type == "can_act_changed":
                    self.current_game.can_act = bool(msg.get("canAct"))
                    if self.current_game.can_act:
                        last_action_time = current_time
                    continue

                # ===== AGENT_VIEW =====
                if msg_type in ("agent_view", "turn_advanced"):
                    view = msg.get("view", {})
                    reason = msg.get("reason", "sync")

                    if view:
                        self.current_game.update_view(view, reason)

                        if not self.current_game.is_alive:
                            logger.info(f"💀 Agent is dead (from view), restarting...")
                            if self.knowledge:
                                self.knowledge.record_outcome("death", {
                                    "kills": self.current_game.kills,
                                    "survival_time": self.current_game.survival_time
                                })
                            raise AgentDeadError("Agent dead (from view)")
                        
                        if self.current_game.hp <= 0:
                            logger.info(f"💀 Agent HP is 0, restarting...")
                            if self.knowledge:
                                self.knowledge.record_outcome("death", {
                                    "kills": self.current_game.kills,
                                    "survival_time": self.current_game.survival_time
                                })
                            raise AgentDeadError("Agent HP is 0")

                        if last_hp == self.current_game.hp and last_turn == self.current_game.turn:
                            stuck_counter += 1
                            if stuck_counter > 10:
                                logger.warning(f"⚠️ Game stuck for {stuck_counter} turns, attempting rejoin...")
                                try:
                                    await self._rejoin_game(self.current_game.entry_type)
                                    return
                                except Exception as e:
                                    logger.error(f"❌ Rejoin on stuck failed: {e}")
                                    raise AgentDeadError("Game stuck - rejoin failed")
                        else:
                            stuck_counter = 0
                        last_hp = self.current_game.hp
                        last_turn = self.current_game.turn

                        can_act = msg.get("canAct", self.current_game.can_act)
                        await self._act(ws, can_act)

                        if can_act:
                            last_action_time = current_time
                    continue

                # ===== ACTION_SYNC =====
                if msg_type == "action_sync":
                    view = msg.get("view", {})
                    if view:
                        self.current_game.update_view(view, "action_sync")
                        if not self.current_game.is_alive:
                            logger.info(f"💀 Agent is dead (from action_sync), restarting...")
                            if self.knowledge:
                                self.knowledge.record_outcome("death", {
                                    "kills": self.current_game.kills,
                                    "survival_time": self.current_game.survival_time
                                })
                            raise AgentDeadError("Agent dead (from action_sync)")
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    if self.current_game.can_act:
                        last_action_time = current_time
                    continue

                # ===== ACTION_REJECTED =====
                if msg_type == "action_rejected":
                    view = msg.get("view", {})
                    if view:
                        self.current_game.update_view(view, "action_rejected")
                        if not self.current_game.is_alive:
                            logger.info(f"💀 Agent is dead (from action_rejected), restarting...")
                            if self.knowledge:
                                self.knowledge.record_outcome("death", {
                                    "kills": self.current_game.kills,
                                    "survival_time": self.current_game.survival_time
                                })
                            raise AgentDeadError("Agent dead (from action_rejected)")
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    if view and self.current_game.is_alive:
                        await self._act(ws, self.current_game.can_act)
                    continue

                # ===== ACTION_RESULT =====
                if msg_type == "action_result":
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    error = msg.get("error")
                    action = msg.get("action")

                    if action and action.get("type") == "pickup":
                        item_id = action.get("itemInstanceId")
                        if error:
                            if item_id:
                                self.current_game.mark_item_attempted(item_id)
                                self.current_game.mark_item_collected(item_id)
                                logger.debug(f"❌ Pickup failed for {item_id[:8]}, marked as collected")
                        else:
                            if item_id:
                                self.current_game.mark_item_collected(item_id)
                                logger.info(f"✅ Pickup success for {item_id[:8]}, marked as collected")

                    if error:
                        code = error.get("code")
                        message = error.get("message", "")

                        if code == "AGENT_DEAD":
                            logger.info(f"💀 Agent dead from action_result: {message}")
                            raise AgentDeadError(f"Agent dead: {message}")

                        if code == "TARGET_DEAD":
                            logger.info(f"🎯 TARGET_DEAD - recomputing (turn {self.current_game.turn})")
                            view = msg.get("view", {})
                            if view:
                                self.current_game.update_view(view, "action_result")
                                if not self.current_game.is_alive:
                                    raise AgentDeadError("Agent dead from action_result view")
                                await self._act(ws, self.current_game.can_act)
                            continue

                        if code == "ACTION_FAILED":
                            logger.warning(f"⚠️ Action failed: {message}")
                            view = msg.get("view", {})
                            if view:
                                self.current_game.update_view(view, "action_result")
                                if not self.current_game.is_alive:
                                    raise AgentDeadError("Agent dead from action_result view")
                                await self._act(ws, self.current_game.can_act)
                            continue

                    if msg.get("action"):
                        self.total_actions += 1
                        self.successful_actions += 1
                        self.strategy.reset_rejection_counter()
                        last_action_time = current_time
                    continue

                # ===== RUIN STATE CHANGED =====
                if msg_type == "ruin_state_changed":
                    try:
                        ruin_data = msg.get("ruin", {})
                        if ruin_data and self.current_game:
                            self.current_game.update_ruin_state(ruin_data)
                    except Exception as e:
                        logger.debug(f"Ruin state handler error: {e}")
                    continue

                # ===== ALERT GAUGE CHANGED =====
                if msg_type == "alert_gauge_changed":
                    try:
                        alert_gauge = msg.get("alertGauge", 0)
                        alert_active = msg.get("alertActive", False)
                        
                        if self.current_game:
                            self.current_game.update_alert_gauge({
                                "alertGauge": alert_gauge,
                                "alertActive": alert_active
                            })
                        
                        if alert_active:
                            logger.warning(f"⚠️⚠️ ALERT ACTIVE! Gauge: {alert_gauge}/10 ⚠️⚠️")
                        else:
                            logger.debug(f"📊 Alert gauge: {alert_gauge}/10")
                    except Exception as e:
                        logger.debug(f"Alert gauge handler error: {e}")
                    continue

                if msg_type not in ["log", "message_sent", "rest_completed"]:
                    logger.debug(f"📨 Unknown message type: {msg_type}")

            except asyncio.TimeoutError:
                logger.warning("⏰ WebSocket receive timeout, checking connection...")
                continue
            except ResumeTargetDeadError:
                raise
            except AgentDeadError:
                raise
            except ConnectionClosed as e:
                if e.code == 1013 and "RESUME_TARGET_DEAD" in str(e.reason):
                    raise ResumeTargetDeadError(f"Resume target dead: {e.reason}")
                raise
            except Exception as e:
                logger.exception(f"💥 Gameplay error: {e}")
                raise
        
        logger.info("🔄 Game finished, exiting gameplay loop...")

    async def _act(self, ws: WSClient, can_act: bool):
        """Ambil tindakan berdasarkan strategy yang dipilih"""
        if not can_act or not self.current_game or not self.current_game.is_alive:
            return

        current_time = __import__('time').time()
        min_action_interval = 0.5
        
        if self._last_action_time > 0:
            elapsed = current_time - self._last_action_time
            if elapsed < min_action_interval:
                wait_time = min_action_interval - elapsed
                logger.debug(f"⏳ Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
        
        self._last_action_time = current_time

        try:
            if self.strategy_mode == "scan_clear" and self.scan_clear:
                decision = self.scan_clear.decide(self.current_game)
                action = self._execute_scan_clear_decision(decision)
                if action:
                    thought = f"Scan & Clear: {decision.get('kind', 'action')}"
                    await ws.send_action(action, thought=thought)
                    await asyncio.sleep(ACTION_INTERVAL_SECONDS)
                    return
            else:
                if self.ai_enabled:
                    decision = await self.ai.decide(self.current_game)
                    action = self._build_action_from_decision(decision)
                    if action:
                        thought = f"Hybrid AI: {decision.reasoning[0] if decision.reasoning else decision.action_type}"
                        await ws.send_action(action, thought=thought)
                        await asyncio.sleep(ACTION_INTERVAL_SECONDS)
                        return

            await self._act_heuristic(ws, can_act)

        except Exception as e:
            logger.error(f"💥 Action error: {e}")
            await self._act_heuristic(ws, can_act)

    def _execute_scan_clear_decision(self, decision: Dict) -> Optional[Dict]:
        """Eksekusi decision dari Scan & Clear"""
        if not self.scan_clear:
            return None
            
        kind = decision.get("kind")
        obj = decision.get("obj")
        
        if kind == "pickup":
            return self.scan_clear.action_builder.pickup(obj)
        elif kind == "attack":
            return self.scan_clear.action_builder.attack(obj)
        elif kind == "move":
            return self.scan_clear.action_builder.move(obj)
        elif kind == "interact":
            return self.scan_clear.action_builder.interact(obj)
        elif kind == "explore":
            return self.scan_clear.action_builder.explore(obj)
        
        return None

    def _build_action_from_decision(self, decision) -> Optional[Dict]:
        """Build action from AI decision"""
        action_type = decision.action_type
        target_id = decision.target_id

        if action_type == "attack":
            target = self._find_target(target_id, "enemies")
            if target:
                return ActionBuilder.attack(target)

        elif action_type == "pickup":
            item = self._find_target(target_id, "items")
            if item:
                return ActionBuilder.pickup(item)

        elif action_type == "interact":
            obj = self._find_target(target_id, "interactables")
            if obj:
                return ActionBuilder.interact(obj)

        elif action_type == "explore":
            obj = self._find_target(target_id, "interactables")
            if obj:
                return ActionBuilder.explore(obj)

        elif action_type == "move":
            conn = self._find_target(target_id, "connections")
            if conn:
                return ActionBuilder.move(conn)
        
        elif action_type == "use":
            item = self._find_target(target_id, "items")
            if item:
                return ActionBuilder.use_item(item)
            if target_id:
                return ActionBuilder.use_item_by_id(target_id)

        return None

    def _find_target(self, target_id: str, category: str) -> Optional[Dict]:
        """Cari target berdasarkan ID dan kategori"""
        if not self.current_game:
            return None

        if category == "enemies":
            for enemy in self.current_game.get_enemies():
                if enemy.get("id") == target_id or enemy.get("agentId") == target_id:
                    return enemy
                if enemy.get("metadata", {}).get("id") == target_id:
                    return enemy
