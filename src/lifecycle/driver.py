# src/lifecycle/driver.py - bagian yang diubah (hanya tambahan)

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
        self._pack_modifiers_loaded = False  # <-- TAMBAHKAN

        # Game state
        self.current_game: Optional[GameState] = None
        self.delay = MIN_RETRY_DELAY
        self.game_count = 0
        self.ai_enabled = True

        # Performance tracking
        self.start_time = None
        self.total_actions = 0
        self.successful_actions = 0

    # ===== TAMBAHKAN METHOD INI =====
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

    async def _start_game(self, entry_type: str):
        """Mulai game baru - via WebSocket dengan Hybrid AI"""
        logger.info(f"🎮 Joining {entry_type} game...")
        logger.info(f"🔑 API Key: {self.rest.api_key[:10]}...")

        try:
            # ===== LOAD PACK MODIFIERS (BARU) =====
            await self._load_pack_modifiers()
            
            if not self.auth_service:
                from ..services.auth_service import AuthService
                self.auth_service = AuthService(self.rest)
                logger.info("✅ Auth service initialized")

            headers = await self.auth_service.get_websocket_auth()
            logger.info(f"📨 Headers: {headers}")

            # ... rest of existing _start_game code ...

    async def _resume_game(self, entry_type: str):
        """Resume game yang sedang berjalan"""
        logger.info(f"🔄 Resuming {entry_type} game...")
        
        # ===== LOAD PACK MODIFIERS (BARU) =====
        await self._load_pack_modifiers()
        
        try:
            await self._start_game(entry_type)
        except ResumeTargetDeadError:
            logger.info(f"{entry_type} resume target dead, re-dialing...")
            raise

    async def _rejoin_game(self, entry_type: str):
        """
        REJOIN: Kembali ke game yang sedang berjalan
        Digunakan saat timeout/stuck, bukan restart
        """
        logger.info(f"🔄 Attempting to REJOIN {entry_type} game...")
        
        # ===== LOAD PACK MODIFIERS (BARU) =====
        await self._load_pack_modifiers()
        
        try:
            # Cek apakah ada game yang sedang berjalan
            account = await self.rest.get_account()
            # ... rest of existing _rejoin_game code ...
