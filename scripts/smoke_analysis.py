#!/usr/bin/env python3
"""Manual smoke test: run one full live analysis (spends LLM/data API credits).

Usage: python scripts/smoke_analysis.py [TICKER]
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.orchestrator import Orchestrator
from src.config import Config
import json


async def test_analysis(ticker: str = "AAPL"):
    """
    Test running an analysis.

    Args:
        ticker: Stock ticker to analyze
    """
    print(f"\n{'='*60}")
    print(f"Testing Multi-Agent Market Research for {ticker}")
    print(f"{'='*60}\n")

    # Check configuration
    print("Checking configuration...")
    if not Config.validate_config():
        print("❌ Configuration validation failed!")
        print("\nPlease:")
        print("1. Copy .env.example to .env")
        print("2. Add your ANTHROPIC_API_KEY (or OPENAI_API_KEY)")
        print("3. Optionally add NEWS_API_KEY, ALPHA_VANTAGE_API_KEY")
        return False

    print("✓ Configuration valid\n")

    # Create orchestrator
    print("Creating orchestrator...")
    orchestrator = Orchestrator()
    print("✓ Orchestrator created\n")

    # Define progress callback
    def progress_callback(update):
        stage = update.get("stage", "unknown")
        progress = update.get("progress", 0)
        message = update.get("message", "")

        status_map = {
            "starting": "🚀 Starting analysis",
            "gathering_data": "📊 Gathering data",
            "running_news": "📰 Fetching news",
            "running_fundamentals": "💼 Analyzing fundamentals",
            "running_market": "📈 Analyzing market",
            "running_technical": "📉 Running technical analysis",
            "analyzing_sentiment": "🧠 Analyzing sentiment",
            "synthesizing": "🤖 Synthesizing results",
            "saving": "💾 Saving to database",
            "complete": "✅ Complete",
            "error": "❌ Error"
        }

        status_text = status_map.get(stage, stage)
        print(f"[{progress:3d}%] {status_text}", end="")
        if message:
            print(f": {message}")
        else:
            print()

    orchestrator.progress_callback = progress_callback

    # Run analysis
    print(f"Starting analysis for {ticker}...")
    print("-" * 60 + "\n")

    try:
        result = await orchestrator.analyze_ticker(ticker)

        print("\n" + "=" * 60)
        print("ANALYSIS RESULTS")
        print("=" * 60 + "\n")

        if result.get("success"):
            analysis = result.get("analysis", {})

            print(f"Ticker: {ticker}")
            print(f"Recommendation: {analysis.get('recommendation', 'N/A')}")
            print(f"Score: {analysis.get('score', 0):+d}")
            print(f"Confidence: {analysis.get('confidence', 0):.0%}")
            print(f"\nReasoning:")
            print(analysis.get('reasoning', 'N/A'))

            print(f"\nRisks:")
            for risk in analysis.get('risks', []):
                print(f"  - {risk}")

            print(f"\nOpportunities:")
            for opp in analysis.get('opportunities', []):
                print(f"  - {opp}")

            print(f"\nPrice Targets:")
            targets = analysis.get('price_targets', {})
            if targets:
                print(f"  Entry: ${targets.get('entry', 'N/A')}")
                print(f"  Target: ${targets.get('target', 'N/A')}")
                print(f"  Stop Loss: ${targets.get('stop_loss', 'N/A')}")

            print(f"\nPosition Size: {analysis.get('position_size', 'N/A')}")
            print(f"Time Horizon: {analysis.get('time_horizon', 'N/A')}")

            print(f"\n{'='*60}")
            print(f"Analysis completed in {result.get('duration_seconds', 0):.1f} seconds")
            print(f"Saved as analysis ID: {result.get('analysis_id', 'N/A')}")
            print(f"{'='*60}\n")

            # Show agent results summary
            print("\nAgent Results Summary:")
            print("-" * 60)
            agent_results = result.get("agent_results", {})
            for agent_name, agent_result in agent_results.items():
                success = agent_result.get("success", False)
                duration = agent_result.get("duration_seconds", 0)
                status = "✓" if success else "✗"
                print(f"{status} {agent_name.capitalize():15s} ({duration:.2f}s)")

            print("\n✅ Test completed successfully!")
            return True

        else:
            print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

    success = asyncio.run(test_analysis(ticker))

    if success:
        print("\n" + "="*60)
        print("Next steps:")
        print("="*60)
        print("1. Start the API server: python run.py")
        print("2. Test with curl: curl -X POST http://localhost:8000/api/analyze/AAPL")
        print("3. Build the React frontend")
        sys.exit(0)
    else:
        print("\n❌ Test failed. Please check your configuration and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
