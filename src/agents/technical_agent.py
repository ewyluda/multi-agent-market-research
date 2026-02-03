"""Technical analysis agent for calculating indicators and signals."""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any
from datetime import datetime, timedelta
from .base_agent import BaseAgent


class TechnicalAgent(BaseAgent):
    """Agent for technical analysis using indicators like RSI, MACD, Bollinger Bands."""

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch price data for technical analysis.

        Returns:
            Dictionary with historical price data
        """
        ticker_obj = yf.Ticker(self.ticker)

        try:
            # Get historical data (6 months for technical indicators)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            history = ticker_obj.history(start=start_date, end=end_date)

            return {
                "history": history,
                "ticker": self.ticker
            }

        except Exception as e:
            self.logger.error(f"Error fetching data for technical analysis of {self.ticker}: {e}")
            raise

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform technical analysis on price data.

        Args:
            raw_data: Historical price data

        Returns:
            Technical analysis with indicators and signals
        """
        history = raw_data.get("history")

        if history is None or history.empty:
            return {
                "error": "No price data available for technical analysis",
                "indicators": {},
                "signals": {},
                "summary": "Insufficient data for technical analysis"
            }

        df = history.copy()

        analysis = {
            "indicators": {},
            "signals": {},
            "patterns": []
        }

        # Calculate RSI
        rsi_period = self.config.get("RSI_PERIOD", 14)
        rsi = self._calculate_rsi(df, rsi_period)
        analysis["indicators"]["rsi"] = {
            "value": rsi,
            "period": rsi_period,
            "interpretation": self._interpret_rsi(rsi)
        }

        # Calculate MACD
        macd_data = self._calculate_macd(
            df,
            fast=self.config.get("MACD_FAST", 12),
            slow=self.config.get("MACD_SLOW", 26),
            signal=self.config.get("MACD_SIGNAL", 9)
        )
        analysis["indicators"]["macd"] = macd_data

        # Calculate Bollinger Bands
        bb_data = self._calculate_bollinger_bands(
            df,
            period=self.config.get("BB_PERIOD", 20),
            std=self.config.get("BB_STD", 2)
        )
        analysis["indicators"]["bollinger_bands"] = bb_data

        # Calculate moving averages
        analysis["indicators"]["ma_10"] = self._calculate_sma(df, 10)
        analysis["indicators"]["ma_20"] = self._calculate_sma(df, 20)
        analysis["indicators"]["ma_50"] = self._calculate_sma(df, 50)

        # Generate trading signals
        analysis["signals"] = self._generate_signals(analysis["indicators"], df)

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
