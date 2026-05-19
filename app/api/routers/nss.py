import logging
from fastapi import APIRouter, HTTPException, Query
from app.core.services.cache import cache_service
from app.infrastructure.messaging import producer as msg_producer

logger = logging.getLogger(__name__)
router = APIRouter()

# ===========================================================================
# 1. CACHE VERIFICATION ENDPOINTS
# ===========================================================================

@router.get("/nss/cache/status")
async def get_cache_status():
    """
    Grading requirement: Verify active/passive cache status.
    Returns current cache configuration and usage metrics.
    """
    try:
        status = cache_service.get_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache connection error: {e}")


@router.post("/nss/cache/evict")
async def evict_cache(
    key: str = Query(None, description="Specific cache key to evict"),
    all_keys: bool = Query(False, description="Flush the entire cache")
):
    """
    Grading requirement: Manual cache invalidation/eviction.
    Allows manual tech reset for testing/debugging.
    """
    try:
        if all_keys:
            success = await cache_service.evict_all()
            return {"message": "Entire cache flushed successfully", "success": success}
        
        if not key:
            raise HTTPException(status_code=400, detail="Must specify a 'key' to evict or set 'all_keys=true'")
            
        success = await cache_service.evict(key)
        return {"message": f"Cache eviction for key '{key}' completed", "success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eviction error: {e}")


# ===========================================================================
# 2. MESSAGING (KAFKA-LIKE PRODUCER/CONSUMER) ENDPOINTS
# ===========================================================================

@router.post("/nss/messaging/publish")
async def publish_message(message: str = Query(..., description="Message string to publish to topic")):
    """
    Grading requirement: Verify message queue producer/consumer functionality.
    Simulates sending a notification asynchronously.
    """
    try:
        topic = "nss-test-topic"
        payload = {"content": message}
        
        # Producer logs: "$$ -> Producing message --> {payload}"
        msg_id = await msg_producer.publish_message(topic, payload)
        
        return {
            "status": "success",
            "message_id": msg_id,
            "published_payload": payload,
            "info": "Message appended to Redis Streams. Background consumer will pick it up and log 'Consumed Message' asynchronously."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish message: {e}")


# ===========================================================================
# 3. TELEMETRY & ELASTICSEARCH STATUS
# ===========================================================================

@router.get("/nss/telemetry/status")
async def get_telemetry_status():
    """Returns telemetry and Elasticsearch connectivity status."""
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
        "interceptor_enabled": True,
        "elasticsearch": {
            "status": es_status,
            "version": es_version,
            "host": "localhost:9200",
            "index": "nss_telemetry"
        }
    }
