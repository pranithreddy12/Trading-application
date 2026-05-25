import re

with open('agents/l7_meta/system_health_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I want to change the scoring logic around ideation, backtest, validation, execution so they don't drop below 50 due to 0 throughput, saving them from false Emergency.

# Find the block where `scores["ideation"]` is computed
ideation_find = '''            scores["ideation"] = min(100.0, recent_strategies * 20)
            if scores["ideation"] < 20:
                degraded.append("ideation")'''

ideation_repl = '''            # Phase 28G: Economic starvation != collapse
            scores["ideation"] = max(50.0, min(100.0, recent_strategies * 20))
            if recent_strategies == 0:
                degraded.append("ideation")'''

content = content.replace(ideation_find, ideation_repl)

backtest_find = '''            scores["backtest"] = min(100.0, recent_backtests * 10)
            if scores["backtest"] < 10:
                degraded.append("backtest")'''

backtest_repl = '''            scores["backtest"] = max(50.0, min(100.0, recent_backtests * 10))
            if recent_backtests == 0:
                degraded.append("backtest")'''

content = content.replace(backtest_find, backtest_repl)

valid_find = '''            scores["validation"] = min(100.0, recent_validations * 25)
            if scores["validation"] < 25:
                degraded.append("validation")'''

valid_repl = '''            scores["validation"] = max(50.0, min(100.0, recent_validations * 25))
            if recent_validations == 0:
                degraded.append("validation")'''

content = content.replace(valid_find, valid_repl)

exec_find = '''            scores["execution"] = min(100.0, recent_trades * 10)
            if scores["execution"] < 10:
                degraded.append("execution")'''

exec_repl = '''            scores["execution"] = max(50.0, min(100.0, recent_trades * 10))
            if recent_trades == 0:
                degraded.append("execution")'''

content = content.replace(exec_find, exec_repl)

# Update system mode thresholds to decouple infrastructure from economic starvation
mode_find = '''        if degraded_pct > 0.5 or composite < 30:
            mode = "emergency"
        elif degraded_pct > 0.25 or composite < 60:
            mode = "degraded"'''

mode_repl = '''        # Phase 28G: Separate infrastructure from economic starvation
        infra_critical = any(x in degraded for x in ["ingestion", "audit", "replay"])
        if infra_critical or composite < 30:
            mode = "emergency"
        elif degraded_pct > 0.5 or composite < 60:
            mode = "degraded"'''

content = content.replace(mode_find, mode_repl)

with open('agents/l7_meta/system_health_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
