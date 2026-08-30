# src/lifecycle/driver.py
"""Driver utama dengan AI Auto-Pilot"""

import asyncio
import logging
import time
from typing import Optional
from ..services.auth_service import AuthService
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
    TargetDeadError
)
from ..core.constants import (
    MIN_RETRY_DELAY,
    MAX_RETRY_DELAY,
    RETRY_BACKOFF_MULTIPLIER,
)
from ..core.config import ACTION_INTERVAL_SECONDS
from ..ai.decision import DecisionEngine
from ..ai.knowledge import KnowledgeBase

logger = logging.getLogger(__name__)


class Driver:
    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
        self.router = StateRouter(rest_client)
        self.version_mgr = VersionManager(rest_client.api_key)
        
        # AI Components
        self.ai = DecisionEngine()
        self.knowledge: Optional[KnowledgeBase] = None
        self.auth_service: Optional[AuthService] = None  # <-- TAMBAH
        
        # Fallback strategy
        self.strategy = StrategyEngine()
        
        self.current_game: Optional[GameState] = None
        self.delay = MIN_RETRY_DELAY
        self.game_count = 0
        self.ai_enabled = True

    async def _start_game(self, entry_type: str):
        """Mulai game baru - menggunakan AuthService"""
        logger.info(f"🎮 Joining {entry_type} game...")
        self.current_game = GameState(entry_type=entry_type)

        try:
            # Gunakan auth service untuk join
            if not self.auth_service:
                from ..services.auth_service import AuthService
                self.auth_service = AuthService(self.rest)
            
            # Join via WebSocket
            ws = await self.auth_service.join_game_websocket(entry_type)
            
            # Tunggu assignment
            assignment = await self.auth_service.wait_for_game_assignment(ws, entry_type)
            
            if assignment and assignment.get("type") in ("assigned", "joined"):
                self.current_game.game_id = assignment.get("gameId")
                logger.info(f"✅ Game joined: {self.current_game.game_id}")
                await self._play_game(ws)
                return
            else:
                logger.warning("❌ Failed to join game, retrying...")
                await asyncio.sleep(3)
                return

        except ResumeTargetDeadError:
            if entry_type == "free":
                logger.info("🔄 Free game target dead, fallback to matchmaking...")
                raise
            else:
                raise
        except Exception as e:
            logger.error(f"❌ Failed to join game: {e}")
            raise

    async def _resume_game(self, entry_type: str):
        """Resume game yang sedang berjalan"""
        logger.info(f"Resuming {entry_type} game...")

        try:
            async with WSClient(self.rest.api_key, self.rest.version) as ws:
                welcome = await ws.recv()
                logger.info(f"Welcome decision: {welcome.get('decision')}")
                await ws.send_hello(entry_type)

                while True:
                    msg = await ws.recv()
                    msg_type = msg.get("type")

                    if msg_type == "assigned":
                        self.current_game = GameState(entry_type=entry_type)
                        self.current_game.game_id = msg.get("gameId")
                        logger.info(f"Assigned to new game {self.current_game.game_id}")
                        await self._play_game(ws)
                        return

                    elif msg_type == "joined":
                        self.current_game = GameState(entry_type=entry_type)
                        self.current_game.game_id = msg.get("gameId")
                        logger.info(f"Resumed game {self.current_game.game_id}")
                        await self._play_game(ws)
                        return

                    elif msg_type == "not_selected":
                        raise NotSelectedError("Not selected for game")
                    elif msg_type == "error":
                        raise RuntimeError(f"Error: {msg}")
                    elif msg_type in ("queued", "waiting"):
                        continue

        except ResumeTargetDeadError:
            logger.info(f"{entry_type} resume target dead, re-dialing...")
            raise

    async def _play_game(self, ws: WSClient):
        """Loop gameplay dengan AI"""
        logger.info("🎮 Starting AI-powered gameplay loop...")

        while True:
            try:
                msg = await ws.recv()
                msg_type = msg.get("type")

                # Kematian
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

                # Game selesai
                if msg_type == "game_settled":
                    self.current_game.mark_finished()
                    logger.info("Game settled!")
                    if self.knowledge:
                        self.knowledge.record_outcome("win", {
                            "kills": self.current_game.kills,
                            "survival_time": self.current_game.survival_time
                        })
                    break

                if msg_type == "game_ended":
                    self.current_game.mark_finished()
                    placement = msg.get("placement")
                    logger.info(f"Game ended! Placement: {placement}")
                    if self.knowledge and placement and placement <= 5:
                        self.knowledge.record_outcome("win", {
                            "kills": self.current_game.kills,
                            "survival_time": self.current_game.survival_time
                        })
                    break

                if msg_type == "can_act_changed":
                    self.current_game.can_act = bool(msg.get("canAct"))
                    continue

                # Agent view / turn advanced
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

                # Action sync
                if msg_type == "action_sync":
                    view = msg.get("view", {})
                    if view:
                        self.current_game.update_view(view, "action_sync")
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    continue

                # Action rejected
                if msg_type == "action_rejected":
                    view = msg.get("view", {})
                    if view:
                        self.current_game.update_view(view, "action_rejected")
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    if view and self.current_game.is_alive:
                        await self._act(ws, self.current_game.can_act)
                    continue

                # Action result
                if msg_type == "action_result":
                    self.current_game.can_act = bool(msg.get("canAct", self.current_game.can_act))
                    error = msg.get("error")

                    if error:
                        code = error.get("code")
                        message = error.get("message", "")

                        if code == "AGENT_DEAD":
                            raise AgentDeadError(f"Agent dead: {message}")

                        if code == "TARGET_DEAD":
                            logger.info(f"TARGET_DEAD - recomputing (turn {self.current_game.turn})")
                            view = msg.get("view", {})
                            if view:
                                self.current_game.update_view(view, "action_result")
                                await self._act(ws, self.current_game.can_act)
                            continue

                        if code == "ACTION_FAILED":
                            logger.warning(f"Action failed: {message}")
                            view = msg.get("view", {})
                            if view:
                                self.current_game.update_view(view, "action_result")
                                await self._act(ws, self.current_game.can_act)
                            continue

                    if msg.get("action"):
                        self.strategy.reset_rejection_counter()
                    continue

                logger.debug(f"Unknown message type: {msg_type}")

            except ResumeTargetDeadError:
                raise
            except AgentDeadError:
                raise
            except ConnectionClosed as e:
                if e.code == 1013 and "RESUME_TARGET_DEAD" in str(e.reason):
                    raise ResumeTargetDeadError(f"Resume target dead: {e.reason}")
                raise
            except Exception as e:
                logger.exception(f"Gameplay error: {e}")
                raise

    async def _act(self, ws: WSClient, can_act: bool):
        """Ambil tindakan menggunakan AI atau fallback"""
        if not can_act or not self.current_game or not self.current_game.is_alive:
            return

        try:
            if self.ai_enabled:
                # AI Decision
                decision = await self.ai.decide(self.current_game)

                logger.info(
                    f"🤖 AI Strategy: {self.ai.get_strategy_name()} | "
                    f"Action: {decision.action_type} "
                    f"(Conf: {decision.confidence:.2f}, "
                    f"Risk: {decision.risk_score:.2f})"
                )

                # Build action from AI decision
                action = self._build_action_from_decision(decision)

                if action:
                    thought = f"AI: {decision.reasoning[0] if decision.reasoning else decision.action_type}"
                    await ws.send_action(action, thought=thought)

                    if decision.action_type != "wait":
                        self.knowledge.data["stats"]["successful_actions"] += 1
                        self.knowledge.save()

                    await asyncio.sleep(ACTION_INTERVAL_SECONDS)
                    return

            # Fallback to heuristic strategy
            await self._act_heuristic(ws, can_act)

        except Exception as e:
            logger.error(f"Action error: {e}")
            await self._act_heuristic(ws, can_act)

    def _build_action_from_decision(self, decision) -> Optional[dict]:
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
        elif action_type in ("interact", "explore"):
            obj = self._find_target(target_id, "interactables")
            if obj:
                if action_type == "explore":
                    return ActionBuilder.explore(obj)
                return ActionBuilder.interact(obj)
        elif action_type == "move":
            conn = self._find_target(target_id, "connections")
            if conn:
                return ActionBuilder.move(conn)

        return None

    def _find_target(self, target_id: str, category: str) -> Optional[dict]:
        """Cari target berdasarkan ID"""
        if not self.current_game:
            return None

        if category == "enemies":
            for enemy in self.current_game.get_enemies():
                if enemy.get("id") == target_id or enemy.get("agentId") == target_id:
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
        """Fallback: heuristic strategy"""
        if not can_act or not self.current_game:
            return

        decision = self.strategy.decide(self.current_game)
        action = self.strategy.execute(self.current_game, decision)

        if action:
            await ws.send_action(action, thought="Heuristic strategy")
            await asyncio.sleep(ACTION_INTERVAL_SECONDS)
