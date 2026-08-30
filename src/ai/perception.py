# src/ai/perception.py
"""Perception Layer - Memahami lingkungan game"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import deque
import math

logger = logging.getLogger(__name__)

@dataclass
class PerceivedEntity:
    id: str
    type: str
    position: Dict[str, float]
    hp: float
    max_hp: float
    is_alive: bool
    is_enemy: bool
    is_guardian: bool = False
    threat_score: float = 0.0
    value_score: float = 0.0
    distance: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerceivedState:
    turn: int
    self: PerceivedEntity
    hp_ratio: float
    in_cave: bool
    region: Dict[str, Any]
    enemies: List[PerceivedEntity] = field(default_factory=list)
    allies: List[PerceivedEntity] = field(default_factory=list)
    items: List[PerceivedEntity] = field(default_factory=list)
    interactables: List[PerceivedEntity] = field(default_factory=list)
    connections: List[PerceivedEntity] = field(default_factory=list)
    danger_level: float = 0.0
    opportunity_score: float = 0.0
    survival_potential: float = 1.0

class PerceptionEngine:
    def __init__(self):
        self.history = deque(maxlen=50)
        self.last_perception = None
        
    def perceive(self, game_state) -> PerceivedState:
        view = game_state.view
        self_data = view.get("self", {})
        region = view.get("currentRegion", {})
        
        self_entity = self._perceive_self(self_data)
        enemies = self._perceive_enemies(view, self_entity)
        items = self._perceive_items(region, self_entity)
        interactables = self._perceive_interactables(region, self_entity)
        connections = self._perceive_connections(region, self_entity)
        
        danger_level = self._calculate_danger_level(enemies, self_entity, view)
        opportunity_score = self._calculate_opportunity(items, interactables, view)
        survival_potential = self._calculate_survival_potential(self_entity, enemies, region)
        
        state = PerceivedState(
            turn=game_state.turn,
            self=self_entity,
            hp_ratio=self_entity.hp / max(self_entity.max_hp, 1),
            in_cave=game_state.in_cave,
            region=region,
            enemies=enemies,
            items=items,
            interactables=interactables,
            connections=connections,
            danger_level=danger_level,
            opportunity_score=opportunity_score,
            survival_potential=survival_potential
        )
        
        self.history.append(state)
        self.last_perception = state
        return state
    
    def _perceive_self(self, data: Dict) -> PerceivedEntity:
        return PerceivedEntity(
            id=data.get("id", ""),
            type="self",
            position={"x": float(data.get("x", 0)), "y": float(data.get("y", 0))},
            hp=float(data.get("hp", data.get("currentHp", 0))),
            max_hp=float(data.get("maxHp", data.get("maxHealth", 1))),
            is_alive=data.get("isAlive", True),
            is_enemy=False,
            metadata={
                "attack": float(data.get("attack", data.get("atk", 0))),
                "defense": float(data.get("defense", data.get("def", 0))),
                "speed": float(data.get("speed", 1)),
                "in_cave": data.get("inCave", False),
                "kills": data.get("kills", 0),
                "survival_time": data.get("survivalTime", 0)
            }
        )
    
    def _perceive_enemies(self, view: Dict, self_entity: PerceivedEntity) -> List[PerceivedEntity]:
        enemies = []
        for agent in view.get("visibleAgents", []):
            if agent.get("isAlive", False):
                enemy = self._create_enemy_entity(agent, "agent", self_entity)
                if enemy:
                    enemies.append(enemy)
        for monster in view.get("visibleMonsters", []):
            if monster.get("isAlive", False):
                enemy = self._create_enemy_entity(monster, "monster", self_entity)
                if enemy:
                    enemies.append(enemy)
        return enemies
    
    def _create_enemy_entity(self, data: Dict, entity_type: str, self_entity: PerceivedEntity) -> Optional[PerceivedEntity]:
        try:
            pos_x = float(data.get("x", data.get("position", {}).get("x", 0)))
            pos_y = float(data.get("y", data.get("position", {}).get("y", 0)))
            self_x = self_entity.position.get("x", 0)
            self_y = self_entity.position.get("y", 0)
            distance = math.sqrt((pos_x - self_x) ** 2 + (pos_y - self_y) ** 2)
            
            is_guardian = data.get("isGuardian", False) or str(data.get("kind", "")).lower() == "guardian"
            threat_score = self._calculate_threat_score(data, distance, is_guardian)
            
            return PerceivedEntity(
                id=data.get("agentId") or data.get("monsterId") or data.get("id", ""),
                type=entity_type,
                position={"x": pos_x, "y": pos_y},
                hp=float(data.get("hp", data.get("currentHp", 0))),
                max_hp=float(data.get("maxHp", data.get("maxHealth", 1))),
                is_alive=data.get("isAlive", True),
                is_enemy=True,
                is_guardian=is_guardian,
                threat_score=threat_score,
                distance=distance,
                metadata={
                    "attack": float(data.get("attack", data.get("atk", 0))),
                    "defense": float(data.get("defense", data.get("def", 0))),
                    "kind": data.get("kind", ""),
                    "name": data.get("name", "")
                }
            )
        except Exception as e:
            return None
    
    def _calculate_threat_score(self, data: Dict, distance: float, is_guardian: bool) -> float:
        hp_ratio = float(data.get("hp", 0)) / max(float(data.get("maxHp", 1)), 1)
        attack = float(data.get("attack", data.get("atk", 0)))
        threat = (attack + 10) * (1 - hp_ratio + 0.3) / max(distance, 1)
        if is_guardian:
            threat *= 1.5
        return min(max(threat, 0), 100)
    
    def _perceive_items(self, region: Dict, self_entity: PerceivedEntity) -> List[PerceivedEntity]:
        items = []
        for item in region.get("items", []):
            try:
                self_x = self_entity.position.get("x", 0)
                self_y = self_entity.position.get("y", 0)
                pos_x = float(item.get("x", 0))
                pos_y = float(item.get("y", 0))
                distance = math.sqrt((pos_x - self_x) ** 2 + (pos_y - self_y) ** 2)
                value_score = self._calculate_item_value(item)
                
                items.append(PerceivedEntity(
                    id=item.get("instanceId") or item.get("itemInstanceId") or item.get("id", ""),
                    type="item",
                    position={"x": pos_x, "y": pos_y},
                    hp=0,
                    max_hp=1,
                    is_alive=True,
                    is_enemy=False,
                    value_score=value_score,
                    distance=distance,
                    metadata={
                        "item_type": item.get("type", item.get("itemType", "")),
                        "heal": float(item.get("heal", item.get("healAmount", 0))),
                        "value": float(item.get("value", item.get("rarityValue", 0)))
                    }
                ))
            except Exception as e:
                pass
        return items
    
    def _calculate_item_value(self, item: Dict) -> float:
        item_type = str(item.get("type", item.get("itemType", ""))).lower()
        value = float(item.get("value", item.get("rarityValue", 0)))
        heal = float(item.get("heal", item.get("healAmount", 0)))
        score = value
        if heal > 0:
            score += heal * 5
        if any(k in item_type for k in ("weapon", "armor", "relic")):
            score += 50
        return score
    
    def _perceive_interactables(self, region: Dict, self_entity: PerceivedEntity) -> List[PerceivedEntity]:
        interactables = []
        for obj in region.get("interactables", []):
            try:
                self_x = self_entity.position.get("x", 0)
                self_y = self_entity.position.get("y", 0)
                pos_x = float(obj.get("x", 0))
                pos_y = float(obj.get("y", 0))
                distance = math.sqrt((pos_x - self_x) ** 2 + (pos_y - self_y) ** 2)
                obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
                
                value_score = 0
                if any(k in obj_type for k in ("medical", "supply", "cache", "watchtower")):
                    value_score = 80
                elif "ruin" in obj_type:
                    value_score = 60 - max(0, region.get("alertGauge", 0) - 6) * 10
                elif obj.get("isExit", False) and "cave" in obj_type:
                    value_score = 100
                
                interactables.append(PerceivedEntity(
                    id=obj.get("interactableId") or obj.get("id", ""),
                    type="interactable",
                    position={"x": pos_x, "y": pos_y},
                    hp=0,
                    max_hp=1,
                    is_alive=True,
                    is_enemy=False,
                    value_score=value_score,
                    distance=distance,
                    metadata={
                        "kind": obj_type,
                        "is_exit": obj.get("isExit", False),
                        "alert_gauge": region.get("alertGauge", 0)
                    }
                ))
            except Exception as e:
                pass
        return interactables
    
    def _perceive_connections(self, region: Dict, self_entity: PerceivedEntity) -> List[PerceivedEntity]:
        connections = []
        for conn in region.get("connections", []):
            try:
                score = 30
                if isinstance(conn, dict):
                    score += float(conn.get("safetyScore", conn.get("zoneSafety", 0))) * 10
                    if conn.get("insideDeathZone") is True:
                        score -= 100
                
                connections.append(PerceivedEntity(
                    id=conn.get("regionId", ""),
                    type="connection",
                    position={"x": 0, "y": 0},
                    hp=0,
                    max_hp=1,
                    is_alive=True,
                    is_enemy=False,
                    value_score=score,
                    distance=0,
                    metadata=conn if isinstance(conn, dict) else {}
                ))
            except Exception as e:
                pass
        return connections
    
    def _calculate_danger_level(self, enemies: List[PerceivedEntity], self_entity: PerceivedEntity, view: Dict) -> float:
        if not enemies:
            return 0.0
        total_threat = sum(e.threat_score for e in enemies)
        hp_penalty = 1 + (1 - self_entity.hp / max(self_entity.max_hp, 1)) * 0.5
        nearby_enemies = len([e for e in enemies if e.distance < 10])
        nearby_factor = 1 + nearby_enemies * 0.3
        guardian_factor = 1 + sum(1 for e in enemies if e.is_guardian) * 0.5
        return min(total_threat * hp_penalty * nearby_factor * guardian_factor, 100)
    
    def _calculate_opportunity(self, items: List[PerceivedEntity], interactables: List[PerceivedEntity], view: Dict) -> float:
        item_value = sum(i.value_score / max(i.distance, 1) for i in items)
        interactable_value = sum(i.value_score / max(i.distance, 1) for i in interactables)
        return min(item_value + interactable_value, 100)
    
    def _calculate_survival_potential(self, self_entity: PerceivedEntity, enemies: List[PerceivedEntity], region: Dict) -> float:
        hp_ratio = self_entity.hp / max(self_entity.max_hp, 1)
        hp_factor = hp_ratio
        enemy_threat = sum(e.threat_score for e in enemies)
        enemy_factor = max(0, 1 - enemy_threat / 100)
        
        items = region.get("items", [])
        healing_items = sum(1 for i in items if float(i.get("heal", i.get("healAmount", 0))) > 0)
        item_factor = min(1 + healing_items * 0.1, 2)
        
        guardian_nearby = any(e.is_guardian and e.distance < 15 for e in enemies)
        guardian_factor = 0.5 if guardian_nearby else 1
        
        return min(max(hp_factor * enemy_factor * item_factor * guardian_factor, 0), 1)