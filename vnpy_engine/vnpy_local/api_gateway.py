"""
API Gateway Module
==================
REST API + WebSocket server for orchestrator communication.
"""

import os
import asyncio
import time
import json
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi.responses import Response
from contextlib import asynccontextmanager

from .shared_state import shared_state
from .main_engine import get_engine

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, redis_client
    engine = get_engine()
    engine.start()
    engine_status.set(1)
    
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected for API")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
    
    logger.info("API Gateway started on port 8000")
    
    yield
    
    if engine:
        engine.stop()
    engine_status.set(0)


app = FastAPI(title="VN.PY Trading Engine API", lifespan=lifespan)

request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
request_duration = Histogram('http_request_duration_seconds', 'Request duration')
engine_status = Gauge('engine_status', 'Engine running status')
positions_count = Gauge('positions_count', 'Number of open positions')

engine: Optional[Any] = None
redis_client: Optional[redis.Redis] = None
websocket_connections: list = []


@app.get("/health")
async def health_check():
    redis_health = shared_state.health_check()
    engine_running = engine.running if engine else False
    
    checks = {
        "api_gateway": "healthy",
        "redis": "healthy" if redis_health else "unhealthy",
        "engine": "healthy" if engine_running else "stopped",
    }
    
    status = "healthy"
    if not redis_health:
        status = "degraded"
        checks["redis"] = "unhealthy"
    if not engine_running:
        status = "unhealthy"
        checks["engine"] = "stopped"
    
    return {
        "status": status,
        "checks": checks,
        "engine_running": engine_running,
        "redis_connected": redis_health,
        "timestamp": time.time()
    }


@app.get("/health/deep")
async def deep_health_check():
    results = {
        "api_gateway": "healthy",
        "redis": "unhealthy",
        "engine": "stopped",
        "strategies": [],
        "positions": 0,
        "memory": {}
    }
    
    import psutil
    process = psutil.Process()
    results["memory"] = {
        "rss_mb": process.memory_info().rss / 1024 / 1024,
        "percent": process.memory_percent()
    }
    
    if shared_state.health_check():
        results["redis"] = "healthy"
    else:
        try:
            redis_async = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            await redis_async.ping()
            results["redis"] = "healthy"
        except Exception as e:
            results["redis"] = f"error: {str(e)}"
    
    if engine:
        results["engine"] = "running" if engine.running else "stopped"
        results["positions"] = len(engine.get_positions())
        results["strategies"] = list(engine.strategies.keys()) if hasattr(engine, 'strategies') else []
    
    overall = "healthy"
    if results["redis"] != "healthy" or results["engine"] != "running":
        overall = "degraded"
    if results["engine"] == "stopped":
        overall = "unhealthy"
    
    results["overall_status"] = overall
    results["timestamp"] = time.time()
    
    status_code = 200 if overall == "healthy" else (503 if overall == "unhealthy" else 200)
    return JSONResponse(content=results, status_code=status_code)


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")


@app.get("/api/v1/status")
async def get_status():
    request_count.labels(method="GET", endpoint="/api/v1/status").inc()
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    return engine.get_status()


@app.get("/api/v1/positions")
async def get_positions():
    request_count.labels(method="GET", endpoint="/api/v1/positions").inc()
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    positions = engine.get_positions()
    positions_count.set(len(positions))
    return {"positions": positions}


@app.get("/api/v1/pnl")
async def get_pnl():
    request_count.labels(method="GET", endpoint="/api/v1/pnl").inc()
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    return engine.get_pnl()


class PositionRequest(BaseModel):
    symbol: str
    target_size: int


@app.post("/api/v1/position/set")
async def set_position(req: PositionRequest):
    request_count.labels(method="POST", endpoint="/api/v1/position/set").inc()
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    success = engine.set_position_target(req.symbol, req.target_size)
    return {"success": success, "symbol": req.symbol, "target_size": req.target_size}


class OrderRequest(BaseModel):
    symbol: str
    action: str
    price: float
    quantity: float = 1.0


@app.post("/api/v1/order")
async def place_order(req: OrderRequest):
    request_count.labels(method="POST", endpoint="/api/v1/order").inc()
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    if req.action not in ["buy", "sell", "close"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    market_data = {
        "price": req.price,
        "volume": req.quantity,
        "volatility": 0.5,
        "trend": 0
    }
    engine.process_market_data(req.symbol, market_data)
    
    return {
        "success": True,
        "symbol": req.symbol,
        "action": req.action,
        "price": req.price
    }


@app.post("/api/v1/strategy/start")
async def start_strategy(strategy_name: str):
    request_count.labels(method="POST", endpoint="/api/v1/strategy/start").inc()
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    if strategy_name in engine.strategies:
        engine.strategies[strategy_name]["running"] = True
        return {"success": True, "strategy": strategy_name}
    
    raise HTTPException(status_code=404, detail="Strategy not found")


@app.post("/api/v1/strategy/stop")
async def stop_strategy(strategy_name: str):
    request_count.labels(method="POST", endpoint="/api/v1/strategy/stop").inc()
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    if strategy_name in engine.strategies:
        engine.strategies[strategy_name]["running"] = False
        return {"success": True, "strategy": strategy_name}
    
    raise HTTPException(status_code=404, detail="Strategy not found")


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    websocket_connections.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(websocket_connections)}")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if message.get("type") == "market_data":
                    symbol = message.get("symbol")
                    engine.process_market_data(symbol, message.get("data", {}))
                    
                    response = {
                        "type": "ack",
                        "symbol": symbol,
                        "timestamp": time.time()
                    }
                    await websocket.send_json(response)
                    
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(websocket_connections)}")


async def broadcast_update(update: Dict[str, Any]):
    for ws in websocket_connections:
        try:
            await ws.send_json(update)
        except:
            pass


def run_server():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    run_server()
