from contextlib import asynccontextmanager
import json
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, ValidationError
import orjson

from app.plugins.base import AnalysisResult, PluginManifestItem
from app.plugins.loader import discover_and_load_plugins, registry
from app.sample_data import SAMPLE_DATASETS

logger = logging.getLogger("libretab")
logging.basicConfig(level=logging.INFO)

# Global watchdog state for orphan process cleanup
last_heartbeat_time = time.time()
watchdog_lock = threading.Lock()


def update_heartbeat():
    global last_heartbeat_time
    with watchdog_lock:
        last_heartbeat_time = time.time()


def start_watchdog_thread(timeout_seconds: float = 10.0, grace_seconds: float = 25.0):
    """
    Background watchdog thread that shuts down the Python process if no heartbeat
    is received from the frontend within `timeout_seconds`.
    """
    def watchdog_loop():
        time.sleep(grace_seconds)
        logger.info(f"Watchdog active (heartbeat timeout: {timeout_seconds}s)...")
        while True:
            time.sleep(1.0)
            with watchdog_lock:
                elapsed = time.time() - last_heartbeat_time
            if elapsed > timeout_seconds:
                logger.warning(
                    f"No heartbeat received for {elapsed:.1f}s (timeout: {timeout_seconds}s). Exiting process..."
                )
                os._exit(0)

    t = threading.Thread(target=watchdog_loop, daemon=True, name="HeartbeatWatchdog")
    t.start()


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively converts all NumPy and Pandas types (int64, float64, ndarray, NaN, Inf)
    into standard JSON-compliant Python primitives.
    """
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    elif hasattr(obj, "item"):
        return sanitize_for_json(obj.item())
    elif hasattr(obj, "to_dict"):
        return sanitize_for_json(obj.to_dict())
    return obj

class FastORJSONResponse(ORJSONResponse):
    def render(self, content: Any) -> bytes:
        return orjson.dumps(
            content,
            default=sanitize_for_json,
            option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing LibRE Tab backend engine...")
    discover_and_load_plugins("app.plugins.modules")
    logger.info(f"Loaded {len(registry.all())} statistical plugins.")
    
    # Emit dynamic handshake JSON to stdout once server is fully initialized
    port = getattr(app.state, "port", None)
    if port:
        handshake = {"status": "ready", "port": port}
        sys.stdout.write(json.dumps(handshake) + "\n")
        sys.stdout.flush()
        
    yield


app = FastAPI(
    title="LibRE Tab API",
    description="Schema-Driven Statistical & Reliability Computing Engine for LibRE Tab",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Heartbeat endpoints
@app.post("/api/v1/heartbeat")
@app.get("/api/v1/heartbeat")
@app.post("/heartbeat")
@app.get("/heartbeat")
async def heartbeat_check():
    """
    Heartbeat ping from the frontend to keep the backend alive.
    """
    update_heartbeat()
    return {
        "status": "alive",
        "timestamp": last_heartbeat_time,
        "plugins": len(registry.all()),
    }


class ColumnMeta(BaseModel):
    id: str
    name: str
    type: Optional[str] = "text"


class ComputeRequest(BaseModel):
    data: List[Dict[str, Any]]
    columns: Optional[List[ColumnMeta]] = None
    params: Dict[str, Any]


@app.get("/api/v1/health")
async def health_check():
    update_heartbeat()
    return {
        "status": "online",
        "app": "LibRE Tab Engine",
        "version": "1.0.0",
        "registered_plugins": len(registry.all()),
    }


@app.get("/api/v1/plugins/manifest", response_model=List[PluginManifestItem])
async def get_plugin_manifest():
    """
    Returns the manifest of all auto-discovered statistical plugins,
    including their Pydantic JSON schemas and menu paths.
    """
    update_heartbeat()
    return registry.get_manifest()


@app.post("/api/v1/compute/{plugin_id}")
async def execute_plugin(plugin_id: str, payload: ComputeRequest):
    """
    Validates tabular data and parameters against plugin schema,
    executes computation on a worker thread, and returns structured results and Plotly charts.
    """
    update_heartbeat()
    import anyio.to_thread

    plugin = registry.get(plugin_id)
    if not plugin:
        raise HTTPException(
            status_code=404,
            detail=f"Plugin '{plugin_id}' not found in registry.",
        )

    # Fast Columnar DataFrame Construction
    if payload.data:
        raw_df = pd.DataFrame.from_records(payload.data)
        raw_df.replace(["", "*", "NA", "NaN"], np.nan, inplace=True)
    else:
        raw_df = pd.DataFrame()

    if payload.columns:
        id_to_name = {col.id: col.name for col in payload.columns if col.name and col.name.strip()}
        df = raw_df.rename(columns=id_to_name)
    else:
        df = raw_df

    # Auto-convert numeric columns if they contain numeric data
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass

    # Validate parameters with Pydantic model
    try:
        validated_params = plugin.param_schema.model_validate(payload.params)
    except ValidationError as ve:
        raise HTTPException(
            status_code=422,
            detail={"error": "Parameter validation failed", "errors": ve.errors()},
        )

    # Execute plugin in threadpool to keep the event loop non-blocking
    try:
        raw_result = await anyio.to_thread.run_sync(plugin.execute, df, validated_params)
        
        # Serialize and sanitize result
        if isinstance(raw_result, BaseModel):
            result_dict = raw_result.model_dump()
        elif isinstance(raw_result, dict):
            result_dict = raw_result
        else:
            result_dict = dict(raw_result)

        sanitized_result = sanitize_for_json(result_dict)
        return FastORJSONResponse(content=sanitized_result)
    except Exception as e:
        logger.exception(f"Error executing plugin {plugin_id}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Computation error: {str(e)}",
        )


@app.get("/api/v1/sample-datasets")
async def list_sample_datasets():
    update_heartbeat()
    return [
        {
            "id": k,
            "name": v["name"],
            "description": v["description"],
            "row_count": len(v["rows"]),
            "column_count": len(v["columns"]),
        }
        for k, v in SAMPLE_DATASETS.items()
    ]


@app.get("/api/v1/sample-datasets/{dataset_id}")
async def get_sample_dataset(dataset_id: str):
    update_heartbeat()
    if dataset_id not in SAMPLE_DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    data = SAMPLE_DATASETS[dataset_id]
    return {
        "id": dataset_id,
        "name": data["name"],
        "description": data["description"],
        "columns": data["columns"],
        "rows": data["rows"],
    }
