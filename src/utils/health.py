# src/utils/health.py
"""Health check server untuk monitoring dengan metrics"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any

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
        self._start_time = time.time()
        self._driver_ref = None  # Reference ke driver untuk metrics
    
    async def start(self, driver=None):
        """Start health check server"""
        if not HAS_AIOHTTP:
            return
        
        if self._running:
            return
        
        self._driver_ref = driver
        
        try:
            app = web.Application()
            app.router.add_get('/health', self._health_handler)
            app.router.add_get('/ready', self._ready_handler)
            app.router.add_get('/metrics', self._metrics_handler)
            app.router.add_get('/stats', self._stats_handler)
            
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
        """Health check endpoint"""
        return web.Response(text="OK", status=200)
    
    @staticmethod
    async def _ready_handler(request):
        """Readiness check endpoint"""
        return web.Response(text="READY", status=200)
    
    async def _metrics_handler(self, request):
        """Metrics endpoint - detailed"""
        uptime = int(time.time() - self._start_time)
        
        metrics = {
            "uptime": uptime,
            "status": "running",
            "timestamp": int(time.time())
        }
        
        # Add driver metrics if available
        if self._driver_ref:
            try:
                perf = self._driver_ref.get_performance() if hasattr(self._driver_ref, 'get_performance') else {}
                metrics.update({
                    "game_count": perf.get("game_count", 0),
                    "total_actions": perf.get("total_actions", 0),
                    "success_rate": perf.get("success_rate", 0),
                    "is_in_game": perf.get("is_in_game", False)
                })
                
                # Hybrid AI stats
                hybrid_stats = perf.get("hybrid_stats", {})
                if hybrid_stats:
                    metrics["hybrid_ai"] = {
                        "decisions": hybrid_stats.get("decisions_made", 0),
                        "ai_decisions": hybrid_stats.get("ai_decisions", 0),
                        "heuristic_decisions": hybrid_stats.get("heuristic_decisions", 0),
                        "survival_priority": hybrid_stats.get("survival_priority", 0),
                        "kill_priority": hybrid_stats.get("kill_priority", 0),
                        "loot_priority": hybrid_stats.get("loot_priority", 0),
                        "explore_priority": hybrid_stats.get("explore_priority", 0)
                    }
            except Exception as e:
                logger.debug(f"Failed to get driver metrics: {e}")
        
        return web.json_response(metrics)
    
    async def _stats_handler(self, request):
        """Stats endpoint - human readable"""
        uptime = int(time.time() - self._start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        
        stats = {
            "bot": {
                "status": "running",
                "uptime": f"{hours}h {minutes}m {seconds}s",
                "version": "6.1.0"
            }
        }
        
        if self._driver_ref:
            try:
                perf = self._driver_ref.get_performance() if hasattr(self._driver_ref, 'get_performance') else {}
                stats["game"] = {
                    "current_games": perf.get("game_count", 0),
                    "total_actions": perf.get("total_actions", 0),
                    "success_rate": f"{perf.get('success_rate', 0) * 100:.1f}%",
                    "is_in_game": perf.get("is_in_game", False)
                }
                
                hybrid_stats = perf.get("hybrid_stats", {})
                if hybrid_stats:
                    stats["hybrid_ai"] = {
                        "total_decisions": hybrid_stats.get("decisions_made", 0),
                        "ai_decisions": hybrid_stats.get("ai_decisions", 0),
                        "heuristic_decisions": hybrid_stats.get("heuristic_decisions", 0),
                        "survival_priority": hybrid_stats.get("survival_priority", 0),
                        "kill_priority": hybrid_stats.get("kill_priority", 0),
                        "loot_priority": hybrid_stats.get("loot_priority", 0),
                        "explore_priority": hybrid_stats.get("explore_priority", 0)
                    }
            except Exception as e:
                logger.debug(f"Failed to get driver stats: {e}")
        
        return web.json_response(stats)
    
    def set_driver(self, driver):
        """Set driver reference untuk metrics"""
        self._driver_ref = driver
