import hmac
import logging
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api.routers import admin, ads, dashboard, games, inventory, live, nss, platform, users, voting
from app.bot.instance import bot
from app.bot.main import dp, start_bot, stop_bot
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_enable_api_docs = settings.debug or settings.app_env != "production"

app = FastAPI(
    title="Sports & Team Logistics Platform API",
    docs_url="/docs" if _enable_api_docs else None,
    redoc_url="/redoc" if _enable_api_docs else None,
    openapi_url="/openapi.json" if _enable_api_docs else None,
)

Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.middleware("http")
async def add_no_cache_header_for_web(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/web"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


_allowed_origins = ["https://t.me", "https://web.telegram.org", settings.webapp_url]
if settings.app_env == "local_dev":
    _allowed_origins.extend(["http://localhost:8000", "http://127.0.0.1:8000"])

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    try:
        if settings.run_migrations:
            from app.db.database import init_models

            await init_models()

        from app.scheduler.main import start_scheduler

        if settings.run_scheduler:
            await start_scheduler(paused=False)
        else:
            await start_scheduler(paused=True)

        if settings.run_consumer:
            from app.infrastructure.messaging import consumer as msg_consumer

            await msg_consumer.start()

        if settings.run_bot:
            import asyncio

            async def safe_start_bot():
                try:
                    await start_bot()
                except Exception as e:
                    logger.error(f"Failed to set commands/webhook: {e}")

            logger.info(
                f"Startup config: APP_ENV={settings.app_env}, USE_POLLING={settings.use_polling}"
            )

            if not hasattr(app.state, "bg_tasks"):
                app.state.bg_tasks = []

            if not settings.use_polling:
                logger.info("Starting Bot in Webhook mode...")
                setup_task = asyncio.create_task(safe_start_bot())
                app.state.bg_tasks.append(setup_task)
            else:
                logger.info("Starting Bot in Polling mode...")
                await bot.delete_webhook(drop_pending_updates=True)
                polling_task = asyncio.create_task(dp.start_polling(bot))
                app.state.bg_tasks.append(polling_task)
                setup_task = asyncio.create_task(safe_start_bot())
                app.state.bg_tasks.append(setup_task)
        elif not settings.bot_username or settings.bot_username == "sports_manager_bot":
            from app.core.events import event_bus
            from app.infrastructure.messaging import producer

            event_bus.set_stream_forwarder(producer.publish_message)
            try:
                me = await bot.get_me()
                if getattr(me, "username", None):
                    settings.bot_username = me.username
                    logger.info(f"API container resolved bot username: {settings.bot_username}")
            except Exception as e:
                logger.warning(f"API container could not resolve bot username via get_me: {e}")

        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)


@app.on_event("shutdown")
async def on_shutdown():
    if settings.run_consumer:
        from app.infrastructure.messaging import consumer as msg_consumer

        try:
            await msg_consumer.stop()
        except Exception as e:
            logger.error(f"Failed to stop messaging consumer: {e}")

    if settings.run_scheduler:
        try:
            from app.scheduler.main import stop_scheduler

            await stop_scheduler()
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")

    if settings.run_bot:
        await stop_bot()


# Routers
app.include_router(live.router, prefix="/api", tags=["LiveStreamAndCalendar"])
app.include_router(platform.router, prefix="/api/v1", tags=["Platform"])
app.include_router(platform.router, prefix="/api", tags=["PlatformLegacy"])
app.include_router(games.router, prefix="/api", tags=["Games"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])
app.include_router(admin.router, prefix="/api/admin", tags=["AdminNew"])
app.include_router(voting.router, prefix="/api", tags=["Voting"])
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(ads.router, prefix="/api", tags=["Ads"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(inventory.router, prefix="/api", tags=["Inventory"])
app.include_router(inventory.router, prefix="/api/dashboard", tags=["InventoryDashboard"])

if _enable_api_docs:
    app.include_router(nss.router, prefix="/api", tags=["Diagnostics"])


@app.get("/web", include_in_schema=False)
@app.get("/web/", include_in_schema=False)
async def redirect_web_root():
    return RedirectResponse(url="/web/profile.html")


app.mount("/web", StaticFiles(directory="app/web", html=True), name="web")


@app.get("/health", tags=["Health"])
@app.get("/health/live", tags=["Health"])
async def health_live():
    """Kubernetes liveness probe: verifies ASGI event-loop responsiveness."""
    return {"status": "ok", "env": settings.app_env}


@app.get("/health/ready", tags=["Health"])
async def health_ready():
    """Kubernetes readiness probe: verifies live PostgreSQL and Redis connectivity."""
    from app.core.services.cache import cache_service
    from app.db.database import async_session_maker

    checks = {"postgres": "down", "redis": "down"}
    healthy = True

    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
            checks["postgres"] = "up"
    except Exception as e:
        healthy = False
        logger.error(f"Readiness check PostgreSQL failure: {e}")

    try:
        if await cache_service.ping():
            checks["redis"] = "up"
    except Exception as e:
        healthy = False
        logger.error(f"Readiness check Redis failure: {e}")

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if healthy else "degraded", "checks": checks},
    )


@app.post("/api/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    expected_token = settings.webhook_secret_token
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, expected_token
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")
    from aiogram.types import Update

    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
async def root():
    return {"message": "Sports & Team Logistics Platform API is running"}
