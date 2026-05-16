"""
Example usage of the Polygon WebSocket Agent for real-time market data ingestion.

This example demonstrates:
1. Initializing the PolygonWebSocketAgent
2. Starting and monitoring data ingestion
3. Handling agent lifecycle
4. Accessing metrics and status
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger
import redis.asyncio as redis

# Setup path to import atlas modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from atlas.agents.l1_data import PolygonWebSocketAgent
from atlas.config.settings import get_settings


# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)


async def example_basic_usage():
    """
    Basic example: Start agent and let it run for a fixed duration.
    """
    logger.info("=" * 80)
    logger.info("Example 1: Basic Usage - Start Agent and Run")
    logger.info("=" * 80)
    
    # Initialize Redis and get settings
    redis_client = await redis.from_url("redis://localhost")
    settings = get_settings()
    
    try:
        # Create agent
        agent = PolygonWebSocketAgent(redis_client, settings.database_url)
        
        # Start agent
        await agent.start()
        logger.info(f"Agent started: {agent.agent_id}")
        logger.info(f"Agent status: {agent.status}")
        
        # Let it run for 30 seconds
        logger.info("Running for 30 seconds...")
        await asyncio.sleep(30)
        
        # Check WebSocket status
        if agent.ws_client:
            status = agent.ws_client.get_status()
            logger.info(f"WebSocket Status: {status}")
        
    finally:
        # Clean up
        await agent.stop()
        await redis_client.close()
        logger.info("Agent stopped")


async def example_with_monitoring():
    """
    Advanced example: Monitor agent metrics in real-time.
    """
    logger.info("=" * 80)
    logger.info("Example 2: With Metrics Monitoring")
    logger.info("=" * 80)
    
    redis_client = await redis.from_url("redis://localhost")
    settings = get_settings()
    
    try:
        # Create agent
        agent = PolygonWebSocketAgent(redis_client, settings.database_url)
        
        # Start agent
        await agent.start()
        logger.info(f"Agent started: {agent.agent_id}")
        
        # Monitor for 60 seconds
        for i in range(6):
            await asyncio.sleep(10)
            
            # Get and log metrics
            logger.info(f"\n--- Metrics Check {i + 1} ---")
            logger.info(f"Messages Received: {agent._messages_received}")
            logger.info(f"Messages Processed: {agent._messages_processed}")
            logger.info(f"Messages Failed: {agent._messages_failed}")
            logger.info(f"DB Errors: {agent._db_errors}")
            
            if agent.ws_client:
                status = agent.ws_client.get_status()
                logger.info(f"Connected: {status['connected']}")
                logger.info(f"Authenticated: {status['authenticated']}")
                logger.info(f"Subscribed Symbols: {len(status['subscribed_symbols'])}")
        
    finally:
        await agent.stop()
        await redis_client.close()
        logger.info("Agent stopped")


async def example_dynamic_subscription():
    """
    Example: Dynamically add/remove symbols during runtime.
    """
    logger.info("=" * 80)
    logger.info("Example 3: Dynamic Symbol Subscription")
    logger.info("=" * 80)
    
    redis_client = await redis.from_url("redis://localhost")
    settings = get_settings()
    
    try:
        # Create agent
        agent = PolygonWebSocketAgent(redis_client, settings.database_url)
        
        # Start agent
        await agent.start()
        logger.info(f"Agent started with initial symbols: {agent.symbols[:5]}")
        
        # Let it run for 10 seconds
        await asyncio.sleep(10)
        
        # Add new symbols
        if agent.ws_client:
            new_symbols = ["TSLA", "NVDA", "META"]
            await agent.ws_client.add_symbols(new_symbols)
            logger.info(f"Added symbols: {new_symbols}")
            
            await asyncio.sleep(10)
            
            # Remove symbols
            await agent.ws_client.remove_symbols(new_symbols)
            logger.info(f"Removed symbols: {new_symbols}")
            
            await asyncio.sleep(10)
            
            status = agent.ws_client.get_status()
            logger.info(f"Final subscribed symbols: {status['subscribed_symbols']}")
        
    finally:
        await agent.stop()
        await redis_client.close()
        logger.info("Agent stopped")


async def main():
    """
    Main entry point - run all examples.
    """
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "Polygon WebSocket Agent - Usage Examples".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("\n")
    
    examples = [
        ("1", "Basic Usage", example_basic_usage),
        ("2", "With Monitoring", example_with_monitoring),
        ("3", "Dynamic Subscription", example_dynamic_subscription),
    ]
    
    print("\nAvailable examples:")
    for choice, name, _ in examples:
        print(f"  {choice}. {name}")
    print("  0. Exit")
    
    # For automated testing, run first example
    try:
        await example_basic_usage()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error running example: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nInterrupted")
        sys.exit(0)
