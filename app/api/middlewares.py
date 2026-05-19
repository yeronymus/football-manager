import time
import logging
import asyncio
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Elasticsearch configuration
ES_URL = "http://localhost:9200/nss_telemetry/_doc"
ES_ENABLED = True

class TelemetryInterceptorMiddleware(BaseHTTPMiddleware):
    """
    DESIGN PATTERN: INTERCEPTOR PATTERN (FASTAPI MIDDLEWARE)
    Intercepts incoming HTTP requests, records telemetry, and exports logs asynchronously to Elasticsearch.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        
        # Intercept and process request
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        
        # Log incoming request before controller (Expected Interceptor behavior)
        logger.info(f"🔌 [Interceptor] Incoming Request: {method} {path} from IP: {client_ip}")
        
        response = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise e
        finally:
            duration = (time.time() - start_time) * 1000 # ms
            logger.info(f"✅ [Interceptor] Response Status: {status_code} | Duration: {duration:.2f}ms")
            
            # Export telemetry to Elasticsearch asynchronously
            if ES_ENABLED:
                telemetry_log = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "method": method,
                    "path": path,
                    "client_ip": client_ip,
                    "status_code": status_code,
                    "duration_ms": duration
                }
                asyncio.create_task(self._send_to_elasticsearch(telemetry_log))
                
        return response

    async def _send_to_elasticsearch(self, log_data: dict):
        """Asynchronously index request logs to Elasticsearch with graceful fail-safe fallback."""
        try:
            import httpx
            # 1. Non-blocking asynchronous POST to Elasticsearch
            async with httpx.AsyncClient(timeout=0.5) as client:
                res = await client.post(ES_URL, json=log_data)
                if res.status_code in [200, 201]:
                    logger.debug("🎯 Telemetry log successfully indexed in Elasticsearch.")
                else:
                    logger.debug(f"Elasticsearch returned status {res.status_code} during telemetry write.")
        except ImportError:
            logger.debug("httpx not installed, skipping Elasticsearch export.")
        except Exception as e:
            # Silence connection errors to keep the application 100% stable if ES is down
            logger.debug(f"Elasticsearch not reachable at localhost:9200 (skipping indexing): {e}")
