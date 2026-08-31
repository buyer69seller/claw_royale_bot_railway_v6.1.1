# src/ai/hybrid_engine.py - bagian _priority_decision (lengkap)

    async def _priority_decision(self, perceived: PerceivedState, state: GameState, threat: Dict) -> PriorityDecision:
        """
        v7 Priority-based decision dengan Item Tracking + Ruin & Alert Management
        """
        
        try:
            me = state.get_self()
            if not isinstance(me, dict):
                return PriorityDecision(priority=5, action_type="wait", reasoning="No self data", confidence=0.1)
            
            my_hp = float(me.get("hp", 0))
            my_max_hp = float(me.get("maxHp", 1))
            hp_ratio = my_hp / max(my_max_hp, 1)
            alert = state.get_region().get("alertGauge", 0)
            my_atk = float(me.get("attack", me.get("atk", 0)))
            
            # === PRIORITY 1: SURVIVAL ===
            
            # USE ITEM DARI INVENTORY
            if hp_ratio < 0.5 and state.has_healing_items():
                best_heal = state.get_best_healing_item()
                if best_heal:
                    heal_amount = float(best_heal.get("heal", best_heal.get("healAmount", 0)))
                    if heal_amount > 0:
                        self.stats["survival_priority"] += 1
                        item_id = best_heal.get("instanceId") or best_heal.get("id")
                        if item_id:
                            logger.info(f"💚 Using healing item: {heal_amount} HP (HP: {hp_ratio:.0%})")
                            state.remove_from_inventory(item_id)
                            return PriorityDecision(
                                priority=1,
                                action_type="use",
                                target_id=item_id,
                                reasoning=f"Using healing item ({heal_amount} HP)",
                                confidence=0.98
                            )
            
            # HP < 40% → CARI HEALING ITEM DI GROUND
            if hp_ratio < 0.4:
                try:
                    healing_items = state.get_healing_items()
                    for item in healing_items:
                        if not isinstance(item, dict):
                            continue
                        heal = float(item.get("heal", item.get("healAmount", 0)))
                        if heal > 0:
                            distance = state._calculate_distance(state.get_self(), item)
                            if distance < 3:
                                self.stats["survival_priority"] += 1
                                item_id = item.get("instanceId") or item.get("id")
                                if item_id:
                                    state.mark_item_attempted(item_id)
                                    return PriorityDecision(
                                        priority=1,
                                        action_type="pickup",
                                        target_id=item_id,
                                        reasoning=f"Pickup healing ({heal} HP) - HP: {hp_ratio:.0%}",
                                        confidence=0.95
                                    )
                except Exception as e:
                    logger.debug(f"Healing items error: {e}")
            
            # HP < 20% → RETREAT
            if hp_ratio < 0.2:
                self.stats["survival_priority"] += 1
                try:
                    for conn in state.get_connections():
                        if isinstance(conn, dict) and not conn.get("insideDeathZone", False):
                            return PriorityDecision(
                                priority=1,
                                action_type="move",
                                target_id=conn.get("regionId"),
                                reasoning=f"Critical HP ({hp_ratio:.0%}) - retreating",
                                confidence=0.9
                            )
                except Exception as e:
                    pass
            
            # In Cave → EXIT
            if state.in_cave:
                try:
                    for obj in state.get_interactables():
                        if isinstance(obj, dict) and obj.get("isExit", False) and "cave" in str(obj.get("type", "")):
                            self.stats["survival_priority"] += 1
                            return PriorityDecision(
                                priority=1,
                                action_type="interact",
                                target_id=obj.get("interactableId") or obj.get("id"),
                                reasoning="Exiting cave",
                                confidence=0.95
                            )
                except Exception as e:
                    pass
            
            # In Death Zone → MOVE TO CENTER
            try:
                region = state.get_region()
                if isinstance(region, dict) and region.get("insideDeathZone", False):
                    self.stats["survival_priority"] += 1
                    for conn in state.get_connections():
                        if isinstance(conn, dict) and not conn.get("insideDeathZone", False):
                            return PriorityDecision(
                                priority=1,
                                action_type="move",
                                target_id=conn.get("regionId"),
                                reasoning="Escaping death zone",
                                confidence=0.9
                            )
            except Exception as e:
                pass
            
            # Alert > 7 → HIDE / RETREAT
            if state.alert_gauge > 7 or state.alert_active:
                self.stats["survival_priority"] += 1
                logger.warning(f"⚠️ High alert ({state.alert_gauge}) - retreating!")
                try:
                    for conn in state.get_connections():
                        if isinstance(conn, dict) and conn.get("safetyScore", 0) > 0.5:
                            return PriorityDecision(
                                priority=1,
                                action_type="move",
                                target_id=conn.get("regionId"),
                                reasoning=f"High alert ({state.alert_gauge}) - moving to safety",
                                confidence=0.9
                            )
                except Exception as e:
                    pass
            
            # === PRIORITY 2: LOOT ===
            
            try:
                loot_items = state.get_loot_items()
                for item in loot_items:
                    if not isinstance(item, dict):
                        continue
                    distance = self._distance(state.get_self(), item)
                    if distance < 3:
                        self.stats["loot_priority"] += 1
                        item_id = item.get("instanceId") or item.get("id")
                        if item_id:
                            state.mark_item_attempted(item_id)
                            return PriorityDecision(
                                priority=2,
                                action_type="pickup",
                                target_id=item_id,
                                reasoning="Collecting loot",
                                confidence=0.8
                            )
            except Exception as e:
                pass
            
            # === PRIORITY 3: KILL ===
            
            if hp_ratio > 0.5 and threat.get("should_fight", False) and not state.alert_active:
                try:
                    enemies = state.get_enemies()
                    if enemies:
                        targetable = []
                        for e in enemies:
                            if not isinstance(e, dict):
                                continue
                            dist = self._distance(state.get_self(), e)
                            if dist < 10:
                                targetable.append(e)
                        
                        if targetable:
                            targetable.sort(key=lambda e: float(e.get("hp", 0)))
                            target = targetable[0]
                            
                            target_hp = float(target.get("hp", 0))
                            target_def = float(target.get("defense", target.get("def", 0)))
                            kill_prob = (my_atk - target_def) / max(target_hp, 1)
                            
                            if kill_prob > 0.6:
                                self.stats["kill_priority"] += 1
                                return PriorityDecision(
                                    priority=3,
                                    action_type="attack",
                                    target_id=target.get("agentId") or target.get("monsterId") or target.get("id"),
                                    reasoning=f"Kill opportunity (HP: {target_hp:.0f})",
                                    confidence=min(kill_prob, 0.9)
                                )
                except Exception as e:
                    pass
            
            # === PRIORITY 4: EXPLORE (DENGAN RUIN FARMING & ALERT MANAGEMENT) ===
            
            # CEK APAKAH AMAN UNTUK EXPLORE
            if hp_ratio > 0.5 and state.can_explore_ruin():
                try:
                    best_ruin = state.get_best_ruin_to_explore()
                    if best_ruin:
                        ruin_id = best_ruin.get("id") or best_ruin.get("ruinId")
                        distance = self._distance(state.get_self(), best_ruin)
                        gauge = best_ruin.get("gauge", 0)
                        content_type = best_ruin.get("contentType", "unknown")
                        max_gauge = best_ruin.get("maxGauge", 3)
                        
                        logger.debug(f"🗺️ Ruin: {content_type}, gauge: {gauge}/{max_gauge}, distance: {distance:.1f}")
                        
                        if distance < 3 and gauge < max_gauge:
                            self.stats["explore_priority"] += 1
                            
                            # Prediksi alert
                            predicted_alert = state.alert_gauge + 2
                            if gauge + 1 >= max_gauge:
                                predicted_alert += 4
                            
                            if predicted_alert >= 10 and hp_ratio < 0.7:
                                logger.warning(f"⚠️ Explore will trigger alert! HP: {hp_ratio:.0%}")
                                continue
                            
                            return PriorityDecision(
                                priority=4,
                                action_type="explore",
                                target_id=ruin_id,
                                reasoning=f"Exploring {content_type} ruin (gauge: {gauge}/{max_gauge})",
                                confidence=0.8
                            )
                        elif distance < 8:
                            self.stats["explore_priority"] += 1
                            return PriorityDecision(
                                priority=4,
                                action_type="move",
                                target_id=best_ruin.get("regionId"),
                                reasoning=f"Moving to {content_type} ruin",
                                confidence=0.65
                            )
                except Exception as e:
                    logger.debug(f"Ruin farming error: {e}")
            
            # === FALLBACK: MOVE TOWARDS CENTER ===
            
            try:
                for conn in state.get_connections():
                    if isinstance(conn, dict) and conn.get("safetyScore", 0) > 0.5:
                        return PriorityDecision(
                            priority=4,
                            action_type="move",
                            target_id=conn.get("regionId"),
                            reasoning="Moving to safer area",
                            confidence=0.5
                        )
                
                for conn in state.get_connections():
                    if isinstance(conn, dict) and not conn.get("insideDeathZone", False):
                        return PriorityDecision(
                            priority=4,
                            action_type="move",
                            target_id=conn.get("regionId"),
                            reasoning="Moving randomly",
                            confidence=0.3
                        )
            except Exception as e:
                pass
            
        except Exception as e:
            logger.debug(f"Priority decision error: {e}")
        
        return PriorityDecision(
            priority=5,
            action_type="wait",
            reasoning="No action available",
            confidence=0.1
        )
