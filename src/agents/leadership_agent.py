"""Leadership agent for evaluating company leadership using the Four Capitals Framework.

The Four Capitals Framework (Athena Alliance / McKinsey):
1. Individual Capital — Self-reflection, vision clarity, cognitive focus, diverse experiences
2. Relational Capital — Deep 1:1 relationships, behavioral integration at the top team
3. Organizational Capital — Management rituals, accountability structures, culture hardwiring
4. Reputational Capital — Strategic storytelling, consistency between words and actions
"""

import asyncio
import anthropic
from openai import OpenAI
from typing import Dict, Any, List, Optional
import json
import re
from datetime import datetime, timezone
from .base_agent import BaseAgent
from ..tavily_client import get_tavily_client


class LeadershipAgent(BaseAgent):
    """Agent for evaluating company leadership using the Four Capitals Framework.
    
    Uses Tavily AI search for comprehensive leadership research and LLM for
    executive summary generation and qualitative scoring.
    """

    # Research query templates for leadership evaluation
    RESEARCH_QUERIES = [
        "{company} {ticker} CEO background tenure experience education",
        "{company} {ticker} executive team C-suite management leadership",
        "{company} {ticker} board of directors independence composition",
        "{company} {ticker} CEO succession plan replacement",
        "{company} {ticker} executive compensation insider ownership equity",
        "{company} {ticker} leadership change CFO departure executive turnover",
        "{company} {ticker} corporate culture employee satisfaction Glassdoor",
        "{company} {ticker} ESG governance score rating board diversity",
    ]

    # Red flag detection keywords/patterns
    RED_FLAG_PATTERNS = {
        "high_turnover": [
            "cfo resigned", "cfo departure", "cfo leaves", "cfo stepping down",
            "executive resigned", "executive departure", "executive leaves",
            "management turnover", "key executive departed", "senior leader departed",
        ],
        "succession_risk": [
            "ceo nearing retirement", "no succession plan", "succession uncertainty",
            "aging ceo", "ceo health", "leadership vacuum", "key person risk",
        ],
        "governance_issue": [
            "board conflict", "activist investor", "proxy fight", "board investigation",
            "sec investigation", "accounting irregularities", "restatement",
            "insider trading", "related party transaction", "dual class shares",
        ],
        "compensation_concern": [
            "excessive compensation", "pay for performance misalignment",
            "golden parachute", "excessive severance", "stock dilution",
            "option backdating",
        ],
        "ethical_concern": [
            "workplace harassment", "discrimination lawsuit", "toxic culture",
            "employee protest", "whistleblower", "ethics violation",
        ],
    }

    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch leadership data using Tavily AI search.
        
        Executes multiple research queries in parallel to gather comprehensive
        leadership information across all Four Capitals dimensions.
        
        Returns:
            Dictionary with research results from all queries
        """
        # Get company info for better query building
        company_info = await self._get_company_info()
        company_name = company_info.get("long_name") or company_info.get("short_name", self.ticker)
        
        # Build all research queries
        queries = [
            query.format(company=company_name, ticker=self.ticker)
            for query in self.RESEARCH_QUERIES
        ]
        
        self.logger.info(f"Fetching leadership data for {self.ticker} using Tavily AI search")
        
        # Execute all queries in parallel
        tavily = get_tavily_client(self.config)
        if not tavily.is_available:
            self.logger.warning(f"Tavily not available for {self.ticker}")
            return {
                "ticker": self.ticker,
                "company_name": company_name,
                "queries": queries,
                "results": [],
                "source": "tavily_unavailable"
            }
        
        search_tasks = [
            self._execute_tavily_search(tavily, query, idx)
            for idx, query in enumerate(queries)
        ]
        
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.warning(f"Query {i+1} failed: {result}")
                processed_results.append({
                    "query": queries[i],
                    "success": False,
                    "error": str(result),
                    "articles": []
                })
            else:
                processed_results.append(result)
        
        # Flatten all articles for analysis
        all_articles = []
        for result in processed_results:
            if result.get("success"):
                all_articles.extend(result.get("articles", []))
        
        # Deduplicate articles by URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)
        
        self.logger.info(
            f"Leadership research for {self.ticker}: {len(unique_articles)} unique articles "
            f"from {len([r for r in processed_results if r.get('success')])} successful queries"
        )
        
        return {
            "ticker": self.ticker,
            "company_name": company_name,
            "company_info": company_info,
            "queries": queries,
            "query_results": processed_results,
            "articles": unique_articles,
            "source": "tavily"
        }

    async def _execute_tavily_search(
        self,
        tavily,
        query: str,
        query_idx: int
    ) -> Dict[str, Any]:
        """Execute a single Tavily search query.
        
        Args:
            tavily: Tavily client instance
            query: Search query string
            query_idx: Index for logging
            
        Returns:
            Dict with search results
        """
        try:
            response = await tavily._client.search(
                query=query,
                max_results=10,
                time_range="365d",  # Look back 1 year for leadership context
                include_answer=False,
                include_raw_content=True,
                search_depth="advanced"
            )
            
            articles = []
            for result in response.get("results", []):
                articles.append({
                    "title": result.get("title", ""),
                    "source": result.get("source", ""),
                    "url": result.get("url", ""),
                    "published_at": result.get("published_date", ""),
                    "content": result.get("raw_content", result.get("content", "")),
                    "snippet": result.get("content", ""),
                    "relevance_score": result.get("score", 0.5),
                })
            
            return {
                "query": query,
                "success": True,
                "articles": articles,
                "count": len(articles)
            }
            
        except Exception as e:
            self.logger.warning(f"Tavily query {query_idx+1} failed: {e}")
            return {
                "query": query,
                "success": False,
                "error": str(e),
                "articles": []
            }

    async def _get_company_info(self) -> Dict[str, str]:
        """Get company information using yfinance.
        
        Returns:
            Dict with company name and other info
        """
        try:
            import yfinance as yf
            info = await self._run_blocking(lambda: yf.Ticker(self.ticker).info)
            
            if info and isinstance(info, dict):
                return {
                    "long_name": info.get("longName", ""),
                    "short_name": info.get("shortName", ""),
                    "sector": info.get("sector", ""),
                    "industry": info.get("industry", ""),
                }
        except Exception as e:
            self.logger.debug(f"Failed to get company info: {e}")
        
        return {
            "long_name": self.ticker,
            "short_name": self.ticker,
            "sector": "",
            "industry": "",
        }

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze leadership data using the Four Capitals Framework.
        
        Args:
            raw_data: Raw research data from fetch_data()
            
        Returns:
            Complete Four Capitals assessment with scores, grades, and insights
        """
        articles = raw_data.get("articles", [])
        company_name = raw_data.get("company_name", self.ticker)
        
        if not articles:
            return self._generate_fallback_assessment(company_name)
        
        # Extract key metrics from articles
        metrics = self._extract_key_metrics(articles)
        
        # Detect red flags
        red_flags = self._detect_red_flags(articles)
        
        # Score each of the Four Capitals
        four_capitals = self._score_four_capitals(articles, metrics, red_flags)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(four_capitals)
        overall_grade = self._score_to_grade(overall_score)
        
        # Generate executive summary using LLM
        executive_summary = await self._generate_executive_summary(
            company_name, four_capitals, red_flags, metrics
        )
        
        assessment = {
            "overall_score": round(overall_score, 1),
            "grade": overall_grade,
            "assessment_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "four_capitals": four_capitals,
            "key_metrics": metrics,
            "red_flags": red_flags,
            "executive_summary": executive_summary,
            "data_source": "tavily",
            "research_queries": raw_data.get("queries", []),
            "article_count": len(articles)
        }
        
        return assessment

    def _extract_key_metrics(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key leadership metrics from articles.
        
        Uses regex patterns to extract quantitative metrics from article content.
        
        Args:
            articles: List of research articles
            
        Returns:
            Dict with extracted metrics
        """
        metrics = {
            "ceo_tenure_years": None,
            "c_suite_turnover_12m": 0,
            "c_suite_turnover_24m": 0,
            "board_independence_pct": None,
            "avg_board_tenure_years": None,
            "institutional_ownership_pct": None,
            "executive_compensation_median": None,
        }
        
        # Combine all article text for analysis
        all_text = " ".join([
            f"{a.get('title', '')} {a.get('content', '')} {a.get('snippet', '')}"
            for a in articles
        ]).lower()
        
        # Extract CEO tenure
        ceo_tenure_patterns = [
            r'ceo(?:\s+\w+)?\s+(?:has\s+been|joined|appointed|served)\s+(?:for\s+)?(\d+(?:\.\d+)?)\s*(?:years?|yrs?)',
            r'ceo(?:\s+\w+)?\s+(?:with|has)\s+(\d+(?:\.\d+)?)\s*-?\s*year\s+(?:tenure|experience)',
            r'ceo\s+since\s+(?:20)?(\d{2})',
        ]
        
        for pattern in ceo_tenure_patterns:
            match = re.search(pattern, all_text)
            if match:
                try:
                    if "since" in pattern:
                        year = int(match.group(1))
                        if year < 50:
                            year += 2000
                        else:
                            year += 1900
                        metrics["ceo_tenure_years"] = datetime.now().year - year
                    else:
                        metrics["ceo_tenure_years"] = float(match.group(1))
                    break
                except (ValueError, TypeError):
                    pass
        
        # Extract board independence
        board_indep_patterns = [
            r'(\d+)%\s+(?:of\s+)?(?:the\s+)?board\s+(?:is\s+)?independent',
            r'(\d+)%\s+independent\s+directors?',
            r'(\d+)\s+of\s+(\d+)\s+(?:board\s+)?members?\s+(?:are\s+)?independent',
        ]
        
        for pattern in board_indep_patterns:
            match = re.search(pattern, all_text)
            if match:
                try:
                    if "of" in pattern and len(match.groups()) > 1:
                        independent = int(match.group(1))
                        total = int(match.group(2))
                        metrics["board_independence_pct"] = round((independent / total) * 100)
                    else:
                        metrics["board_independence_pct"] = int(match.group(1))
                    break
                except (ValueError, TypeError):
                    pass
        
        # Extract board tenure
        board_tenure_patterns = [
            r'average\s+board\s+tenure\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*years?',
            r'board\s+members?\s+(?:serve|tenure)\s+(?:an\s+)?average\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*years?',
        ]
        
        for pattern in board_tenure_patterns:
            match = re.search(pattern, all_text)
            if match:
                try:
                    metrics["avg_board_tenure_years"] = float(match.group(1))
                    break
                except (ValueError, TypeError):
                    pass
        
        # Extract institutional ownership
        inst_own_patterns = [
            r'institutional\s+(?:ownership|investors?)\s+(?:of\s+)?(\d+)%',
            r'(\d+)%\s+(?:is\s+)?(?:held\s+by\s+)?institutional',
        ]
        
        for pattern in inst_own_patterns:
            match = re.search(pattern, all_text)
            if match:
                try:
                    metrics["institutional_ownership_pct"] = int(match.group(1))
                    break
                except (ValueError, TypeError):
                    pass
        
        # Count executive turnover mentions (rough heuristic)
        turnover_keywords = ["resigned", "departed", "stepping down", "leaving", "departing"]
        for keyword in turnover_keywords:
            metrics["c_suite_turnover_12m"] += all_text.count(f"cfo {keyword}")
            metrics["c_suite_turnover_12m"] += all_text.count(f"coo {keyword}")
            metrics["c_suite_turnover_12m"] += all_text.count(f"cto {keyword}")
        
        # Cap at reasonable values
        metrics["c_suite_turnover_12m"] = min(metrics["c_suite_turnover_12m"], 5)
        metrics["c_suite_turnover_24m"] = metrics["c_suite_turnover_12m"] * 2  # Estimate
        
        return {k: v for k, v in metrics.items() if v is not None}

    def _detect_red_flags(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect leadership red flags from articles.
        
        Args:
            articles: List of research articles
            
        Returns:
            List of detected red flags with severity and description
        """
        red_flags = []
        all_text = " ".join([
            f"{a.get('title', '')} {a.get('content', '')}"
            for a in articles
        ]).lower()
        
        for flag_type, keywords in self.RED_FLAG_PATTERNS.items():
            for keyword in keywords:
                if keyword in all_text:
                    # Determine severity based on context
                    severity = self._determine_severity(flag_type, keyword, all_text)
                    
                    # Find the article that mentions this flag
                    source_article = None
                    for article in articles:
                        article_text = f"{article.get('title', '')} {article.get('content', '')}".lower()
                        if keyword in article_text:
                            source_article = article
                            break
                    
                    # Create flag entry if not already detected
                    existing = [f for f in red_flags if f["type"] == flag_type]
                    if not existing:
                        red_flags.append({
                            "type": flag_type,
                            "severity": severity,
                            "description": self._generate_flag_description(flag_type, keyword, source_article),
                            "source": source_article.get("source", "news_search") if source_article else "news_search"
                        })
                    break  # Only capture one instance per flag type
        
        return red_flags

    def _determine_severity(self, flag_type: str, keyword: str, context: str) -> str:
        """Determine the severity of a red flag based on context.
        
        Args:
            flag_type: Type of red flag
            keyword: Matched keyword
            context: Surrounding text context
            
        Returns:
            Severity level: low, medium, or high
        """
        high_severity_indicators = [
            "scandal", "fraud", "investigation", "lawsuit", "criminal",
            "resigned immediately", "fired", "terminated", "accounting irregularities"
        ]
        
        for indicator in high_severity_indicators:
            if indicator in context:
                return "high"
        
        # Default severities by type
        severity_map = {
            "high_turnover": "medium",
            "succession_risk": "medium",
            "governance_issue": "high",
            "compensation_concern": "low",
            "ethical_concern": "high",
        }
        
        return severity_map.get(flag_type, "medium")

    def _generate_flag_description(
        self,
        flag_type: str,
        keyword: str,
        article: Optional[Dict[str, Any]]
    ) -> str:
        """Generate a human-readable description for a red flag.
        
        Args:
            flag_type: Type of red flag
            keyword: Matched keyword
            article: Source article if available
            
        Returns:
            Description string
        """
        descriptions = {
            "high_turnover": "Executive turnover detected in the past 12 months",
            "succession_risk": "Potential succession planning concerns identified",
            "governance_issue": "Corporate governance issues or board conflicts reported",
            "compensation_concern": "Executive compensation or pay-for-performance concerns raised",
            "ethical_concern": "Ethical concerns or workplace culture issues reported",
        }
        
        base_desc = descriptions.get(flag_type, f"{flag_type.replace('_', ' ').title()} identified")
        
        if article and article.get("title"):
            return f"{base_desc}: {article['title']}"
        
        return base_desc

    def _score_four_capitals(
        self,
        articles: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        red_flags: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Score each of the Four Capitals dimensions.
        
        Args:
            articles: Research articles
            metrics: Extracted key metrics
            red_flags: Detected red flags
            
        Returns:
            Dict with scores and insights for each capital
        """
        all_text = " ".join([
            f"{a.get('title', '')} {a.get('content', '')}"
            for a in articles
        ]).lower()
        
        # Individual Capital
        individual = self._score_individual_capital(all_text, metrics, red_flags)
        
        # Relational Capital
        relational = self._score_relational_capital(all_text, metrics, red_flags)
        
        # Organizational Capital
        organizational = self._score_organizational_capital(all_text, metrics, red_flags)
        
        # Reputational Capital
        reputational = self._score_reputational_capital(all_text, metrics, red_flags)
        
        return {
            "individual": individual,
            "relational": relational,
            "organizational": organizational,
            "reputational": reputational
        }

    def _score_individual_capital(
        self,
        text: str,
        metrics: Dict[str, Any],
        red_flags: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Score Individual Capital (CEO capability and experience).
        
        Factors: tenure, experience indicators, vision clarity, diversity of background
        """
        score = 70  # Base score
        insights = []
        capital_red_flags = []
        
        # CEO tenure scoring
        tenure = metrics.get("ceo_tenure_years")
        if tenure:
            if tenure >= 10:
                score += 15
                insights.append(f"CEO has {tenure:.1f} years tenure, demonstrating stability")
            elif tenure >= 5:
                score += 10
                insights.append(f"CEO has {tenure:.1f} years tenure")
            elif tenure >= 2:
                score += 5
                insights.append(f"CEO has {tenure:.1f} years tenure, still establishing track record")
            else:
                score -= 10
                capital_red_flags.append("CEO tenure less than 2 years")
                insights.append("CEO is relatively new, limited track record")
        else:
            insights.append("CEO tenure information not available")
        
        # Experience indicators
        experience_keywords = [
            "industry veteran", "decades of experience", "former ceo", "previously led",
            "20+ years", "extensive experience", "proven track record"
        ]
        experience_score = sum(1 for kw in experience_keywords if kw in text)
        if experience_score >= 2:
            score += 10
            insights.append("CEO has extensive industry experience")
        elif experience_score >= 1:
            score += 5
        
        # Education/pedigree (weak signal)
        education_keywords = ["mba", "harvard", "stanford", "wharton", "mit"]
        if any(kw in text for kw in education_keywords):
            score += 3
        
        # Vision clarity indicators
        vision_keywords = ["strategic vision", "clear strategy", "long-term vision", "transformation"]
        if any(kw in text for kw in vision_keywords):
            score += 5
            insights.append("Leadership has articulated clear strategic vision")
        
        # Check for red flags
        relevant_flags = [f for f in red_flags if f["type"] in ["succession_risk", "ethical_concern"]]
        for flag in relevant_flags:
            score -= 15 if flag["severity"] == "high" else 10
            capital_red_flags.append(flag["description"])
        
        score = max(0, min(100, score))
        
        return {
            "score": score,
            "grade": self._score_to_grade(score),
            "insights": insights if insights else ["Limited information on individual leadership capabilities"],
            "red_flags": capital_red_flags
        }

    def _score_relational_capital(
        self,
        text: str,
        metrics: Dict[str, Any],
        red_flags: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Score Relational Capital (team dynamics and collaboration).
        
        Factors: C-suite stability, teamwork indicators, board relationships
        """
        score = 70  # Base score
        insights = []
        capital_red_flags = []
        
        # C-suite turnover
        turnover_12m = metrics.get("c_suite_turnover_12m", 0)
        if turnover_12m == 0:
            score += 15
            insights.append("No significant C-suite turnover in past 12 months")
        elif turnover_12m == 1:
            score += 5
            insights.append("One C-suite departure in past 12 months")
        elif turnover_12m <= 2:
            score -= 10
            capital_red_flags.append("Multiple executive departures in past 12 months")
        else:
            score -= 20
            capital_red_flags.append("High executive turnover indicating team instability")
        
        # Team collaboration indicators
        team_keywords = ["strong team", "collaborative", "work closely", "partnership", "aligned"]
        if any(kw in text for kw in team_keywords):
            score += 8
            insights.append("Evidence of strong executive team collaboration")
        
        # Board relationships
        board_keywords = ["strong board", "board support", "works closely with board"]
        if any(kw in text for kw in board_keywords):
            score += 5
        
        # Check for high turnover red flags
        relevant_flags = [f for f in red_flags if f["type"] == "high_turnover"]
        for flag in relevant_flags:
            score -= 15 if flag["severity"] == "high" else 10
            capital_red_flags.append(flag["description"])
        
        score = max(0, min(100, score))
        
        return {
            "score": score,
            "grade": self._score_to_grade(score),
            "insights": insights if insights else ["Limited information on executive team dynamics"],
            "red_flags": capital_red_flags
        }

    def _score_organizational_capital(
        self,
        text: str,
        metrics: Dict[str, Any],
        red_flags: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Score Organizational Capital (culture, structure, accountability).
        
        Factors: board independence, governance structure, culture indicators
        """
        score = 70  # Base score
        insights = []
        capital_red_flags = []
        
        # Board independence
        independence = metrics.get("board_independence_pct")
        if independence:
            if independence >= 85:
                score += 15
                insights.append(f"Highly independent board ({independence}%)")
            elif independence >= 75:
                score += 10
                insights.append(f"Majority independent board ({independence}%)")
            elif independence >= 50:
                score += 5
                insights.append(f"Board independence at {independence}%")
            else:
                score -= 15
                capital_red_flags.append(f"Low board independence ({independence}%)")
        
        # Board tenure balance
        avg_tenure = metrics.get("avg_board_tenure_years")
        if avg_tenure:
            if 5 <= avg_tenure <= 10:
                score += 5
                insights.append(f"Balanced average board tenure ({avg_tenure} years)")
            elif avg_tenure > 12:
                score -= 5
                insights.append(f"Long-tenured board may benefit from fresh perspectives")
        
        # Culture indicators
        culture_positive = ["strong culture", "employee satisfaction", "great place to work", "diversity inclusion"]
        culture_negative = ["toxic culture", "employee complaints", "high turnover", "burnout"]
        
        pos_score = sum(1 for kw in culture_positive if kw in text)
        neg_score = sum(1 for kw in culture_negative if kw in text)
        
        if pos_score > neg_score:
            score += 10
            insights.append("Positive organizational culture indicators")
        elif neg_score > pos_score:
            score -= 10
            capital_red_flags.append("Negative culture indicators detected")
        
        # Governance red flags
        relevant_flags = [f for f in red_flags if f["type"] == "governance_issue"]
        for flag in relevant_flags:
            score -= 20 if flag["severity"] == "high" else 15
            capital_red_flags.append(flag["description"])
        
        score = max(0, min(100, score))
        
        return {
            "score": score,
            "grade": self._score_to_grade(score),
            "insights": insights if insights else ["Limited information on organizational structure"],
            "red_flags": capital_red_flags
        }

    def _score_reputational_capital(
        self,
        text: str,
        metrics: Dict[str, Any],
        red_flags: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Score Reputational Capital (external perception and credibility).
        
        Factors: ESG scores, media sentiment, consistency of messaging
        """
        score = 70  # Base score
        insights = []
        capital_red_flags = []
        
        # ESG governance indicators
        esg_positive = ["strong governance", "high esg score", "best-in-class governance", "transparency"]
        esg_negative = ["esg concerns", "governance issues", "transparency concerns", "accounting issues"]
        
        pos_esg = sum(1 for kw in esg_positive if kw in text)
        neg_esg = sum(1 for kw in esg_negative if kw in text)
        
        if pos_esg > neg_esg:
            score += 12
            insights.append("Strong ESG governance indicators")
        elif neg_esg > pos_esg:
            score -= 15
            capital_red_flags.append("ESG or governance concerns raised")
        
        # Institutional ownership (indicates institutional confidence)
        inst_own = metrics.get("institutional_ownership_pct")
        if inst_own:
            if inst_own >= 70:
                score += 10
                insights.append(f"High institutional ownership ({inst_own}%) indicates external confidence")
            elif inst_own >= 50:
                score += 5
        
        # Compensation alignment
        comp_positive = ["pay for performance", "aligned incentives", "reasonable compensation"]
        comp_negative = ["excessive compensation", "pay controversy", "misaligned incentives"]
        
        if any(kw in text for kw in comp_positive):
            score += 8
        elif any(kw in text for kw in comp_negative):
            score -= 10
            capital_red_flags.append("Executive compensation concerns")
        
        # Media sentiment (simple heuristic)
        media_positive = ["respected leader", "admired company", "leadership excellence", "industry leader"]
        media_negative = ["leadership crisis", "under pressure", "scandal", "controversy"]
        
        pos_media = sum(1 for kw in media_positive if kw in text)
        neg_media = sum(1 for kw in media_negative if kw in text)
        
        if pos_media > neg_media:
            score += 8
            insights.append("Positive external media perception of leadership")
        elif neg_media > pos_media:
            score -= 12
            capital_red_flags.append("Negative media coverage of leadership")
        
        # Red flags
        relevant_flags = [f for f in red_flags if f["type"] in ["compensation_concern", "ethical_concern"]]
        for flag in relevant_flags:
            score -= 15 if flag["severity"] == "high" else 10
            capital_red_flags.append(flag["description"])
        
        score = max(0, min(100, score))
        
        return {
            "score": score,
            "grade": self._score_to_grade(score),
            "insights": insights if insights else ["Limited information on reputational factors"],
            "red_flags": capital_red_flags
        }

    def _calculate_overall_score(self, four_capitals: Dict[str, Dict[str, Any]]) -> float:
        """Calculate weighted overall score from Four Capitals.
        
        Weights: Individual 30%, Relational 25%, Organizational 25%, Reputational 20%
        
        Args:
            four_capitals: Dict with scores for each capital
            
        Returns:
            Weighted overall score
        """
        weights = {
            "individual": 0.30,
            "relational": 0.25,
            "organizational": 0.25,
            "reputational": 0.20
        }
        
        total = 0.0
        for capital, data in four_capitals.items():
            total += data["score"] * weights.get(capital, 0.25)
        
        return round(total, 1)

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade.
        
        Args:
            score: Numeric score 0-100
            
        Returns:
            Letter grade (A+ to F)
        """
        if score >= 97:
            return "A+"
        elif score >= 93:
            return "A"
        elif score >= 90:
            return "A-"
        elif score >= 87:
            return "B+"
        elif score >= 83:
            return "B"
        elif score >= 80:
            return "B-"
        elif score >= 77:
            return "C+"
        elif score >= 73:
            return "C"
        elif score >= 70:
            return "C-"
        elif score >= 67:
            return "D+"
        elif score >= 63:
            return "D"
        elif score >= 60:
            return "D-"
        else:
            return "F"

    async def _generate_executive_summary(
        self,
        company_name: str,
        four_capitals: Dict[str, Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        metrics: Dict[str, Any]
    ) -> str:
        """Generate executive summary using LLM.
        
        Falls back to rule-based summary if LLM is unavailable.
        
        Args:
            company_name: Company name
            four_capitals: Four Capitals assessment
            red_flags: Detected red flags
            metrics: Key metrics
            
        Returns:
            Executive summary string
        """
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")
        
        try:
            if provider == "anthropic":
                return await self._generate_summary_with_anthropic(
                    company_name, four_capitals, red_flags, metrics, llm_config
                )
            elif provider in ("xai", "openai"):
                return await self._generate_summary_with_openai(
                    company_name, four_capitals, red_flags, metrics, llm_config
                )
        except Exception as e:
            self.logger.warning(f"LLM summary generation failed: {e}")
        
        # Fallback to rule-based summary
        return self._generate_fallback_summary(company_name, four_capitals, red_flags)

    async def _generate_summary_with_anthropic(
        self,
        company_name: str,
        four_capitals: Dict[str, Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        llm_config: Dict[str, Any]
    ) -> str:
        """Generate summary using Anthropic Claude."""
        api_key = llm_config.get("api_key")
        if not api_key:
            raise ValueError("No Anthropic API key")
        
        prompt = self._build_summary_prompt(company_name, four_capitals, red_flags, metrics)
        
        client = anthropic.Anthropic(api_key=api_key)
        
        def _call_anthropic():
            return client.messages.create(
                model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
        
        message = await asyncio.to_thread(_call_anthropic)
        return message.content[0].text.strip()

    async def _generate_summary_with_openai(
        self,
        company_name: str,
        four_capitals: Dict[str, Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        llm_config: Dict[str, Any]
    ) -> str:
        """Generate summary using OpenAI-compatible API."""
        api_key = llm_config.get("api_key")
        if not api_key:
            raise ValueError("No API key")
        
        prompt = self._build_summary_prompt(company_name, four_capitals, red_flags, metrics)
        
        client = OpenAI(
            api_key=api_key,
            base_url=llm_config.get("base_url")
        )
        
        def _call_openai():
            return client.chat.completions.create(
                model=llm_config.get("model", "gpt-4"),
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
        
        response = await asyncio.to_thread(_call_openai)
        return response.choices[0].message.content.strip()

    def _build_summary_prompt(
        self,
        company_name: str,
        four_capitals: Dict[str, Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        metrics: Dict[str, Any]
    ) -> str:
        """Build the LLM prompt for executive summary."""
        overall_score = self._calculate_overall_score(four_capitals)
        overall_grade = self._score_to_grade(overall_score)
        
        prompt = f"""Write a concise executive summary (2-3 sentences) evaluating the leadership quality of {company_name} ({self.ticker}).

Four Capitals Assessment:
- Individual Capital (CEO capability): {four_capitals['individual']['grade']} ({four_capitals['individual']['score']}/100)
- Relational Capital (team dynamics): {four_capitals['relational']['grade']} ({four_capitals['relational']['score']}/100)
- Organizational Capital (structure/culture): {four_capitals['organizational']['grade']} ({four_capitals['organizational']['score']}/100)
- Reputational Capital (external perception): {four_capitals['reputational']['grade']} ({four_capitals['reputational']['score']}/100)

Overall: {overall_grade} ({overall_score}/100)

Key Metrics:
- CEO Tenure: {metrics.get('ceo_tenure_years', 'N/A')} years
- Board Independence: {metrics.get('board_independence_pct', 'N/A')}%
- C-Suite Turnover (12m): {metrics.get('c_suite_turnover_12m', 'N/A')}

"""
        
        if red_flags:
            prompt += f"Red Flags ({len(red_flags)}):\n"
            for flag in red_flags[:3]:  # Limit to top 3
                prompt += f"- {flag['type']}: {flag['description']} (severity: {flag['severity']})\n"
        else:
            prompt += "No significant red flags detected.\n"
        
        prompt += "\nProvide a balanced, objective assessment focusing on the strongest and weakest areas. Be specific about what the leadership team does well and where they face challenges."
        
        return prompt

    def _generate_fallback_summary(
        self,
        company_name: str,
        four_capitals: Dict[str, Dict[str, Any]],
        red_flags: List[Dict[str, Any]]
    ) -> str:
        """Generate a rule-based summary when LLM is unavailable."""
        scores = {k: v["score"] for k, v in four_capitals.items()}
        best_capital = max(scores, key=scores.get)
        weakest_capital = min(scores, key=scores.get)
        
        capital_names = {
            "individual": "individual leadership capability",
            "relational": "team dynamics and collaboration",
            "organizational": "organizational structure and culture",
            "reputational": "external reputation and credibility"
        }
        
        summary = f"{company_name} demonstrates "
        
        if scores[best_capital] >= 80:
            summary += f"strong {capital_names[best_capital]}"
        elif scores[best_capital] >= 70:
            summary += f"solid {capital_names[best_capital]}"
        else:
            summary += f"adequate {capital_names[best_capital]}"
        
        if scores[weakest_capital] < 70:
            summary += f", though {capital_names[weakest_capital]} shows room for improvement"
        
        summary += "."
        
        if red_flags:
            high_severity = [f for f in red_flags if f["severity"] == "high"]
            if high_severity:
                summary += f" Investors should monitor {len(high_severity)} high-severity concern(s) identified in the assessment."
        
        return summary

    def _generate_fallback_assessment(self, company_name: str) -> Dict[str, Any]:
        """Generate a minimal assessment when no data is available."""
        return {
            "overall_score": 50,
            "grade": "C",
            "assessment_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "four_capitals": {
                "individual": {
                    "score": 50,
                    "grade": "C",
                    "insights": ["Insufficient data to assess individual capital"],
                    "red_flags": []
                },
                "relational": {
                    "score": 50,
                    "grade": "C",
                    "insights": ["Insufficient data to assess relational capital"],
                    "red_flags": []
                },
                "organizational": {
                    "score": 50,
                    "grade": "C",
                    "insights": ["Insufficient data to assess organizational capital"],
                    "red_flags": []
                },
                "reputational": {
                    "score": 50,
                    "grade": "C",
                    "insights": ["Insufficient data to assess reputational capital"],
                    "red_flags": []
                }
            },
            "key_metrics": {},
            "red_flags": [],
            "executive_summary": f"Insufficient research data available to assess {company_name} leadership using the Four Capitals Framework.",
            "data_source": "tavily",
            "research_queries": [],
            "article_count": 0
        }
