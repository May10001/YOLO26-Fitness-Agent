import sys
import json
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from code.pose_analyzer import EXERCISE_STANDARDS

EXERCISE_LIST = list(EXERCISE_STANDARDS.keys())
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

router = APIRouter(prefix="/api")

CHAT_SYSTEM_PROMPT = "你是一位专业的健身教练AI助手，擅长运动指导、动作纠正和训练规划。回答简洁专业。"

# In-memory session store for active training sessions
_active_sessions: dict[str, dict] = {}


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
    diagnosis: dict | None = None           # Phase 3: LLM diagnostic JSON
    recommended_cues: list[dict] | None = None  # Phase 3: extracted cue list


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    config = _load_api_config()
    remote_ok = bool(config.get("use_remote") and config.get("api_key"))

    # --- Path A: pose_context provided → always use LangGraph CoachAgent ---
    # The CoachAgent internally checks API availability via call_dashscope_node.
    # When the API is not configured it returns a clear Chinese error message
    # instead of crashing. This path never touches transformers.
    if req.pose_context:
        try:
            from code.langgraph_agent.agent import CoachAgent
            from code.langgraph_agent.state import state_from_dict
            agent = CoachAgent(api_config=config)

            # Parse pose_context JSON to build full state
            try:
                data = json.loads(req.pose_context)
                chat_mode = data.get("chat_mode", "reactive")
            except json.JSONDecodeError:
                data = {}
                chat_mode = "reactive"

            state = state_from_dict(
                data, chat_mode=chat_mode,
                user_message=req.message,
                api_config=config,
            )
            result = agent._graph.invoke(state)

            reply = result.get("guidance_text") or result.get("response", "")
            diagnosis = result.get("diagnosis_json") or None
            cues = result.get("recommended_cues") or None
        except Exception as e:
            reply = f"AI教练服务异常: {e}"
            diagnosis = None
            cues = None
        return ChatResponse(reply=reply, diagnosis=diagnosis, recommended_cues=cues)

    # --- Path B: generic chat (no pose_context), remote API available ---
    if remote_ok:
        try:
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
        return ChatResponse(reply=reply)

    # --- Path C: generic chat, no remote → local model (requires transformers) ---
    try:
        from ..services.agent_service import get_agent
        agent = get_agent()
        reply = agent.chat(req.message, pose_context=req.pose_context)
    except Exception as e:
        reply = (
            "本地模型不可用（需安装transformers）。"
            "请在项目根目录的 data/api_config.json 中配置 DashScope 远程 API：\n"
            '{"use_remote": true, "api_key": "sk-xxx", "model_code": "qwen2.5-7b-instruct-xxx"}'
        )

    return ChatResponse(reply=reply)


@router.get("/exercises")
async def list_exercises():
    return {"exercises": EXERCISE_LIST}


@router.post("/session/start")
async def session_start(req: dict):
    """Start a training session — create a session record."""
    exercise = req.get("exercise", "深蹲")
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    _active_sessions[session_id] = {
        "session_id": session_id,
        "exercise": exercise,
        "start_time": datetime.now().isoformat(),
        "duration_seconds": 0.0,
        "total_reps": 0,
        "best_score": 0.0,
        "avg_score": 0.0,
        "errors": {},
    }
    return {"status": "started", "session_id": session_id}


@router.post("/session/stop")
async def session_stop(req: dict):
    """Stop a training session — finalize with stats from detector."""
    session_id = req.get("session_id", "")
    stats = req.get("stats", {})
    if session_id in _active_sessions:
        session = _active_sessions[session_id]
        session["duration_seconds"] = req.get("duration_seconds", 0.0)
        session["total_reps"] = stats.get("total_reps", 0)
        session["best_score"] = stats.get("best_score", 0.0)
        session["avg_score"] = stats.get("avg_score", 0.0)
        session["errors"] = stats.get("error_counts", {})

        # Persist to JSON
        try:
            from code.workout_app import HistoryManager
            from code.workout_app import SessionRecord as WkSessionRecord
            mgr = HistoryManager()
            record = WkSessionRecord(
                session_id=session["session_id"],
                exercise=session["exercise"],
                start_time=session["start_time"],
                duration_seconds=session["duration_seconds"],
                total_reps=session["total_reps"],
                best_score=session["best_score"],
                avg_score=session["avg_score"],
                scores=[],
                errors=session["errors"],
            )
            mgr.save(record)
        except Exception:
            pass  # History persistence failure is non-critical

        _active_sessions.pop(session_id, None)
        return {"status": "stopped", "session": session}
    return {"status": "not_found"}


@router.get("/sessions")
async def list_sessions():
    """Return recent training history (up to 30 sessions)."""
    try:
        from code.workout_app import HistoryManager
        mgr = HistoryManager()
        records = mgr.load_recent(30)
        return {
            "sessions": [
                {
                    "session_id": r.session_id,
                    "exercise": r.exercise,
                    "start_time": r.start_time,
                    "duration_seconds": r.duration_seconds,
                    "total_reps": r.total_reps,
                    "best_score": r.best_score,
                    "avg_score": r.avg_score,
                    "errors": r.errors,
                }
                for r in records
            ]
        }
    except Exception:
        return {"sessions": []}


# ---------------------------------------------------------------------------
# User profile + plan generation
# ---------------------------------------------------------------------------

@router.get("/profile/{name}")
async def get_profile(name: str):
    """Load or create a user profile."""
    try:
        from code.planning.user_profile import UserProfile
        profile = UserProfile.load(name)
        return {
            "name": profile.name,
            "age": profile.age,
            "weight_kg": profile.weight_kg,
            "height_cm": profile.height_cm,
            "fitness_level": profile.fitness_level.value if hasattr(profile.fitness_level, 'value') else str(profile.fitness_level),
            "goal": profile.goal.value if hasattr(profile.goal, 'value') else str(profile.goal),
            "equipment": profile.equipment.value if hasattr(profile.equipment, 'value') else str(profile.equipment),
        }
    except Exception as e:
        return {"name": name, "error": str(e)}


@router.post("/profile")
async def save_profile(req: dict):
    """Save a user profile and persist to JSON."""
    try:
        from code.planning.user_profile import UserProfile, FitnessLevel, FitnessGoal, Equipment
        level_map = {"beginner": FitnessLevel.BEGINNER, "intermediate": FitnessLevel.INTERMEDIATE, "advanced": FitnessLevel.ADVANCED}
        goal_map = {"strength": FitnessGoal.STRENGTH, "hypertrophy": FitnessGoal.HYPERTROPHY, "endurance": FitnessGoal.ENDURANCE, "weight_loss": FitnessGoal.WEIGHT_LOSS, "general": FitnessGoal.GENERAL}
        equip_map = {"none": Equipment.NONE, "mat": Equipment.MAT, "dumbbells": Equipment.DUMBBELLS, "resistance_band": Equipment.RESISTANCE_BAND, "full_gym": Equipment.FULL_GYM}

        profile = UserProfile(
            name=req.get("name", "用户"),
            age=int(req.get("age", 25)),
            weight_kg=float(req.get("weight_kg", 70)),
            height_cm=float(req.get("height_cm", 170)),
            fitness_level=level_map.get(req.get("fitness_level", "beginner"), FitnessLevel.BEGINNER),
            goal=goal_map.get(req.get("goal", "general"), FitnessGoal.GENERAL),
            equipment=equip_map.get(req.get("equipment", "mat"), Equipment.MAT),
        )
        profile.save()
        return {"status": "saved", "name": profile.name}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/plan/generate")
async def generate_plan(req: dict):
    """Generate a weekly workout plan from user profile data."""
    try:
        from code.planning.user_profile import UserProfile, FitnessLevel, FitnessGoal, Equipment
        from code.planning.plan_generator import PlanGenerator

        level_map = {"beginner": FitnessLevel.BEGINNER, "intermediate": FitnessLevel.INTERMEDIATE, "advanced": FitnessLevel.ADVANCED}
        goal_map = {"strength": FitnessGoal.STRENGTH, "hypertrophy": FitnessGoal.HYPERTROPHY, "endurance": FitnessGoal.ENDURANCE, "weight_loss": FitnessGoal.WEIGHT_LOSS, "general": FitnessGoal.GENERAL}
        equip_map = {"none": Equipment.NONE, "mat": Equipment.MAT, "dumbbells": Equipment.DUMBBELLS, "resistance_band": Equipment.RESISTANCE_BAND, "full_gym": Equipment.FULL_GYM}

        profile = UserProfile(
            name=req.get("name", "用户"),
            age=int(req.get("age", 25)),
            weight_kg=float(req.get("weight_kg", 70)),
            height_cm=float(req.get("height_cm", 170)),
            fitness_level=level_map.get(req.get("fitness_level", "beginner"), FitnessLevel.BEGINNER),
            goal=goal_map.get(req.get("goal", "general"), FitnessGoal.GENERAL),
            equipment=equip_map.get(req.get("equipment", "mat"), Equipment.MAT),
        )
        generator = PlanGenerator(profile)
        plan = generator.generate_weekly_plan()

        return {
            "user_name": plan.user_name,
            "goal": plan.goal,
            "level": plan.level,
            "week_start": plan.week_start,
            "days": [
                {
                    "day": d.day,
                    "focus": d.focus,
                    "exercises": [
                        {"name": e.name, "sets": e.sets, "reps": e.reps, "rest_seconds": e.rest_seconds, "notes": e.notes}
                        for e in d.exercises
                    ],
                }
                for d in plan.days
            ],
        }
    except Exception as e:
        return {"error": str(e)}
