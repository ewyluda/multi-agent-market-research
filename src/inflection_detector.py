"""Inflection detection engine with convergence scoring.

Compares prior and current KPI snapshots to identify meaningful inflection points
across agent sources. Convergence scoring measures how many independent agent
sources agree on direction.
"""

from typing import Any

# Per-category detection configuration
CATEGORY_THRESHOLDS: dict[str, dict[str, Any]] = {
    "valuation": {"min_pct_change": 5.0, "positive_direction": "down"},
    "growth": {"min_pct_change": 10.0, "positive_direction": "up"},
    "margins": {"min_pct_change": 5.0, "positive_direction": "up"},
    "guidance": {"min_pct_change": 3.0, "positive_direction": "up"},
    "sentiment": {"min_pct_change": 15.0, "positive_direction": "up"},
    "analyst": {"min_pct_change": 5.0, "positive_direction": "up"},
    "technical": {"min_pct_change": 10.0, "positive_direction": "up"},
}

# Per-KPI direction overrides for macro category
MACRO_POSITIVE_DIRECTIONS: dict[str, str] = {
    "fed_funds_rate": "down",
    "cpi_yoy": "down",
    "gdp_growth": "up",
    "yield_spread": "up",
}

MACRO_THRESHOLD = 5.0


class InflectionDetector:
    """Detects meaningful inflections in KPI snapshots and scores cross-agent convergence."""

    def detect(self, prior: list[dict], current: list[dict]) -> list[dict]:
        """Compare prior and current KPI snapshots and return detected inflections.

        Args:
            prior: List of prior KPI snapshot dicts with kpi_name, kpi_category, value, source_agent.
            current: List of current KPI snapshot dicts with same structure.

        Returns:
            List of inflection dicts for KPIs that exceeded their category threshold.
        """
        if not prior:
            return []

        # Build lookup: kpi_name -> snapshot
        prior_by_kpi: dict[str, dict] = {s["kpi_name"]: s for s in prior}

        inflections = []
        for snap in current:
            kpi_name = snap["kpi_name"]
            category = snap["kpi_category"]
            current_val = snap["value"]
            source_agent = snap["source_agent"]

            prior_snap = prior_by_kpi.get(kpi_name)
            if prior_snap is None:
                continue

            prior_val = prior_snap["value"]
            if prior_val == 0:
                continue

            pct_change = ((current_val - prior_val) / abs(prior_val)) * 100

            # Determine threshold and positive direction
            if category == "macro":
                threshold = MACRO_THRESHOLD
                positive_direction = MACRO_POSITIVE_DIRECTIONS.get(kpi_name, "up")
            else:
                cat_config = CATEGORY_THRESHOLDS.get(category)
                if cat_config is None:
                    continue
                threshold = cat_config["min_pct_change"]
                positive_direction = cat_config["positive_direction"]

            if abs(pct_change) < threshold:
                continue

            # Determine direction
            if positive_direction == "up":
                direction = "positive" if pct_change > 0 else "negative"
            else:  # positive_direction == "down"
                direction = "positive" if pct_change < 0 else "negative"

            magnitude = min(abs(pct_change) / 100, 1.0)

            inflections.append({
                "kpi_name": kpi_name,
                "direction": direction,
                "magnitude": magnitude,
                "prior_value": prior_val,
                "current_value": current_val,
                "pct_change": pct_change,
                "source_agent": source_agent,
                "summary": self._build_inflection_summary(
                    kpi_name, direction, pct_change, prior_val, current_val
                ),
            })

        return inflections

    def build_summary(self, inflections: list[dict]) -> dict:
        """Compute convergence score and build summary from inflections.

        Convergence is measured per unique agent source — multiple inflections from
        the same agent count as one vote in the direction of that agent's first inflection.

        Args:
            inflections: List of inflection dicts from detect().

        Returns:
            Summary dict with direction, convergence_score, inflection_count, headline, inflections.
        """
        if not inflections:
            return {
                "direction": "neutral",
                "convergence_score": 0.0,
                "inflection_count": 0,
                "headline": "No significant inflections detected.",
                "inflections": [],
            }

        # Each agent casts one vote — use the direction of the first inflection seen from that agent
        agent_direction: dict[str, str] = {}
        for inf in inflections:
            agent = inf["source_agent"]
            if agent not in agent_direction:
                agent_direction[agent] = inf["direction"]

        directions = list(agent_direction.values())
        positive_count = directions.count("positive")
        negative_count = directions.count("negative")
        total_agents = len(directions)

        if positive_count >= negative_count:
            majority_direction = "positive"
            agreeing = positive_count
        else:
            majority_direction = "negative"
            agreeing = negative_count

        convergence_score = agreeing / total_agents if total_agents > 0 else 0.0

        return {
            "direction": majority_direction,
            "convergence_score": convergence_score,
            "inflection_count": len(inflections),
            "headline": self._build_headline(inflections, majority_direction, convergence_score),
            "inflections": inflections,
        }

    def _build_inflection_summary(
        self,
        kpi_name: str,
        direction: str,
        pct_change: float,
        prior_val: float,
        current_val: float,
    ) -> str:
        """Build a human-readable one-liner for an inflection."""
        sign = "+" if pct_change > 0 else ""
        return (
            f"{kpi_name} moved {sign}{pct_change:.1f}% "
            f"({prior_val:.4g} → {current_val:.4g}): {direction}"
        )

    def _build_headline(
        self, inflections: list[dict], direction: str, convergence: float
    ) -> str:
        """Build a headline string summarising the inflection cluster.

        Format: "Strong/Moderate/Weak positive/negative inflection: kpi1, kpi2, kpi3"
        """
        if convergence >= 0.8:
            strength = "Strong"
        elif convergence >= 0.5:
            strength = "Moderate"
        else:
            strength = "Weak"

        kpi_names = ", ".join(inf["kpi_name"] for inf in inflections[:3])
        return f"{strength} {direction} inflection: {kpi_names}"
