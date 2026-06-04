"""
regime_selector.py — Strategy selection weighted by market regime affinity.

Strategies whose archetype matches the current regime get a 2x weight
in selection rankings.
"""

from sqlalchemy import text


class RegimeSelector:
    """
    Selects strategies based on current market regime.
    Strategies that historically perform in the current regime
    get 2x weight in selection.
    """

    REGIME_AFFINITY = {
        "trending":        ["momentum", "trend_following", "breakout"],
        "ranging":         ["mean_reversion", "volatility_regime"],
        "high_volatility": ["volatility_regime", "breakout"],
        "oversold":        ["mean_reversion", "momentum"],
        "overbought":      ["mean_reversion", "volatility_regime"],
    }

    async def get_regime_weighted_ranking(
        self,
        db,
        current_regime: str,
        limit: int = 10,
    ) -> list[dict]:
        """
        Returns strategies ranked by composite_fitness × regime_affinity_multiplier.

        Parameters
        ----------
        db : TimescaleClient
            Database client with an ``engine`` attribute.
        current_regime : str
            One of the known regime labels (trending, ranging, high_volatility,
            oversold, overbought, etc.).
        limit : int
            Maximum number of results to return.

        Returns
        -------
        list[dict]
            Ranked strategies sorted by ``regime_weighted_score`` descending.
        """
        affinity_archetypes = self.REGIME_AFFINITY.get(
            current_regime, [],
        )

        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT
                    s.id::text,
                    s.name,
                    s.parameters->>'archetype' as archetype,
                    s.parameters->>'tags' as tags,
                    b.composite_fitness,
                    b.win_rate,
                    b.sharpe,
                    b.short_window_score
                FROM strategies s
                JOIN backtest_results b ON b.strategy_id = s.id
                WHERE s.status IN ('validated','elite','research_candidate')
                  AND b.composite_fitness > 0
                ORDER BY b.composite_fitness DESC
                LIMIT :limit
            """), {"limit": limit * 3})
            rows = r.fetchall()

        results = []
        for row in rows:
            d = dict(row._mapping)
            archetype = d.get("archetype") or ""
            tags = d.get("tags") or ""

            # Apply regime affinity multiplier
            multiplier = 1.0
            for aff in affinity_archetypes:
                if aff in str(archetype) or aff in str(tags):
                    multiplier = 2.0
                    break

            composite = float(d.get("composite_fitness") or 0)
            d["regime_weighted_score"] = composite * multiplier
            d["regime_multiplier"] = multiplier
            results.append(d)

        results.sort(key=lambda x: x["regime_weighted_score"], reverse=True)
        return results[:limit]
