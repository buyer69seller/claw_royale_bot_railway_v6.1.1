# src/main.py
"""Entry point bot Claw Royale dengan AI Auto-Pilot"""

import asyncio
import logging
import sys
import signal
from pathlib import Path

# Tambahkan src ke path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .client.rest_client import RestClient
from .lifecycle.driver import Driver
from .core.config import API_KEY
from .utils.logger import setup_logging
from .services.reward_service import RewardService
from .services.loadout_service import LoadoutService
from .utils.health import HealthServer
from .ai.knowledge import KnowledgeBase
from .core.constants import ensure_directories

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


# src/main.py - update main function

from .services.auth_service import AuthService

# src/main.py - tambahkan di bagian main

async def main():
    global health_server, driver_task, knowledge

    ensure_directories()
    setup_logging()
    logger = logging.getLogger(__name__)

    if not API_KEY:
        logger.error("❌ CLAW_API_KEY not set!")
        sys.exit(1)

    logger.info("🦀 Starting Claw Royale Bot v6.1 - Hybrid AI")
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
        # === LOGIN ===
        auth_service = AuthService(rest)
        
        try:
            account = await auth_service.login()
            logger.info("=" * 60)
            logger.info("✅ LOGIN SUCCESSFUL")
            logger.info(f"   Account: {account.get('name')}")
            logger.info(f"   ID: {account.get('id')}")
            logger.info(f"   Wallet: {account.get('walletAddress')}")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"❌ Login failed: {e}")
            sys.exit(1)

        # Auto-claim rewards
        try:
            reward_service = RewardService(rest)
            await reward_service.redeem_welcome_bundle()
        except Exception as e:
            logger.debug(f"Reward check skipped: {e}")

        # Loadout optimization
        try:
            loadout_service = LoadoutService(rest)
            if not await loadout_service.is_full_set():
                logger.info("🔧 Loadout not full, optimizing...")
                await loadout_service.optimize_loadout()
        except Exception as e:
            logger.debug(f"Loadout optimization skipped: {e}")

        logger.info("=" * 60)
        logger.info("🚀 Starting Hybrid AI Auto-Pilot...")
        logger.info("🧠 AI Engine: AI Auto-Pilot + Competitive v7")
        logger.info("🎮 Ready to join games...")
        logger.info("=" * 60)

        # Run driver with Hybrid AI
        driver = Driver(rest)
        driver.knowledge = knowledge
        driver.auth_service = auth_service
        driver_task = asyncio.create_task(driver.run())

        # Connect driver ke health server untuk metrics
        if health_server:
            health_server.set_driver(driver)

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
