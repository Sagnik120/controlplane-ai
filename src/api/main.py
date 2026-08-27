from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from src.api.routes import router as api_router

app = FastAPI(title="ControlPlane-AI")

# Mount API routes
app.include_router(api_router, prefix="/api")

# Get absolute path for UI folder
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
ui_path = os.path.join(project_root, "src/ui")
os.makedirs(ui_path, exist_ok=True)

@app.get("/health")
def health_check():
    return {"status": "ok", "system": "ControlPlane-AI Dashboard"}

# Mount Static UI (Vanilla HTML/CSS/JS) at the very bottom so it doesn't intercept /health
app.mount("/", StaticFiles(directory=ui_path, html=True), name="static")
