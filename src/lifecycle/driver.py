# src/lifecycle/driver.py
"""Driver utama dengan Hybrid AI (AI Auto-Pilot + Competitive v7)"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any

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
    """Driver utama bot dengan Hybrid AI"""

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

        # Game state
        self.current_game: Optional[GameState] = None
        self.delay = MIN_RETRY_DELAY
        self.game_count = 0
        self.ai_enabled = True

        # Performance tracking
        self.start_time = None
        self.total_actions = 0
        self.successful_actions = 0

    async def run(self):
        """Loop utama driver"""
        logger.info("🚀 Driver run() started!")  # <-- DEBUG
        self.delay = MIN_RETRY_DELAY
        self.start_time = __import__('time').time()
        logger.info(f"⏰ Start time: {self.start_time}")  # <-- DEBUG

        loop_count = 0  # <-- DEBUG

        while True:
            loop_count += 1
            logger.info(f"🔄 Driver loop iteration #{loop_count}")  # <-- DEBUG

            try:
                # Update version
                logger.info("📥 Checking version...")  # <-- DEBUG
                await self.version_mgr.ensure_current(self.rest._session)
                logger.info(f"✅ Version: {self.version_mgr.version}")  # <-- DEBUG

                # Determine state
                logger.info("🔍 Determining game state...")  # <-- DEBUG
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
                await asyncio.sleep(1)
                self.delay = MIN_RETRY_DELAY

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

    async def _start_game(self, entry_type: str):
        """Mulai game baru - via WebSocket dengan Hybrid AI"""
        logger.info(f"🎮 Joining {entry_type} game...")
        logger.info(f"🔑 API Key: {self.rest.api_key[:10]}...")

        try:
            # Pastikan auth_service ada
            if not self.auth_service:
                from ..services.auth_service import AuthService
                self.auth_service = AuthService(self.rest)
                logger.info("✅ Auth service initialized")

            # Dapatkan headers
            headers = await self.auth_service.get_websocket_auth()
            logger.info(f"📨 Headers: {headers}")

            # Connect via WebSocket
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

            # Baca welcome frame
            welcome = json.loads(await connection.recv())
            decision = welcome.get("decision")
            logger.info(f"📨 Welcome decision: {decision}")

            # Kirim hello
            hello = {"type": "hello", "entryType": entry_type}
            if entry_type == "paid":
                hello["mode"] = "offchain"
            await connection.send(json.dumps(hello))
            logger.info(f"📤 Sent hello: {entry_type}")

            # Tunggu response
            while True:
                msg = json.loads(await connection.recv())
                msg_type = msg.get("type")
                logger.info(f"📨 Received: {msg_type}")

                if msg_type in ("assigned", "joined"):
                    self.current_game = GameState(entry_type=entry_type)
                    self.current_game.game_id = msg.get("gameId")
                    self.game_count += 1
                    logger.info(f"✅ {msg_type} to game {self.current_game.game_id}")

                    # Wrap connection in WSClient
                    ws = WSClient(self.rest.api_key, self.rest.version)
                    ws._ws = connection

                    # Start gameplay with Hybrid AI
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
            await self._start_game(entry_type)
        except ResumeTargetDeadError:
            logger.info(f"{entry_type} resume target dead, re-dialing...")
            raise

    async def _play_game(self, ws: WSClient):
        """Loop gameplay dengan Hybrid AI"""
        logger.info("🎮 Starting Hybrid AI-powered gameplay loop...")
        logger.info("🧠 Hybrid AI = AI Auto-Pilot + Competitive v7")

        while True:
            try:
                msg = await ws.recv()
                msg_type = msg.get("type")

                # ===== KEMATIAN =====
                if msg_type == "agent_died":
                    if msg.get("meta", {}).get("youDied") is True:
                        self.current_game.mark_dead()
                        if self.knowledge:
                            self.knowledge.record_outcome("death", {
                                "kills": self.current_game.kills,
                                "survival_time": self.current_game.survival_time
                            })
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
                    continue

                # ===== AGENT_VIEW / TURN_ADVANCED =====
                if msg_type in ("agent_view", "turn_advanced"):
                    view = msg.get("view", {})
                    reason = msg.get("reason", "sync")

                    if view:
                        self.current_game.update_view(view, reason)
                        if not self.current_game.is_alive:
                            raise AgentDeadError("Agent dead (from view)")

                        can_act = msg.get("canAct", self.current_game.can_act)
                        await self._act(ws, can_act)
                    continue

                # ===== ACTION_SYNC =====
                if msg_type == "action_sync":
                    view = msg.get("view", {})
                    if view:
                        self.current_game.update_view(view, "action_sync")
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    continue

                # ===== ACTION_REJECTED =====
                if msg_type == "action_rejected":
                    view = msg.get("view", {})
                    if view:
                        self.current_game.update_view(view, "action_rejected")
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    if view and self.current_game.is_alive:
                        await self._act(ws, self.current_game.can_act)
                    continue

                # ===== ACTION_RESULT =====
                if msg_type == "action_result":
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    error = msg.get("error")

                    if error:
                        code = error.get("code")
                        message = error.get("message", "")

                        if code == "AGENT_DEAD":
                            raise AgentDeadError(f"Agent dead: {message}")

                        if code == "TARGET_DEAD":
                            logger.info(f"🎯 TARGET_DEAD - recomputing (turn {self.current_game.turn})")
                            view = msg.get("view", {})
                            if view:
                                self.current_game.update_view(view, "action_result")
                                await self._act(ws, self.current_game.can_act)
                            continue

                        if code == "ACTION_FAILED":
                            logger.warning(f"⚠️ Action failed: {message}")
                            view = msg.get("view", {})
                            if view:
                                self.current_game.update_view(view, "action_result")
                                await self._act(ws, self.current_game.can_act)
                            continue

                    if msg.get("action"):
                        self.total_actions += 1
                        self.successful_actions += 1
                        self.strategy.reset_rejection_counter()
                    continue

                logger.debug(f"📨 Unknown message type: {msg_type}")

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

# src/lifecycle/driver.py - di method _act

    async def _act(self, ws: WSClient, can_act: bool):
        """Ambil tindakan menggunakan Hybrid AI"""
        if not can_act or not self.current_game or not self.current_game.is_alive:
            logger.info(f"⏳ Cannot act: can_act={can_act}, is_alive={self.current_game.is_alive if self.current_game else None}")
            return

        try:
            if self.ai_enabled:
                # Hybrid AI Decision
                decision = await self.ai.decide(self.current_game)

                # Get strategy name
                strategy_name = self.ai.ai.get_strategy_name() if hasattr(self.ai, 'ai') else "Hybrid"

                logger.info(
                    f"🧠 Hybrid AI [{strategy_name}]: {decision.action_type} "
                    f"(Conf: {decision.confidence:.2f}, "
                    f"Risk: {decision.risk_score:.2f}, "
                    f"Value: {decision.expected_value:.2f})"
                )

                # Build action from decision
                action = self._build_action_from_decision(decision)

                if action:
                    thought = f"Hybrid AI: {decision.reasoning[0] if decision.reasoning else decision.action_type}"
                    logger.info(f"📤 Sending action: {action}")  # <-- TAMBAHKAN
                    await ws.send_action(action, thought=thought)

                    if decision.action_type != "wait":
                        if self.knowledge:
                            self.knowledge.data["stats"]["successful_actions"] += 1
                            self.knowledge.save()

                    await asyncio.sleep(ACTION_INTERVAL_SECONDS)
                    return
                else:
                    logger.warning(f"⚠️ Failed to build action from decision: {decision}")

            # Fallback to heuristic strategy
            await self._act_heuristic(ws, can_act)

        except Exception as e:
            logger.error(f"💥 Hybrid AI error: {e}")
            await self._act_heuristic(ws, can_act)

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

        elif category == "items":
            for item in self.current_game.get_items():
                if item.get("id") == target_id or item.get("instanceId") == target_id:
                    return item

        elif category == "interactables":
            for obj in self.current_game.get_interactables():
                if obj.get("id") == target_id or obj.get("interactableId") == target_id:
                    return obj

        elif category == "connections":
            for conn in self.current_game.get_connections():
                if conn.get("id") == target_id or conn.get("regionId") == target_id:
                    return conn

        return None

    async def _act_heuristic(self, ws: WSClient, can_act: bool):
        """Fallback: heuristic strategy (v7)"""
        if not can_act or not self.current_game:
            return

        decision = self.strategy.decide(self.current_game)
        action = self.strategy.execute(self.current_game, decision)

        if action:
            thought = f"Heuristic (v7): {decision.get('kind', 'action')}"
            await ws.send_action(action, thought=thought)
            await asyncio.sleep(ACTION_INTERVAL_SECONDS)

    def _log_hybrid_stats(self):
        """Log Hybrid AI statistics"""
        stats = self.ai.get_stats() if hasattr(self.ai, 'get_stats') else {}

        logger.info("=" * 60)
        logger.info("📊 Hybrid AI Performance Summary")
        logger.info("=" * 60)
        logger.info(f"   Total Decisions: {stats.get('decisions_made', 0)}")
        logger.info(f"   AI Decisions: {stats.get('ai_decisions', 0)}")
        logger.info(f"   Heuristic Decisions: {stats.get('heuristic_decisions', 0)}")
        logger.info(f"   Survival Priority: {stats.get('survival_priority', 0)}")
        logger.info(f"   Kill Priority: {stats.get('kill_priority', 0)}")
        logger.info(f"   Loot Priority: {stats.get('loot_priority', 0)}")
        logger.info(f"   Explore Priority: {stats.get('explore_priority', 0)}")
        logger.info(f"   Total Actions: {self.total_actions}")
        logger.info(f"   Success Rate: {self.successful_actions / max(self.total_actions, 1) * 100:.1f}%")
        logger.info("=" * 60)

    def get_performance(self) -> Dict[str, Any]:
        """Dapatkan performa bot"""
        uptime = int(__import__('time').time() - (self.start_time or 0))

        return {
            "uptime": uptime,
            "game_count": self.game_count,
            "total_actions": self.total_actions,
            "success_rate": self.successful_actions / max(self.total_actions, 1),
            "hybrid_stats": self.ai.get_stats() if hasattr(self.ai, 'get_stats') else {},
            "current_state": self.current_game.entry_type if self.current_game else "none",
            "is_in_game": self.current_game is not None and self.current_game.is_alive
        }
