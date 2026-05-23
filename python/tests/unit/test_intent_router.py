"""Unit tests for cquant.ai_advisor.router."""

import pytest
from cquant.ai_advisor.router import AgentIntent, IntentRouter, RoutingRule, ROUTING_TABLE


class TestIntentRouter:
    def setup_method(self) -> None:
        self.router = IntentRouter()

    # ── Risk routing ───────────────────────────────────────────────────────────

    def test_risk_keyword_routes_risk_agent(self) -> None:
        intent = self.router.classify("What is the current drawdown?")
        assert "risk" in intent.required_roles

    def test_var_keyword_routes_risk_agent(self) -> None:
        intent = self.router.classify("Show me the VaR and CVaR metrics.")
        assert "risk" in intent.required_roles

    def test_beta_keyword_routes_risk_agent(self) -> None:
        intent = self.router.classify("What is the portfolio beta?")
        assert "risk" in intent.required_roles

    def test_overfit_routes_risk_agent(self) -> None:
        intent = self.router.classify("Is this strategy overfitting? Check PSR.")
        assert "risk" in intent.required_roles

    # ── Execution routing ──────────────────────────────────────────────────────

    def test_run_id_routes_execution_agent(self) -> None:
        intent = self.router.classify("Check run_id abc-123 status.")
        assert "execution" in intent.required_roles

    def test_job_status_phrase_routes_execution(self) -> None:
        intent = self.router.classify("What is the job status?")
        assert "execution" in intent.required_roles

    def test_backtest_run_routes_execution(self) -> None:
        intent = self.router.classify("Start a backtest run for strategy A.")
        assert "execution" in intent.required_roles

    # ── Multi-agent routing ────────────────────────────────────────────────────

    def test_both_risk_and_execution_match(self) -> None:
        intent = self.router.classify("Check run_id abc-123 for drawdown risk.")
        assert "risk" in intent.required_roles
        assert "execution" in intent.required_roles

    def test_no_duplicates_in_roles(self) -> None:
        intent = self.router.classify("risk risk risk drawdown var cvar")
        assert intent.required_roles.count("risk") == 1

    # ── General query — no specialist routing ─────────────────────────────────

    def test_general_query_returns_empty_roles(self) -> None:
        intent = self.router.classify("What is the momentum factor performance?")
        assert intent.required_roles == []

    def test_empty_string_returns_empty(self) -> None:
        intent = self.router.classify("")
        assert intent.required_roles == []

    # ── Custom rules ──────────────────────────────────────────────────────────

    def test_custom_rule_added_at_runtime(self) -> None:
        custom_router = IntentRouter(rules=[])
        custom_router.add_rule(RoutingRule(
            keywords=frozenset({"portfolio", "allocation"}),
            agent_roles=("portfolio",),
        ))
        intent = custom_router.classify("Show portfolio allocation breakdown.")
        assert "portfolio" in intent.required_roles

    def test_empty_rules_always_returns_empty(self) -> None:
        router = IntentRouter(rules=[])
        intent = router.classify("Check drawdown and run_id abc123")
        assert intent.required_roles == []

    # ── ROUTING_TABLE integrity ────────────────────────────────────────────────

    def test_routing_table_has_risk_and_execution_rules(self) -> None:
        all_roles = {role for rule in ROUTING_TABLE for role in rule.agent_roles}
        assert "risk" in all_roles
        assert "execution" in all_roles
