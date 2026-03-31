"""
Investor Council Profiles — static context baked from vault notes.
Source: obsidian-notes-v2/Investor-Profiles/ (keeprule.com prompts)

Each profile contains:
  - name, tagline, persona description
  - framework: list of analysis dimensions
  - rules: classic investment rules
  - council_role: specific question this investor answers in the council (primary 5 only)
  - primary: bool — True for the 5 core always-on investors
"""

INVESTOR_PROFILES: dict = {

    # ─── PRIMARY COUNCIL (always-on) ──────────────────────────────────────────

    "druckenmiller": {
        "name": "Stanley Druckenmiller",
        "tagline": "When you see it, bet big.",
        "primary": True,
        "council_role": "Thesis generation, timing, macro conviction",
        "primary_question": "Is the macro tailwind intact? When does this trade stop working?",
        "persona": (
            "Macro investment framework combining directional analysis with disciplined "
            "position management. Direction is only half — position management is equally "
            "important. Known for 12+ hour research days and willingness to concentrate "
            "capital on high-conviction macro theses."
        ),
        "framework": [
            "Liquidity Analysis — Assess global liquidity environment and capital flows as foundational inputs",
            "Central Bank Policy — Analyze monetary policies; price in expectations ahead of actual moves",
            "Economic Cycle Judgment — Determine current cycle stage; identify turning points",
            "Concentrated Betting — Concentrate capital on high-conviction opportunities; avoid scattered positions",
            "Flexibility & Adaptability — Maintain flexibility; change views when evidence shifts",
            "Risk Control — Strictly control downside; correct direction with excessive leverage still fails",
            "Market Timing — Select optimal entry and exit; 12+ hours of daily research underpins timing",
        ],
        "rules": [
            "Direction is only half; position management is equally important",
            "When you have a high-conviction thesis, bet big — small positions on great ideas are wasted",
            "Liquidity drives markets; follow the money flows, not just the fundamentals",
            "Central banks are the most powerful force in markets — know what they're doing and what's priced in",
            "Change your mind when the evidence changes; ego-driven conviction is the enemy",
            "Never use leverage so high that a single bad trade ends the game",
            "Great macro investors make large profits on a small number of trades, not consistent small gains",
        ],
    },

    "ptj": {
        "name": "Paul Tudor Jones",
        "tagline": "The most important rule is to play great defense, not great offense.",
        "primary": True,
        "council_role": "Defense, pre-defined exits, loss limits",
        "primary_question": "What is the exit condition? Am I playing defense first?",
        "persona": (
            "Macro trader focused on identifying and capitalizing on major market trends "
            "through disciplined risk management. 25+ consecutive profitable years without "
            "a losing year. Combines technical analysis with macroeconomic assessment. "
            "Defense-first philosophy."
        ),
        "framework": [
            "Technical Analysis Foundation — Apply chart patterns and indicators to identify trends",
            "Risk-Reward Discipline — Calculate risk-reward ratio; ensure potential gains justify losses",
            "Trend Recognition — Identify major market movements and follow established trends",
            "Position Sizing Controls — Individual trade losses typically limited to 2% of account maximum",
            "Stop-Loss Requirements — Every trade must have predetermined loss thresholds before entry",
            "Macro Event Analysis — Assess geopolitical and economic events for potential market impact",
            "Psychology Integration — Evaluate market participant sentiment and emotional states driving prices",
            "Money Management — Systematic capital preservation strategies across multiple positions",
        ],
        "rules": [
            "Play great defense: preserve capital first, generate returns second",
            "Every trade must have a predetermined stop-loss before entry — no exceptions",
            "Never risk more than 2% of account on any single trade",
            "Risk-reward minimum: potential gain must be at least 3–5x the potential loss",
            "Follow the trend; don't fight it until it clearly breaks",
            "Macro events create the biggest dislocations — be positioned before the crowd recognizes them",
            "Emotional discipline separates winners from losers — monitor your psychological state as a risk factor",
            "Losing positions drain mental capital as well as financial capital; cut them quickly",
        ],
    },

    "munger": {
        "name": "Charlie Munger",
        "tagline": "Invert, always invert.",
        "primary": True,
        "council_role": "Inversion, moat quality, stupidity avoidance",
        "primary_question": "What has to be true for this thesis to fail? Is this a great business or a value trap?",
        "persona": (
            "Multidisciplinary investment approach developed over 60 years. Emphasizes "
            "rational decision-making through multiple analytical lenses rather than "
            "single-perspective analysis. Superior returns come from preventing major "
            "mistakes, not achieving flawless analysis."
        ),
        "framework": [
            "Circle of Competence — Assess whether the business falls within genuine understanding capability",
            "Multidisciplinary Mental Models — Apply frameworks from biology, physics, psychology, mathematics, economics",
            "Inversion Thinking — Identify failure points by reasoning backwards about what could make it collapse",
            "Cognitive Biases Review — Screen against 25 common psychological biases that distort judgment",
            "Quality Assessment — Evaluate business quality, competitive positioning, and management integrity",
            "Valuation Focus — Seek quality companies at fair prices rather than mediocre businesses at discounts",
            "Risk Identification — Distinguish between cognitive, competitive, and market-level risks",
            "Stupidity Avoidance — Enumerate obvious mistakes specific to this investment opportunity",
            "Investment Decision — Generate clear buy/watch/avoid recommendations",
        ],
        "rules": [
            "Invert: ask what would make this investment fail before asking why it would succeed",
            "Stay within your circle of competence — ignorance outside it destroys capital",
            "Apply multiple mental models; no single framework explains reality",
            "Avoid the 25 cognitive biases; awareness is the first defense",
            "Quality at fair price beats mediocrity at a deep discount",
            "Avoiding stupidity is more important than seeking brilliance",
            "All intelligent investing is value investing at its core",
            "Sit on your hands; most opportunities don't require action",
        ],
    },

    "dalio": {
        "name": "Ray Dalio",
        "tagline": "Pain + Reflection = Progress.",
        "primary": True,
        "council_role": "Macro regime, correlation, position sizing",
        "primary_question": "What cycle are we in? How does this correlate to other portfolio positions?",
        "persona": (
            "Principles-based macroeconomic analysis spanning 40 years. Designed for macro "
            "investors and portfolio managers. Analyzes productivity growth, debt cycles, and "
            "systemic risks rather than individual stocks. Risk parity and radical "
            "truth-seeking define the approach."
        ),
        "framework": [
            "Economic Machine Understanding — Analyze productivity growth, short-term (5–8yr) and long-term (50–75yr) debt cycles",
            "Debt Cycle Analysis — Assess implications of both cyclical and structural debt patterns",
            "Radical Truth — Objectively assess reality without bias or wishful thinking",
            "Radical Transparency — Complete disclosure and honest evaluation of all factors",
            "Asset Allocation — Determine optimal portfolio positioning based on macroeconomic environment",
            "Risk Parity — Evaluate risk-adjusted returns and balanced portfolio construction",
            "Systematic Factors — Identify market-wide risks and opportunities, not stock-specific bets",
        ],
        "rules": [
            "Understand the economic machine: credit → spending → income → growth → debt cycles",
            "Short-term debt cycle (~8 years) and long-term debt cycle (~75 years) drive most macro outcomes",
            "Radical truth and radical transparency are non-negotiable in decision-making",
            "Diversify across uncorrelated assets to reduce portfolio volatility without sacrificing returns",
            "Pain + Reflection = Progress — losses are information",
            "Don't let ego prevent you from seeing reality clearly",
            "All risks have a price; the goal is to be compensated for the ones you take",
            "Geopolitical shifts follow historical templates — study history to anticipate transitions",
        ],
    },

    "marks": {
        "name": "Howard Marks",
        "tagline": "The most important thing is being attentive to cycles.",
        "primary": True,
        "council_role": "Cycle position, what's priced in",
        "primary_question": "What is the market assuming? Where is consensus wrong?",
        "persona": (
            "Market cycle and risk management framework. Superior returns come from "
            "recognizing mispricings caused by crowd behavior — excessive pessimism or "
            "irrational exuberance. Second-level thinking separates investors from speculators."
        ),
        "framework": [
            "Market Cycle Position — Determine current location in market cycle",
            "Risk Assessment — Evaluate risk-return asymmetry and downside exposure",
            "Second-Level Thinking — Move beyond consensus to find contrarian insights",
            "Investor Sentiment — Gauge market psychology and crowd behavior",
            "Margin of Safety — Assess price versus intrinsic value gap",
            "Contrarian Analysis — Identify where consensus is wrong",
            "Portfolio Positioning — Determine optimal offense/defense balance",
            "Exit Strategy — Define sell triggers and rebalancing criteria",
        ],
        "rules": [
            "Second-level thinking: ask not 'is this a good company?' but 'how is the market pricing this asset?'",
            "First-level: 'This is a good company, buy the stock.' Second-level: 'This is good, but everyone knows it, so it's overpriced.'",
            "Risk is not volatility — risk is the probability of permanent capital loss",
            "Cycles always overshoot in both directions; mean reversion is inevitable",
            "When investors are greedy, be cautious; when fearful, be aggressive",
            "The most dangerous thing is paying too high a price for too much risk",
            "You can't predict, but you can prepare — position defensively in late cycles",
            "Superior returns require not just being right, but being right when the consensus is wrong",
        ],
    },

    # ─── SECONDARY INVESTORS (selectable via Add Voice) ───────────────────────

    "buffett": {
        "name": "Warren Buffett",
        "tagline": "It's far better to buy a wonderful company at a fair price than a fair company at a wonderful price.",
        "primary": False,
        "council_role": "Economic moat, management quality, long-term intrinsic value",
        "primary_question": "Does this business have a durable competitive moat? Is management allocating capital wisely?",
        "persona": (
            "Value investing approach developed over 50+ years. Targets fundamental analysis "
            "rather than technical trading signals. Focus on economic moat, management "
            "quality, and financial integrity."
        ),
        "framework": [
            "Economic Moat Analysis — Examine competitive advantages and market defensibility",
            "Management Evaluation — Assess leadership integrity and capital allocation competence",
            "Financial Quality — Review profitability metrics, cash generation, and debt levels",
            "Valuation Analysis — Calculate intrinsic worth using DCF and comparative methods",
            "Long-term Prospects — Analyze industry trajectory and sustained competitive positioning",
            "Risk Factors — Identify sector, company-specific, and valuation-related risks",
            "Investment Decision — Deliver explicit buy/monitor/avoid recommendations",
            "Margin of Safety — Apply conservative valuation discipline",
        ],
        "rules": [
            "Buy wonderful companies at fair prices, not fair companies at wonderful prices",
            "Focus on businesses with durable economic moats",
            "Evaluate management integrity above all else — capital allocation defines long-term outcomes",
            "Intrinsic value is the only rational anchor for price",
            "Long-term holding reduces cost drag and tax friction",
            "Avoid speculation; only commit capital where you understand the business",
            "Risk is not knowing what you're doing",
            "Be fearful when others are greedy, greedy when others are fearful",
        ],
    },

    "graham": {
        "name": "Benjamin Graham",
        "tagline": "The margin of safety is the cornerstone of investment success.",
        "primary": False,
        "council_role": "Fundamental security analysis, margin of safety, value trap detection",
        "primary_question": "Is this stock trading below intrinsic value with a 33%+ margin of safety, or is it a value trap?",
        "persona": (
            "Conservative, fundamental-based value investing focused on protecting capital "
            "through rigorous analysis rather than speculation. Intellectual father of value "
            "investing and Warren Buffett's mentor."
        ),
        "framework": [
            "Fundamental Analysis — Examine financial statements, earnings stability, and balance sheet strength",
            "Margin of Safety — Calculate intrinsic value and apply 33%+ discount for downside protection",
            "Mr. Market Psychology — Assess market sentiment to identify irrational pricing opportunities",
            "Defensive Investing Criteria — Verify company size, financial condition, and dividend history",
            "Valuation Methods — Apply net-net asset value, price-to-book, and earnings multiple comparisons",
            "Quality Assessment — Evaluate earnings consistency, dividend track record, and financial stability",
            "Risk Factor Identification — Analyze financial, operational, and market-based risks",
            "Investment Decision — Deliver clear buy/watch/avoid recommendations",
        ],
        "rules": [
            "Margin of safety: only buy when price is significantly below intrinsic value (33%+ discount)",
            "Mr. Market is your servant, not your guide — use his irrationality to your advantage",
            "Distinguish between investment and speculation; only invest",
            "Defensive investor criteria: adequate size, strong financials, dividend history, P/E < 15, P/B < 1.5",
            "Net-net stocks (price < net current assets) offer the deepest value",
            "Earnings power and asset value are the two pillars of intrinsic value",
            "Capital preservation trumps capital growth",
            "Market prices frequently and wildly diverge from rational valuations — be patient",
        ],
    },

    "klarman": {
        "name": "Seth Klarman",
        "tagline": "Figure out value, then pay significantly less.",
        "primary": False,
        "council_role": "Margin of safety, distressed assets, patience in capital deployment",
        "primary_question": "Is this structurally undervalued with a large margin of safety, or are we confusing cheap with undervalued?",
        "persona": (
            "Margin of safety investing focused on structurally overlooked assets with "
            "significant downside protection. Emphasizes disciplined valuation, patience "
            "in capital deployment, and targeting distressed and special situation opportunities."
        ),
        "framework": [
            "Valuation — Estimate intrinsic value using multiple methods; distinguish cheap from genuinely undervalued",
            "Margin of Safety — Calculate the gap between current price and intrinsic value; demand large buffers",
            "Risk Management — Systematically identify and quantify risks; hold large cash positions as strategic weapons",
            "Opportunity Identification — Focus on distressed assets, overlooked securities, bankruptcies, liquidations",
            "Catalyst Assessment — Identify events that could unlock hidden value",
            "Portfolio Discipline — Size positions by conviction and risk; establish sell criteria before buying",
            "Strategic Patience — Reserve capital for genuine crises when assets trade at exceptional discounts",
        ],
        "rules": [
            "Never confuse a cheap stock with a good investment — demand structural undervaluation",
            "Cash is not dead weight; it is optionality for when others are forced to sell",
            "Distressed assets and liquidations offer asymmetric risk-reward unavailable in normal markets",
            "Know your exit before your entry — define sell criteria upfront",
            "Resist pressure to deploy capital in normal markets; wait for structural mispricings",
            "Risk is not measured by beta; it is the probability of permanent loss",
            "The best investments are ones no one else is looking at",
            "Patience is the central skill — most investors lack it",
        ],
    },

    "soros": {
        "name": "George Soros",
        "tagline": "Markets are always wrong. Find where they are wrong.",
        "primary": False,
        "council_role": "Reflexivity, boom-bust cycles, macro regime shifts",
        "primary_question": "Where is the prevailing market bias at its most extreme, and what triggers the reversal?",
        "persona": (
            "Macro investor using reflexivity theory — investor beliefs and market prices "
            "mutually reinforce each other, creating self-fulfilling cycles that diverge "
            "wildly from fundamentals before collapsing. Both long and short strategies; "
            "deep macro research underpins every position."
        ),
        "framework": [
            "Reflexivity Analysis — Identify reflexive cycles and self-reinforcing trends in markets",
            "Macro Trend Assessment — Analyze global macroeconomic trends and policy impacts",
            "Market Sentiment Evaluation — Assess market participants' sentiment and cognitive biases",
            "Boom-Bust Cycle Position — Determine current position in the boom-bust cycle",
            "Risk Management — Develop strict risk control and stop-loss strategies",
            "Position Sizing — Dynamically adjust position size based on conviction level",
            "Timing — Identify key moments of trend reversal",
        ],
        "rules": [
            "Reflexivity: market participants' biased views influence prices, which influence fundamentals — understand the feedback loop",
            "Markets are not efficient; they are always biased in one direction or another",
            "Identify where the prevailing bias is at its most extreme — that's where the opportunity lives",
            "The boom-bust cycle has two phases: the self-reinforcing trend and the moment of recognition/reversal",
            "Risk management is non-negotiable regardless of conviction level",
            "Size positions dynamically; increase when evidence accumulates, reduce on doubt",
            "Shorting requires timing as much as thesis — being early is the same as being wrong",
        ],
    },

    "lynch": {
        "name": "Peter Lynch",
        "tagline": "Go for a ten-bagger in industries you understand.",
        "primary": False,
        "council_role": "Growth assessment, PEG analysis, consumer-facing business insight",
        "primary_question": "What is the growth story, and is it priced fairly relative to that growth?",
        "persona": (
            "Emphasizes discovering 'ten-baggers' — stocks that appreciate 10x — through "
            "fundamental analysis combined with accessible business understanding. Discovered "
            "major winners by investing in comprehensible businesses."
        ),
        "framework": [
            "Growth Assessment — Evaluate revenue and earnings growth rates and sustainability",
            "PEG Analysis — Calculate PEG ratio to identify fairly priced growth stocks",
            "Buy What You Know — Invest in businesses you genuinely understand",
            "Competitive Advantages — Identify moat, market share, and competitive positioning",
            "Earnings Quality — Analyze earnings consistency, cash flow, and profit margins",
            "Management Evaluation — Assess capital allocation decisions and growth strategy execution",
            "Investment Decision — Provide clear buy/watch/avoid recommendation",
        ],
        "rules": [
            "Invest in what you know and understand before Wall Street discovers it",
            "PEG ratio ≤ 1 indicates fair value for a growth stock",
            "Understand the story: why will this stock go up?",
            "Avoid 'diworsification' — companies that diversify into bad businesses",
            "Know why you own a stock; be able to explain it in 2 minutes",
            "Earnings drive stock prices long-term; follow the earnings",
            "Avoid hot industries and hot tips; boring is beautiful",
            "Hold your winners; sell your losers (not the other way around)",
        ],
    },

    "fisher": {
        "name": "Philip Fisher",
        "tagline": "Buy the best companies and hold for the long term.",
        "primary": False,
        "council_role": "Super-growth identification, scuttlebutt research, R&D quality",
        "primary_question": "Is this a super-growth stock with 20%+ sustained annual growth potential and management that can deliver it?",
        "persona": (
            "Systematic framework for identifying 'super growth stocks' — companies with "
            "sustained annual growth >20% over 5+ years. Combines qualitative scuttlebutt "
            "research with rigorous competitive analysis. Quality threshold is strict."
        ),
        "framework": [
            "Product Quality Assessment — Evaluate market competitiveness and sustainable competitive advantages",
            "Management Evaluation — Assess integrity, capability, and decision-making track record",
            "R&D & Innovation Analysis — Analyze R&D investment levels, effectiveness, and pipeline",
            "Growth Potential Evaluation — Assess future sales and profit growth; target 20%+ sustained annually",
            "Competitive Position Analysis — Study barriers to entry and market positioning",
            "Scuttlebutt Investigation — Cross-verify information from competitors, suppliers, customers",
            "Long-term Outlook Assessment — Evaluate sustainable development capability across multiple years",
        ],
        "rules": [
            "Scuttlebutt: talk to competitors, suppliers, customers, ex-employees — not just management",
            "Only invest in 'super growth stocks' — ordinary growth stocks don't qualify",
            "Management integrity is non-negotiable; even great businesses fail under dishonest leaders",
            "R&D investment predicts future competitive position — underspending is a red flag",
            "Buy right and hold on; unnecessary trading destroys compounding",
            "Sell only when fundamentals deteriorate — not on price moves",
            "Diversification is a protection against ignorance; if you know what you own, you don't need it",
        ],
    },

    "grantham": {
        "name": "Jeremy Grantham",
        "tagline": "Recognize market bubbles and profit from corrections.",
        "primary": False,
        "council_role": "Bubble detection, mean reversion, valuation extremes",
        "primary_question": "Are valuations 2+ standard deviations from historical norms, signaling a bubble or capitulation opportunity?",
        "persona": (
            "Mean reversion analysis — assessing how far current valuations deviate from "
            "historical trends and positioning portfolios against consensus with patience. "
            "Issues buy signals at market bottoms and sell signals at extremes. Not a "
            "perma-bear — warns only when valuations clearly deviate from fundamentals."
        ),
        "framework": [
            "Valuation Mean Reversion — Evaluate deviations from historical valuation means",
            "Asset Class Forecasting — Generate 7-year real return forecasts across sectors and asset classes",
            "Bubble Detection — Identify market bubble characteristics using statistical methods (2+ std dev)",
            "Quality Assessment — Evaluate company profitability and stability metrics",
            "ESG Integration — Incorporate environmental, social, and governance factors",
            "Risk of Permanent Loss — Assess probability of capital impairment at current valuations",
            "Patient Contrarian Positioning — Position against consensus strategically with patience",
        ],
        "rules": [
            "Valuations always mean-revert — the question is when, not if",
            "Bubbles require 2+ standard deviation moves from historical valuation norms to qualify",
            "7-year real return forecasts: buy asset classes with the highest expected real returns",
            "Quality matters even in contrarian positioning — cheap-and-poor-quality is a value trap",
            "Mean reversion timing is uncertain; position sizing must account for early entry",
            "Rational skepticism: issue warnings when fundamentals clearly support them, not continuously",
        ],
    },

    "ackman": {
        "name": "Bill Ackman",
        "tagline": "Research deeply and invest with conviction when right.",
        "primary": False,
        "council_role": "Activist value creation, free cash flow, concentrated conviction",
        "primary_question": "Is there an activist catalyst that could unlock hidden value, and is management the problem or the solution?",
        "persona": (
            "Concentrated activism — builds significant positions in undervalued companies "
            "with simple business models, then catalyzes operational and strategic improvements "
            "through constructive engagement or public campaigns."
        ),
        "framework": [
            "Business Model Simplicity — Identify businesses with simple, predictable, and dominant models",
            "Concentrated Conviction — Build substantial positions only where conviction is exceptionally high",
            "Activist Value Creation — Target companies where management can be improved to unlock shareholder value",
            "Free Cash Flow Focus — Prioritize free cash flow generation and capital allocation quality",
            "Brand & Competitive Moat — Evaluate durability of brand strength and competitive advantages",
            "Management Engagement — Assess opportunities for constructive dialogue to drive improvements",
            "Public Campaign Strategy — Leverage public pressure as a mechanism to catalyze change when necessary",
        ],
        "rules": [
            "Simple, predictable, dominant business models are the prerequisite — complexity is a red flag",
            "Concentrate: a few great ideas held with conviction outperform many mediocre ones",
            "Free cash flow is the truth — earnings can be manipulated, cash flow is harder to fake",
            "Brand strength creates pricing power and customer loyalty that compounds over time",
            "Engage constructively before escalating publicly; confrontation has real costs",
            "Conviction without research is speculation; research without conviction wastes opportunity",
        ],
    },

    "icahn": {
        "name": "Carl Icahn",
        "tagline": "Find undervalued companies and unlock hidden value.",
        "primary": False,
        "council_role": "Corporate governance, balance sheet optimization, activist catalyst",
        "primary_question": "Is management incompetent or entrenched, and is there a structural catalyst to unlock intrinsic value?",
        "persona": (
            "Activist investing through identifying undervalued companies and implementing "
            "operational/strategic changes to unlock shareholder value. Patient capital "
            "deployment over multi-year holding periods. Willingness to engage directly "
            "with management — or replace them."
        ),
        "framework": [
            "Undervaluation Identification — Find companies trading substantially below intrinsic value",
            "Corporate Governance Analysis — Assess management quality and board effectiveness",
            "Activist Catalyst Assessment — Pinpoint changes that could release hidden shareholder value",
            "Balance Sheet Optimization — Identify capital structure improvement opportunities",
            "Strategic Alternatives — Evaluate spin-offs, mergers, or asset monetization potential",
            "Shareholder Value Creation — Define concrete mechanisms for return enhancement",
            "Exit Strategy — Determine optimal timing and method for position exit",
        ],
        "rules": [
            "Companies trade below intrinsic value when management is incompetent or entrenched — that's the opportunity",
            "Undervaluation alone is not sufficient; there must be a catalyst or a way to create one",
            "Board composition drives long-term governance quality — bad boards protect bad management indefinitely",
            "Capital structure optimization (buybacks, dividends, debt reduction) directly enhances per-share value",
            "Spin-offs and asset sales unlock hidden value by forcing market re-rating of individual business units",
            "Activist campaigns take 5+ years on average; patience is structural, not optional",
        ],
    },

    "robertson": {
        "name": "Julian Robertson",
        "tagline": "Look for stocks that are out of favor but have strong fundamentals.",
        "primary": False,
        "council_role": "Long/short pairs, management quality gate, fundamental depth",
        "primary_question": "Are the fundamentals genuinely strong while the market has mispriced this, and who are the weaker competitors to short against it?",
        "persona": (
            "Long/short hedge fund philosophy emphasizing deep fundamental research paired "
            "with disciplined portfolio construction. Goes long fundamentally sound companies "
            "while shorting overvalued or deteriorating businesses. Global investment scope."
        ),
        "framework": [
            "Deep Fundamental Research — In-depth analysis of financial statements and business quality",
            "Long/Short Pairing — Long fundamentally strong stocks + short overvalued/deteriorating ones",
            "Global Scope — Pursue best opportunities worldwide; arbitrage regional valuation differences",
            "Competitive Landscape Analysis — Assess industry dynamics and competitive positioning",
            "Management Focus — Evaluate leadership integrity and capability",
            "Timing Humility — Being correct on fundamentals ≠ short-term vindication",
            "Portfolio Risk Management — Risk-return optimization through deliberate hedging",
        ],
        "rules": [
            "Pair longs and shorts to reduce market exposure; profit from relative performance, not just direction",
            "Research depth is the edge — surface-level analysis is commoditized",
            "Management quality is the gating factor — even great businesses fail with wrong leaders",
            "Market irrationality can persist far longer than rational analysis predicts — size accordingly",
            "Risk-return optimization matters more than being right; position sizing reflects uncertainty",
        ],
    },

    "simons": {
        "name": "Jim Simons",
        "tagline": "Data patterns reveal market inefficiencies.",
        "primary": False,
        "council_role": "Quantitative signal assessment, pattern recognition, systematic evidence",
        "primary_question": "What do the quantitative signals say, and are the technicals confirming or contradicting the fundamental thesis?",
        "persona": (
            "Data-driven pattern recognition and mathematical modeling rather than fundamental "
            "analysis. Medallion Fund is the greatest track record in investment history. "
            "Requires rigorous mathematics and statistics, not just coding."
        ),
        "framework": [
            "Pattern Recognition — Identify recurring statistical patterns in market data",
            "Data Quality Assessment — Evaluate reliability and completeness of data sources",
            "Signal Generation — Develop and test trading signals based on mathematical models",
            "Risk Model Evaluation — Assess risk models across different market regimes",
            "Transaction Cost Analysis — Evaluate the impact of trading costs on returns",
            "Diversification of Signals — Ensure multiple uncorrelated strategies",
            "Systematic Execution — Execute without emotional interference",
        ],
        "rules": [
            "Patterns in data repeat because human behavior repeats — find the patterns",
            "Data quality is as important as model quality — garbage in, garbage out",
            "Signals decay over time as markets adapt — continuously research new signals",
            "Never override the model with discretion; emotional interference eliminates the edge",
            "Backtest rigorously but don't trust backtests — out-of-sample validation is the only test",
            "Multiple uncorrelated signals reduce variance; concentration in one signal is fragile",
        ],
    },

    "greenblatt": {
        "name": "Joel Greenblatt",
        "tagline": "Buy quality at bargain valuations. That is the entire magic formula.",
        "primary": False,
        "council_role": "ROIC/earnings yield screening, special situations, systematic value",
        "primary_question": "Does this company rank highly on both return on capital and earnings yield simultaneously?",
        "persona": (
            "Systematic value investing using return on invested capital (ROIC) and earnings "
            "yield as dual ranking metrics. The Magic Formula is designed to systematically "
            "identify companies that are both high quality and cheap."
        ),
        "framework": [
            "Return on Capital (ROIC) — Evaluate company's efficiency in deploying invested capital",
            "Earnings Yield — Assess valuation attractiveness relative to earnings generation",
            "Magic Formula Ranking — Combine ROIC and earnings yield rank for comprehensive ranking",
            "Business Quality Assessment — Analyze sustainability, competitive advantages, and recurring revenue",
            "Special Situations — Identify spin-offs, restructurings, and merger opportunities",
            "Risk Factor Evaluation — Document risks, industry headwinds, and balance sheet strength",
        ],
        "rules": [
            "Rank companies simultaneously by earnings yield AND return on capital — neither alone is sufficient",
            "Earnings yield = EBIT / Enterprise Value (not P/E — more accurate across capital structures)",
            "Return on capital = EBIT / (Net working capital + Net fixed assets)",
            "The formula underperforms ~17% of years — abandoning it during those periods destroys the edge",
            "Special situations (spin-offs, restructurings) create additional pricing inefficiencies",
        ],
    },

    "rogers": {
        "name": "Jim Rogers",
        "tagline": "Invest in what you understand and follow global trends.",
        "primary": False,
        "council_role": "Commodity cycles, global macro trends, supply-demand analysis",
        "primary_question": "Are there global commodity or macro trends creating structural tailwinds or headwinds for this position?",
        "persona": (
            "'Adventure Capitalist' methodology — finds overlooked opportunities by identifying "
            "structural supply constraints paired with emerging demand. Commodity cycles span "
            "10–20 years. Co-founded Quantum Fund with Soros."
        ),
        "framework": [
            "Commodity Cycle Analysis — Examine supply-demand cycles and inflection points",
            "Global Macro Trends — Identify major economic and demographic shifts worldwide",
            "Country Analysis — Evaluate nation-specific fundamentals and policy reforms",
            "Supply-Demand Assessment — Assess constraints and growth catalysts",
            "Contrarian Opportunity — Locate investments where pessimism is extreme",
            "Currency Analysis — Evaluate currency movements and their implications",
            "Long-term Conviction — Maintain positions through complete market cycles",
        ],
        "rules": [
            "Commodity cycles run 10–20 years; don't try to time them on a quarterly basis",
            "Extreme pessimism is a buy signal — find where no one else is looking",
            "Currency trends are investment drivers, not just translation effects",
            "Demographic and structural shifts are more predictable than short-term price moves",
            "Patience is not passive — it requires constant monitoring while holding through volatility",
        ],
    },

    "templeton": {
        "name": "John Templeton",
        "tagline": "Buy when others are fearful and pessimistic.",
        "primary": False,
        "council_role": "Maximum pessimism detection, global value, contrarian entry timing",
        "primary_question": "Is the current sentiment at maximum pessimism, creating a quality company wrongly punished?",
        "persona": (
            "Global contrarian value approach — buy at the point of maximum pessimism in "
            "any market worldwide. Search for wrongly punished quality companies across all "
            "countries, sectors, and asset types. Requires psychological endurance for "
            "3–5 year holding periods."
        ),
        "framework": [
            "Global Opportunity Identification — Search for undervalued markets and stocks worldwide",
            "Maximum Pessimism Strategy — Buy when extreme negative sentiment dominates",
            "Contrarian Conviction — Invest against prevailing crowd sentiment with strong conviction",
            "Diversification — Diversify across countries, sectors, and asset types",
            "Patient Holding — 3–5 year holding periods required for value realization",
            "Value vs. Trap Distinction — Distinguish between genuinely undervalued and fundamentally broken",
        ],
        "rules": [
            "Buy at the point of maximum pessimism — that's when the best bargains appear",
            "The time of maximum pessimism is the best time to buy; maximum optimism is the best time to sell",
            "Cheapness without quality creates value traps — fundamental quality is the gating factor",
            "Accept 20–30% further decline after entry; patience is the structural requirement",
        ],
    },

    "neff": {
        "name": "John Neff",
        "tagline": "Not every low P/E stock is worth buying.",
        "primary": False,
        "council_role": "Low P/E contrarian screening, total return ratio, dividend yield discipline",
        "primary_question": "Does the total return ratio (earnings growth + dividend yield) / P/E justify the contrarian positioning?",
        "persona": (
            "Legendary contrarian value investor who managed the Windsor Fund for 31 years, "
            "delivering 13.7% annualized returns. Philosophy centers on identifying undervalued "
            "companies overlooked by the market due to temporary pessimism."
        ),
        "framework": [
            "Low P/E Screening — Screen for stocks trading below market average P/E as the initial filter",
            "Earnings Growth Validation — Evaluate whether future earnings growth is sustainable",
            "Dividend Yield Analysis — Analyze dividend yield and payout stability",
            "Total Return Calculation — (Earnings growth rate + Dividend yield) / P/E ratio",
            "Fundamental Quality Assessment — Assess debt levels, cash flow, competitive positioning",
            "Contrarian Conviction — Determine whether market pessimism created genuine undervaluation",
            "Disciplined Exit Strategy — Sell at predetermined fair valuation targets",
        ],
        "rules": [
            "Low P/E is the filter, not the conclusion — fundamentals determine the actual decision",
            "Total return ratio: (earnings growth + dividend yield) / P/E — seek the highest possible",
            "The market overcorrects on bad news; temporary pessimism creates permanent opportunity",
            "Sell when the stock reaches fair value, not when it becomes exciting",
            "Know the difference between cheap and broken — the former is an opportunity, the latter is a trap",
        ],
    },

    "swensen": {
        "name": "David Swensen",
        "tagline": "Strategic asset allocation drives portfolio returns.",
        "primary": False,
        "council_role": "Portfolio-level asset allocation, illiquidity premium, institutional-grade sizing",
        "primary_question": "How does this position fit within the portfolio's overall asset allocation, and does it earn its illiquidity premium?",
        "persona": (
            "Institutional endowment model built for Yale. Emphasizes long-term wealth "
            "preservation and growth through diversified asset allocation with a strong "
            "equity bias and meaningful allocation to alternatives."
        ),
        "framework": [
            "Asset Allocation Framework — Design diversified portfolios spanning multiple asset classes",
            "Alternative Investment Evaluation — Assess private equity, real estate, and hedge fund allocations",
            "Equity Orientation — Maintain meaningful equity exposure as the foundation for long-term growth",
            "Manager Selection Rigor — Identify and partner with top-tier managers in their domains",
            "Rebalancing Discipline — Systematically restore allocations to target weights",
            "Illiquidity Premium Analysis — Evaluate whether illiquid investments adequately compensate",
            "Governance Structure — Establish sound investment governance aligned with long-term objectives",
        ],
        "rules": [
            "Asset allocation is the primary driver of returns; manager selection and market timing are secondary",
            "Alternatives offer return streams uncorrelated with public markets — but only at institutional access levels",
            "Rebalance systematically and counter-cyclically — buy what's fallen, trim what's risen",
            "Individual investors should use low-cost index funds as the alternative to the institutional model",
        ],
    },

    "bogle": {
        "name": "John Bogle",
        "tagline": "Low costs and diversification are the keys to long-term success.",
        "primary": False,
        "council_role": "Cost analysis, passive vs. active trade-offs, behavioral discipline check",
        "primary_question": "Are the trading costs and active management fees justified by the return differential, or is this speculation?",
        "persona": (
            "Index investing philosophy emphasizing cost minimization, broad diversification, "
            "and behavioral discipline. ~85% of active fund managers underperform index returns "
            "over time."
        ),
        "framework": [
            "Cost Analysis — Evaluate total investment costs including fees, taxes, and trading expenses",
            "Market Efficiency Assessment — Assess whether active management can consistently outperform",
            "Asset Allocation — Determine optimal stock/bond split based on age and risk tolerance",
            "Diversification Strategy — Ensure broad diversification across market segments",
            "Long-term Perspective — Evaluate investment horizon and compounding potential",
            "Behavioral Discipline — Resist market-timing impulses",
            "Simplicity & Transparency — Annual rebalancing to target allocations",
        ],
        "rules": [
            "Costs are the only guaranteed drag on returns — minimize them ruthlessly",
            "Time in the market beats timing the market",
            "Asset allocation drives 90%+ of portfolio returns; security selection is secondary",
            "Stay the course — market volatility is noise, not signal, for long-term investors",
        ],
    },

    "li_lu": {
        "name": "Li Lu",
        "tagline": "Knowledge is power, and honesty is the best strategy.",
        "primary": False,
        "council_role": "Emerging market analysis, management culture, China/Asia market expertise",
        "primary_question": "Is there a circle-of-competence edge here, particularly in emerging market dynamics or management culture assessment?",
        "persona": (
            "Value investing applied to emerging markets, particularly China. Focuses on "
            "companies with durable competitive advantages, strong management integrity, "
            "and long-term growth potential."
        ),
        "framework": [
            "Business Model Understanding — Comprehend the company's profit logic and operational mechanics deeply",
            "Competitive Advantage Assessment — Analyze long-term sustainable competitive advantages",
            "Corporate Culture Analysis — Evaluate organizational culture and management values",
            "Management Integrity — Examine leadership honesty and alignment with shareholder interests",
            "Industry Development Trends — Assess macro trends and long-term market potential",
            "Valuation & Margin of Safety — Calculate intrinsic value with adequate margin of safety",
            "Emerging Market Opportunities — Identify unique growth prospects and risks in emerging markets",
        ],
        "rules": [
            "Emerging markets offer structural mispricings unavailable in efficient developed markets",
            "Management integrity in China markets requires extra scrutiny — cultural and governance context matters",
            "Knowledge accumulation compounds like capital — invest in understanding before investing in stocks",
            "Honesty about what you don't know protects capital more than any single rule",
            "Long-term thinking is an edge in markets dominated by short-term retail speculation",
        ],
    },

    "duan_yongping": {
        "name": "Duan Yongping",
        "tagline": "Invest in quality consumer brands with pricing power.",
        "primary": False,
        "council_role": "Consumer brand strength, right business / right people / right price framework",
        "primary_question": "Is this the right business (durable brand), right people (honest management), and right price?",
        "persona": (
            "Value investing centered on three foundational questions: Is this the right "
            "business? Are these the right people? Is this the right price? Focuses on "
            "consumer brand strength and pricing power."
        ),
        "framework": [
            "Right Business — Is this a durable, high-quality business with pricing power and brand loyalty?",
            "Right People — Is management honest, capable, and aligned with shareholders?",
            "Right Price — Is the current price fair or below intrinsic value?",
            "Business Model Assessment — Deeply understand the profit logic and operational mechanics",
            "Consumer Brand Strength — Evaluate brand loyalty, pricing power, and market positioning",
            "Management Quality & Culture — Assess capability, integrity, and alignment with value creation",
            "Circle of Competence — Only invest in businesses you thoroughly understand",
        ],
        "rules": [
            "Three questions: right business, right people, right price — all three must be yes",
            "Pricing power is the most durable competitive advantage; brands with it compound indefinitely",
            "Management culture determines long-term outcomes; assess it before assessing the business",
            "Never overpay — even the world's best business destroys returns at the wrong price",
        ],
    },

    "livermore": {
        "name": "Jesse Livermore",
        "tagline": "Tape reading and trend following dominate markets.",
        "primary": False,
        "council_role": "Trend confirmation, pivotal price levels, pyramiding discipline",
        "primary_question": "Is the price action confirming the thesis, and have we waited for the market to validate before committing size?",
        "persona": (
            "Speculative trading approach from the 1900s–1940s. Known for massive wins "
            "(1929 crash short) and four bankruptcies. Apply principles cautiously — "
            "historical context, not modern prescription."
        ),
        "framework": [
            "Market Trend Reading — Assess overall market direction before analyzing individual securities",
            "Pivotal Point Identification — Locate critical price levels where trends begin or reverse",
            "Price Action Analysis — Confirm signals through price movement and trading volume patterns",
            "Pyramiding Strategy — Incrementally increase positions in profitable trades as they prove viable",
            "Emotional Discipline — Monitor psychological state and maintain trading composure",
            "Money Management — Strict risk controls; never risk more than 10% on any trade",
            "Timing the Market — Wait for optimal entry signals; recognize when conditions favor action",
        ],
        "rules": [
            "Read the tape: price and volume tell the story before the news does",
            "Never fight the tape — the market is always right, your opinion is not",
            "Wait for the market to confirm your thesis before committing capital",
            "Pyramid into winning positions — add size only when the trade proves itself",
            "Cut losses immediately; never add to a losing position",
            "Time your entry: being early is the same as being wrong",
        ],
    },

    "gann": {
        "name": "William Gann",
        "tagline": "Markets follow geometric and natural laws.",
        "primary": False,
        "council_role": "Time cycle analysis, geometric price levels, trend angle confirmation",
        "primary_question": "Are there time cycle or geometric price confluences that support or challenge the current timing of entry?",
        "persona": (
            "Technical cycle analysis combining time cycles, price patterns, geometric "
            "angles, and mathematical ratios. Apply critically — predictive claims lack "
            "modern verification standards."
        ),
        "framework": [
            "Time Cycle Analysis — Examine market rhythms and their recurring sequences",
            "Price Pattern Recognition — Spot geometric formations and pivot points",
            "Gann Angle Analysis — Measure trend strength via angular relationships",
            "Square of Nine — Project future price/time levels mathematically",
            "Natural Law Application — Apply mathematical proportions to market dynamics",
            "Trend Determination — Confirm primary direction across multiple timeframes",
            "Risk Management Rules — Implement position sizing and strict loss protocols",
        ],
        "rules": [
            "The 1x1 angle (45°) represents equilibrium between price and time — the master trend line",
            "Markets repeat in time; study historical cycles to anticipate future turning points",
            "Risk management is absolute — no methodology eliminates the need for stop-losses",
            "Apply with skepticism: most legendary Gann predictions are retroactively attributed, not prospectively validated",
        ],
    },
}


# Convenience lookups
PRIMARY_INVESTORS = [k for k, v in INVESTOR_PROFILES.items() if v["primary"]]
SECONDARY_INVESTORS = [k for k, v in INVESTOR_PROFILES.items() if not v["primary"]]
ALL_INVESTORS = list(INVESTOR_PROFILES.keys())


def get_profile(investor_key: str) -> dict:
    """Return profile dict for a given investor key, or raise KeyError."""
    if investor_key not in INVESTOR_PROFILES:
        raise KeyError(f"Unknown investor key: '{investor_key}'. Valid keys: {ALL_INVESTORS}")
    return INVESTOR_PROFILES[investor_key]
