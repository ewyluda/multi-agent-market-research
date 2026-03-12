"""Macroeconomic agent for fetching and analyzing US economic indicators."""

from typing import Dict, Any, Optional, List

from .base_agent import BaseAgent


class MacroAgent(BaseAgent):
    """Agent for fetching US macroeconomic data via OpenBB data provider.

    Provides broader economic context (interest rates, GDP, inflation,
    unemployment, yield curve) to supplement stock-specific analysis.

    Data source: OpenBB Platform (FRED) via injected data provider.
    No fallback source — macro data is supplementary.
    """

    # ── Core agent methods ───────────────────────────────────────────

    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch macroeconomic data via the injected data provider."""
        if not self._data_provider:
            self.logger.info("No data provider available, skipping macro agent")
            return {"ticker": self.ticker, "source": "none", "data": {}}

        self.logger.info("Fetching macroeconomic indicators from OpenBB")

        try:
            result = await self._data_provider.get_macro_indicators()
        except Exception as e:
            self.logger.error(f"Data provider error fetching macro indicators: {e}")
            return {"ticker": self.ticker, "source": "none", "data": {}}

        if result is None:
            self.logger.info("No macro data returned (FRED_API_KEY may be missing)")
            return {"ticker": self.ticker, "source": "none", "data": {}}

        # Map provider keys to expected dict structure
        fetched = sum(
            1 for k in ["fed_funds", "cpi", "gdp", "treasury_10y", "treasury_2y", "unemployment", "inflation"]
            if result.get(k)
        )
        self.logger.info(f"Fetched {fetched}/7 macro indicators from OpenBB")

        return {
            "ticker": self.ticker,
            "source": "openbb",
            "federal_funds_rate": result.get("fed_funds"),
            "cpi": result.get("cpi"),
            "real_gdp": result.get("gdp"),
            "treasury_yield_10y": result.get("treasury_10y"),
            "treasury_yield_2y": result.get("treasury_2y"),
            "unemployment": result.get("unemployment"),
            "inflation": result.get("inflation"),
        }

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze macroeconomic data and compute derived metrics."""
        if raw_data.get("source") == "none":
            return {
                "indicators": {},
                "yield_curve": {},
                "economic_cycle": "unknown",
                "risk_environment": "unknown",
                "data_source": "none",
                "summary": "No macroeconomic data available (no Alpha Vantage API key).",
            }

        indicators = {}

        # Process each indicator series
        indicator_map = {
            "federal_funds_rate": raw_data.get("federal_funds_rate"),
            "cpi": raw_data.get("cpi"),
            "real_gdp": raw_data.get("real_gdp"),
            "treasury_yield_10y": raw_data.get("treasury_yield_10y"),
            "treasury_yield_2y": raw_data.get("treasury_yield_2y"),
            "unemployment": raw_data.get("unemployment"),
            "inflation": raw_data.get("inflation"),
        }

        for name, series in indicator_map.items():
            indicators[name] = self._compute_trend(series)

        # Yield curve analysis
        yield_curve = self._compute_yield_curve(
            indicators.get("treasury_yield_10y", {}),
            indicators.get("treasury_yield_2y", {}),
        )

        # Economic cycle assessment
        economic_cycle = self._assess_economic_cycle(
            indicators.get("real_gdp", {}),
            indicators.get("unemployment", {}),
        )

        # Risk environment
        risk_environment = self._assess_risk_environment(
            indicators.get("federal_funds_rate", {}),
            indicators.get("inflation", {}),
        )

        # Generate summary
        summary = self._generate_macro_summary(indicators, yield_curve, economic_cycle, risk_environment)

        return {
            "indicators": indicators,
            "yield_curve": yield_curve,
            "economic_cycle": economic_cycle,
            "risk_environment": risk_environment,
            "data_source": raw_data.get("source", "openbb"),
            "summary": summary,
        }

    # ── Analysis helpers ─────────────────────────────────────────────

    def _compute_trend(self, series: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Compute current value, previous value, change, and trend for a series."""
        if not series or len(series) == 0:
            return {}

        current = series[0]["value"]
        # Compare to oldest available entry for trend
        previous = series[-1]["value"] if len(series) > 1 else current
        change = round(current - previous, 4)

        # Classify trend
        if abs(change) < 0.01 * max(abs(current), 0.01):
            trend = "stable"
        elif change > 0:
            trend = "rising"
        else:
            trend = "falling"

        return {
            "current": current,
            "previous": previous,
            "change": change,
            "trend": trend,
        }

    def _compute_yield_curve(
        self, yield_10y: Dict[str, Any], yield_2y: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute yield curve spread and status."""
        current_10y = yield_10y.get("current")
        current_2y = yield_2y.get("current")

        if current_10y is None or current_2y is None:
            return {"spread": None, "status": "unknown"}

        spread = round(current_10y - current_2y, 3)

        if spread > 0.5:
            status = "normal"
        elif spread >= 0:
            status = "flat"
        else:
            status = "inverted"

        return {"spread": spread, "status": status}

    def _assess_economic_cycle(
        self, gdp: Dict[str, Any], unemployment: Dict[str, Any]
    ) -> str:
        """Assess economic cycle from GDP and unemployment trends."""
        gdp_trend = gdp.get("trend", "")
        unemp_trend = unemployment.get("trend", "")

        if gdp_trend == "rising" and unemp_trend == "falling":
            return "expansion"
        elif gdp_trend == "rising" and unemp_trend == "rising":
            return "peak"
        elif gdp_trend == "falling" and unemp_trend == "rising":
            return "contraction"
        elif gdp_trend == "falling" and unemp_trend == "falling":
            return "trough"
        return "uncertain"

    def _assess_risk_environment(
        self, fed_funds: Dict[str, Any], inflation: Dict[str, Any]
    ) -> str:
        """Assess risk environment from fed funds and inflation trends."""
        fed_trend = fed_funds.get("trend", "")
        inflation_trend = inflation.get("trend", "")

        if fed_trend == "rising" or inflation_trend == "rising":
            return "hawkish"
        elif fed_trend == "falling" and inflation_trend in ("falling", "stable"):
            return "dovish"
        return "transitional"

    def _generate_macro_summary(
        self,
        indicators: Dict[str, Dict],
        yield_curve: Dict[str, Any],
        economic_cycle: str,
        risk_environment: str,
    ) -> str:
        """Generate a concise text summary of macroeconomic conditions."""
        parts = []

        fed = indicators.get("federal_funds_rate", {})
        if fed.get("current") is not None:
            parts.append(
                f"Fed funds rate at {fed['current']:.2f}% ({fed.get('trend', 'N/A')})"
            )

        yc = yield_curve
        if yc.get("spread") is not None:
            parts.append(
                f"yield curve {yc['status']} (10Y-2Y spread: {yc['spread']:+.2f}%)"
            )

        unemp = indicators.get("unemployment", {})
        if unemp.get("current") is not None:
            parts.append(f"unemployment {unemp['current']:.1f}% ({unemp.get('trend', 'N/A')})")

        infl = indicators.get("inflation", {})
        if infl.get("current") is not None:
            parts.append(f"inflation {infl['current']:.1f}% ({infl.get('trend', 'N/A')})")

        if not parts:
            return "Insufficient macroeconomic data available."

        summary = "Macro environment: " + ", ".join(parts) + ". "
        summary += f"Economic cycle: {economic_cycle}. Risk environment: {risk_environment}."
        return summary
