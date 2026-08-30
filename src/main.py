# src/main.py
"""Entry point bot Claw Royale dengan AI Auto-Pilot"""

import asyncio
import logging
import sys
import signal
from pathlib import Path

# Tambahkan src ke path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.rest_client import RestClient
from lifecycle.driver import Driver
from core.config import API_KEY
from utils.logger import setup_logging
from services.reward_service import RewardService
from services.loadout_service import LoadoutService
from utils.health import HealthServer
from ai.knowledge import KnowledgeBase

# Global untuk cleanup
health_server = None
driver_task = None
knowledge = None

async def shutdown(signal, loop):
    """Graceful shutdown"""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signal}, shutting down...")
    
    # Save knowledge
    if knowledge:
        knowledge.save()
        logger.info("Knowledge saved")
    
    # Stop health server
    if health_server:
        await health_server.stop()
    
    # Cancel driver task
    if driver_task:
        driver_task.cancel()
        try:
            await driver_task
        except asyncio.CancelledError:
            pass
    
    loop.stop()

async def main():
    """Main entry point"""
    global health_server, driver_task, knowledge
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Cek API key
    if not API_KEY:
        logger.error("❌ CLAW_API_KEY not set! Please set in .env or environment")
        sys.exit(1)
    
    logger.info("🦀 Starting Claw Royale Bot v6.1 - AI Auto-Pilot")
    logger.info("=" * 60)
    
    # Init Knowledge Base
    knowledge = KnowledgeBase()
    insights = knowledge.get_insights()
    logger.info(f"📊 AI Knowledge:")
    logger.info(f"   - Win Rate: {insights['performance']['win_rate']*100:.1f}%")
    logger.info(f"   - Avg Survival: {insights['performance']['avg_survival']:.0f} turns")
    logger.info(f"   - Kills/Game: {insights['performance']['kills_per_game']:.1f}")
    logger.info(f"   - Success Rate: {insights['performance']['success_rate']*100:.1f}%")
    logger.info(f"   - Total Games: {insights['total_games']}")
    logger.info("=" * 60)
    
    # Setup health check server
    health_server = HealthServer(port=8080)
    await health_server.start()
    logger.info("✅ Health server started on port 8080")
    
    # Start bot
    async with RestClient(API_KEY) as rest:
        # Auto-claim rewards at startup
        try:
            reward_service = RewardService(rest)
            
            # Welcome bundle
            if await reward_service.redeem_welcome_bundle():
                logger.info("🎁 Welcome bundle claimed!")
            
            # Check available rewards
            available = await reward_service.get_available_rewards()
            if available.get("daily") or available.get("quests"):
                logger.info(f"📦 Rewards available: {available}")
                result = await reward_service.check_and_claim_rewards()
                if result["claimed"]:
                    logger.info(f"🎉 Claimed: {result['claimed']}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to check rewards: {e}")
        
        # Optimize loadout
        try:
            loadout_service = LoadoutService(rest)
            if not await loadout_service.is_full_set():
                logger.info("🔧 Loadout not full, optimizing...")
                result = await loadout_service.optimize_loadout()
                if result.get("changes"):
                    logger.info(f"✅ Loadout optimized: {result['changes']}")
                else:
                    logger.info("✅ Loadout already optimal")
        except Exception as e:
            logger.warning(f"⚠️ Failed to optimize loadout: {e}")
        
        logger.info("=" * 60)
        logger.info("🚀 Starting AI Auto-Pilot...")
        logger.info("=" * 60)
        
        # Run driver with AI
        driver = Driver(rest)
        driver.knowledge = knowledge
        driver_task = asyncio.create_task(driver.run())
        
        try:
            await driver_task
        except asyncio.CancelledError:
            logger.info("Driver task cancelled")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Setup signal handlers
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    finally:
        if knowledge:
            knowledge.save()
        loop.close()
        sys.exit(0)