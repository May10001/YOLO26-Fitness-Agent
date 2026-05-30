import sys
import json
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from code.pose_analyzer import EXERCISE_STANDARDS

EXERCISE_LIST = list(EXERCISE_STANDARDS.keys())
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

router = APIRouter(prefix="/api")

CHAT_SYSTEM_PROMPT = "你是一位专业的健身教练AI助手，擅长运动指导、动作纠正和训练规划。回答简洁专业。"


def _load_api_config() -> dict:
    for name in ["api_config.json", "data/api_config.json"]:
        path = PROJECT_ROOT / name
        if path.exists():
            return json.loads(path.read_text())
    return {"use_remote": False, "api_key": "", "model_code": ""}


class ChatRequest(BaseModel):
    message: str
    pose_context: str | None = None


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    config = _load_api_config()

    if config.get("use_remote") and config.get("api_key"):
        try:
            # LangGraph coaching path: use structured pose_context + coach prompts
            if req.pose_context:
                from code.langgraph_agent.agent import CoachAgent
                agent = CoachAgent(api_config=config)
                reply = agent.chat(req.message, pose_context_str=req.pose_context)
            else:
                # Original generic DashScope path (unchanged)
                from openai import OpenAI
                client = OpenAI(
                    api_key=config["api_key"],
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                )
                completion = client.chat.completions.create(
                    model=config.get("model_code", "qwen-plus"),
                    messages=[
                        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                        {"role": "user", "content": req.message},
                    ],
                    temperature=0.7,
                    max_tokens=800,
                )
                reply = completion.choices[0].message.content
        except Exception as e:
            reply = f"远程API调用失败: {e}"
    else:
        try:
            from ..services.agent_service import get_agent
            agent = get_agent()
            reply = agent.chat(req.message, pose_context=req.pose_context)
        except Exception as e:
            reply = f"本地模型不可用（需安装transformers），请配置远程API。错误: {e}"

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
