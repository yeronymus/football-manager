from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "minimal"}

@app.get("/")
async def root():
    return {"message": "Minimal App Works"}
