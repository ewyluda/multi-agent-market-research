"""Technical analysis agent for calculating indicators and signals."""

import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from .base_agent import BaseAgent


class TechnicalAgent(BaseAgent):
    """Agent for technical analysis using indicators like RSI, MACD, Bollinger Bands.

    Data source priority:
        1. Alpha Vantage API (RSI, MACD, BBANDS, SMA endpoints)
        2. yfinance + local calculation (fallback)
    """

    # ──────────────────────────────────────────────
    # Alpha Vantage Data Fetching
    # ──────────────────────────────────────────────

    async def _fetch_av_rsi(self) -> Optional[float]:
        """
        Fetch latest RSI value from Alpha Vantage RSI endpoint.

        Returns:
            Latest RSI value, or None
        """
        period = self.config.get("RSI_PERIOD", 14)
        data = await self._av_request({
            "function": "RSI",
            "symbol": self.ticker,
            "interval": "daily",
            "time_period": str(period),
            "series_type": "close",
            "datatype": "json",
        })
        if not data:
            return None

        ts_key = "Technical Analysis: RSI"
        if ts_key not in data:
            return None

        time_series = data[ts_key]
        if not time_series:
            return None

        # Get the most recent value (first key when sorted descending)
        latest_date = max(time_series.keys())
        try:
            return float(time_series[latest_date]["RSI"])
        except (KeyError, ValueError, TypeError):
            return None

    async def _fetch_av_macd(self) -> Optional[Dict[str, Any]]:
        """
        Fetch latest MACD values from Alpha Vantage MACD endpoint.

        Returns:
            Dict with macd_line, signal_line, histogram, or None
        """
        fast = self.config.get("MACD_FAST", 12)
        slow = self.config.get("MACD_SLOW", 26)
        signal = self.config.get("MACD_SIGNAL", 9)

        data = await self._av_request({
            "function": "MACD",
            "symbol": self.ticker,
            "interval": "daily",
            "series_type": "close",
            "fastperiod": str(fast),
            "slowperiod": str(slow),
            "signalperiod": str(signal),
            "datatype": "json",
        })
        if not data:
            return None

        ts_key = "Technical Analysis: MACD"
        if ts_key not in data:
            return None

        time_series = data[ts_key]
        if not time_series:
            return None

        latest_date = max(time_series.keys())
        entry = time_series[latest_date]
        try:
            macd_val = float(entry.get("MACD", 0))
            signal_val = float(entry.get("MACD_Signal", 0))
            hist_val = float(entry.get("MACD_Hist", 0))

            if hist_val > 0 and macd_val > signal_val:
                interpretation = "bullish"
            elif hist_val < 0 and macd_val < signal_val:
                interpretation = "bearish"
            else:
                interpretation = "neutral"

            return {
                "macd_line": macd_val,
                "signal_line": signal_val,
                "histogram": hist_val,
                "interpretation": interpretation,
            }
        except (ValueError, TypeError):
            return None

    async def _fetch_av_bbands(self) -> Optional[Dict[str, Any]]:
        """
        Fetch latest Bollinger Bands from Alpha Vantage BBANDS endpoint.

        Returns:
            Dict with upper/middle/lower bands, or None
        """
        period = self.config.get("BB_PERIOD", 20)
        std = self.config.get("BB_STD", 2)

        data = await self._av_request({
            "function": "BBANDS",
            "symbol": self.ticker,
            "interval": "daily",
            "time_period": str(period),
            "series_type": "close",
            "nbdevup": str(std),
            "nbdevdn": str(std),
            "datatype": "json",
        })
        if not data:
            return None

        ts_key = "Technical Analysis: BBANDS"
        if ts_key not in data:
            return None

        time_series = data[ts_key]
        if not time_series:
            return None

        latest_date = max(time_series.keys())
        entry = time_series[latest_date]
        try:
            upper = float(entry.get("Real Upper Band", 0))
            middle = float(entry.get("Real Middle Band", 0))
            lower = float(entry.get("Real Lower Band", 0))

            return {
                "upper_band": upper,
                "middle_band": middle,
                "lower_band": lower,
            }
        except (ValueError, TypeError):
            return None

    async def _fetch_av_sma(self, period: int) -> Optional[float]:
        """
        Fetch latest SMA value from Alpha Vantage SMA endpoint.

        Args:
            period: Number of data points for the moving average

        Returns:
            Latest SMA value, or None
        """
        data = await self._av_request({
            "function": "SMA",
            "symbol": self.ticker,
            "interval": "daily",
            "time_period": str(period),
            "series_type": "close",
            "datatype": "json",
        })
        if not data:
            return None

        ts_key = "Technical Analysis: SMA"
        if ts_key not in data:
            return None

        time_series = data[ts_key]
        if not time_series:
            return None

        latest_date = max(time_series.keys())
        try:
            return float(time_series[latest_date]["SMA"])
        except (KeyError, ValueError, TypeError):
            return None

    async def _fetch_av_daily_prices(self) -> Optional[pd.DataFrame]:
        """
        Fetch daily price data from Alpha Vantage TIME_SERIES_DAILY for BB position check.

        Returns:
            DataFrame with OHLCV, or None
        """
        data = await self._av_request({
            "function": "TIME_SERIES_DAILY",
            "symbol": self.ticker,
            "outputsize": "full",
            "datatype": "json",
        })
        if not data:
            return None

        ts_key = "Time Series (Daily)"
        if ts_key not in data:
            return None

        time_series = data[ts_key]
        if not time_series:
            return None

        try:
            rows = []
            for date_str, values in time_series.items():
                rows.append({
                    "Date": pd.Timestamp(date_str),
                    "Open": float(values.get("1. open", 0)),
                    "High": float(values.get("2. high", 0)),
                    "Low": float(values.get("3. low", 0)),
                    "Close": float(values.get("4. close", 0)),
                    "Volume": int(values.get("5. volume", 0)),
                })
            df = pd.DataFrame(rows)
            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True)
            return df
        except Exception as e:
            self.logger.warning(f"Failed to parse AV daily prices: {e}")
            return None

    # ──────────────────────────────────────────────
    # Data Fetching (AV first, yfinance fallback)
    # ──────────────────────────────────────────────

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch price data and technical indicators.
        Tries Alpha Vantage indicator endpoints first, falls back to yfinance.

        Returns:
            Dictionary with historical price data and/or pre-computed indicators
        """
        result = {"ticker": self.ticker, "source": "unknown"}

        # ── Try Alpha Vantage first ──
        av_api_key = self.config.get("ALPHA_VANTAGE_API_KEY", "")
        if av_api_key:
            self.logger.info(f"Fetching {self.ticker} technical indicators from Alpha Vantage (primary)")

            # Fetch all indicators + daily prices concurrently
            av_rsi, av_macd, av_bbands, av_sma10, av_sma20, av_sma50, av_daily = await asyncio.gather(
                self._fetch_av_rsi(),
                self._fetch_av_macd(),
                self._fetch_av_bbands(),
                self._fetch_av_sma(10),
                self._fetch_av_sma(20),
                self._fetch_av_sma(50),
                self._fetch_av_daily_prices(),
                return_exceptions=True,
            )

            # Handle exceptions
            av_rsi = None if isinstance(av_rsi, Exception) else av_rsi
            av_macd = None if isinstance(av_macd, Exception) else av_macd
            av_bbands = None if isinstance(av_bbands, Exception) else av_bbands
            av_sma10 = None if isinstance(av_sma10, Exception) else av_sma10
            av_sma20 = None if isinstance(av_sma20, Exception) else av_sma20
            av_sma50 = None if isinstance(av_sma50, Exception) else av_sma50
            av_daily = None if isinstance(av_daily, Exception) else av_daily

            # We need at least RSI or MACD to consider AV successful
            if av_rsi is not None or av_macd is not None:
                self.logger.info(f"Alpha Vantage technical indicators retrieved for {self.ticker}")

                result["source"] = "alpha_vantage"
                result["av_indicators"] = {
                    "rsi": av_rsi,
                    "macd": av_macd,
                    "bbands": av_bbands,
                    "sma_10": av_sma10,
                    "sma_20": av_sma20,
                    "sma_50": av_sma50,
                }
                # Include daily prices for BB position check and current price
                result["history"] = av_daily
                return result
            else:
                self.logger.info(f"Alpha Vantage technical data incomplete for {self.ticker}, falling back to yfinance")

        # ── Fallback to yfinance ──
        self.logger.info(f"Fetching {self.ticker} technical data from yfinance (fallback)")
        result["source"] = "yfinance"

        ticker_obj = yf.Ticker(self.ticker)

        try:
            # Get historical data (6 months for technical indicators)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            history = ticker_obj.history(start=start_date, end=end_date)
            result["history"] = history
        except Exception as e:
            self.logger.error(f"Error fetching data for technical analysis of {self.ticker}: {e}")
            raise

        return result

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform technical analysis on price data.

        When Alpha Vantage provides pre-computed indicators, uses those directly.
        Falls back to local calculation from yfinance price history.

        Args:
            raw_data: Historical price data and/or pre-computed indicators

        Returns:
            Technical analysis with indicators and signals
        """
        history = raw_data.get("history")
        av_indicators = raw_data.get("av_indicators")
        data_source = raw_data.get("source", "unknown")

        analysis = {
            "indicators": {},
            "signals": {},
            "patterns": [],
            "data_source": data_source,
        }

        # ── Use Alpha Vantage pre-computed indicators ──
        if av_indicators:
            self.logger.info(f"Using Alpha Vantage pre-computed indicators for {self.ticker}")

            # RSI
            av_rsi = av_indicators.get("rsi")
            if av_rsi is not None:
                rsi_period = self.config.get("RSI_PERIOD", 14)
                analysis["indicators"]["rsi"] = {
                    "value": av_rsi,
                    "period": rsi_period,
                    "interpretation": self._interpret_rsi(av_rsi),
                }
            else:
                analysis["indicators"]["rsi"] = {
                    "value": 50.0, "period": 14, "interpretation": "neutral"
                }

            # MACD
            av_macd = av_indicators.get("macd")
            if av_macd:
                analysis["indicators"]["macd"] = av_macd
            else:
                analysis["indicators"]["macd"] = {
                    "macd_line": 0, "signal_line": 0, "histogram": 0, "interpretation": "neutral"
                }

            # Bollinger Bands
            av_bbands = av_indicators.get("bbands")
            if av_bbands:
                current_price = None
                if history is not None and not history.empty:
                    current_price = float(history['Close'].iloc[-1])

                interpretation = "neutral"
                if current_price and av_bbands.get("upper_band") and av_bbands.get("lower_band"):
                    if current_price > av_bbands["upper_band"]:
                        interpretation = "overbought"
                    elif current_price < av_bbands["lower_band"]:
                        interpretation = "oversold"

                analysis["indicators"]["bollinger_bands"] = {
                    "upper_band": av_bbands.get("upper_band"),
                    "middle_band": av_bbands.get("middle_band"),
                    "lower_band": av_bbands.get("lower_band"),
                    "current_price": current_price,
                    "interpretation": interpretation,
                }
            else:
                analysis["indicators"]["bollinger_bands"] = {
                    "upper_band": None, "middle_band": None, "lower_band": None,
                    "current_price": None, "interpretation": "neutral"
                }

            # Moving Averages
            analysis["indicators"]["ma_10"] = av_indicators.get("sma_10")
            analysis["indicators"]["ma_20"] = av_indicators.get("sma_20")
            analysis["indicators"]["ma_50"] = av_indicators.get("sma_50")

        # ── Fallback: Calculate from yfinance history ──
        elif history is not None and not history.empty:
            df = history.copy()

            rsi_period = self.config.get("RSI_PERIOD", 14)
            rsi = self._calculate_rsi(df, rsi_period)
            analysis["indicators"]["rsi"] = {
                "value": rsi,
                "period": rsi_period,
                "interpretation": self._interpret_rsi(rsi)
            }

            macd_data = self._calculate_macd(
                df,
                fast=self.config.get("MACD_FAST", 12),
                slow=self.config.get("MACD_SLOW", 26),
                signal=self.config.get("MACD_SIGNAL", 9)
            )
            analysis["indicators"]["macd"] = macd_data

            bb_data = self._calculate_bollinger_bands(
                df,
                period=self.config.get("BB_PERIOD", 20),
                std=self.config.get("BB_STD", 2)
            )
            analysis["indicators"]["bollinger_bands"] = bb_data

            analysis["indicators"]["ma_10"] = self._calculate_sma(df, 10)
            analysis["indicators"]["ma_20"] = self._calculate_sma(df, 20)
            analysis["indicators"]["ma_50"] = self._calculate_sma(df, 50)

        else:
            return {
                "error": "No price data available for technical analysis",
                "indicators": {},
                "signals": {},
                "summary": "Insufficient data for technical analysis",
                "data_source": data_source,
            }

        # Generate trading signals (works with both AV and yfinance indicators)
        df_for_signals = history if (history is not None and not history.empty) else pd.DataFrame()
        analysis["signals"] = self._generate_signals(analysis["indicators"], df_for_signals)

        # Calculate overall technical score
        analysis["technical_score"] = self._calculate_technical_score(analysis)

        # Generate summary
        analysis["summary"] = self._generate_summary(analysis)

        return analysis

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(df) < period + 1:
            return 50.0  # Neutral if insufficient data

        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    def _interpret_rsi(self, rsi: float) -> str:
        """Interpret RSI value."""
        if rsi >= 70:
            return "overbought"
        elif rsi <= 30:
            return "oversold"
        else:
            return "neutral"

    def _calculate_macd(
        self,
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, Any]:
        """Calculate MACD indicator."""
        if len(df) < slow:
            return {
                "macd_line": 0,
                "signal_line": 0,
                "histogram": 0,
                "interpretation": "neutral"
            }

        exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
        exp2 = df['Close'].ewm(span=slow, adjust=False).mean()

        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        # Get most recent values
        macd_val = float(macd_line.iloc[-1])
        signal_val = float(signal_line.iloc[-1])
        hist_val = float(histogram.iloc[-1])

        # Determine interpretation
        if hist_val > 0 and macd_val > signal_val:
            interpretation = "bullish"
        elif hist_val < 0 and macd_val < signal_val:
            interpretation = "bearish"
        else:
            interpretation = "neutral"

        return {
            "macd_line": macd_val,
            "signal_line": signal_val,
            "histogram": hist_val,
            "interpretation": interpretation
        }

    def _calculate_bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = 20,
        std: int = 2
    ) -> Dict[str, Any]:
        """Calculate Bollinger Bands."""
        if len(df) < period:
            return {
                "upper_band": None,
                "middle_band": None,
                "lower_band": None,
                "current_price": None,
                "interpretation": "neutral"
            }

        sma = df['Close'].rolling(window=period).mean()
        std_dev = df['Close'].rolling(window=period).std()

        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)

        current_price = df['Close'].iloc[-1]
        upper = float(upper_band.iloc[-1])
        middle = float(sma.iloc[-1])
        lower = float(lower_band.iloc[-1])

        # Interpret position relative to bands
        if current_price > upper:
            interpretation = "overbought"
        elif current_price < lower:
            interpretation = "oversold"
        else:
            interpretation = "neutral"

        return {
            "upper_band": upper,
            "middle_band": middle,
            "lower_band": lower,
            "current_price": float(current_price),
            "interpretation": interpretation
        }

    def _calculate_sma(self, df: pd.DataFrame, period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(df) < period:
            return None

        sma = df['Close'].rolling(window=period).mean()
        return float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else None

    def _generate_signals(
        self,
        indicators: Dict[str, Any],
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Generate trading signals based on indicators."""
        signals = {
            "overall": "neutral",
            "strength": 0,  # -100 to +100
            "components": {}
        }

        score = 0

        # RSI signal
        rsi_data = indicators.get("rsi", {})
        rsi_val = rsi_data.get("value", 50)
        rsi_interp = rsi_data.get("interpretation", "neutral")

        if rsi_interp == "oversold":
            signals["components"]["rsi"] = "buy"
            score += 20
        elif rsi_interp == "overbought":
            signals["components"]["rsi"] = "sell"
            score -= 20
        else:
            signals["components"]["rsi"] = "neutral"

        # MACD signal
        macd_data = indicators.get("macd", {})
        macd_interp = macd_data.get("interpretation", "neutral")

        if macd_interp == "bullish":
            signals["components"]["macd"] = "buy"
            score += 25
        elif macd_interp == "bearish":
            signals["components"]["macd"] = "sell"
            score -= 25
        else:
            signals["components"]["macd"] = "neutral"

        # Bollinger Bands signal
        bb_data = indicators.get("bollinger_bands", {})
        bb_interp = bb_data.get("interpretation", "neutral")

        if bb_interp == "oversold":
            signals["components"]["bollinger_bands"] = "buy"
            score += 15
        elif bb_interp == "overbought":
            signals["components"]["bollinger_bands"] = "sell"
            score -= 15
        else:
            signals["components"]["bollinger_bands"] = "neutral"

        # Moving average crossover
        ma_10 = indicators.get("ma_10")
        ma_20 = indicators.get("ma_20")
        ma_50 = indicators.get("ma_50")

        if ma_10 and ma_20 and ma_50:
            if ma_10 > ma_20 > ma_50:
                signals["components"]["moving_averages"] = "buy"
                score += 20
            elif ma_10 < ma_20 < ma_50:
                signals["components"]["moving_averages"] = "sell"
                score -= 20
            else:
                signals["components"]["moving_averages"] = "neutral"

        # Determine overall signal
        signals["strength"] = max(-100, min(100, score))

        if score > 30:
            signals["overall"] = "buy"
        elif score < -30:
            signals["overall"] = "sell"
        else:
            signals["overall"] = "neutral"

        return signals

    def _calculate_technical_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall technical score (0-100)."""
        signals = analysis.get("signals", {})
        strength = signals.get("strength", 0)

        # Convert -100 to +100 range to 0 to 100 range
        score = (strength + 100) / 2

        return score

    def _generate_summary(self, analysis: Dict[str, Any]) -> str:
        """Generate technical analysis summary."""
        indicators = analysis.get("indicators", {})
        signals = analysis.get("signals", {})

        rsi = indicators.get("rsi", {}).get("value", "N/A")
        macd_interp = indicators.get("macd", {}).get("interpretation", "neutral")
        bb_interp = indicators.get("bollinger_bands", {}).get("interpretation", "neutral")
        overall_signal = signals.get("overall", "neutral")
        strength = signals.get("strength", 0)

        summary = f"Technical signals: {overall_signal.upper()} (strength: {strength:+d}). "
        summary += f"RSI: {rsi:.1f}" if isinstance(rsi, (int, float)) else f"RSI: {rsi}"
        summary += f", MACD: {macd_interp}, Bollinger Bands: {bb_interp}."

        return summary
