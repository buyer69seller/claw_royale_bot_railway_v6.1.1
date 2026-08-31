# src/lifecycle/driver.py - bagian yang diperbaiki

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
        """
        REJOIN: Kembali ke game yang sedang berjalan
        Digunakan saat timeout/stuck, bukan restart
        """
        logger.info(f"🔄 Attempting to REJOIN {entry_type} game...")
        
        # ===== LOAD PACK MODIFIERS =====
        try:
            await self._load_pack_modifiers()
        except Exception as e:
            logger.debug(f"Failed to load pack modifiers: {e}")
        
        try:
            # Cek apakah ada game yang sedang berjalan
            account = await self.rest.get_account()
            current_games = account.get("currentGames", [])
            
            # Cari game yang masih hidup
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
            
            # ... rest of rejoin code ...
            
        except Exception as e:
            logger.error(f"❌ Failed to rejoin game: {e}")
            logger.info("🔄 Falling back to new game...")
            await self._start_game(entry_type)
