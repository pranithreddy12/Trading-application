# PHASE 28G — DIVERSITY REBALANCE REPORT

## Overview
The Diversity Engine was previously acting as a firewall, enforcing a rigid 75% hard overlap threshold. This led to strategy fossilization and evolutionary blockage as the strategy pool became saturated.

## Corrective Actions
1. **Hard Rejection Shift**: The hard rejection threshold was shifted from 0.75 to 0.95. The system now only strictly rejects exact byte-clones and literal duplicates to prevent replay clones and infinite archetype loops.
2. **Soft Evolutionary Penalties**: We implemented an institutional-grade governance approach. Strategies with high overlap (0.75 - 0.94) are no longer blocked. Instead, they receive soft evolutionary penalties:
   - Reduced exploration priority multiplier (0.5x)
   - Reduced mutation probability multiplier (0.5x)
   - Reduced evolutionary fitness bonus (-0.2)
3. **Novelty Boosts**: Truly novel organisms (overlap < 0.75) now receive corresponding evolutionary boosts to reward genuine exploration:
   - Exploration priority multiplier (1.5x)
   - Mutation probability multiplier (1.5x)
   - Evolutionary fitness bonus (+0.2)
4. **Evolutionary Memory Windowing**: Overlaps against the historical database are now scaled by a `time_weight`. This ensures recency decay, so that older archetypes slowly fade from the 'recent memory' penalty space, allowing the organism to revisit historically successful strategies without fossilizing over long soaks.

## Result
Governance-as-firewall has been successfully replaced with governance-as-evolutionary-pressure. The organism's throughput is unblocked while maintaining strict control over exact clone replication.
