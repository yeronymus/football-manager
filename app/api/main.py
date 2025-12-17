from fastapi import FastAPI, Request
from aiogram.types import Update
from app.bot.main import bot, dp, start_bot, stop_bot
from app.config import settings
import logging

from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.on_event("startup")
async def on_startup():
    from app.db.database import init_models
    from app.scheduler.main import start_scheduler
    await init_models()
    await start_scheduler()
    
    if not settings.USE_POLLING:
        await start_bot()

from fastapi.staticfiles import StaticFiles

from app.api.endpoints import router as game_router
app.include_router(game_router, prefix="/api")

app.mount("/web", StaticFiles(directory="app/web", html=True), name="web")

@app.on_event("shutdown")
async def on_shutdown():
    await stop_bot()

@app.post("/webhook")
async def webhook(request: Request):
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"message": "Football Manager Bot API is running"}
