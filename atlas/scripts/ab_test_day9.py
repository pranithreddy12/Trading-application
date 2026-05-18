import os
import sys
import time
import asyncio
import subprocess
from pathlib import Path
from loguru import logger
from sqlalchemy import create_engine, text
from atlas.config.settings import get_settings

engine = create_engine(get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://"))

def get_count(batch: str, status: str = None) -> int:
    with engine.connect() as conn:
        if status:
            return conn.execute(text(f"SELECT COUNT(*) FROM strategies WHERE generation_batch = '{batch}' AND status = '{status}'")).scalar()
        else:
            return conn.execute(text(f"SELECT COUNT(*) FROM strategies WHERE generation_batch = '{batch}'")).scalar()

def run_batch(batch_name: str, mutation_flag: str, target_count: int = 50):
    logger.info(f"=== STARTING BATCH: {batch_name} (MUTATION_INTELLIGENCE={mutation_flag}) ===")
    
    env = os.environ.copy()
    env["MUTATION_INTELLIGENCE"] = mutation_flag
    env["GENERATION_BATCH"] = batch_name
    # atlas.* imports resolve when the parent of the atlas/ folder is on PYTHONPATH
    parent_dir = str(Path(os.getcwd()).parent)
    cwd = os.getcwd()
    env["PYTHONPATH"] = parent_dir + os.pathsep + cwd + os.pathsep + env.get("PYTHONPATH", "")

    logger.info(f"Starting IdeatorAgent...")
    ideator = subprocess.Popen([sys.executable, "-m", "agents.l2_strategy.ideator_agent_v2"], env=env)
    
    # Wait for target_count strategies to be generated
    while True:
        count = get_count(batch_name)
        logger.info(f"[{batch_name}] Generated: {count}/{target_count}")
        if count >= target_count:
            break
        time.sleep(10)
        
    logger.info(f"[{batch_name}] Target reached! Terminating Ideator...")
    ideator.terminate()
    ideator.wait()

    logger.info(f"[{batch_name}] Starting CoderAgent...")
    coder = subprocess.Popen([sys.executable, "-m", "agents.l2_strategy.coder_agent"], env=env)
    while True:
        pending = get_count(batch_name, "pending_code")
        logger.info(f"[{batch_name}] Pending Code: {pending}")
        if pending == 0:
            break
        time.sleep(10)
    coder.terminate()
    coder.wait()
    
    logger.info(f"[{batch_name}] Starting Backtester...")
    # backtest_runner processes pending_backtest
    # Let's use batch_reprocess_all.py or run backtest_runner directly
    backtest = subprocess.Popen([sys.executable, "-m", "agents.l3_backtest.backtest_runner"], env=env)
    while True:
        pending = get_count(batch_name, "pending_backtest")
        logger.info(f"[{batch_name}] Pending Backtest: {pending}")
        if pending == 0:
            break
        time.sleep(10)
    backtest.terminate()
    backtest.wait()

    logger.info(f"[{batch_name}] Starting Validator...")
    validator = subprocess.Popen([sys.executable, "-m", "agents.l3_backtest.validator_agent"], env=env)
    while True:
        pending = get_count(batch_name, "pending_validation")
        logger.info(f"[{batch_name}] Pending Validation: {pending}")
        if pending == 0:
            break
        time.sleep(10)
    validator.terminate()
    validator.wait()

    logger.info(f"=== FINISHED BATCH: {batch_name} ===")

if __name__ == "__main__":
    logger.info("Cleaning up any existing day9 strategies to start fresh...")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM strategies WHERE generation_batch IN ('day9_control', 'day9_priors')"))
    
    run_batch("day9_control", "OFF", 50)
    run_batch("day9_priors", "ON", 50)
    
    logger.info("A/B Test completed!")
