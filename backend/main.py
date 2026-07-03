import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.detect import router as detect_router
from .routers.chat import router as chat_router
from .routers.config import router as config_router
from .routers.rag import router as rag_router

app = FastAPI(title="ForMAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(detect_router)
app.include_router(chat_router)
app.include_router(config_router)
app.include_router(rag_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
