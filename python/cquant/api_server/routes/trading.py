"""cquant.api_server.routes.trading — Trading operations API.

Provides endpoints for order management, position queries, account state,
and algorithmic order execution (TWAP/VWAP).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from cquant.execution.algo_orders import (
    AlgoOrderManager,
    AlgoOrderParams,
    AlgoType,
)
from cquant.execution.broker import Order, OrderStatus
from cquant.execution.paper_broker import PaperBroker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trading", tags=["trading"])

# Singleton PaperBroker for demo (in production, per-session or per-user)
_paper_broker: PaperBroker | None = None
_algo_manager: AlgoOrderManager | None = None


def _get_paper_broker() -> PaperBroker:
    global _paper_broker
    if _paper_broker is None:
        from cquant.core.config import settings
        _paper_broker = PaperBroker(initial_cash=settings.backtest.initial_cash)
    return _paper_broker


def _get_algo_manager() -> AlgoOrderManager:
    global _algo_manager
    if _algo_manager is None:
        broker = _get_paper_broker()
        _algo_manager = AlgoOrderManager(broker)
    return _algo_manager


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
        "return_pct": ((account.nav / broker_inst._initial_cash) - 1) * 100 if account.nav > 0 else 0,
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


# ── Algo Order Models ─────────────────────────────────────────────────────────


class AlgoOrderRequest(BaseModel):
    """Request to place an algorithmic order."""
    algo_type: str  # "twap" | "vwap"
    asset_id: str
    side: str  # "buy", "sell"
    total_qty: int
    start_time: datetime
    end_time: datetime
    num_slices: int = 10
    lookback_days: int = 20
    broker: str = "paper"
    strategy_id: str = ""

    @field_validator("total_qty")
    @classmethod
    def validate_qty(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("total_qty must be > 0")
        return v

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        if v not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        return v

    @field_validator("algo_type")
    @classmethod
    def validate_algo_type(cls, v: str) -> str:
        if v not in {"twap", "vwap"}:
            raise ValueError("algo_type must be 'twap' or 'vwap'")
        return v

    @field_validator("asset_id")
    @classmethod
    def validate_asset_id(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError("asset_id must be EXCHANGE:CODE (e.g. SSE:600036)")
        return v

    @field_validator("num_slices")
    @classmethod
    def validate_num_slices(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("num_slices must be > 0")
        return v


# ── Algo Order Endpoints ──────────────────────────────────────────────────────


@router.post("/algo-order")
async def place_algo_order(req: AlgoOrderRequest) -> dict[str, Any]:
    """Place a TWAP or VWAP algorithm order.

    Creates an algorithmic order that splits execution into multiple slices
    over the specified time window.

    - **TWAP**: Equal time intervals, equal quantities
    - **VWAP**: Based on historical volume profile
    """
    # Validate time window
    if req.end_time <= req.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time",
        )

    # Create AlgoOrderParams
    params = AlgoOrderParams(
        algo_type=AlgoType(req.algo_type),
        asset_id=req.asset_id,
        side=req.side,
        total_qty=req.total_qty,
        start_time=req.start_time,
        end_time=req.end_time,
        num_slices=req.num_slices,
        lookback_days=req.lookback_days,
        broker=req.broker,
        strategy_id=req.strategy_id,
    )

    manager = _get_algo_manager()
    try:
        order = manager.create_order(params)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    logger.info(
        "Algo order placed: %s %s %s x%d (%s)",
        order.order_id,
        req.algo_type,
        req.asset_id,
        req.total_qty,
        req.side,
    )

    return order.to_dict()


@router.get("/algo-order/{order_id}")
async def get_algo_order_status(order_id: str) -> dict[str, Any]:
    """Get algo order execution status.

    Returns the current status of the algorithmic order including:
    - Overall order status and progress
    - Individual slice details (scheduled time, fill status, prices)
    - Cumulative filled quantity and average price
    """
    manager = _get_algo_manager()
    order = manager.get_order(order_id)

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Algo order not found: {order_id}",
        )

    return order.to_dict()


@router.get("/algo-orders")
async def list_algo_orders(
    status: str | None = None,
) -> dict[str, Any]:
    """List all algorithmic orders.

    Parameters
    ----------
    status:
        Filter by order status: "active", "completed", "cancelled".
    """
    manager = _get_algo_manager()
    orders = manager.get_orders(status=status)

    return {
        "items": [o.to_dict() for o in orders],
        "total": len(orders),
    }


@router.delete("/algo-order/{order_id}")
async def cancel_algo_order(order_id: str) -> dict[str, Any]:
    """Cancel an algorithmic order.

    Cancels all pending slices. Already-filled slices are not affected.
    """
    manager = _get_algo_manager()
    try:
        order = manager.cancel_order(order_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return order.to_dict()


@router.post("/algo-order/{order_id}/execute")
async def execute_algo_slices(order_id: str) -> dict[str, Any]:
    """Execute due slices for an algorithmic order.

    Triggers execution of any slices whose scheduled_time has passed.
    This endpoint can be called periodically (e.g., by a scheduler) to
    advance the algo order execution.
    """
    manager = _get_algo_manager()
    order = manager.get_order(order_id)

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Algo order not found: {order_id}",
        )

    if order.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Algo order is not active (status: {order.status})",
        )

    executed = manager.execute_due_slices(order_id)

    return {
        "order_id": order_id,
        "executed_slices": len(executed),
        "order": order.to_dict(),
    }
