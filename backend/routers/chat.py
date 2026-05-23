import sys
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from code.pose_analyzer import EXERCISE_STANDARDS

from ..services.agent_service import get_agent

EXERCISE_LIST = list(EXERCISE_STANDARDS.keys())

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str
    pose_context: str | None = None


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    agent = get_agent()
    reply = agent.chat(req.message, pose_context=req.pose_context)
    return ChatResponse(reply=reply)


@router.get("/exercises")
async def list_exercises():
    return {"exercises": EXERCISE_LIST}


@router.post("/session/start")
async def session_start():
    return {"status": "started"}


@router.post("/session/stop")
async def session_stop():
    return {"status": "stopped"}
