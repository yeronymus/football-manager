import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.auth import require_system_owner
from app.core.services.cache import cache_service
from app.infrastructure.messaging import producer as msg_producer

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_system_owner)])


@router.get("/nss/cache/status")
async def get_cache_status():
    """Returns current cache configuration and usage metrics (System Owner only)."""
    try:
        return cache_service.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache connection error: {e}")


@router.post("/nss/cache/evict")
async def evict_cache(
    key: str = Query(None, description="Specific cache key to evict"),
    all_keys: bool = Query(False, description="Flush the isolated cache logical DB"),
):
    """Manual cache invalidation restricted to System Owners on isolated Redis Cache DB."""
    if not all_keys and not key:
        raise HTTPException(
            status_code=400,
            detail="Must specify a 'key' to evict or set 'all_keys=true'",
        )
    try:
        if all_keys:
            success = await cache_service.evict_all()
            return {"message": "Cache logical database flushed successfully", "success": success}

        success = await cache_service.evict(key)
        return {"message": f"Cache eviction for key '{key}' completed", "success": success}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eviction error: {e}")


@router.post("/nss/messaging/publish")
async def publish_message(
    message: str = Query(..., description="Diagnostic event message to publish"),
):
    """Diagnostic Redis Streams producer check restricted to System Owners."""
    try:
        topic = "diagnostic-topic"
        payload = {"content": message}
        msg_id = await msg_producer.publish_message(topic, payload)
        return {
            "status": "success",
            "message_id": msg_id,
            "published_payload": payload,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish message: {e}")


@router.get("/nss/telemetry/status")
async def get_telemetry_status():
    """Returns diagnostic telemetry status (System Owner only)."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            res = await client.get("http://localhost:9200/")
            if res.status_code == 200:
                es_status = "connected"
                es_version = res.json().get("version", {}).get("number", "unknown")
            else:
                es_status = f"error ({res.status_code})"
                es_version = None
    except Exception as e:
        es_status = f"unavailable ({type(e).__name__})"
        es_version = None

    return {
        "interceptor_enabled": False,
        "elasticsearch": {
            "status": es_status,
            "version": es_version,
            "host": "localhost:9200",
        },
    }
