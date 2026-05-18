"""
score_contract.py — Single Source of Truth for Institutional Strategy Scoring.

This contract normalizes scoring logic across the entire ATLAS ecosystem (Validators, Mutators, Ideators, Meta-Agents).
It resolves schema drift by strictly mapping physical backtest result fields to a unified 'institutional_score'.
"""

PRIMARY_SCORE_FIELD = "institutional_score"

def compute_institutional_score(results: dict) -> float:
    """
    Computes the canonical institutional score for a strategy based on its backtest results.
    
    If temporal scores are available (e.g., score_7d, score_14d), it can weight them.
    Currently defaults to 'short_window_score' as the provisional composite baseline, 
    ensuring continuity while supporting future structural upgrades without breaking agents.
    """
    if not results:
        return 0.0

    # If the system has migrated to explicitly passing 'institutional_score'
    if "institutional_score" in results:
        return float(results["institutional_score"])
        
    # If the legacy composite_score is present (and we want to honor it as truth for older runs)
    if "composite_score" in results:
        return float(results["composite_score"])
        
    # The current standard: short_window_score
    if "short_window_score" in results:
        return float(results["short_window_score"])

    # Fallback zero
    return 0.0
