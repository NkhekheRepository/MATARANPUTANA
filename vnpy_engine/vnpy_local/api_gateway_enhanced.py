"""
API Gateway Module (Enhanced)
=============================
Central FastAPI gateway with event bus integration, debug endpoints,
trace ID tracking, and layer registration.
Serves as the single entry point for external clients.
"""

import os
import time
import json
import uuid
import hashlib
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from collections import defaultdict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Request, Depends
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from loguru import logger
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from contextlib import asynccontextmanager
import jwt
import redis

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from vnpy_engine.vnpy_local.shared_state import shared_state

# Constants
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
JWT_SECRET = os.getenv("JWT_SECRET_KEY", hashlib.sha256(b"financial_orchestrator_default_secret").hexdigest())
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# Create FastAPI app
app = FastAPI(
    title="Financial Orchestrator API",
    description="Central API Gateway for Paper Trading Engine",
    version="1.0.0"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, redis_client
    
    try:
        from vnpy_engine.vnpy_local.main_engine import get_engine
        engine = get_engine()
        engine.start()
        engine_status.set(1)
        logger.info("Trading engine started")
    except Exception as e:
        logger.error(f"Failed to start engine: {e}")
        engine_status.set(0)
    
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        redis_client = None
    
    register_default_layers()
    
    trading_mode = os.getenv("TRADING_MODE", "paper")
    server_type = os.getenv("BINANCE_SERVER", "REAL")
    logger.info(f"API Gateway started on port 8000 | Mode: {trading_mode} | Server: {server_type}")
    
    yield
    
    if engine:
        engine.stop()
    engine_status.set(0)


app = FastAPI(
    title="Financial Orchestrator API",
    description="Central API Gateway for Paper Trading Engine",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all API endpoints except health/auth."""
    path = request.url.path
    if path in ["/health", "/health/deep", "/health/layers", "/metrics", "/auth/token"]:
        return await call_next(request)
    
    client_id = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_id):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "retry_after": rate_limiter.window_seconds}
        )
    
    return await call_next(request)

# JWT security scheme
security = HTTPBearer(auto_error=False)


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """Dependency that requires valid JWT token."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    return decode_jwt_token(credentials.credentials)


async def optional_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """Dependency that optionally accepts JWT token."""
    if credentials is None:
        return None
    try:
        return decode_jwt_token(credentials.credentials)
    except HTTPException:
        return None


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@app.post("/auth/token", response_model=TokenResponse)
async def get_access_token(request: TokenRequest):
    """Get JWT access token using API key."""
    valid_keys = os.getenv("API_KEYS", "").split(",")
    default_key = hashlib.sha256(b"financial_orchestrator_default_api_key").hexdigest()
    
    if request.api_key not in valid_keys and request.api_key != default_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": "trading_api_user",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "scope": "read write admin"
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    logger.info("JWT token issued")
    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRE_MINUTES * 60
    )

# Prometheus metrics
request_count = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('api_request_duration_seconds', 'Request duration', ['endpoint'])
engine_status = Gauge('engine_status', 'Engine running status')
positions_count = Gauge('positions_count', 'Number of open positions')
event_count = Gauge('event_count', 'Total events published')
orders_submitted = Counter('orders_submitted_total', 'Total orders submitted', ['mode', 'status'])
order_fill_duration = Histogram('order_fill_duration_seconds', 'Time from submission to fill')
gateway_health = Gauge('gateway_health', 'Gateway connection health', ['gateway'])
emergency_stop_count = Counter('emergency_stop_total', 'Emergency stop triggers')
rate_limit_rejections = Counter('rate_limit_rejections_total', 'Requests rejected by rate limiter')
active_orders_gauge = Gauge('active_orders_count', 'Number of active in-flight orders')
account_balance = Gauge('account_balance', 'Current account balance')

# Global state
engine = None
redis_client: Optional[redis.Redis] = None
websocket_connections: List[WebSocket] = []
layer_registry: Dict[str, Dict[str, Any]] = {}
trace_store: Dict[str, List[Dict]] = {}


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        self.requests[client_id] = [t for t in self.requests[client_id] if t > cutoff]
        if len(self.requests[client_id]) >= self.max_requests:
            rate_limit_rejections.inc()
            return False
        self.requests[client_id].append(now)
        return True

rate_limiter = RateLimiter(
    max_requests=int(os.getenv("API_RATE_LIMIT", "120")),
    window_seconds=int(os.getenv("API_RATE_WINDOW", "60"))
)  # Store traces by trace_id


class TraceRequest(BaseModel):
    trace_id: str
    include_events: bool = True
    max_events: int = 100


class LayerRegistration(BaseModel):
    layer_id: str
    layer_name: str
    layer_type: str  # data, risk, signal, intelligence, execution, orchestration, control
    health_endpoint: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CommandRequest(BaseModel):
    command: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None


def register_default_layers():
    """Register default layer information."""
    default_layers = [
        {"layer_id": "layer1", "layer_name": "Data & Connectivity", "layer_type": "data"},
        {"layer_id": "layer2", "layer_name": "Risk Management", "layer_type": "risk"},
        {"layer_id": "layer3", "layer_name": "Signal Generation", "layer_type": "signal"},
        {"layer_id": "layer4", "layer_name": "Intelligence (ML/AI)", "layer_type": "intelligence"},
        {"layer_id": "layer5", "layer_name": "Execution", "layer_type": "execution"},
        {"layer_id": "layer6", "layer_name": "Orchestration", "layer_type": "orchestration"},
        {"layer_id": "layer7", "layer_name": "Command & Control", "layer_type": "control"},
    ]
    
    for layer in default_layers:
        layer_registry[layer["layer_id"]] = {
            **layer,
            "status": "registered",
            "registered_at": time.time()
        }


# ============================================================================
# Health Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    redis_healthy = False
    if redis_client:
        try:
            redis_client.ping()
            redis_healthy = True
        except:
            pass
    
    engine_running = engine.running if engine else False
    
    status = "healthy"
    if not redis_healthy:
        status = "degraded"
    if not engine_running:
        status = "unhealthy"
    
    return {
        "status": status,
        "checks": {
            "api_gateway": "healthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
            "engine": "healthy" if engine_running else "stopped"
        },
        "timestamp": time.time()
    }


@app.get("/health/deep")
async def deep_health_check():
    """Detailed health check with memory and component status."""
    import psutil
    process = psutil.Process()
    
    redis_healthy = False
    if redis_client:
        try:
            redis_client.ping()
            redis_healthy = True
        except:
            pass
    
    engine_running = engine.running if engine else False
    positions = engine.get_positions() if engine else {}
    
    results = {
        "api_gateway": "healthy",
        "redis": "healthy" if redis_healthy else "unhealthy",
        "engine": "running" if engine_running else "stopped",
        "memory": {
            "rss_mb": process.memory_info().rss / 1024 / 1024,
            "percent": process.memory_percent()
        },
        "positions_count": len(positions),
        "websocket_connections": len(websocket_connections),
        "registered_layers": len(layer_registry),
        "timestamp": time.time()
    }
    
    overall = "healthy"
    if not redis_healthy or not engine_running:
        overall = "degraded"
    if not engine_running:
        overall = "unhealthy"
    
    results["overall_status"] = overall
    status_code = 200 if overall in ["healthy", "degraded"] else 503
    
    return JSONResponse(content=results, status_code=status_code)


@app.get("/health/layers")
async def layers_health():
    """Check health of all registered layers."""
    layer_health = {}
    
    for layer_id, layer_info in layer_registry.items():
        layer_health[layer_id] = {
            "name": layer_info.get("layer_name", layer_id),
            "type": layer_info.get("layer_type", "unknown"),
            "status": layer_info.get("status", "unknown"),
            "registered_at": layer_info.get("registered_at")
        }
    
    return {
        "layers": layer_health,
        "total_layers": len(layer_health),
        "timestamp": time.time()
    }


# ============================================================================
# Metrics Endpoint
# ============================================================================

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")


# ============================================================================
# Debug Endpoints
# ============================================================================

@app.get("/api/v1/debug/trace/{trace_id}")
async def get_trace(trace_id: str, include_events: bool = Query(True), _: Dict = Depends(require_auth)):
    """Get trace information by trace_id for debugging."""
    # First try Redis
    trace_data = None
    if redis_client:
        try:
            # Look for events with this trace_id
            event_key = f"fo:event_hash:{trace_id}"
            event_data = redis_client.hgetall(event_key)
            if event_data:
                trace_data = event_data
        except Exception as e:
            logger.error(f"Redis trace lookup error: {e}")
    
    # Check local store
    if not trace_data and trace_id in trace_store:
        trace_data = {"events": trace_store[trace_id]}
    
    if not trace_data:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    
    return {
        "trace_id": trace_id,
        "data": trace_data,
        "timestamp": time.time()
    }


@app.get("/api/v1/debug/events")
async def get_recent_events(
    event_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    _: Dict = Depends(require_auth)
):
    """Get recent events for debugging."""
    events = []
    
    if redis_client:
        try:
            # Get events from history list
            event_data_list = redis_client.lrange("fo:event_history", 0, limit - 1)
            for event_data in event_data_list:
                try:
                    event = json.loads(event_data)
                    if not event_type or event.get("event_type") == event_type:
                        events.append(event)
                except:
                    pass
        except Exception as e:
            logger.error(f"Redis events lookup error: {e}")
    
    return {
        "events": events,
        "count": len(events),
        "filter": {"event_type": event_type, "limit": limit},
        "timestamp": time.time()
    }


@app.get("/api/v1/debug/redis")
async def redis_debug(_: Dict = Depends(require_auth)):
    """Debug Redis connection and data."""
    if not redis_client:
        return {"status": "disconnected"}
    
    try:
        info = redis_client.info()
        keys = redis_client.keys("*")
        
        # Count keys by prefix
        key_counts = {}
        for key in keys:
            prefix = key.split(":")[0] if ":" in key else "other"
            key_counts[prefix] = key_counts.get(prefix, 0) + 1
        
        return {
            "status": "connected",
            "redis_version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "total_keys": len(keys),
            "key_counts_by_prefix": key_counts,
            "timestamp": time.time()
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/v1/debug/state")
async def debug_state(_: Dict = Depends(require_auth)):
    """Get current engine state for debugging."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not running")
    
    try:
        status = engine.get_status()
        positions = engine.get_positions()
        
        return {
            "engine_status": status,
            "positions": positions,
            "strategies": list(engine.strategies.keys()) if hasattr(engine, 'strategies') else [],
            "active_strategy": getattr(engine, 'active_strategy', None),
            "current_regime": getattr(engine, 'current_regime', None),
            "capital": getattr(engine, 'capital', 0),
            "daily_pnl": getattr(engine, 'daily_pnl', 0),
            "leverage": getattr(engine, 'leverage', 1),
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting state: {str(e)}")


# ============================================================================
# Status Endpoints
# ============================================================================

@app.get("/api/v1/status")
async def get_status(_: Dict = Depends(require_auth)):
    """Get current engine status."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    return engine.get_status()


@app.get("/api/v1/positions")
async def get_positions(_: Dict = Depends(require_auth)):
    """Get all positions."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    positions = engine.get_positions()
    positions_count.set(len(positions))
    return {"positions": positions}


@app.get("/api/v1/pnl")
async def get_pnl(_: Dict = Depends(require_auth)):
    """Get P&L information."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    return engine.get_pnl()


@app.get("/api/v1/strategies")
async def get_strategies(_: Dict = Depends(require_auth)):
    """Get all strategies and their status."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    strategies = {}
    if hasattr(engine, 'strategies'):
        for name, info in engine.strategies.items():
            strategies[name] = {
                "running": info.get("running", False),
                "pnl": info.get("pnl", 0),
                "trades": info.get("trades", 0)
            }
    
    return {
        "strategies": strategies,
        "active_strategy": getattr(engine, 'active_strategy', None)
    }


# ============================================================================
# Control Endpoints
# ============================================================================

class PositionRequest(BaseModel):
    symbol: str
    target_size: int


@app.post("/api/v1/position/set")
async def set_position(req: PositionRequest, _: Dict = Depends(require_auth)):
    """Set position target for a symbol."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    success = engine.set_position_target(req.symbol, req.target_size)
    return {"success": success, "symbol": req.symbol, "target_size": req.target_size}


class OrderRequest(BaseModel):
    symbol: str
    action: str
    price: float
    quantity: float = 1.0
    order_type: str = "limit"


@app.post("/api/v1/order")
async def place_order(req: OrderRequest, _: Dict = Depends(require_auth)):
    """Place an order."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    if req.action not in ["buy", "sell", "close"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use: buy, sell, close")

    if req.order_type not in ["limit", "market"]:
        raise HTTPException(status_code=400, detail="Invalid order_type. Use: limit, market")

    market_data = {
        "price": req.price,
        "volume": req.quantity,
        "symbol": req.symbol
    }

    engine.process_market_data(req.symbol, market_data)

    if req.action != "hold":
        engine._execute_action(req.symbol, req.action, req.price, req.quantity)

    return {
        "success": True,
        "symbol": req.symbol,
        "action": req.action,
        "price": req.price,
        "quantity": req.quantity,
        "order_type": req.order_type
    }


@app.post("/api/v1/command")
async def send_command(req: CommandRequest, _: Dict = Depends(require_auth)):
    """Send a command to the engine."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    trace_id = req.trace_id or str(uuid.uuid4())
    
    # Store trace
    if trace_id not in trace_store:
        trace_store[trace_id] = []
    
    trace_store[trace_id].append({
        "type": "command_received",
        "command": req.command,
        "parameters": req.parameters,
        "timestamp": time.time()
    })
    
    # Process command
    result = {"success": True, "command": req.command, "trace_id": trace_id}
    
    if req.command == "start":
        engine.start()
        result["message"] = "Engine started"
    elif req.command == "stop":
        engine.stop()
        result["message"] = "Engine stopped"
    elif req.command == "emergency_stop":
        engine.emergency_stop()
        emergency_stop_count.inc()
        result["message"] = "Emergency stop triggered"
    elif req.command == "switch_strategy":
        strategy_name = req.parameters.get("strategy")
        action = req.parameters.get("action", "stop")
        if strategy_name:
            success = engine.switch_strategy(strategy_name, action)
            result["success"] = success
            result["message"] = f"Strategy {strategy_name} {action}ed" if success else f"Failed to {action} {strategy_name}"
        else:
            result["success"] = False
            result["message"] = "Missing strategy parameter"
    else:
        result["success"] = False
        result["message"] = f"Unknown command: {req.command}"
    
    return result


@app.post("/api/v1/strategy/start/{strategy_name}")
async def start_strategy(strategy_name: str, _: Dict = Depends(require_auth)):
    """Start a specific strategy."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    if strategy_name in engine.strategies:
        engine.strategies[strategy_name]["running"] = True
        return {"success": True, "strategy": strategy_name}
    
    raise HTTPException(status_code=404, detail=f"Strategy {strategy_name} not found")


@app.post("/api/v1/strategy/stop/{strategy_name}")
async def stop_strategy(strategy_name: str, _: Dict = Depends(require_auth)):
    """Stop a specific strategy."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    if strategy_name in engine.strategies:
        engine.strategies[strategy_name]["running"] = False
        return {"success": True, "strategy": strategy_name}
    
    raise HTTPException(status_code=404, detail=f"Strategy {strategy_name} not found")


# ============================================================================
# Live Trading Control Endpoints
# ============================================================================

@app.post("/api/v1/control/emergency_stop")
async def emergency_stop(_: Dict = Depends(require_auth)):
    """Trigger emergency stop - cancels all orders and closes all positions."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    engine.emergency_stop()
    emergency_stop_count.inc()
    engine_status.set(0)
    
    return {
        "success": True,
        "message": "Emergency stop triggered",
        "timestamp": time.time()
    }


class StrategyControlRequest(BaseModel):
    strategy_name: str
    action: str = Field(..., description="start, stop, or reload")


@app.post("/api/v1/control/strategy")
async def control_strategy(req: StrategyControlRequest, _: Dict = Depends(require_auth)):
    """Start, stop, or reload a specific strategy."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    success = engine.switch_strategy(req.strategy_name, req.action)
    if not success:
        raise HTTPException(status_code=404, detail=f"Strategy {req.strategy_name} not found or action failed")
    
    return {
        "success": True,
        "strategy": req.strategy_name,
        "action": req.action,
        "timestamp": time.time()
    }


@app.post("/api/v1/control/sync")
async def manual_sync(_: Dict = Depends(require_auth)):
    """Manually trigger account and position sync with exchange."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    engine._sync_account_from_exchange()
    
    return {
        "success": True,
        "message": "Account sync triggered",
        "timestamp": time.time()
    }


@app.get("/api/v1/control/preflight")
async def preflight_check(_: Dict = Depends(require_auth)):
    """Run pre-flight checks for live trading readiness."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    checks = engine._preflight_check()
    
    return {
        "ready": checks["ready"],
        "checks": checks,
        "timestamp": time.time()
    }


@app.get("/api/v1/control/gateway_health")
async def gateway_health_check(_: Dict = Depends(require_auth)):
    """Check gateway connection health."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    health = {}
    for gw_name, gw_info in engine.gateways.items():
        health[gw_name] = {
            "connected": gw_info.get("connected", False),
            "type": gw_info.get("type", "unknown"),
            "mode": gw_info.get("mode", "unknown"),
            "last_error": gw_info.get("last_error"),
            "last_error_time": gw_info.get("last_error_time")
        }
        gw_health_val = 1.0 if gw_info.get("connected", False) else 0.0
        gateway_health.labels(gateway=gw_name).set(gw_health_val)
    
    return {
        "gateways": health,
        "timestamp": time.time()
    }


# ============================================================================
# Execution & Order Management Endpoints
# ============================================================================

@app.get("/api/v1/orders")
async def get_orders(
    status_filter: Optional[str] = Query(None, description="Filter by status: active, completed, all"),
    limit: int = Query(50, ge=1, le=500),
    _: Dict = Depends(require_auth)
):
    """Get order history with optional status filter."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    try:
        from vnpy_engine.vnpy_local.order_tracker import order_tracker
    except ImportError:
        raise HTTPException(status_code=503, detail="Order tracker not available")
    
    if status_filter == "active":
        orders = order_tracker.get_active_orders()
    elif status_filter == "completed":
        orders = order_tracker.get_completed_orders(limit=limit)
    else:
        active = order_tracker.get_active_orders()
        completed = order_tracker.get_completed_orders(limit=limit)
        orders = {**active, **completed}
    
    active_orders_gauge.set(len(order_tracker.get_active_orders()))
    
    return {
        "orders": orders,
        "count": len(orders),
        "filter": status_filter or "all",
        "timestamp": time.time()
    }


@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: str, _: Dict = Depends(require_auth)):
    """Get specific order details."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    try:
        from vnpy_engine.vnpy_local.order_tracker import order_tracker
    except ImportError:
        raise HTTPException(status_code=503, detail="Order tracker not available")
    
    order = order_tracker.get_order_status(order_id)
    if not order:
        order = engine.orders.get(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    
    return {"order": order}


@app.post("/api/v1/orders/{order_id}/cancel")
async def cancel_order(order_id: str, _: Dict = Depends(require_auth)):
    """Cancel an active order."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    try:
        from vnpy_engine.vnpy_local.order_tracker import order_tracker
    except ImportError:
        raise HTTPException(status_code=503, detail="Order tracker not available")
    
    success = order_tracker.cancel_order(order_id, engine.vnpy_main_engine.cancel_order)
    if not success:
        raise HTTPException(status_code=400, detail=f"Cannot cancel order {order_id}")
    
    return {
        "success": True,
        "order_id": order_id,
        "message": "Cancel requested",
        "timestamp": time.time()
    }


@app.get("/api/v1/execution/summary")
async def execution_summary(_: Dict = Depends(require_auth)):
    """Get execution performance summary."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    try:
        from vnpy_engine.vnpy_local.order_tracker import order_tracker
    except ImportError:
        raise HTTPException(status_code=503, detail="Order tracker not available")
    
    summary = order_tracker.get_execution_summary()
    
    orders_submitted.labels(mode=engine.gateways.get("binance", {}).get("mode", "paper"), status="all").inc(0)
    active_orders_gauge.set(summary.get("active_orders", 0))
    
    return {
        "execution_summary": summary,
        "timestamp": time.time()
    }


# ============================================================================
# Account & Risk Endpoints
# ============================================================================

@app.get("/api/v1/account")
async def get_account_info(_: Dict = Depends(require_auth)):
    """Get current account information."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    account_status = shared_state.get_system_status("account")
    
    if account_status:
        account_balance.set(account_status.get("balance", 0))
    
    return {
        "account": account_status or {"message": "No account data synced yet"},
        "trading_mode": os.getenv("TRADING_MODE", "paper"),
        "timestamp": time.time()
    }


@app.get("/api/v1/risk/status")
async def get_risk_status(_: Dict = Depends(require_auth)):
    """Get current risk management status."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    try:
        from vnpy_engine.vnpy_local.risk_manager import risk_manager
    except ImportError:
        raise HTTPException(status_code=503, detail="Risk manager not available")
    
    return {
        "risk_status": risk_manager.get_risk_status(),
        "timestamp": time.time()
    }


@app.get("/api/v1/reconciliation")
async def get_reconciliation_status(_: Dict = Depends(require_auth)):
    """Get position reconciliation status."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    recon_status = shared_state.get_system_status("reconciliation")
    
    return {
        "reconciliation": recon_status or {"message": "No reconciliation data"},
        "timestamp": time.time()
    }


# ============================================================================
# Layer Registration
# ============================================================================

@app.post("/api/v1/layers/register")
async def register_layer(layer: LayerRegistration, _: Dict = Depends(require_auth)):
    """Register a layer in the registry."""
    layer_registry[layer.layer_id] = {
        "layer_id": layer.layer_id,
        "layer_name": layer.layer_name,
        "layer_type": layer.layer_type,
        "health_endpoint": layer.health_endpoint,
        "metadata": layer.metadata,
        "status": "registered",
        "registered_at": time.time()
    }
    
    return {"success": True, "layer_id": layer.layer_id, "message": "Layer registered"}


@app.get("/api/v1/layers")
async def get_layers():
    """Get all registered layers."""
    return {
        "layers": layer_registry,
        "total": len(layer_registry)
    }


@app.get("/api/v1/layers/{layer_id}")
async def get_layer(layer_id: str):
    """Get a specific layer's information."""
    if layer_id not in layer_registry:
        raise HTTPException(status_code=404, detail=f"Layer {layer_id} not found")
    
    return layer_registry[layer_id]


# ============================================================================
# WebSocket Endpoints
# ============================================================================

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time data streaming."""
    await websocket.accept()
    websocket_connections.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(websocket_connections)}")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Handle different message types
                msg_type = message.get("type")
                
                if msg_type == "market_data" and engine:
                    symbol = message.get("symbol")
                    engine.process_market_data(symbol, message.get("data", {}))
                    await websocket.send_json({
                        "type": "ack",
                        "symbol": symbol,
                        "timestamp": time.time()
                    })
                elif msg_type == "subscribe":
                    # Subscribe to events
                    await websocket.send_json({
                        "type": "subscribed",
                        "timestamp": time.time()
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })
                    
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(websocket_connections)}")


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket endpoint for streaming events."""
    await websocket.accept()
    websocket_connections.append(websocket)
    logger.info(f"Event WebSocket client connected")
    
    try:
        while True:
            # Keep connection alive and send periodic updates
            await websocket.send_json({
                "type": "ping",
                "timestamp": time.time()
            })
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        logger.info("Event WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Event WebSocket error: {e}")
        websocket_connections.remove(websocket)


async def broadcast_update(update: Dict[str, Any]):
    """Broadcast update to all connected WebSocket clients."""
    for ws in websocket_connections:
        try:
            await ws.send_json(update)
        except:
            pass


# ============================================================================
# Main Entry Point
# ============================================================================

def run_server():
    """Run the API gateway server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    import asyncio
    run_server()