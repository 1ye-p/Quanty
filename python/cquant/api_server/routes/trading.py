"""cquant.api_server.routes.trading — Trading operations API.

Provides endpoints for order management, position queries, and account state.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from cquant.execution.broker import Order, OrderStatus
from cquant.execution.paper_broker import PaperBroker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trading", tags=["trading"])

# Singleton PaperBroker for demo (in production, per-session or per-user)
_paper_broker: PaperBroker | None = None


def _get_paper_broker() -> PaperBroker:
    global _paper_broker
    if _paper_broker is None:
        _paper_broker = PaperBroker(initial_cash=1_000_000)
    return _paper_broker


def _get_broker(name: str):
    """Get broker by name."""
    if name == "paper":
        return _get_paper_broker()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported broker '{name}'. Only 'paper' is currently available.",
    )


# ── Request/Response Models ────────────────────────────────────────────────────


class OrderRequest(BaseModel):
    asset_id: str
    side: str  # "buy", "sell"
    qty: int
    order_type: str = "market"  # "market", "limit"
    limit_price: float | None = None
    broker: str = "paper"
    strategy_id: str = ""

    @field_validator("qty")
    @classmethod
    def validate_qty(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("qty must be > 0")
        return v

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        if v not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        return v

    @field_validator("order_type")
    @classmethod
    def validate_order_type(cls, v: str) -> str:
        if v not in {"market", "limit"}:
            raise ValueError("order_type must be 'market' or 'limit'")
        return v

    @field_validator("asset_id")
    @classmethod
    def validate_asset_id(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError("asset_id must be EXCHANGE:CODE (e.g. SSE:600036)")
        return v


class OrderResponse(BaseModel):
    order_id: str
    asset_id: str
    side: str
    qty: int
    order_type: str
    status: str
    filled_qty: int
    filled_price: float
    commission: float
    stamp_duty: float
    slippage: float
    total_cost: float
    reject_reason: str
    submitted_at: str | None
    filled_at: str | None


class AccountResponse(BaseModel):
    broker: str
    cash: float
    nav: float
    gross_exposure: float
    net_exposure: float
    realized_pnl: float
    unrealized_pnl: float
    positions_count: int


class PositionResponse(BaseModel):
    asset_id: str
    qty: int
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/order", response_model=OrderResponse)
async def place_order(req: OrderRequest) -> dict[str, Any]:
    """Place a new order."""
    # Validate limit order
    if req.order_type == "limit" and (req.limit_price is None or req.limit_price <= 0):
        raise HTTPException(status_code=400, detail="Limit orders require limit_price > 0")

    broker = _get_broker(req.broker)

    order = Order(
        order_id=str(uuid.uuid4())[:8],
        asset_id=req.asset_id,
        side=req.side,
        qty=req.qty,
        order_type=req.order_type,
        limit_price=req.limit_price,
        strategy_id=req.strategy_id,
    )

    # Update prices for paper broker
    if req.broker == "paper":
        from cquant.datahub.connectors.realtime_connector import QuoteFeed
        feed = QuoteFeed()
        symbol = req.asset_id.split(":")[-1] if ":" in req.asset_id else req.asset_id
        quotes = feed.get_quotes([symbol])
        if quotes:
            broker.update_prices({q.asset_id: q.price for q in quotes.values()})

    result = broker.submit_order(order)
    return _order_to_dict(result)


@router.delete("/order/{order_id}", response_model=OrderResponse)
async def cancel_order(order_id: str, broker: str = "paper") -> dict[str, Any]:
    """Cancel an order."""
    broker_inst = _get_broker(broker)
    try:
        result = broker_inst.cancel_order(order_id)
        return _order_to_dict(result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/orders")
async def list_orders(
    broker: str = "paper",
    status: str | None = None,
) -> dict[str, Any]:
    """List orders, optionally filtered by status."""
    broker_inst = _get_broker(broker)
    status_filter = None
    if status:
        try:
            status_filter = OrderStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    orders = broker_inst.get_orders(status=status_filter)
    return {
        "items": [_order_to_dict(o) for o in orders[-100:]],
        "total": len(orders),
    }


@router.get("/positions")
async def list_positions(broker: str = "paper") -> dict[str, Any]:
    """List current positions."""
    broker_inst = _get_broker(broker)
    positions = broker_inst.get_positions()

    items = []
    for asset_id, pos in positions.items():
        items.append({
            "asset_id": pos.asset_id,
            "qty": pos.qty,
            "avg_cost": pos.avg_cost,
            "market_value": pos.market_value,
            "unrealized_pnl": pos.unrealized_pnl,
            "realized_pnl": pos.realized_pnl,
        })

    return {"items": items, "total": len(items)}


@router.get("/account", response_model=AccountResponse)
async def get_account(broker: str = "paper") -> dict[str, Any]:
    """Get account state."""
    broker_inst = _get_broker(broker)
    account = broker_inst.get_account()

    return {
        "broker": broker,
        "cash": account.cash,
        "nav": account.nav,
        "gross_exposure": account.gross_exposure,
        "net_exposure": account.net_exposure,
        "realized_pnl": account.realized_pnl,
        "unrealized_pnl": account.unrealized_pnl,
        "positions_count": len(account.positions),
    }


@router.get("/fills")
async def list_fills(broker: str = "paper") -> dict[str, Any]:
    """List filled orders (convenience endpoint)."""
    broker_inst = _get_broker(broker)
    filled = broker_inst.get_orders(status=OrderStatus.FILLED)

    return {
        "items": [_order_to_dict(o) for o in filled[-100:]],
        "total": len(filled),
    }


@router.get("/pnl")
async def get_pnl(broker: str = "paper") -> dict[str, Any]:
    """Get PnL summary."""
    broker_inst = _get_broker(broker)
    account = broker_inst.get_account()

    return {
        "broker": broker,
        "nav": account.nav,
        "realized_pnl": account.realized_pnl,
        "unrealized_pnl": account.unrealized_pnl,
        "total_pnl": account.realized_pnl + account.unrealized_pnl,
        "return_pct": ((account.nav / 1_000_000) - 1) * 100 if account.nav > 0 else 0,
    }


def _order_to_dict(order: Order) -> dict[str, Any]:
    """Convert Order to dict."""
    return {
        "order_id": order.order_id,
        "asset_id": order.asset_id,
        "side": order.side,
        "qty": order.qty,
        "order_type": order.order_type,
        "status": order.status.value,
        "filled_qty": order.filled_qty,
        "filled_price": order.filled_price,
        "commission": order.commission,
        "stamp_duty": order.stamp_duty,
        "slippage": order.slippage,
        "total_cost": order.total_cost,
        "reject_reason": order.reject_reason,
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "filled_at": order.filled_at.isoformat() if order.filled_at else None,
    }
