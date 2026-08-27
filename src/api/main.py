"""
FastAPI entrypoint for ControlPlane.ai
"""
from fastapi import FastAPI

app = FastAPI(title="ControlPlane.ai", description="Model-agnostic runtime governance layer")

@app.get("/health")
async def health():
    return {"status": "ok"}
