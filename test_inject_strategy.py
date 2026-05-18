import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
import uuid
import json

async def main():
    settings = get_settings()
    timescale = TimescaleClient(settings.database_url)
    await timescale.connect()
    
    # Inject known-good strategy
    strategy_id = str(uuid.uuid4())
    params = {
        "strategy_name": "known_good_rsi",
        "hypothesis": "Test RSI mean reversion",
        "entry_conditions": ["rsi_14 < 40"],
        "exit_conditions": ["rsi_14 > 60"],
        "stop_loss": "0.5% below entry",
        "take_profit": "1% above entry",
        "position_sizing": "10% of portfolio",
        "timeframe": "1m",
        "asset_class": "equity",
        "expected_sharpe": 1.5,
        "expected_win_rate": 0.55,
        "risk_level": "medium",
        "tags": ["mean_reversion"]
    }
    
    await timescale.save_strategy(
        spec=params,
        status="pending_code",
        author_agent="manual_test"
    )
    print(f"Injected strategy {strategy_id} as pending_code")

if __name__ == '__main__':
    asyncio.run(main())
