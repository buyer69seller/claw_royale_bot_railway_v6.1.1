# src/utils/health.py
"""Health check server untuk monitoring"""

import asyncio
import logging

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger(__name__)

class HealthServer:
    def __init__(self, port: int = 8080):
        self.port = port
        self._runner = None
        self._site = None
        self._running = False
        
    async def start(self):
        if not HAS_AIOHTTP:
            return
        
        if self._running:
            return
        
        try:
            app = web.Application()
            app.router.add_get('/health', self._health_handler)
            app.router.add_get('/ready', self._ready_handler)
            app.router.add_get('/metrics', self._metrics_handler)
            
            self._runner = web.AppRunner(app)
            await self._runner.setup()
            self._site = web.TCPSite(self._runner, '0.0.0.0', self.port)
            await self._site.start()
            self._running = True
            logger.info(f"Health server started on port {self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start health server: {e}")
    
    async def stop(self):
        if self._runner and self._running:
            await self._runner.cleanup()
            self._running = False
    
    @staticmethod
    async def _health_handler(request):
        return web.Response(text="OK", status=200)
    
    @staticmethod
    async def _ready_handler(request):
        return web.Response(text="READY", status=200)
    
    @staticmethod
    async def _metrics_handler(request):
        import time
        return web.json_response({
            "uptime": int(time.time() - request.app.get("start_time", time.time())),
            "status": "running"
        })