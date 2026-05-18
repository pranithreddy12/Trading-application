"""
Integration verification script for Polygon WebSocket Agent.

This script tests all components to ensure proper setup:
1. Configuration loading
2. Database connectivity
3. Redis connectivity
4. API key validation
5. Client initialization

Run: python verify_setup.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Tuple

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.data.ingestion.polygon_ws_client import PolygonWebSocketClient
import redis.asyncio as redis


class Colors:
    """Terminal color codes"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str) -> None:
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")


def print_success(text: str, detail: str = "") -> None:
    """Print success message"""
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")
    if detail:
        print(f"  {Colors.YELLOW}→ {detail}{Colors.RESET}")


def print_error(text: str, detail: str = "") -> None:
    """Print error message"""
    print(f"{Colors.RED}✗{Colors.RESET} {text}")
    if detail:
        print(f"  {Colors.RED}→ {detail}{Colors.RESET}")


def print_info(text: str, detail: str = "") -> None:
    """Print info message"""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {text}")
    if detail:
        print(f"  {Colors.YELLOW}→ {detail}{Colors.RESET}")


async def verify_configuration() -> Tuple[bool, object]:
    """Verify configuration loading"""
    print_header("Configuration Verification")
    
    try:
        settings = get_settings()
        print_success("Settings loaded successfully")
        
        # Verify required settings
        checks = [
            ("Database URL", settings.database_url, "postgresql://" in settings.database_url),
            ("Redis URL", settings.redis_url, "redis://" in settings.redis_url),
            ("Polygon API Key", settings.polygon_api_key, len(settings.polygon_api_key) > 0),
            ("Watchlist", settings.watchlist, "," in settings.watchlist or len(settings.watchlist) > 0),
        ]
        
        all_ok = True
        for name, value, check in checks:
            if check:
                masked = value[:20] + "..." if len(value) > 20 else value
                print_success(f"{name} configured", masked)
            else:
                print_error(f"{name} not configured properly")
                all_ok = False
        
        return all_ok, settings
        
    except Exception as e:
        print_error("Failed to load settings", str(e))
        return False, None


async def verify_database(settings) -> bool:
    """Verify TimescaleDB connectivity"""
    print_header("Database Connectivity Verification")
    
    try:
        client = TimescaleClient(settings.database_url)
        await client.connect()
        print_success("Connected to TimescaleDB")
        
        # Test with a simple query
        async with client.engine.connect() as conn:
            result = await conn.execute(__import__('sqlalchemy').text("SELECT version();"))
            version = result.fetchone()
            print_success("Database query successful", f"Version: {version[0][:50]}...")
        
        return True
        
    except Exception as e:
        print_error("Database connection failed", str(e))
        return False


async def verify_redis(settings) -> bool:
    """Verify Redis connectivity"""
    print_header("Redis Connectivity Verification")
    
    try:
        redis_client = await redis.from_url(settings.redis_url)
        await redis_client.ping()
        print_success("Connected to Redis")
        
        # Test set/get
        await redis_client.set("test_key", "test_value", ex=1)
        value = await redis_client.get("test_key")
        
        if value and value.decode() == "test_value":
            print_success("Redis read/write test passed")
        else:
            print_error("Redis read/write test failed")
            return False
        
        await redis_client.close()
        return True
        
    except Exception as e:
        print_error("Redis connection failed", str(e))
        return False


async def verify_watchlist(settings) -> Tuple[bool, list]:
    """Verify watchlist parsing"""
    print_header("Watchlist Verification")
    
    try:
        watchlist = [s.strip().upper() for s in settings.watchlist.split(",")]
        watchlist = [s for s in watchlist if s]
        
        print_success(f"Watchlist parsed: {len(watchlist)} symbols")
        print(f"  {Colors.YELLOW}→ Symbols: {', '.join(watchlist[:10])}{'...' if len(watchlist) > 10 else ''}{Colors.RESET}")
        
        return True, watchlist
        
    except Exception as e:
        print_error("Watchlist parsing failed", str(e))
        return False, []


async def verify_polygon_client(settings, watchlist: list) -> bool:
    """Verify Polygon WebSocket client initialization"""
    print_header("Polygon WebSocket Client Verification")
    
    try:
        # Create test handler
        async def test_handler(msg):
            pass
        
        client = PolygonWebSocketClient(
            api_key=settings.polygon_api_key,
            symbols=watchlist[:3],  # Test with first 3 symbols
            message_handler=test_handler,
            stream_types=["Q", "T", "A"]
        )
        
        print_success("Client initialized successfully")
        
        # Check status
        status = client.get_status()
        print_success("Client status check passed", f"Subscriptions: {len(status['subscribed_symbols'])}")
        
        # Verify stream types
        print(f"  {Colors.YELLOW}→ Stream types: {', '.join(status['stream_types'])}{Colors.RESET}")
        print(f"  {Colors.YELLOW}→ Connected: {status['connected']}{Colors.RESET}")
        print(f"  {Colors.YELLOW}→ Authenticated: {status['authenticated']}{Colors.RESET}")
        
        return True
        
    except Exception as e:
        print_error("Polygon client initialization failed", str(e))
        return False


async def verify_data_models() -> bool:
    """Verify data models"""
    print_header("Data Models Verification")
    
    try:
        from atlas.data.storage.timescale_client import (
            QuoteData, TradeData, AggregateData
        )
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        
        # Test Quote
        quote = QuoteData(
            time=now,
            symbol="AAPL",
            bid=150.0,
            ask=150.01,
            bid_size=1000,
            ask_size=2000,
            bid_exchange="Q",
            ask_exchange="Q"
        )
        print_success("QuoteData model validated")
        
        # Test Trade
        trade = TradeData(
            time=now,
            symbol="AAPL",
            price=150.05,
            size=100,
            side="buy",
            exchange="Q"
        )
        print_success("TradeData model validated")
        
        # Test Aggregate
        agg = AggregateData(
            time=now,
            symbol="AAPL",
            open=149.5,
            high=151.0,
            low=149.0,
            close=150.5,
            volume=1000000,
            vwap=150.25
        )
        print_success("AggregateData model validated")
        
        return True
        
    except Exception as e:
        print_error("Data model validation failed", str(e))
        return False


async def verify_agent_import() -> bool:
    """Verify agent can be imported"""
    print_header("Agent Import Verification")
    
    try:
        from atlas.agents.l1_data import PolygonWebSocketAgent
        print_success("PolygonWebSocketAgent imported successfully")
        
        # Verify it extends BaseAgent
        from atlas.core.agent_base import BaseAgent
        if issubclass(PolygonWebSocketAgent, BaseAgent):
            print_success("PolygonWebSocketAgent correctly extends BaseAgent")
        else:
            print_error("PolygonWebSocketAgent does not extend BaseAgent")
            return False
        
        return True
        
    except Exception as e:
        print_error("Agent import failed", str(e))
        return False


async def main() -> None:
    """Run all verification checks"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "Polygon WebSocket Agent - Setup Verification".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    print(Colors.RESET)
    
    results = {}
    
    # Run all checks
    config_ok, settings = await verify_configuration()
    results["Configuration"] = config_ok
    
    if not settings:
        print_error("Cannot proceed without configuration")
        sys.exit(1)
    
    results["Database"] = await verify_database(settings)
    results["Redis"] = await verify_redis(settings)
    
    watchlist_ok, watchlist = await verify_watchlist(settings)
    results["Watchlist"] = watchlist_ok
    
    if watchlist:
        results["Polygon Client"] = await verify_polygon_client(settings, watchlist)
    
    results["Data Models"] = await verify_data_models()
    results["Agent Import"] = await verify_agent_import()
    
    # Summary
    print_header("Verification Summary")
    
    total_checks = len(results)
    passed_checks = sum(1 for v in results.values() if v)
    
    for check_name, result in results.items():
        if result:
            print_success(f"{check_name}: PASSED")
        else:
            print_error(f"{check_name}: FAILED")
    
    print()
    print(f"{'─'*70}")
    if passed_checks == total_checks:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ All checks passed! ({passed_checks}/{total_checks}){Colors.RESET}")
        print(f"\n{Colors.GREEN}The setup is ready to run the Polygon WebSocket Agent.{Colors.RESET}\n")
        print("Next steps:")
        print("  1. Review configuration in .env")
        print("  2. Initialize database: psql -U postgres -d atlas_db -f atlas/data/storage/schema.sql")
        print("  3. Run the agent: python -m atlas.agents.l1_data.polygon_ws_agent")
        print("  4. Or run examples: python atlas/agents/l1_data/examples.py\n")
        sys.exit(0)
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Some checks failed ({passed_checks}/{total_checks}){Colors.RESET}")
        print(f"\n{Colors.RED}Please fix the issues above before running the agent.{Colors.RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Verification cancelled by user{Colors.RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Verification failed: {e}{Colors.RESET}\n")
        sys.exit(1)
