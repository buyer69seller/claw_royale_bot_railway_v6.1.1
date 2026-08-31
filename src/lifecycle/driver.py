# src/lifecycle/driver.py
"""Driver utama dengan Hybrid AI (AI Auto-Pilot + Competitive v7) + RL + Region Tracking"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any, Set, List

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
        
        # ===== HYBRID STRATEGY STATE =====
        self._strategy_mode = "balanced"  # balanced, aggressive, defensive, explore
        self._strategy_switch_timer = 0
        self._last_strategy_switch = 0

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
                
                # Handle specific close codes
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
                self._reset_region_tracking()
                # Reset hybrid AI stats
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
                self._strategy_mode = "balanced"
                await asyncio.sleep(1)
                self.delay = MIN_RETRY_DELAY
                logger.info("🔄 Force rejoining new game...")
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

    # ===== REGION TRACKING METHODS =====
    
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
        
        # Deteksi loop
        visit_count = self._region_visit_count[region_id]
        if visit_count > 3:
            self._region_loop_detected = True
            logger.warning(f"⚠️ Region {region_id[:8]} visited {visit_count}x - possible loop!")
        else:
            self._region_loop_detected = False

    def _is_region_visited(self, region_id: str) -> bool:
        """Cek apakah region sudah dikunjungi"""
        return region_id in self._visited_regions

    def _get_region_visit_count(self, region_id: str) -> int:
        """Dapatkan jumlah kunjungan ke region"""
        return self._region_visit_count.get(region_id, 0)

    # ===== HYBRID STRATEGY METHODS =====
    
    def _update_strategy_mode(self, state: GameState):
        """Update strategy mode berdasarkan kondisi game"""
        hp_ratio = state.hp_ratio()
        enemies = state.get_enemies()
        items = state.get_valid_items()
        
        # Defensive: HP rendah atau banyak musuh
        if hp_ratio < 0.3:
            self._strategy_mode = "defensive"
            logger.debug(f"🛡️ Strategy: Defensive (HP: {hp_ratio:.0%})")
        # Aggressive: HP tinggi dan sedikit musuh
        elif hp_ratio > 0.7 and len(enemies) < 2 and len(items) > 0:
            self._strategy_mode = "aggressive"
            logger.debug(f"⚔️ Strategy: Aggressive (HP: {hp_ratio:.0%}, Enemies: {len(enemies)})")
        # Explore: HP bagus dan ada ruin
        elif hp_ratio > 0.6:
            for obj in state.get_interactables():
                if "ruin" in str(obj.get("type", obj.get("kind", ""))).lower():
                    self._strategy_mode = "explore"
                    logger.debug(f"🔍 Strategy: Explore (HP: {hp_ratio:.0%})")
                    return
            self._strategy_mode = "balanced"
        else:
            self._strategy_mode = "balanced"
            logger.debug(f"⚖️ Strategy: Balanced (HP: {hp_ratio:.0%})")

    def _get_strategy_priority(self) -> Dict[str, float]:
        """Dapatkan priority weights berdasarkan strategy mode"""
        if self._strategy_mode == "defensive":
            return {
                "survival": 2.0,
                "heal": 1.8,
                "loot": 0.8,
                "kill": 0.5,
                "explore": 0.3,
                "move": 0.6
            }
        elif self._strategy_mode == "aggressive":
            return {
                "survival": 0.8,
                "heal": 0.6,
                "loot": 1.2,
                "kill": 2.0,
                "explore": 0.8,
                "move": 0.5
            }
        elif self._strategy_mode == "explore":
            return {
                "survival": 1.0,
                "heal": 0.8,
                "loot": 1.0,
                "kill": 0.6,
                "explore": 2.0,
                "move": 1.2
            }
        else:  # balanced
            return {
                "survival": 1.0,
                "heal": 1.0,
                "loot": 1.0,
                "kill": 1.0,
                "explore": 1.0,
                "move": 1.0
            }

    # ===== LOAD PACK MODIFIERS =====
    
    async def _load_pack_modifiers(self):
        """Load pack modifiers dari loadout untuk strategy"""
        try:
            loadout = await self.rest.get_loadout()
            main_pack = loadout.get("mainPack", {})
            sub_pack = loadout.get("subPack", {})
            
            # Set modifiers ke strategy
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

    # ===== GAME MANAGEMENT =====
    
    async def _start_game(self, entry_type: str):
        """Mulai game baru - reset semua tracking"""
        logger.info(f"🎮 Joining {entry_type} game...")
        logger.info(f"🔑 API Key: {self.rest.api_key[:10]}...")
        
        # ===== RESET REGION TRACKING =====
        self._reset_region_tracking()
        self._strategy_mode = "balanced"
        logger.info("🗺️ Region tracking reset for new game")

        try:
            # ===== LOAD PACK MODIFIERS =====
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
        
        # ===== LOAD PACK MODIFIERS =====
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
        
        # ===== LOAD PACK MODIFIERS =====
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
            
            # Rejoin via WebSocket
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

    # ===== GAMEPLAY LOOP =====
    
    async def _play_game(self, ws: WSClient):
        """Loop gameplay dengan Hybrid AI + RL + Region Tracking + Hybrid Strategy"""
        logger.info("🎮 Starting Hybrid AI-powered gameplay loop...")
        logger.info("🧠 Hybrid AI = AI Auto-Pilot + Competitive v7 + RL")
        logger.info("👻 Only detecting OWN death, ignoring other agents")
        logger.info("🗺️ Region tracking active - avoiding loops")
        logger.info("⚖️ Hybrid Strategy: Adaptive mode switching")

        # Timeout tracking
        last_action_time = __import__('time').time()
        no_action_timeout = 120
        last_view_time = __import__('time').time()
        view_timeout = 90
        stuck_counter = 0
        last_hp = 0
        last_turn = 0
        
        # Heartbeat tracking
        last_ping_time = __import__('time').time()
        ping_interval = 30

        while True:
            try:
                # ===== HEARTBEAT / PING =====
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
                    
                    # ===== TRACK REGION =====
                    if msg_type == "agent_view":
                        view = msg.get("view", {})
                        region = view.get("currentRegion", {})
                        region_id = region.get("id")
                        if region_id:
                            self._track_region(region_id)

                # ===== CEK TIMEOUT =====
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

                # ===== AGENT_DIED =====
                if msg_type == "agent_died":
                    if msg.get("meta", {}).get("youDied") is True:
                        self.current_game.mark_dead()
                        if self.knowledge:
                            self.knowledge.record_outcome("death", {
                                "kills": self.current_game.kills,
                                "survival_time": self.current_game.survival_time
                            })
                        logger.info(f"💀 YOU DIED! Survival: {self.current_game.survival_time}, Kills: {self.current_game.kills}")
                        raise AgentDeadError("You died!")
                    continue

                # ===== GAME SELESAI =====
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
                            logger.info("💀 Agent is dead (from view), restarting...")
                            if self.knowledge:
                                self.knowledge.record_outcome("death", {
                                    "kills": self.current_game.kills,
                                    "survival_time": self.current_game.survival_time
                                })
                            raise AgentDeadError("Agent dead (from view)")

                        if self.current_game.hp <= 0:
                            logger.info("💀 Agent HP is 0, restarting...")
                            if self.knowledge:
                                self.knowledge.record_outcome("death", {
                                    "kills": self.current_game.kills,
                                    "survival_time": self.current_game.survival_time
                                })
                            raise AgentDeadError("Agent HP is 0")

                        # ===== UPDATE HYBRID STRATEGY =====
                        self._update_strategy_mode(self.current_game)
                        strategy_priority = self._get_strategy_priority()

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
                        await self._act(ws, can_act, strategy_priority)

                        if can_act:
                            last_action_time = current_time
                    continue

                # ===== ACTION_SYNC =====
                if msg_type == "action_sync":
                    view = msg.get("view", {})
                    if view:
                        self.current_game.update_view(view, "action_sync")
                        if not self.current_game.is_alive:
                            logger.info("💀 Agent is dead (from action_sync), restarting...")
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
                            logger.info("💀 Agent is dead (from action_rejected), restarting...")
                            if self.knowledge:
                                self.knowledge.record_outcome("death", {
                                    "kills": self.current_game.kills,
                                    "survival_time": self.current_game.survival_time
                                })
                            raise AgentDeadError("Agent dead (from action_rejected)")
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    if view and self.current_game.is_alive:
                        await self._act(ws, self.current_game.can_act, self._get_strategy_priority())
                    continue

                # ===== ACTION_RESULT =====
                if msg_type == "action_result":
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    error = msg.get("error")
                    action = msg.get("action")

                    # ===== RL REWARD TRACKING =====
                    if action:
                        action_type = action.get("type", "")
                        if error:
                            self._rl_action_tracking["success"] = False
                            if self.ai and hasattr(self.ai, '_update_rl_reward'):
                                self.ai._update_rl_reward(self.current_game, action_type, False)
                            logger.debug(f"❌ RL: Action {action_type} failed")
                        else:
                            self._rl_action_tracking["success"] = True
                            if self.ai and hasattr(self.ai, '_update_rl_reward'):
                                self.ai._update_rl_reward(self.current_game, action_type, True)
                            logger.debug(f"✅ RL: Action {action_type} succeeded")

                    # Track item jika action adalah pickup
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
                                await self._act(ws, self.current_game.can_act, self._get_strategy_priority())
                            continue

                        if code == "ACTION_FAILED":
                            logger.warning(f"⚠️ Action failed: {message}")
                            view = msg.get("view", {})
                            if view:
                                self.current_game.update_view(view, "action_result")
                                if not self.current_game.is_alive:
                                    raise AgentDeadError("Agent dead from action_result view")
                                await self._act(ws, self.current_game.can_act, self._get_strategy_priority())
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
                            ruin_id = ruin_data.get("ruinId", "unknown")[:8]
                            gauge = ruin_data.get("gauge", 0)
                            max_gauge = ruin_data.get("maxGauge", 3)
                            content_type = ruin_data.get("contentType", "unknown")
                            is_empty = ruin_data.get("isEmpty", False)
                            
                            if is_empty:
                                logger.info(f"🗺️ Ruin {ruin_id} cleared! (content: {content_type})")
                            else:
                                logger.debug(f"🗺️ Ruin {ruin_id}: gauge {gauge}/{max_gauge} ({content_type})")
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
                            if self.current_game and self.current_game.can_act:
                                logger.info("🛡️ Alert active - focusing on survival!")
                        else:
                            if alert_gauge > 5:
                                logger.info(f"⚡ Alert gauge: {alert_gauge}/10 (moderate)")
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

    # ===== ACTION EXECUTION =====
    
    async def _act(self, ws: WSClient, can_act: bool, priority: Dict[str, float] = None):
        """Ambil tindakan menggunakan Hybrid AI dengan priority dan region tracking"""
        if not can_act or not self.current_game or not self.current_game.is_alive:
            return

        # ===== RATE LIMIT PROTECTION =====
        current_time
