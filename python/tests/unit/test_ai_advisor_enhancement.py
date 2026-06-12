"""Tests for AI Advisor enhancement: OllamaProvider, IntentRouter LLM fallback, ChartGenerator."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── OllamaProvider ───────────────────────────────────────────────────────────


class TestOllamaProvider:
    """Tests for OllamaProvider (httpx-based, no real server needed)."""

    def test_init_defaults(self):
        from cquant.ai_advisor.providers.ollama import OllamaProvider

        p = OllamaProvider()
        assert p.model == "qwen2.5:14b"
        assert p.base_url == "http://localhost:11434"
        assert p.name == "ollama"

    def test_init_custom(self):
        from cquant.ai_advisor.providers.ollama import OllamaProvider

        p = OllamaProvider(model="llama3:8b", base_url="http://remote:9999")
        assert p.model == "llama3:8b"
        assert p.base_url == "http://remote:9999"

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_unreachable(self):
        from cquant.ai_advisor.providers.ollama import OllamaProvider

        p = OllamaProvider()
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get.side_effect = Exception("connection refused")
            MockClient.return_value.__aenter__ = AsyncMock(return_value=instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await p.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_generate_returns_unavailable_when_server_down(self):
        from cquant.ai_advisor.providers.ollama import OllamaProvider
        from cquant.ai_advisor.providers.base import Message

        p = OllamaProvider()
        with patch.object(p, "is_available", return_value=False):
            resp = await p.generate([Message(role="user", content="hello")])
            assert resp.stop_reason == "unavailable"
            assert "not reachable" in resp.content or "not loaded" in resp.content

    @pytest.mark.asyncio
    async def test_chat_error_dict(self):
        from cquant.ai_advisor.providers.ollama import OllamaProvider

        p = OllamaProvider()
        with patch("httpx.AsyncClient") as MockClient:
            instance = MagicMock()
            resp_mock = MagicMock()
            resp_mock.status_code = 500
            resp_mock.text = "Internal Server Error"

            import httpx
            resp_mock.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=resp_mock
            )
            instance.post = AsyncMock(return_value=resp_mock)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await p.chat([{"role": "user", "content": "test"}])
            assert "error" in result


# ── IntentRouter ─────────────────────────────────────────────────────────────


class TestIntentRouter:
    """Tests for keyword-based and LLM-fallback routing."""

    def test_keyword_match_risk(self):
        from cquant.ai_advisor.router import IntentRouter

        router = IntentRouter()
        result = router.classify("What is my portfolio drawdown risk?")
        assert "risk" in result.required_roles

    def test_keyword_match_execution(self):
        from cquant.ai_advisor.router import IntentRouter

        router = IntentRouter()
        result = router.classify("Check the backtest run status")
        assert "execution" in result.required_roles

    def test_keyword_match_research(self):
        from cquant.ai_advisor.router import IntentRouter

        router = IntentRouter()
        result = router.classify("Run ML prediction on this model")
        assert "research" in result.required_roles

    def test_keyword_match_multiple_roles(self):
        from cquant.ai_advisor.router import IntentRouter

        router = IntentRouter()
        result = router.classify("Run backtest run and check risk exposure and drawdown")
        assert "risk" in result.required_roles
        assert "execution" in result.required_roles

    def test_keyword_match_chinese(self):
        from cquant.ai_advisor.router import IntentRouter

        router = IntentRouter()
        result = router.classify("查看回撤和风险指标")
        assert "risk" in result.required_roles

    def test_no_keyword_match_returns_empty(self):
        from cquant.ai_advisor.router import IntentRouter

        router = IntentRouter()
        result = router.classify("Hello, how are you today?")
        assert result.required_roles == []

    def test_llm_fallback_sync(self):
        from cquant.ai_advisor.router import IntentRouter
        from cquant.ai_advisor.providers.base import ModelResponse

        mock_provider = MagicMock()
        mock_provider.generate_sync.return_value = ModelResponse(
            content='["risk"]',
            input_tokens=10,
            output_tokens=5,
            model="test",
            stop_reason="stop",
        )

        router = IntentRouter(llm_provider=mock_provider)
        result = router.classify("What is the volatility of my portfolio?")
        # Should have matched via keywords first (volatility -> risk)
        assert "risk" in result.required_roles

    def test_llm_fallback_on_no_keyword_match(self):
        from cquant.ai_advisor.router import IntentRouter
        from cquant.ai_advisor.providers.base import LLMProvider, ModelResponse

        class FakeProvider(LLMProvider):
            name = "fake"
            def generate_sync(self, messages, system="", max_tokens=4096):
                return ModelResponse(content='["research"]', input_tokens=10, output_tokens=5, model="test", stop_reason="stop")
            async def generate(self, messages, system="", max_tokens=4096):
                return ModelResponse(content='["research"]', input_tokens=10, output_tokens=5, model="test", stop_reason="stop")

        router = IntentRouter(llm_provider=FakeProvider())
        result = router.classify("Analyze the momentum factor decay pattern")
        assert "research" in result.required_roles

    def test_llm_fallback_error_returns_empty(self):
        from cquant.ai_advisor.router import IntentRouter

        mock_provider = MagicMock()
        mock_provider.generate_sync.side_effect = Exception("API error")

        router = IntentRouter(llm_provider=mock_provider)
        result = router.classify("Random query with no keywords")
        assert result.required_roles == []

    def test_parse_roles_json(self):
        from cquant.ai_advisor.router import IntentRouter

        router = IntentRouter()
        assert router._parse_roles('["risk", "research"]') == ["risk", "research"]
        assert router._parse_roles('["invalid_role"]') == []
        assert router._parse_roles("not json") == []
        assert router._parse_roles('["execution", "unknown"]') == ["execution"]

    def test_parse_roles_regex_fallback(self):
        from cquant.ai_advisor.router import IntentRouter

        router = IntentRouter()
        result = router._parse_roles('I think "risk" and "research" are needed')
        assert "risk" in result
        assert "research" in result

    def test_add_rule(self):
        from cquant.ai_advisor.router import IntentRouter, RoutingRule

        router = IntentRouter()
        router.add_rule(RoutingRule(
            keywords=frozenset({"custom_keyword"}),
            agent_roles=("execution",),
        ))
        result = router.classify("Please use custom_keyword now")
        assert "execution" in result.required_roles


# ── ChartGenerator ───────────────────────────────────────────────────────────


class TestChartGenerator:
    """Tests for ChartGenerator spec creation and marker parsing."""

    def test_metric_cards(self):
        from cquant.ai_advisor.chart_generator import ChartGenerator

        gen = ChartGenerator()
        spec = gen.metric_cards([
            {"label": "Sharpe", "value": 1.23},
            {"label": "MaxDD", "value": "-12.5%"},
        ])
        assert spec.chart_type == "metric_cards"
        assert spec.title == "Key Metrics"
        assert len(spec.data) == 2
        marker = spec.to_marker()
        assert marker.startswith("[CHART:metric_cards:")
        assert "Sharpe" in marker

    def test_line_chart(self):
        from cquant.ai_advisor.chart_generator import ChartGenerator

        gen = ChartGenerator()
        data = [
            {"date": "2025-01", "pnl": 100, "benchmark": 95},
            {"date": "2025-02", "pnl": 110, "benchmark": 98},
        ]
        spec = gen.line(data, x_key="date", y_keys=["pnl", "benchmark"], title="Cumulative PnL")
        assert spec.chart_type == "line"
        assert spec.config["x_key"] == "date"
        assert len(spec.config["y_keys"]) == 2

    def test_bar_chart(self):
        from cquant.ai_advisor.chart_generator import ChartGenerator

        gen = ChartGenerator()
        data = [{"category": "SMA", "value": 0.15}, {"category": "RSI", "value": 0.08}]
        spec = gen.bar(data, title="Factor IC")
        assert spec.chart_type == "bar"
        assert spec.config["x_key"] == "category"

    def test_pie_chart(self):
        from cquant.ai_advisor.chart_generator import ChartGenerator

        gen = ChartGenerator()
        data = [{"name": "Tech", "value": 35}, {"name": "Finance", "value": 25}]
        spec = gen.pie(data, title="Sector Allocation")
        assert spec.chart_type == "pie"
        assert spec.config["name_key"] == "name"

    def test_parse_markers(self):
        from cquant.ai_advisor.chart_generator import ChartGenerator

        text = (
            "Here is the analysis.\n"
            '[CHART:line:{"chart_type":"line","title":"PnL","data":[{"date":"2025-01","v":100}],"config":{}}]\n'
            "And some more text."
        )
        markers = ChartGenerator.parse_markers(text)
        assert len(markers) == 1
        assert markers[0]["chart_type"] == "line"
        assert markers[0]["title"] == "PnL"

    def test_parse_markers_multiple(self):
        from cquant.ai_advisor.chart_generator import ChartGenerator

        text = (
            '[CHART:metric_cards:{"chart_type":"metric_cards","title":"M","data":[],"config":{}}]'
            " middle "
            '[CHART:bar:{"chart_type":"bar","title":"B","data":[],"config":{}}]'
        )
        markers = ChartGenerator.parse_markers(text)
        assert len(markers) == 2
        assert markers[0]["chart_type"] == "metric_cards"
        assert markers[1]["chart_type"] == "bar"

    def test_parse_markers_none(self):
        from cquant.ai_advisor.chart_generator import ChartGenerator

        assert ChartGenerator.parse_markers("No charts here.") == []

    def test_to_marker_roundtrip(self):
        from cquant.ai_advisor.chart_generator import ChartGenerator

        gen = ChartGenerator()
        spec = gen.pie([{"name": "A", "value": 1}])
        marker = spec.to_marker()
        markers = ChartGenerator.parse_markers(marker)
        assert len(markers) == 1
        assert markers[0]["chart_type"] == "pie"
        assert markers[0]["data"][0]["name"] == "A"
