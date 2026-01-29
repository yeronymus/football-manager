from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

from app.config import settings
from app.bot.main import bot, dp, start_bot, stop_bot
from app.api.endpoints import router as game_router

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Football Manager Bot API")

# Middlewares
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
        from app.db.database import init_models
        from app.scheduler.main import start_scheduler
        
        await init_models()
        await start_scheduler()
        
        # STARTUP LOGIC
        # If Webhook: we await start_bot (critical path).
        # If Polling: we run start_bot in background to avoid blocking startup (network logs).
        
        async def safe_start_bot():
            try:
                await start_bot()
            except Exception as e:
                logger.error(f"Failed to set commands/webhook: {e}")

        logger.info(f"Configuration: USE_POLLING={settings.use_polling}, WEBHOOK_URL={settings.webhook_url}")

        if not settings.use_polling:
            # Webhook mode: Block to ensure it's set
            logger.info("Starting in Webhook mode...")
            await safe_start_bot()
        else:
            # Polling mode: Background
            import asyncio
            logger.info("Starting in Polling mode...")
            # Start polling
            logger.info("Deleting webhook before polling...")
            await bot.delete_webhook(drop_pending_updates=True)
            
            logger.info("Launching start_polling task...")
            asyncio.create_task(dp.start_polling(bot))
            
            # Start commands setup in background
            logger.info("Launching safe_start_bot task...")
            asyncio.create_task(safe_start_bot())
            logger.info("Bot started in Polling Mode (Background setup)")
            
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)

@app.on_event("shutdown")
async def on_shutdown():
    await stop_bot()

# Routes
app.include_router(game_router, prefix="/api")
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
