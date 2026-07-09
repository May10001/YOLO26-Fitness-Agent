import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from code.pose_analyzer import EXERCISE_STANDARDS
from ..config import load_api_config

EXERCISE_LIST = list(EXERCISE_STANDARDS.keys())

router = APIRouter(prefix="/api")

CHAT_SYSTEM_PROMPT = """你是一位拥有10年经验的资深健身教练和运动科学专家，精通运动生物力学、康复训练和营养学。

## 回答要求
1. **详细具体**：每个回答至少150字，充分展开论述，包含原理、步骤和注意事项
2. **知识深度**：引用运动科学原理（如生物力学、肌肉解剖、能量系统）来解释你的建议
3. **分点结构**：使用清晰的层次结构（问题分析→原因解释→解决方案→注意事项）
4. **可操作**：给出具体、可量化的指导（精确的角度、次数、节奏、时长）
5. **个性化**：根据用户水平调整建议，提供进阶/退阶方案
6. **安全第一**：优先标注风险动作和禁忌人群

## 回答格式
- 先分析问题根因（为什么会出现这个问题）
- 再给出解决方案（具体怎么做，分步骤）
- 最后补充进阶知识（相关训练原理、辅助练习）

请用中文回答，保持专业、鼓励、清晰的语气。"""

# In-memory session store for active training sessions
_active_sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str
    pose_context: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    reply: str
    diagnosis: dict | None = None           # Phase 3: LLM diagnostic JSON
    recommended_cues: list[dict] | None = None  # Phase 3: extracted cue list


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    config = load_api_config()
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
        if req.stream:
            return StreamingResponse(
                _stream_chat(config, req.message),
                media_type="text/event-stream",
            )
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
                max_tokens=1200,
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


async def _stream_chat(config: dict, message: str):
    """SSE streaming for generic chat."""
    from openai import OpenAI
    queue: asyncio.Queue = asyncio.Queue()

    def _run():
        try:
            client = OpenAI(
                api_key=config["api_key"],
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            stream = client.chat.completions.create(
                model=config.get("model_code", "qwen-plus"),
                messages=[
                    {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                temperature=0.7,
                max_tokens=1200,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    queue.put_nowait(json.dumps({'text': delta.content}))
            queue.put_nowait(json.dumps({'done': True}))
        except Exception as e:
            queue.put_nowait(json.dumps({'error': str(e)}))

    asyncio.get_event_loop().run_in_executor(None, _run)

    while True:
        data = await queue.get()
        yield f"data: {data}\n\n"
        if '"done": true' in data or '"error"' in data:
            break


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


PLAN_AI_SYSTEM_PROMPT = """你是一名资深健身教练和运动训练专家。根据用户的画像和需求，生成一份详细、结构化、富含知识点的训练计划。

## 计划要求
1. **详细说明**：每个动作附带2-3句要点说明（目标肌群、发力技巧、常见错误）
2. **科学依据**：在warmup/cooldown的notes中简短说明选择这些动作的运动科学原理
3. **个性化**：根据用户伤病历史、偏好、水平精确调整动作选择
4. **可量化**：每个参数（次数、组数、休息、节奏）都基于训练目标科学设定

## 训练参数参考
- 增肌(hypertrophy): 8-12次 × 3-4组, 休息60-90s, 节奏2-1-2
- 力量(strength): 5-8次 × 4-5组, 休息90-120s, 节奏3-1-1
- 减脂(weight_loss): 12-20次 × 3组, 休息30-45s, 节奏1-0-1
- 新手: 10-12次 × 2-3组, 休息60s

## 安全规则
- 有伤病历史时，用替代动作避开风险区域，并在notes中说明
- 排除用户标记为"不想做"的动作

## 可用动作列表
深蹲, 俯卧撑, 平板支撑, 卷腹, 开合跳, 引体向上, 臀桥, 高抬腿, 肩推, 侧平举

## 输出格式 (严格 JSON)
```json
{
  "plan_name": "计划名称",
  "plan_type": "strength|endurance|weight_loss|general",
  "total_duration_minutes": 30,
  "warmup": [
    {"exercise": "动作名", "reps": 20, "rest_after_seconds": 30}
  ],
  "blocks": [
    {
      "name": "训练块名称",
      "rounds": 1,
      "exercises": [
        {"exercise": "动作名", "sets": 3, "reps": 12, "rest_seconds": 60, "notes": "要点"}
      ]
    }
  ],
  "cooldown": [
    {"exercise": "动作名", "duration_seconds": 30}
  ]
}
```

## 规则
1. 所有 exercise 必须是可用动作列表中的名称
2. warmup 用开合跳/高抬腿等有氧动作，reps 10-30
3. cooldown 用平板支撑等静态动作，duration_seconds 20-60
4. 根据用户伤病历史排除不合适动作
5. 根据用户偏好增加/减少动作
6. 每周训练天数决定训练量
7. reps/sets 根据水平调整：新手8-10次，中级10-15次，高级15-20次
8. 只输出JSON，不输出其他内容
"""

PLAN_AI_USER_TEMPLATE = """## 用户画像
- 年龄: {age}
- 身高: {height_cm}cm / 体重: {weight_kg}kg
- 健身目标: {goal}
- 训练水平: {fitness_level}
- 每周训练天数: {training_days_per_week}
- 伤病史: {injury_history}
- 喜欢动作: {liked_exercises}
- 不想做: {disliked_exercises}

## 用户需求
{user_request}

请生成一份完整的训练计划JSON。"""


@router.post("/plan/ai-generate")
async def ai_generate_plan(req: dict):
    """Generate a workout plan using LLM based on user profile and request."""
    profile = req.get("profile", {})
    user_request = req.get("user_request", "")

    if not user_request:
        return {"error": "请描述你的训练需求（例如：我想练腿，30分钟，中等强度）"}

    # Load API config
    config = load_api_config()
    if not config.get("use_remote") or not config.get("api_key"):
        return {"error": "AI计划生成需要配置 DashScope API，请在 data/api_config.json 中设置"}

    # Build prompts
    liked = ", ".join(profile.get("liked_exercises", [])) or "无偏好"
    disliked = ", ".join(profile.get("disliked_exercises", [])) or "无"
    injury = profile.get("injury_history", "") or "无"

    goal_map = {
        "strength": "增肌", "hypertrophy": "增肌塑形",
        "endurance": "耐力", "weight_loss": "减脂", "general": "综合健康",
    }
    level_map_cn = {"beginner": "新手", "intermediate": "中级", "advanced": "高级"}

    user_prompt = PLAN_AI_USER_TEMPLATE.format(
        age=profile.get("age", 25),
        height_cm=profile.get("height_cm", 170),
        weight_kg=profile.get("weight_kg", 70),
        goal=goal_map.get(profile.get("goal", "general"), "综合"),
        fitness_level=level_map_cn.get(profile.get("fitness_level", "beginner"), "新手"),
        training_days_per_week=profile.get("training_days_per_week", 3),
        injury_history=injury,
        liked_exercises=liked,
        disliked_exercises=disliked,
        user_request=user_request,
    )

    try:
        from openai import OpenAI

        def _call_api():
            client = OpenAI(
                api_key=config["api_key"],
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            completion = client.chat.completions.create(
                model=config.get("model_code", "qwen-plus"),
                messages=[
                    {"role": "system", "content": PLAN_AI_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            return completion.choices[0].message.content

        import asyncio
        reply = await asyncio.get_event_loop().run_in_executor(None, _call_api)

        # Parse JSON from LLM response (handle markdown code fences)
        reply_clean = reply.strip()
        if reply_clean.startswith("```"):
            lines = reply_clean.split("\n")
            # Remove first line (```json or ```) and last line (```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            reply_clean = "\n".join(lines)

        import json as _json
        plan = _json.loads(reply_clean)

        # Validate exercise names
        valid_exercises = set(EXERCISE_LIST)
        all_steps = list(plan.get("warmup", []))
        for block in plan.get("blocks", []):
            all_steps.extend(block.get("exercises", []))
        all_steps.extend(plan.get("cooldown", []))

        for step in all_steps:
            ex_name = step.get("exercise", "")
            if ex_name not in valid_exercises:
                step["exercise"] = "深蹲"  # fallback

        return {"plan": plan}

    except _json.JSONDecodeError:
        return {"error": "AI 生成的计划格式有误，请重试", "raw": reply_clean[:500]}
    except Exception as e:
        return {"error": f"AI 计划生成失败: {str(e)}"}
