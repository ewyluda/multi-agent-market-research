"""Options flow agent for analyzing options market data and unusual activity."""

import asyncio
import yfinance as yf
from typing import Dict, Any, Optional, List
from .base_agent import BaseAgent


class OptionsAgent(BaseAgent):
    """Agent for fetching and analyzing options chain data.

    Data source priority:
        1. Alpha Vantage API (REALTIME_OPTIONS + HISTORICAL_OPTIONS)
        2. yfinance (fallback)

    Analyzes:
        - Put/Call ratios (volume and open interest)
        - Max pain strike price
        - Unusual activity (volume >> open interest)
        - Implied volatility distribution
        - Near-term expiry summaries
    """

    # ──────────────────────────────────────────────
    # Alpha Vantage Data Fetching
    # ──────────────────────────────────────────────

    async def _fetch_av_realtime_options(self) -> Optional[Dict[str, Any]]:
        """
        Fetch realtime options chain from Alpha Vantage REALTIME_OPTIONS.

        Returns:
            Dict with options chain data, or None
        """
        data = await self._av_request({
            "function": "REALTIME_OPTIONS",
            "symbol": self.ticker,
            "require_greeks": "true",
            "datatype": "json",
        })
        if not data:
            return None

        # Check for premium endpoint error
        if "message" in data and "premium" in data.get("message", "").lower():
            self.logger.info(f"REALTIME_OPTIONS is a premium endpoint for {self.ticker}")
            return None

        contracts = data.get("data", [])
        if not contracts:
            return None

        return {"contracts": contracts, "source": "realtime"}

    async def _fetch_av_historical_options(self) -> Optional[Dict[str, Any]]:
        """
        Fetch historical options chain from Alpha Vantage HISTORICAL_OPTIONS.

        Returns:
            Dict with options chain data, or None
        """
        data = await self._av_request({
            "function": "HISTORICAL_OPTIONS",
            "symbol": self.ticker,
            "datatype": "json",
        })
        if not data:
            return None

        # Check for premium endpoint error
        if "Information" in data and "premium" in data.get("Information", "").lower():
            self.logger.info(f"HISTORICAL_OPTIONS is a premium endpoint for {self.ticker}")
            return None
        if "message" in data and "premium" in data.get("message", "").lower():
            self.logger.info(f"HISTORICAL_OPTIONS is a premium endpoint for {self.ticker}")
            return None

        contracts = data.get("data", [])
        if not contracts:
            return None

        return {"contracts": contracts, "source": "historical"}

    # ──────────────────────────────────────────────
    # yfinance Fallback
    # ──────────────────────────────────────────────

    async def _fetch_yfinance_options(self) -> Optional[Dict[str, Any]]:
        """
        Fetch options chain from yfinance as fallback.

        Returns:
            Dict with normalized options chain data, or None
        """
        ticker_obj = yf.Ticker(self.ticker)

        # Get available expiration dates
        expirations = await self._retry_fetch(
            lambda: ticker_obj.options,
            label=f"{self.ticker} options expirations",
        )
        if not expirations or len(expirations) == 0:
            return None

        # Fetch chains for the nearest 2 expiration dates
        all_contracts = []
        for exp in expirations[:2]:
            chain = await self._retry_fetch(
                lambda e=exp: ticker_obj.option_chain(e),
                label=f"{self.ticker} option_chain({exp})",
            )
            if chain is None:
                continue

            # Normalize calls
            if chain.calls is not None and not chain.calls.empty:
                for _, row in chain.calls.iterrows():
                    all_contracts.append(self._normalize_yf_contract(row, "call", exp))

            # Normalize puts
            if chain.puts is not None and not chain.puts.empty:
                for _, row in chain.puts.iterrows():
                    all_contracts.append(self._normalize_yf_contract(row, "put", exp))

        if not all_contracts:
            return None

        return {"contracts": all_contracts, "source": "yfinance"}

    def _normalize_yf_contract(self, row, option_type: str, expiration: str) -> Dict[str, Any]:
        """Normalize a yfinance option row to match AV schema."""
        return {
            "contractID": str(row.get("contractSymbol", "")),
            "symbol": self.ticker,
            "expiration": expiration,
            "strike": str(row.get("strike", 0)),
            "type": option_type,
            "last": str(row.get("lastPrice", 0)),
            "mark": str((row.get("bid", 0) + row.get("ask", 0)) / 2),
            "bid": str(row.get("bid", 0)),
            "ask": str(row.get("ask", 0)),
            "volume": str(int(row.get("volume", 0)) if row.get("volume") is not None else 0),
            "open_interest": str(int(row.get("openInterest", 0)) if row.get("openInterest") is not None else 0),
            "impliedVolatility": str(row.get("impliedVolatility", 0)),
        }

    # ──────────────────────────────────────────────
    # Data Fetching (AV first, yfinance fallback)
    # ──────────────────────────────────────────────

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch options chain data. Tries Alpha Vantage first, falls back to yfinance.

        Returns:
            Dictionary with options chain contracts and source
        """
        result = {"ticker": self.ticker, "source": "unknown"}

        # ── Try Alpha Vantage first ──
        av_api_key = self.config.get("ALPHA_VANTAGE_API_KEY", "")
        if av_api_key:
            self.logger.info(f"Fetching {self.ticker} options data from Alpha Vantage (primary)")

            # Try realtime first, then historical
            av_realtime, av_historical = await asyncio.gather(
                self._fetch_av_realtime_options(),
                self._fetch_av_historical_options(),
                return_exceptions=True,
            )

            if isinstance(av_realtime, Exception):
                self.logger.warning(f"Alpha Vantage realtime options fetch raised: {av_realtime}")
                av_realtime = None
            if isinstance(av_historical, Exception):
                self.logger.warning(f"Alpha Vantage historical options fetch raised: {av_historical}")
                av_historical = None

            # Prefer realtime, fall back to historical
            av_data = av_realtime or av_historical
            if av_data and av_data.get("contracts"):
                self.logger.info(
                    f"Alpha Vantage returned {len(av_data['contracts'])} option contracts for {self.ticker}"
                )
                result["source"] = "alpha_vantage"
                result["contracts"] = av_data["contracts"]
                result["av_source_type"] = av_data.get("source", "unknown")
                return result
            else:
                self.logger.info(f"Alpha Vantage options incomplete for {self.ticker}, falling back to yfinance")

        # ── Fallback to yfinance ──
        self.logger.info(f"Fetching {self.ticker} options data from yfinance (fallback)")

        yf_data = await self._fetch_yfinance_options()
        if yf_data and yf_data.get("contracts"):
            result["source"] = "yfinance"
            result["contracts"] = yf_data["contracts"]
            return result

        # No options data available — not all tickers have options
        self.logger.warning(f"No options data available for {self.ticker}")
        result["source"] = "none"
        result["contracts"] = []
        return result

    # ──────────────────────────────────────────────
    # Analysis
    # ──────────────────────────────────────────────

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze options chain data for unusual activity and market signals.

        Args:
            raw_data: Raw options chain data from AV or yfinance

        Returns:
            Options analysis with P/C ratios, unusual activity, and signals
        """
        contracts = raw_data.get("contracts", [])
        source = raw_data.get("source", "unknown")

        analysis = {
            "data_source": source,
            "total_contracts": len(contracts),
        }

        if not contracts:
            analysis["put_call_ratio"] = None
            analysis["put_call_oi_ratio"] = None
            analysis["max_pain"] = None
            analysis["unusual_activity"] = []
            analysis["highest_iv_contracts"] = []
            analysis["near_term_summary"] = {}
            analysis["overall_signal"] = "neutral"
            analysis["summary"] = f"No options data available for {self.ticker}. [Source: {source}]"
            return analysis

        # Separate calls and puts
        calls = [c for c in contracts if c.get("type", "").lower() == "call"]
        puts = [c for c in contracts if c.get("type", "").lower() == "put"]

        # Calculate put/call ratios
        analysis["put_call_ratio"] = self._calculate_pc_ratio(calls, puts, "volume")
        analysis["put_call_oi_ratio"] = self._calculate_pc_ratio(calls, puts, "open_interest")

        # Calculate max pain
        analysis["max_pain"] = self._calculate_max_pain(contracts)

        # Detect unusual activity
        analysis["unusual_activity"] = self._detect_unusual_activity(contracts)

        # Find highest IV contracts
        analysis["highest_iv_contracts"] = self._find_highest_iv(contracts)

        # Near-term expiry summary
        analysis["near_term_summary"] = self._summarize_near_term(contracts)

        # Determine overall signal
        analysis["overall_signal"] = self._determine_signal(analysis)

        # Generate summary
        analysis["summary"] = self._generate_summary(analysis)

        return analysis

    def _safe_float(self, value, default: float = 0.0) -> float:
        """Safely convert a value to float."""
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def _safe_int(self, value, default: int = 0) -> int:
        """Safely convert a value to int."""
        try:
            return int(float(value)) if value is not None else default
        except (ValueError, TypeError):
            return default

    def _calculate_pc_ratio(
        self, calls: List[Dict], puts: List[Dict], field: str
    ) -> Optional[float]:
        """Calculate put/call ratio for a given field (volume or open_interest)."""
        total_call = sum(self._safe_int(c.get(field, 0)) for c in calls)
        total_put = sum(self._safe_int(p.get(field, 0)) for p in puts)

        if total_call == 0:
            return None

        return round(total_put / total_call, 3)

    def _calculate_max_pain(self, contracts: List[Dict]) -> Optional[float]:
        """
        Calculate max pain strike — the price where option writers suffer least.

        Max pain = strike with minimum total intrinsic value across all options.
        """
        # Collect unique strikes
        strikes = set()
        for c in contracts:
            strike = self._safe_float(c.get("strike"))
            if strike > 0:
                strikes.add(strike)

        if not strikes:
            return None

        calls = [c for c in contracts if c.get("type", "").lower() == "call"]
        puts = [c for c in contracts if c.get("type", "").lower() == "put"]

        min_pain = float("inf")
        max_pain_strike = None

        for test_price in sorted(strikes):
            total_pain = 0.0

            # Pain for call holders if price settles at test_price
            for c in calls:
                strike = self._safe_float(c.get("strike"))
                oi = self._safe_int(c.get("open_interest"))
                if test_price > strike:
                    total_pain += (test_price - strike) * oi

            # Pain for put holders if price settles at test_price
            for p in puts:
                strike = self._safe_float(p.get("strike"))
                oi = self._safe_int(p.get("open_interest"))
                if test_price < strike:
                    total_pain += (strike - test_price) * oi

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_price

        return max_pain_strike

    def _detect_unusual_activity(self, contracts: List[Dict], threshold: float = 2.0) -> List[Dict]:
        """
        Detect contracts with unusual volume relative to open interest.

        Args:
            contracts: Option contracts
            threshold: Volume/OI ratio threshold (default: 2x)

        Returns:
            List of unusual contracts (sorted by volume/OI ratio, top 10)
        """
        unusual = []
        for c in contracts:
            volume = self._safe_int(c.get("volume"))
            oi = self._safe_int(c.get("open_interest"))

            if volume > 0 and oi > 0 and volume > oi * threshold:
                unusual.append({
                    "contractID": c.get("contractID", ""),
                    "type": c.get("type", ""),
                    "strike": self._safe_float(c.get("strike")),
                    "expiration": c.get("expiration", ""),
                    "volume": volume,
                    "open_interest": oi,
                    "vol_oi_ratio": round(volume / oi, 2),
                })

        # Sort by vol/oi ratio descending, take top 10
        unusual.sort(key=lambda x: x["vol_oi_ratio"], reverse=True)
        return unusual[:10]

    def _find_highest_iv(self, contracts: List[Dict]) -> List[Dict]:
        """Find contracts with highest implied volatility."""
        iv_contracts = []
        for c in contracts:
            iv = self._safe_float(c.get("impliedVolatility") or c.get("implied_volatility"))
            if iv > 0:
                iv_contracts.append({
                    "contractID": c.get("contractID", ""),
                    "type": c.get("type", ""),
                    "strike": self._safe_float(c.get("strike")),
                    "expiration": c.get("expiration", ""),
                    "implied_volatility": round(iv, 4),
                    "volume": self._safe_int(c.get("volume")),
                })

        iv_contracts.sort(key=lambda x: x["implied_volatility"], reverse=True)
        return iv_contracts[:5]

    def _summarize_near_term(self, contracts: List[Dict]) -> Dict[str, Any]:
        """Summarize options activity for the nearest expiration dates."""
        # Group by expiration
        by_exp: Dict[str, List[Dict]] = {}
        for c in contracts:
            exp = c.get("expiration", "unknown")
            by_exp.setdefault(exp, []).append(c)

        # Sort expirations chronologically, take first 2
        sorted_exps = sorted(by_exp.keys())[:2]

        summary = {}
        for exp in sorted_exps:
            exp_contracts = by_exp[exp]
            exp_calls = [c for c in exp_contracts if c.get("type", "").lower() == "call"]
            exp_puts = [c for c in exp_contracts if c.get("type", "").lower() == "put"]

            total_call_vol = sum(self._safe_int(c.get("volume")) for c in exp_calls)
            total_put_vol = sum(self._safe_int(c.get("volume")) for c in exp_puts)
            total_call_oi = sum(self._safe_int(c.get("open_interest")) for c in exp_calls)
            total_put_oi = sum(self._safe_int(c.get("open_interest")) for c in exp_puts)

            summary[exp] = {
                "total_contracts": len(exp_contracts),
                "call_volume": total_call_vol,
                "put_volume": total_put_vol,
                "call_oi": total_call_oi,
                "put_oi": total_put_oi,
                "pc_volume_ratio": round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else None,
            }

        return summary

    def _determine_signal(self, analysis: Dict[str, Any]) -> str:
        """
        Determine overall options flow signal.

        Bearish signals: high P/C ratio (>1.2), unusual put activity
        Bullish signals: low P/C ratio (<0.7), unusual call activity
        """
        pc_ratio = analysis.get("put_call_ratio")
        unusual = analysis.get("unusual_activity", [])

        # Score-based approach
        score = 0

        # P/C ratio signal
        if pc_ratio is not None:
            if pc_ratio > 1.5:
                score -= 2  # Very bearish
            elif pc_ratio > 1.2:
                score -= 1  # Bearish
            elif pc_ratio < 0.5:
                score += 2  # Very bullish
            elif pc_ratio < 0.7:
                score += 1  # Bullish

        # Unusual activity direction
        unusual_calls = sum(1 for u in unusual if u.get("type", "").lower() == "call")
        unusual_puts = sum(1 for u in unusual if u.get("type", "").lower() == "put")

        if unusual_calls > unusual_puts * 2:
            score += 1
        elif unusual_puts > unusual_calls * 2:
            score -= 1

        if score >= 2:
            return "bullish"
        elif score <= -2:
            return "bearish"
        else:
            return "neutral"

    def _generate_summary(self, analysis: Dict[str, Any]) -> str:
        """Generate a human-readable summary of options analysis."""
        parts = []

        pc = analysis.get("put_call_ratio")
        if pc is not None:
            parts.append(f"P/C ratio: {pc:.2f}")

        max_pain = analysis.get("max_pain")
        if max_pain is not None:
            parts.append(f"Max pain: ${max_pain:.2f}")

        unusual_count = len(analysis.get("unusual_activity", []))
        if unusual_count > 0:
            parts.append(f"{unusual_count} unusual activity contracts detected")

        signal = analysis.get("overall_signal", "neutral")
        parts.append(f"Signal: {signal}")

        source = analysis.get("data_source", "unknown")
        parts.append(f"[Source: {source}]")

        return ". ".join(parts) + "."
