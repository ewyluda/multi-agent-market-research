"""PDF report generator for analysis exports."""

import io
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
    KeepTogether,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """Generates branded PDF reports from analysis data."""

    # Color palette matching the frontend dark theme (adapted for print)
    COLORS = {
        "primary": HexColor("#006fee"),
        "success": HexColor("#17c964"),
        "danger": HexColor("#f31260"),
        "warning": HexColor("#f5a524"),
        "dark_bg": HexColor("#18181b"),
        "dark_card": HexColor("#27272a"),
        "text_primary": HexColor("#1a1a1a"),
        "text_secondary": HexColor("#4a4a4a"),
        "text_muted": HexColor("#71717a"),
        "white": HexColor("#ffffff"),
        "black": HexColor("#000000"),
        "light_gray": HexColor("#f4f4f5"),
        "border_gray": HexColor("#d4d4d8"),
        "table_header_bg": HexColor("#27272a"),
        "table_alt_row": HexColor("#f9fafb"),
    }

    # Preferred agent order for display
    AGENT_ORDER = ["market", "technical", "options", "fundamentals", "sentiment", "macro", "news"]

    # Agent display names
    AGENT_DISPLAY_NAMES = {
        "market": "Market Data",
        "technical": "Technical Analysis",
        "options": "Options Flow",
        "fundamentals": "Fundamentals",
        "sentiment": "Sentiment Analysis",
        "macro": "Macroeconomic",
        "news": "News",
    }

    def __init__(self):
        """Initialize the PDF report generator with custom styles."""
        self._styles = getSampleStyleSheet()
        self._register_custom_styles()

    def _register_custom_styles(self):
        """Register custom paragraph styles for the report."""
        self._styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=self._styles["Title"],
            fontSize=22,
            leading=28,
            textColor=self.COLORS["dark_bg"],
            spaceAfter=4,
            alignment=TA_LEFT,
        ))

        self._styles.add(ParagraphStyle(
            name="ReportSubtitle",
            parent=self._styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=self.COLORS["text_muted"],
            spaceAfter=12,
        ))

        self._styles.add(ParagraphStyle(
            name="SectionHeading",
            parent=self._styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=self.COLORS["primary"],
            spaceBefore=16,
            spaceAfter=8,
            borderWidth=0,
        ))

        self._styles.add(ParagraphStyle(
            name="SubSectionHeading",
            parent=self._styles["Heading3"],
            fontSize=11,
            leading=14,
            textColor=self.COLORS["dark_bg"],
            spaceBefore=10,
            spaceAfter=4,
        ))

        self._styles.add(ParagraphStyle(
            name="ReportBody",
            parent=self._styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=self.COLORS["text_primary"],
            spaceAfter=6,
        ))

        self._styles.add(ParagraphStyle(
            name="SmallText",
            parent=self._styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=self.COLORS["text_muted"],
        ))

        self._styles.add(ParagraphStyle(
            name="FooterText",
            parent=self._styles["Normal"],
            fontSize=7,
            leading=9,
            textColor=self.COLORS["text_muted"],
            alignment=TA_CENTER,
        ))

        self._styles.add(ParagraphStyle(
            name="BadgeText",
            parent=self._styles["Normal"],
            fontSize=12,
            leading=16,
            textColor=self.COLORS["white"],
            alignment=TA_CENTER,
        ))

        self._styles.add(ParagraphStyle(
            name="MetricValue",
            parent=self._styles["Normal"],
            fontSize=18,
            leading=22,
            textColor=self.COLORS["dark_bg"],
            alignment=TA_CENTER,
        ))

        self._styles.add(ParagraphStyle(
            name="MetricLabel",
            parent=self._styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=self.COLORS["text_muted"],
            alignment=TA_CENTER,
        ))

        self._styles.add(ParagraphStyle(
            name="AgentHeader",
            parent=self._styles["Heading3"],
            fontSize=11,
            leading=14,
            textColor=self.COLORS["dark_bg"],
            spaceBefore=8,
            spaceAfter=4,
        ))

        self._styles.add(ParagraphStyle(
            name="ReasoningText",
            parent=self._styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=self.COLORS["text_primary"],
            spaceAfter=4,
            leftIndent=0,
        ))

        self._styles.add(ParagraphStyle(
            name="BulletItem",
            parent=self._styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=self.COLORS["text_primary"],
            leftIndent=16,
            bulletIndent=4,
            spaceAfter=2,
        ))

    def generate(self, analysis_data: Dict[str, Any]) -> bytes:
        """
        Generate a PDF report from analysis data. Returns PDF as bytes.

        Args:
            analysis_data: Complete analysis data from db_manager.get_analysis_with_agents()

        Returns:
            PDF file contents as bytes
        """
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.6 * inch,
            bottomMargin=0.8 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            title=self._build_title(analysis_data),
            author="AI Trading Analyst",
        )

        # Build the story (list of flowables)
        story = []

        # Page 1: Executive Summary
        story.extend(self._build_header(analysis_data))
        story.extend(self._build_recommendation_badge(analysis_data))
        story.extend(self._build_metrics_table(analysis_data))
        story.extend(self._build_executive_summary(analysis_data))
        story.extend(self._build_price_targets(analysis_data))
        story.extend(self._build_risks_opportunities(analysis_data))

        # Page 2: Agent Details
        story.append(PageBreak())
        story.extend(self._build_agent_details(analysis_data))

        # Page 3 (if needed): Full Reasoning
        reasoning = self._safe_get(analysis_data, "solution_agent_reasoning", "")
        if reasoning and len(reasoning) > 200:
            story.append(PageBreak())
            story.extend(self._build_full_reasoning(analysis_data))

        # Sentiment factors (if present)
        sentiment_factors = analysis_data.get("sentiment_factors") or {}
        if sentiment_factors:
            story.extend(self._build_sentiment_factors(sentiment_factors))

        # Build PDF with footer
        timestamp = self._parse_timestamp(analysis_data.get("timestamp"))
        footer_text = f"Generated by AI Trading Analyst  |  {timestamp}"

        doc.build(
            story,
            onFirstPage=lambda canvas, doc: self._draw_footer(canvas, doc, footer_text),
            onLaterPages=lambda canvas, doc: self._draw_footer(canvas, doc, footer_text),
        )

        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    # ─── Page Building Helpers ───────────────────────────────────────────

    def _build_title(self, data: Dict[str, Any]) -> str:
        """Build the document title string."""
        ticker = self._safe_get(data, "ticker", "UNKNOWN")
        return f"AI Trading Analyst - {ticker} Analysis Report"

    def _build_header(self, data: Dict[str, Any]) -> List:
        """Build the report header with title and date."""
        elements = []
        ticker = self._safe_get(data, "ticker", "UNKNOWN")
        timestamp = self._parse_timestamp(data.get("timestamp"))

        elements.append(Paragraph(
            f"AI Trading Analyst &mdash; {self._escape(ticker)} Analysis Report",
            self._styles["ReportTitle"],
        ))
        elements.append(Paragraph(
            f"Report generated: {timestamp}",
            self._styles["ReportSubtitle"],
        ))
        elements.append(HRFlowable(
            width="100%",
            thickness=1.5,
            color=self.COLORS["primary"],
            spaceAfter=12,
        ))
        return elements

    def _build_recommendation_badge(self, data: Dict[str, Any]) -> List:
        """Build the recommendation badge with score and confidence."""
        elements = []
        recommendation = self._safe_get(data, "recommendation", "N/A")
        confidence = data.get("confidence_score")
        sentiment = data.get("overall_sentiment_score")

        badge_color = self._recommendation_color(recommendation)

        # Recommendation badge as a colored table cell
        badge_data = [[
            Paragraph(
                f"<b>{self._escape(recommendation)}</b>",
                self._styles["BadgeText"],
            )
        ]]
        badge_table = Table(badge_data, colWidths=[1.8 * inch], rowHeights=[0.45 * inch])
        badge_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), badge_color),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ]))

        # Confidence and sentiment as side metrics
        conf_text = f"{confidence:.0%}" if confidence is not None else "N/A"
        sent_text = f"{sentiment:+.2f}" if sentiment is not None else "N/A"

        info_data = [[
            badge_table,
            Paragraph(f"<b>{conf_text}</b>", self._styles["MetricValue"]),
            Paragraph(f"<b>{sent_text}</b>", self._styles["MetricValue"]),
        ], [
            Paragraph("", self._styles["MetricLabel"]),
            Paragraph("Confidence", self._styles["MetricLabel"]),
            Paragraph("Sentiment Score", self._styles["MetricLabel"]),
        ]]

        info_table = Table(info_data, colWidths=[2.2 * inch, 2.2 * inch, 2.6 * inch])
        info_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        elements.append(info_table)
        elements.append(Spacer(1, 8))
        return elements

    def _build_metrics_table(self, data: Dict[str, Any]) -> List:
        """Build the at-a-glance metrics table."""
        elements = []
        elements.append(Paragraph("At a Glance", self._styles["SectionHeading"]))

        duration = data.get("duration_seconds")
        duration_str = f"{duration:.1f}s" if duration is not None else "N/A"
        analysis_id = data.get("id")
        id_str = str(analysis_id) if analysis_id is not None else "N/A"
        ticker = self._safe_get(data, "ticker", "N/A")

        # Extract agent count
        agents = data.get("agents") or []
        successful_agents = sum(1 for a in agents if a.get("success"))
        total_agents = len(agents)
        agents_str = f"{successful_agents}/{total_agents}"

        # Extract data sources
        sources = set()
        for agent in agents:
            agent_data = agent.get("data") or {}
            src = agent_data.get("data_source")
            if src:
                sources.add(src)
        sources_str = ", ".join(sorted(sources)) if sources else "N/A"

        metrics = [
            ["Ticker", "Analysis ID", "Duration", "Agents Succeeded", "Data Sources"],
            [ticker, id_str, duration_str, agents_str, sources_str],
        ]

        table = Table(metrics, colWidths=[1.2 * inch, 1.2 * inch, 1.2 * inch, 1.4 * inch, 2.0 * inch])
        table.setStyle(TableStyle([
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), self.COLORS["table_header_bg"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.COLORS["white"]),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            # Data row
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TEXTCOLOR", (0, 1), (-1, -1), self.COLORS["text_primary"]),
            # General
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, self.COLORS["border_gray"]),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 8))
        return elements

    def _build_executive_summary(self, data: Dict[str, Any]) -> List:
        """Build executive summary from the solution agent reasoning."""
        elements = []
        reasoning = self._safe_get(data, "solution_agent_reasoning", "")

        if not reasoning:
            return elements

        elements.append(Paragraph("Executive Summary", self._styles["SectionHeading"]))

        # Extract first paragraph or first few sentences as executive summary
        summary_text = self._extract_executive_summary(reasoning)
        if summary_text:
            elements.append(Paragraph(
                self._escape(summary_text),
                self._styles["ReportBody"],
            ))

        elements.append(Spacer(1, 4))
        return elements

    def _build_price_targets(self, data: Dict[str, Any]) -> List:
        """Build price targets table if available from agent data."""
        elements = []

        # Try to extract price targets from agents
        targets = self._extract_price_targets(data)
        if not targets:
            return elements

        elements.append(Paragraph("Price Targets", self._styles["SectionHeading"]))

        headers = ["Entry Price", "Target Price", "Stop Loss"]
        values = [
            self._format_price(targets.get("entry")),
            self._format_price(targets.get("target")),
            self._format_price(targets.get("stop_loss")),
        ]

        # Only show if at least one target is available
        if all(v == "N/A" for v in values):
            return elements

        table_data = [headers, values]
        table = Table(table_data, colWidths=[2.33 * inch, 2.33 * inch, 2.34 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.COLORS["table_header_bg"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.COLORS["white"]),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("TEXTCOLOR", (0, 1), (-1, -1), self.COLORS["text_primary"]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, self.COLORS["border_gray"]),
            # Accent colors for the values
            ("TEXTCOLOR", (0, 1), (0, 1), self.COLORS["primary"]),
            ("TEXTCOLOR", (1, 1), (1, 1), self.COLORS["success"]),
            ("TEXTCOLOR", (2, 1), (2, 1), self.COLORS["danger"]),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 8))
        return elements

    def _build_risks_opportunities(self, data: Dict[str, Any]) -> List:
        """Build risks and opportunities columns."""
        elements = []

        risks = self._extract_list_from_reasoning(data, "risks")
        opportunities = self._extract_list_from_reasoning(data, "opportunities")

        if not risks and not opportunities:
            return elements

        elements.append(Paragraph("Risks &amp; Opportunities", self._styles["SectionHeading"]))

        # Build two-column layout
        left_items = []
        right_items = []

        left_items.append(Paragraph(
            "<b>Risks</b>",
            ParagraphStyle("RiskHeader", parent=self._styles["SubSectionHeading"], textColor=self.COLORS["danger"]),
        ))
        for risk in risks[:5]:
            left_items.append(Paragraph(
                f"&bull; {self._escape(risk)}",
                self._styles["BulletItem"],
            ))

        right_items.append(Paragraph(
            "<b>Opportunities</b>",
            ParagraphStyle("OppHeader", parent=self._styles["SubSectionHeading"], textColor=self.COLORS["success"]),
        ))
        for opp in opportunities[:5]:
            right_items.append(Paragraph(
                f"&bull; {self._escape(opp)}",
                self._styles["BulletItem"],
            ))

        # Pad the shorter column
        max_rows = max(len(left_items), len(right_items))
        while len(left_items) < max_rows:
            left_items.append(Paragraph("", self._styles["SmallText"]))
        while len(right_items) < max_rows:
            right_items.append(Paragraph("", self._styles["SmallText"]))

        table_data = list(zip(left_items, right_items))
        table = Table(table_data, colWidths=[3.5 * inch, 3.5 * inch])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("LEFTPADDING", (1, 0), (1, -1), 12),
            ("LINEAFTER", (0, 0), (0, -1), 0.5, self.COLORS["border_gray"]),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 8))
        return elements

    def _build_agent_details(self, data: Dict[str, Any]) -> List:
        """Build agent analysis detail sections."""
        elements = []
        elements.append(Paragraph("Agent Analysis Details", self._styles["ReportTitle"]))
        elements.append(HRFlowable(
            width="100%",
            thickness=1.5,
            color=self.COLORS["primary"],
            spaceAfter=12,
        ))

        agents = data.get("agents") or []
        agents_by_type = {a.get("agent_type", ""): a for a in agents}

        for agent_type in self.AGENT_ORDER:
            agent = agents_by_type.get(agent_type)
            if agent is None:
                continue

            section = self._build_single_agent_section(agent)
            elements.extend(section)

        # Any agents not in the preferred order
        for agent in agents:
            agent_type = agent.get("agent_type", "")
            if agent_type not in self.AGENT_ORDER:
                section = self._build_single_agent_section(agent)
                elements.extend(section)

        return elements

    def _build_single_agent_section(self, agent: Dict[str, Any]) -> List:
        """Build a single agent's detail section."""
        elements = []
        agent_type = agent.get("agent_type", "unknown")
        display_name = self.AGENT_DISPLAY_NAMES.get(agent_type, agent_type.title())
        success = agent.get("success", False)
        duration = agent.get("duration_seconds")
        error = agent.get("error")
        agent_data = agent.get("data") or {}
        data_source = agent_data.get("data_source", "")

        # Status indicator
        status_color = self.COLORS["success"] if success else self.COLORS["danger"]
        status_text = "OK" if success else "FAILED"

        # Build header row: name | status | data source | duration
        header_parts = [f"<b>{self._escape(display_name)}</b>"]

        meta_parts = []
        meta_parts.append(f'<font color="{self._color_hex(status_color)}">[{status_text}]</font>')
        if data_source:
            source_label = data_source.replace("_", " ").title()
            meta_parts.append(f'<font color="{self._color_hex(self.COLORS["primary"])}">{self._escape(source_label)}</font>')
        if duration is not None:
            meta_parts.append(f"{duration:.1f}s")

        header_line = f"{header_parts[0]}  &nbsp;&nbsp;{'&nbsp;&nbsp;|&nbsp;&nbsp;'.join(meta_parts)}"

        agent_section = []
        agent_section.append(Paragraph(header_line, self._styles["AgentHeader"]))

        # Divider line
        agent_section.append(HRFlowable(
            width="100%",
            thickness=0.5,
            color=self.COLORS["border_gray"],
            spaceAfter=4,
        ))

        # Error message
        if error:
            agent_section.append(Paragraph(
                f'<font color="{self._color_hex(self.COLORS["danger"])}">Error: {self._escape(str(error))}</font>',
                self._styles["ReportBody"],
            ))

        # Summary text
        summary = agent_data.get("summary", "")
        if summary:
            # Truncate very long summaries for the detail page
            if len(summary) > 800:
                summary = summary[:797] + "..."
            agent_section.append(Paragraph(
                self._escape(summary),
                self._styles["ReportBody"],
            ))

        # Add key metrics specific to each agent type
        key_metrics = self._extract_agent_key_metrics(agent_type, agent_data)
        if key_metrics:
            metrics_table = self._build_key_metrics_mini_table(key_metrics)
            agent_section.append(metrics_table)

        agent_section.append(Spacer(1, 8))

        elements.append(KeepTogether(agent_section))
        return elements

    def _build_key_metrics_mini_table(self, metrics: List[Tuple[str, str]]) -> Table:
        """Build a small key-value metrics table for an agent section."""
        table_data = [[
            Paragraph(f"<b>{self._escape(label)}</b>", self._styles["SmallText"]),
            Paragraph(self._escape(str(value)), self._styles["SmallText"]),
        ] for label, value in metrics]

        col_widths = [2.0 * inch, 5.0 * inch]
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (0, -1), 4),
            ("BACKGROUND", (0, 0), (-1, -1), self.COLORS["light_gray"]),
            ("GRID", (0, 0), (-1, -1), 0.25, self.COLORS["border_gray"]),
        ]))
        return table

    def _extract_agent_key_metrics(self, agent_type: str, agent_data: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Extract key metrics for display based on agent type."""
        metrics = []

        if agent_type == "market":
            price = agent_data.get("current_price")
            if price is not None:
                metrics.append(("Current Price", self._format_price(price)))
            trend = agent_data.get("trend")
            if trend:
                metrics.append(("Trend", str(trend)))
            support = agent_data.get("support_level")
            if support is not None:
                metrics.append(("Support", self._format_price(support)))
            resistance = agent_data.get("resistance_level")
            if resistance is not None:
                metrics.append(("Resistance", self._format_price(resistance)))

        elif agent_type == "technical":
            indicators = agent_data.get("indicators") or {}
            rsi = indicators.get("rsi") or {}
            rsi_val = rsi.get("value")
            rsi_interp = rsi.get("interpretation", "")
            if rsi_val is not None:
                metrics.append(("RSI", f"{rsi_val} ({rsi_interp})"))
            macd = indicators.get("macd") or {}
            macd_interp = macd.get("interpretation")
            if macd_interp:
                metrics.append(("MACD", str(macd_interp)))
            signals = agent_data.get("signals") or {}
            overall = signals.get("overall")
            strength = signals.get("strength")
            if overall:
                sig_str = str(overall)
                if strength is not None:
                    sig_str += f" (strength: {strength})"
                metrics.append(("Overall Signal", sig_str))

        elif agent_type == "options":
            pcr = agent_data.get("put_call_ratio")
            if pcr is not None:
                metrics.append(("Put/Call Ratio", f"{pcr:.2f}" if isinstance(pcr, (int, float)) else str(pcr)))
            max_pain = agent_data.get("max_pain")
            if max_pain is not None:
                metrics.append(("Max Pain", self._format_price(max_pain)))
            signal = agent_data.get("overall_signal")
            if signal:
                metrics.append(("Options Signal", str(signal)))

        elif agent_type == "fundamentals":
            company = agent_data.get("company_name")
            if company:
                metrics.append(("Company", str(company)))
            health = agent_data.get("health_score")
            if health is not None:
                metrics.append(("Health Score", f"{health}/100"))
            pe = agent_data.get("pe_ratio")
            if pe is not None:
                metrics.append(("P/E Ratio", f"{pe:.1f}" if isinstance(pe, (int, float)) else str(pe)))

        elif agent_type == "sentiment":
            overall = agent_data.get("overall_sentiment")
            if overall is not None:
                metrics.append(("Overall Sentiment", f"{overall:+.2f}" if isinstance(overall, (int, float)) else str(overall)))
            conf = agent_data.get("confidence")
            if conf is not None:
                metrics.append(("Confidence", f"{conf:.0%}" if isinstance(conf, (int, float)) else str(conf)))
            themes = agent_data.get("key_themes") or []
            if themes:
                themes_str = ", ".join(str(t) for t in themes[:4])
                metrics.append(("Key Themes", themes_str))

        elif agent_type == "macro":
            cycle = agent_data.get("economic_cycle")
            if cycle:
                metrics.append(("Economic Cycle", str(cycle)))
            risk_env = agent_data.get("risk_environment")
            if risk_env:
                metrics.append(("Risk Environment", str(risk_env)))

        elif agent_type == "news":
            total = agent_data.get("total_count")
            if total is not None:
                metrics.append(("Total Articles", str(total)))
            headlines = agent_data.get("key_headlines") or []
            if headlines:
                top_headline = headlines[0].get("title", "") if isinstance(headlines[0], dict) else str(headlines[0])
                if top_headline:
                    if len(top_headline) > 100:
                        top_headline = top_headline[:97] + "..."
                    metrics.append(("Top Headline", top_headline))

        return metrics

    def _build_full_reasoning(self, data: Dict[str, Any]) -> List:
        """Build the full reasoning section."""
        elements = []
        elements.append(Paragraph("Full Analysis Reasoning", self._styles["ReportTitle"]))
        elements.append(HRFlowable(
            width="100%",
            thickness=1.5,
            color=self.COLORS["primary"],
            spaceAfter=12,
        ))

        reasoning = self._safe_get(data, "solution_agent_reasoning", "")
        if not reasoning:
            elements.append(Paragraph("No reasoning available.", self._styles["ReportBody"]))
            return elements

        # Split reasoning into paragraphs and render each
        paragraphs = reasoning.split("\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                elements.append(Spacer(1, 4))
                continue

            # Detect numbered steps (e.g., "1. Fundamentals...")
            step_match = re.match(r'^(\d{1,2})\.\s+(.*)', para)
            if step_match:
                step_num = step_match.group(1)
                step_text = step_match.group(2)
                elements.append(Paragraph(
                    f'<b><font color="{self._color_hex(self.COLORS["primary"])}">{step_num}.</font></b> {self._escape(step_text)}',
                    self._styles["ReasoningText"],
                ))
            else:
                elements.append(Paragraph(
                    self._escape(para),
                    self._styles["ReasoningText"],
                ))

        return elements

    def _build_sentiment_factors(self, sentiment_factors: Dict[str, Any]) -> List:
        """Build sentiment factors breakdown table."""
        elements = []

        if not sentiment_factors:
            return elements

        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Sentiment Factor Breakdown", self._styles["SectionHeading"]))

        headers = ["Factor", "Score", "Weight", "Contribution"]
        rows = [headers]

        for factor, vals in sentiment_factors.items():
            if not isinstance(vals, dict):
                continue
            score = vals.get("score")
            weight = vals.get("weight")
            contribution = vals.get("contribution")
            rows.append([
                factor.replace("_", " ").title(),
                f"{score:+.2f}" if score is not None else "N/A",
                f"{weight:.0%}" if weight is not None else "N/A",
                f"{contribution:+.3f}" if contribution is not None else "N/A",
            ])

        if len(rows) < 2:
            return elements

        table = Table(rows, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.COLORS["table_header_bg"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.COLORS["white"]),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TEXTCOLOR", (0, 1), (-1, -1), self.COLORS["text_primary"]),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, self.COLORS["border_gray"]),
            # Alternate row coloring
            *[("BACKGROUND", (0, i), (-1, i), self.COLORS["table_alt_row"])
              for i in range(2, len(rows), 2)],
        ]))

        elements.append(table)
        return elements

    # ─── Footer Drawing ──────────────────────────────────────────────────

    def _draw_footer(self, canvas, doc, footer_text: str):
        """Draw footer on each page."""
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(self.COLORS["text_muted"])

        page_num = canvas.getPageNumber()
        page_text = f"Page {page_num}"

        # Footer line
        y_pos = 0.5 * inch
        canvas.setStrokeColor(self.COLORS["border_gray"])
        canvas.setLineWidth(0.5)
        canvas.line(
            doc.leftMargin,
            y_pos + 10,
            letter[0] - doc.rightMargin,
            y_pos + 10,
        )

        # Left: footer text
        canvas.drawString(doc.leftMargin, y_pos, footer_text)

        # Right: page number
        canvas.drawRightString(letter[0] - doc.rightMargin, y_pos, page_text)

        # Disclaimer
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(self.COLORS["text_muted"])
        disclaimer = "This report is AI-generated and for informational purposes only. Not financial advice."
        canvas.drawCentredString(letter[0] / 2, y_pos - 12, disclaimer)

        canvas.restoreState()

    # ─── Data Extraction Helpers ─────────────────────────────────────────

    def _extract_executive_summary(self, reasoning: str) -> str:
        """Extract a concise executive summary from the full reasoning text."""
        if not reasoning:
            return ""

        # Try to get the first meaningful paragraph
        paragraphs = [p.strip() for p in reasoning.split("\n") if p.strip()]

        if not paragraphs:
            return ""

        # If reasoning starts with numbered steps, take the first 2-3 sentences
        # Otherwise take the first paragraph
        first_para = paragraphs[0]

        # For numbered reasoning (1. 2. 3.), collect a brief overview
        if re.match(r'^1\.', first_para):
            summary_parts = []
            for p in paragraphs:
                if re.match(r'^\d{1,2}\.', p):
                    # Take first sentence of each numbered point
                    sentence = p.split(". ", 1)[-1] if ". " in p else p
                    first_sentence = sentence.split(". ")[0]
                    summary_parts.append(first_sentence.strip())
                    if len(summary_parts) >= 3:
                        break
            return ". ".join(summary_parts) + "." if summary_parts else first_para[:500]

        # Take first paragraph, cap at ~500 chars
        sentences = re.split(r'(?<=[.!?])\s+', first_para)
        summary = ""
        for sentence in sentences:
            if len(summary) + len(sentence) > 500:
                break
            summary += sentence + " "

        return summary.strip() if summary.strip() else first_para[:500]

    def _extract_price_targets(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract price targets from agent data."""
        # Look in market agent for support/resistance as proxy targets
        agents = data.get("agents") or []
        agents_by_type = {a.get("agent_type", ""): a for a in agents}

        targets = {}

        # Try market agent for entry context
        market_agent = agents_by_type.get("market")
        if market_agent:
            market_data = market_agent.get("data") or {}
            current_price = market_data.get("current_price")
            support = market_data.get("support_level")
            resistance = market_data.get("resistance_level")

            if current_price is not None:
                targets["entry"] = current_price
            if resistance is not None:
                targets["target"] = resistance
            if support is not None:
                targets["stop_loss"] = support

        # Try to parse from reasoning text (LLM sometimes includes them)
        reasoning = self._safe_get(data, "solution_agent_reasoning", "")
        if reasoning:
            # Look for price target patterns like "entry: $150" or "target price: 175"
            entry_match = re.search(r'entry[:\s]*\$?([\d,.]+)', reasoning, re.IGNORECASE)
            target_match = re.search(r'(?:price\s+)?target[:\s]*\$?([\d,.]+)', reasoning, re.IGNORECASE)
            stop_match = re.search(r'stop[_\s-]*loss[:\s]*\$?([\d,.]+)', reasoning, re.IGNORECASE)

            if entry_match and "entry" not in targets:
                try:
                    targets["entry"] = float(entry_match.group(1).replace(",", ""))
                except ValueError:
                    pass
            if target_match and "target" not in targets:
                try:
                    targets["target"] = float(target_match.group(1).replace(",", ""))
                except ValueError:
                    pass
            if stop_match and "stop_loss" not in targets:
                try:
                    targets["stop_loss"] = float(stop_match.group(1).replace(",", ""))
                except ValueError:
                    pass

        return targets if targets else None

    def _extract_list_from_reasoning(self, data: Dict[str, Any], list_type: str) -> List[str]:
        """
        Extract risks or opportunities from the reasoning text.

        Args:
            data: Analysis data
            list_type: Either "risks" or "opportunities"

        Returns:
            List of extracted items
        """
        reasoning = self._safe_get(data, "solution_agent_reasoning", "")
        if not reasoning:
            return []

        items = []

        # Look for sections labeled with the list type
        pattern = rf'{list_type}[:\s]*\n?((?:[\-\*\d]+\.?\s+.+\n?)+)'
        match = re.search(pattern, reasoning, re.IGNORECASE)
        if match:
            block = match.group(1)
            for line in block.split("\n"):
                line = line.strip()
                # Strip bullet markers
                line = re.sub(r'^[\-\*\d]+\.?\s*', '', line).strip()
                if line and len(line) > 3:
                    items.append(line)

        # Also try to find JSON-style lists in reasoning
        if not items:
            json_pattern = rf'"{list_type}":\s*\[(.*?)\]'
            match = re.search(json_pattern, reasoning, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    import json
                    raw = "[" + match.group(1) + "]"
                    parsed = json.loads(raw)
                    items = [str(item) for item in parsed if item]
                except (json.JSONDecodeError, ValueError):
                    pass

        # Look in agent data for structured risks/opps (from LLM output saved in DB)
        if not items:
            agents = data.get("agents") or []
            for agent in agents:
                agent_data = agent.get("data") or {}
                found = agent_data.get(list_type) or []
                if isinstance(found, list) and found:
                    items = [str(item) for item in found[:5]]
                    break

        return items[:5]

    # ─── Formatting Helpers ──────────────────────────────────────────────

    def _safe_get(self, data: Dict[str, Any], key: str, default: Any = "") -> Any:
        """Safely get a value from a dict, returning default if None or missing."""
        if data is None:
            return default
        value = data.get(key)
        return value if value is not None else default

    def _escape(self, text: str) -> str:
        """Escape text for ReportLab XML paragraphs."""
        if not text:
            return ""
        text = str(text)
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        return text

    def _parse_timestamp(self, timestamp: Any) -> str:
        """Parse a timestamp into a human-readable format."""
        if not timestamp:
            return datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

        if isinstance(timestamp, datetime):
            return timestamp.strftime("%B %d, %Y at %H:%M UTC")

        try:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            return dt.strftime("%B %d, %Y at %H:%M UTC")
        except (ValueError, TypeError):
            return str(timestamp)

    def _format_price(self, value: Any) -> str:
        """Format a price value."""
        if value is None:
            return "N/A"
        try:
            return f"${float(value):,.2f}"
        except (ValueError, TypeError):
            return str(value)

    def _recommendation_color(self, recommendation: str) -> Color:
        """Get the color for a recommendation badge."""
        rec = (recommendation or "").upper()
        if rec == "BUY":
            return self.COLORS["success"]
        elif rec == "SELL":
            return self.COLORS["danger"]
        elif rec == "HOLD":
            return self.COLORS["warning"]
        return self.COLORS["text_muted"]

    def _color_hex(self, color: Color) -> str:
        """Convert a ReportLab Color to a hex string for use in Paragraph markup."""
        if hasattr(color, "hexval"):
            return color.hexval()
        r = int(color.red * 255)
        g = int(color.green * 255)
        b = int(color.blue * 255)
        return f"#{r:02x}{g:02x}{b:02x}"
