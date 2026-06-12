"""cquant.ai_advisor.chart_generator -- Generate chart specs for the AI advisor frontend.

Produces lightweight JSON chart specifications that the frontend renders with Recharts.
Supported chart types: metric_cards, line, bar, pie.

Chart specs are embedded in agent output as ``[CHART:type:json_payload]`` markers
which the AdvisorPage frontend parses and renders inline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChartSpec:
    """A single chart specification."""

    chart_type: str  # "metric_cards" | "line" | "bar" | "pie"
    title: str
    data: list[dict[str, Any]]
    config: dict[str, Any] = field(default_factory=dict)

    def to_marker(self) -> str:
        """Serialize to ``[CHART:type:json]`` marker string for embedding in agent text."""
        payload = {
            "chart_type": self.chart_type,
            "title": self.title,
            "data": self.data,
            "config": self.config,
        }
        return f"[CHART:{self.chart_type}:{json.dumps(payload, ensure_ascii=False)}]"


class ChartGenerator:
    """Factory for common financial chart specifications.

    Usage::

        gen = ChartGenerator()
        marker = gen.metric_cards([{"label": "Sharpe", "value": 1.23}])
        # Embed marker.to_marker() in agent response text.
    """

    # ------------------------------------------------------------------
    # Metric cards (KPI tiles)
    # ------------------------------------------------------------------

    def metric_cards(
        self,
        cards: list[dict[str, Any]],
        title: str = "Key Metrics",
    ) -> ChartSpec:
        """Generate a metric-cards chart.

        Each card: ``{"label": str, "value": str|number, "delta"?: str|number, "color"?: str}``
        """
        return ChartSpec(
            chart_type="metric_cards",
            title=title,
            data=cards,
        )

    # ------------------------------------------------------------------
    # Line chart
    # ------------------------------------------------------------------

    def line(
        self,
        data: list[dict[str, Any]],
        x_key: str = "date",
        y_keys: list[str] | None = None,
        title: str = "Line Chart",
    ) -> ChartSpec:
        """Generate a line chart spec.

        Each data point: ``{"date": "2025-01-01", "series_a": 100, "series_b": 95, ...}``
        """
        config = {"x_key": x_key, "y_keys": y_keys or []}
        return ChartSpec(chart_type="line", title=title, data=data, config=config)

    # ------------------------------------------------------------------
    # Bar chart
    # ------------------------------------------------------------------

    def bar(
        self,
        data: list[dict[str, Any]],
        x_key: str = "category",
        y_key: str = "value",
        title: str = "Bar Chart",
    ) -> ChartSpec:
        """Generate a bar chart spec.

        Each data point: ``{"category": "SMA", "value": 0.15, ...}``
        """
        config = {"x_key": x_key, "y_key": y_key}
        return ChartSpec(chart_type="bar", title=title, data=data, config=config)

    # ------------------------------------------------------------------
    # Pie chart
    # ------------------------------------------------------------------

    def pie(
        self,
        data: list[dict[str, Any]],
        name_key: str = "name",
        value_key: str = "value",
        title: str = "Distribution",
    ) -> ChartSpec:
        """Generate a pie chart spec.

        Each slice: ``{"name": "Tech", "value": 35, ...}``
        """
        config = {"name_key": name_key, "value_key": value_key}
        return ChartSpec(chart_type="pie", title=title, data=data, config=config)

    # ------------------------------------------------------------------
    # Convenience: parse markers from text
    # ------------------------------------------------------------------

    @staticmethod
    def parse_markers(text: str) -> list[dict[str, Any]]:
        """Extract all ``[CHART:type:json]`` markers from agent text.

        Uses bracket-depth tracking to correctly handle JSON payloads containing
        nested ``[]`` characters.
        """
        import re
        results = []
        prefix = "[CHART:"
        idx = 0
        while True:
            start = text.find(prefix, idx)
            if start == -1:
                break
            # Skip past "[CHART:"
            colon1 = text.find(":", start + len(prefix))
            if colon1 == -1:
                break
            chart_type = text[start + len(prefix):colon1].strip()
            if not re.match(r"^\w+$", chart_type):
                idx = colon1 + 1
                continue
            # Track bracket depth from the JSON payload start
            payload_start = colon1 + 1
            depth = 0
            end = -1
            for i in range(payload_start, len(text)):
                ch = text[i]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                elif ch == "]" and depth <= 0:
                    end = i
                    break
            if end == -1:
                break
            json_str = text[payload_start:end]
            try:
                payload = json.loads(json_str)
            except json.JSONDecodeError:
                idx = end + 1
                continue
            results.append(payload)
            idx = end + 1
        return results
