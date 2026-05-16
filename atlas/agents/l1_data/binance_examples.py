"""
Binance WebSocket Agent Examples

Demonstrates usage of the BinanceWebSocketAgent for crypto market data ingestion.
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger
import redis.asyncio as redis

# Setup path to import atlas modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from atlas.agents.l1_data import BinanceWebSocketAgent
from atlas.config.settings import get_settings


# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)


async def example_basic_crypto():
    """
    Basic example: Start Binance agent and run for a fixed duration.
    """
    logger.info("=" * 80)
    logger.info("Example 1: Binance WebSocket Agent - Basic Usage")
    logger.info("=" * 80)
    
    # Initialize Redis and get settings
    redis_client = await redis.from_url("redis://localhost")
    settings = get_settings()
    
    try:
        # Create agent
        agent = BinanceWebSocketAgent(redis_client, settings.database_url)
        
        # Start agent
        await agent.start()
        logger.info(f"Agent started: {agent.agent_id}")
        logger.info(f"Crypto pairs: {agent.trading_pairs}")
        logger.info(f"Streams: {agent.stream_types}")
        
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


async def example_crypto_monitoring():
    """
    Advanced example: Monitor crypto agent metrics in real-time.
    """
    logger.info("=" * 80)
    logger.info("Example 2: Binance Agent - Metrics Monitoring")
    logger.info("=" * 80)
    
    redis_client = await redis.from_url("redis://localhost")
    settings = get_settings()
    
    try:
        # Create agent
        agent = BinanceWebSocketAgent(redis_client, settings.database_url)
        
        # Start agent
        await agent.start()
        logger.info(f"Agent started with {len(agent.trading_pairs)} crypto pairs")
        
        # Monitor for 60 seconds
        for i in range(6):
            await asyncio.sleep(10)
            
            # Get and log metrics
            logger.info(f"\n--- Metrics Check {i + 1} ---")
            logger.info(f"Messages Received: {agent._messages_received}")
            logger.info(f"Messages Processed: {agent._messages_processed}")
            logger.info(f"Messages Failed: {agent._messages_failed}")
            logger.info(f"Trades Received: {agent._trades_received}")
            logger.info(f"Depth Updates: {agent._depth_received}")
            logger.info(f"DB Errors: {agent._db_errors}")
            
            if agent.ws_client:
                status = agent.ws_client.get_status()
                logger.info(f"Connected: {status['connected']}")
                logger.info(f"Subscribed Pairs: {len(status['subscribed_pairs'])}")
        
    finally:
        await agent.stop()
        await redis_client.close()
        logger.info("Agent stopped")


async def example_crypto_vs_stocks():
    """
    Example: Compare Binance crypto and Polygon stocks in same system.
    
    Shows how both agents can run simultaneously.
    """
    logger.info("=" * 80)
    logger.info("Example 3: Multi-Source Data Ingestion (Crypto + Stocks)")
    logger.info("=" * 80)
    
    redis_client = await redis.from_url("redis://localhost")
    settings = get_settings()
    
    try:
        # Create Binance crypto agent
        crypto_agent = BinanceWebSocketAgent(redis_client, settings.database_url)
        
        # Try to create Polygon agent if available
        try:
            from atlas.agents.l1_data import PolygonWebSocketAgent
            stock_agent = PolygonWebSocketAgent(redis_client, settings.database_url)
            logger.info(f"Stock Agent: {len(stock_agent.symbols)} symbols")
        except Exception as e:
            logger.warning(f"Stock agent not available: {e}")
            stock_agent = None
        
        logger.info(f"Crypto Agent: {len(crypto_agent.trading_pairs)} pairs")
        
        # Start both agents
        await crypto_agent.start()
        if stock_agent:
            await stock_agent.start()
        
        logger.info("Both agents running for 30 seconds...")
        await asyncio.sleep(30)
        
        # Display metrics
        logger.info("\n--- Crypto Metrics ---")
        logger.info(f"Messages: {crypto_agent._messages_received}")
        logger.info(f"Trades: {crypto_agent._trades_received}")
        logger.info(f"Depth: {crypto_agent._depth_received}")
        
        if stock_agent:
            logger.info("\n--- Stock Metrics ---")
            logger.info(f"Messages: {stock_agent._messages_received}")
            logger.info(f"Processed: {stock_agent._messages_processed}")
        
    finally:
        await crypto_agent.stop()
        if stock_agent:
            await stock_agent.stop()
        await redis_client.close()
        logger.info("All agents stopped")


async def main():
    """
    Main entry point - run examples.
    """
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "Binance WebSocket Agent - Usage Examples".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("\n")
    
    examples = [
        ("1", "Basic Crypto", example_basic_crypto),
        ("2", "Metrics Monitoring", example_crypto_monitoring),
        ("3", "Multi-Source (Crypto + Stocks)", example_crypto_vs_stocks),
    ]
    
    print("\nAvailable examples:")
    for choice, name, _ in examples:
        print(f"  {choice}. {name}")
    print("  0. Exit")
    
    # For automated testing, run first example
    try:
        await example_basic_crypto()
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
