from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

from app.config import settings
from app.bot.instance import bot
from app.bot.main import dp, start_bot, stop_bot
from app.api.routers import games, admin, voting, users, ads, dashboard, nss

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Football Manager Bot API")

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)

# Middlewares
from app.api.middlewares import TelemetryInterceptorMiddleware
app.add_middleware(TelemetryInterceptorMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://t.me", "https://web.telegram.org", settings.webapp_url],
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
        
        if settings.run_scheduler:
            from app.scheduler.main import start_scheduler
            await start_scheduler()
        
        if settings.run_consumer:
            # Start persistent messaging consumer for volatile event safety
            from app.infrastructure.messaging import consumer as msg_consumer
            await msg_consumer.start()
        
        if settings.run_bot:
            # STARTUP LOGIC
            # If Webhook: we await start_bot (critical path).
            # If Polling: we run start_bot in background to avoid blocking startup (network logs).
            
            async def safe_start_bot():
                try:
                    await start_bot()
                except Exception as e:
                    logger.error(f"Failed to set commands/webhook: {e}")

            logger.info(f"Configuration: USE_POLLING={settings.use_polling}, WEBHOOK_URL={settings.webhook_url}")

            import asyncio
            if not hasattr(app.state, "bg_tasks"):
                app.state.bg_tasks = []

            if not settings.use_polling:
                # Webhook mode: Background setup
                logger.info("Starting in Webhook mode (Background setup)...")
                setup_task = asyncio.create_task(safe_start_bot())
                app.state.bg_tasks.append(setup_task)
            else:
                # Polling mode: Background
                logger.info("Starting in Polling mode...")
                # Start polling
                logger.info("Deleting webhook before polling...")
                await bot.delete_webhook(drop_pending_updates=True)
                
                logger.info("Launching start_polling task...")
                polling_task = asyncio.create_task(dp.start_polling(bot))
                app.state.bg_tasks.append(polling_task)
                
                # Start commands setup in background
                logger.info("Launching safe_start_bot task...")
                setup_task = asyncio.create_task(safe_start_bot())
                app.state.bg_tasks.append(setup_task)
                
                logger.info("Bot started in Polling Mode (Background setup)")
            
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
app.include_router(games.router, prefix="/api", tags=["Games"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])
app.include_router(admin.router, prefix="/api/admin", tags=["AdminNew"])
app.include_router(voting.router, prefix="/api", tags=["Voting"])
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(ads.router, prefix="/api", tags=["Ads"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(nss.router, prefix="/api", tags=["NSS Verification"])

app.mount("/web", StaticFiles(directory="app/web", html=True), name="web")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/webhook")
async def webhook(request: Request):
    from aiogram.types import Update
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"message": "Football Manager Bot API is running"}
