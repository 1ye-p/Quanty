"""Unit tests for cquant.core.types and cquant.core.enums."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from cquant.core.enums import AdjMethod, AssetClass, AssetStatus, Currency, Exchange
from cquant.core.types import Asset, Bar, RiskDecision
from cquant.core.enums import RiskDecisionType


def test_asset_id_validation_ok() -> None:
    a = Asset(
        asset_id="SSE:600036",
        symbol="600036",
        exchange=Exchange.SSE,
        asset_class=AssetClass.EQUITY,
        currency=Currency.CNY,
    )
    assert a.asset_id == "SSE:600036"


def test_asset_id_validation_fails_without_colon() -> None:
    with pytest.raises(ValueError, match="asset_id must follow"):
        Asset(
            asset_id="600036",
            symbol="600036",
            exchange=Exchange.SSE,
            asset_class=AssetClass.EQUITY,
            currency=Currency.CNY,
        )


def test_risk_decision_approved() -> None:
    decision = RiskDecision(
        decision=RiskDecisionType.APPROVED,
        original_qty=Decimal("1000"),
        approved_qty=Decimal("1000"),
    )
    assert decision.decision == RiskDecisionType.APPROVED
    assert decision.approved_qty == Decimal("1000")
