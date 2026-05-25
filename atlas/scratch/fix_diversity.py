import re

with open('agents/l2_strategy/ideator_agent_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_block = '''
    def _compute_adaptive_threshold(
        self, regime: str = "neutral", strategy_throughput: int = 0
    ) -> tuple[float, float]:
        # Phase 28G: 0.95 hard duplicate threshold
        hard_threshold = 0.95
        soft_threshold = 0.75

        regime_lower = regime.lower()
        if "high_vol" in regime_lower or "panic" in regime_lower or "trending" in regime_lower:
            soft_threshold += 0.10
        elif "ranging" in regime_lower or "neutral" in regime_lower:
            soft_threshold -= 0.05
        elif "oversold" in regime_lower or "overbought" in regime_lower:
            soft_threshold += 0.05

        if strategy_throughput < 5:
            soft_threshold += 0.15
        elif strategy_throughput > 30:
            soft_threshold -= 0.05

        soft_threshold = max(0.40, min(0.90, soft_threshold))
        return hard_threshold, soft_threshold

    def _check_diversity(
        self,
        spec: dict,
        recent_combos: list[tuple[set[str], str]] | list[tuple],
        regime: str = "neutral",
        strategy_throughput: int = 0,
    ) -> tuple[bool, str, dict]:
        entry = spec.get("entry_conditions", [])
        exit_ = spec.get("exit_conditions", [])

        new_features: set[str] = set()
        for cond in entry + exit_:
            if isinstance(cond, str):
                new_features |= _known_features_in(cond)

        if not new_features:
            return True, "no features to compare", {}

        new_families: set[str] = set()
        for feat in new_features:
            family = _FEATURE_FAMILIES.get(feat)
            if family:
                new_families.add(family)

        if len(new_families) == 1:
            return False, f"single feature family only ({list(new_families)[0]})", {}

        adaptive_hard, adaptive_soft = self._compute_adaptive_threshold(
            regime, strategy_throughput
        )

        max_overlap = 0.0
        worst_match = ""
        
        # Phase 28G: Evolutionary memory windowing / recency decay
        for combo in recent_combos:
            if len(combo) >= 3:
                existing_features, archetype, time_weight = combo[0], combo[1], combo[2]
            elif len(combo) >= 2:
                existing_features, archetype = combo[0], combo[1]
                time_weight = 1.0
            else:
                continue

            if not existing_features:
                continue

            intersection = new_features & existing_features
            union = new_features | existing_features
            jaccard = len(intersection) / len(union) if union else 0.0

            # Evolutionary memory window decay - apply time_weight to overlap
            weighted_jaccard = jaccard * time_weight

            if weighted_jaccard > max_overlap:
                max_overlap = weighted_jaccard
                worst_match = archetype

            if weighted_jaccard >= adaptive_hard:
                shared = ", ".join(sorted(intersection)[:5])
                return False, f"exact clone overlap {weighted_jaccard:.0%} with {archetype}", {}

        modifiers = {}
        if max_overlap >= adaptive_soft:
            modifiers = {
                "exploration_priority_mult": 0.5,
                "mutation_probability_mult": 0.5,
                "evolutionary_fitness_bonus": -0.2
            }
            logger.info(f"{self.name}: Diversity soft penalty - {max_overlap:.0%} overlap with {worst_match}")
        else:
            modifiers = {
                "exploration_priority_mult": 1.5,
                "mutation_probability_mult": 1.5,
                "evolutionary_fitness_bonus": 0.2
            }
            logger.info(f"{self.name}: Diversity boost - novel organism (overlap {max_overlap:.0%})")

        self._prev_diversity_accept_rate = self._prev_diversity_accept_rate * 0.9 + 0.1
        return True, f"diverse (max_overlap={max_overlap:.0%})", modifiers
'''

content = re.sub(
    r'    def _compute_adaptive_threshold\(.*?(?=    # ─────────────────────────────────────────────────────────)',
    new_block,
    content,
    flags=re.DOTALL
)

# Also fix ideator pipeline around line 466 to receive modifiers and attach them
pipeline_find = '''                accepted, div_reason = self._check_diversity(
                    spec, existing_combos,
                    regime=regime_for_div,
                    strategy_throughput=throughput
                )'''

pipeline_replace = '''                # Phase 28G: Soft evolutionary penalties
                accepted, div_reason, modifiers = self._check_diversity(
                    spec, existing_combos,
                    regime=regime_for_div,
                    strategy_throughput=throughput
                )
                if modifiers:
                    if "metadata" not in spec:
                        spec["metadata"] = {}
                    spec["metadata"]["evolutionary_modifiers"] = modifiers
'''

content = content.replace(pipeline_find, pipeline_replace)

with open('agents/l2_strategy/ideator_agent_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)
