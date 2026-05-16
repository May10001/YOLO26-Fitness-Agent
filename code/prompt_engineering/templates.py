"""
Prompt templates for fitness guidance generation.

Two main templates:
  1. ErrorGuidancePrompt: structured error info → natural language guidance
  2. PlanningPrompt: user profile info → weekly workout plan

Both include system prompts, few-shot examples, and structured output specs.
"""

import json
import random
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# System Prompts
# ============================================================

SYSTEM_PROMPT_CORRECTION = """你是一名拥有10年经验的资深健身教练和运动康复专家。你的任务是根据用户训练中检测到的动作错误，生成专业、具体、可操作的纠正指导。

请遵循以下原则：
1. **安全第一**：始终优先考虑动作安全性，避免加重受伤风险
2. **具体可操作**：每个建议都要具体到"怎么做"，而不是只说"注意XX"
3. **解释原因**：简短解释为什么这个错误有害，让用户理解并重视
4. **鼓励性语气**：用鼓励和正面的方式表达，不要让用户感到挫败
5. **分级指导**：根据错误严重程度调整语气的紧迫感
   - 严重度1（轻微）：温和提醒
   - 严重度2（中等）：明确指出，给出2-3个具体改进方法
   - 严重度3（危险）：严肃警告，要求立即调整
6. **个性化**：结合动作类型和用户可能的训练水平给出恰当建议
7. **语言要求**：用中文回答，口语化但不失专业，每条指导80-200字"""

SYSTEM_PROMPT_PLANNING = """你是一名专业的健身训练计划制定师，拥有运动科学硕士学位和ACE/NSCA认证。

你的任务是根据用户的身体数据、健身目标和约束条件，制定科学合理、个性化且可执行的周度训练计划。

请遵循以下原则：
1. **科学性**：基于运动科学原则（FITT-VP：频率、强度、时间、类型、总量、渐进）
2. **个性化**：充分考虑用户的年龄、性别、体重、健身水平、目标和可用器械
3. **安全渐进**：初学者从低强度开始，中级适度挑战，高级安排突破性训练
4. **可执行性**：考虑现实约束（时间、器械、空间），给出可落地的计划
5. **完整性**：包含热身、正式训练、拉伸放松、营养建议和恢复建议
6. **激励性**：用鼓励的语气，设定可达成的里程碑
7. **禁忌注意**：明确标注任何需要注意的伤病或特殊状况的禁忌动作
8. **语言要求**：用中文回答，结构清晰，每个训练日详细列出动作名称、组数、次数、休息时间"""


# ============================================================
# Few-Shot Examples
# ============================================================

CORRECTION_FEWSHOT = [
    {
        "input": {
            "exercise": "深蹲",
            "detected_error": "膝盖内扣",
            "severity": 2,
            "phase": "低位",
            "score": 55,
        },
        "output": "深蹲时膝盖出现了内扣，这会让膝关节内侧副韧带承受额外的压力，长期如此可能导致膝盖疼痛或受伤。请在下一次深蹲时有意识地将膝盖向外打开，确保膝盖始终指向第二脚趾的方向。如果感觉难以控制，可以试试在膝盖上方套一根弹力带，下蹲时抵抗弹力带的拉力主动向外撑开——这会激活你的臀中肌，帮助膝盖保持正确位置。建议先减少下蹲深度和次数，等膝盖轨迹稳定后再逐步增加。",
    },
    {
        "input": {
            "exercise": "俯卧撑",
            "detected_error": "塌腰/髋部下塌",
            "severity": 2,
            "phase": "低位",
            "score": 48,
        },
        "output": "做俯卧撑时你的髋部下塌了，这会让腰椎受力过大，不仅没有有效锻炼核心，还可能引起下背部疼痛。调整方法：先收紧臀部（像夹一张纸），再收紧腹部（把肚脐往脊椎方向吸），让你的身体从肩膀到脚踝形成一条笔直的线。如果你发现很难保持，说明目前的核心力量还不足以支撑标准俯卧撑——那完全没关系，可以先从跪姿俯卧撑开始，把动作做标准再进阶。",
    },
    {
        "input": {
            "exercise": "平板支撑",
            "detected_error": "髋部下塌",
            "severity": 1,
            "phase": "保持",
            "score": 62,
        },
        "output": "平板支撑时髋部有轻微下塌，虽然不算严重，但会让腰椎开始受力。小调整：把肚脐向脊椎方向微微收紧，同时臀部轻轻夹紧。想象你的身体是一块木板——从头到脚踝，任何一点都不能下垂。如果调整后还是控制不住，没关系，缩短时间到你能保持完美姿势的时长，然后分多组来做。20秒的标准平板支撑 > 60秒的变形平板支撑。",
    },
    {
        "input": {
            "exercise": "卷腹",
            "detected_error": "颈部用力代偿",
            "severity": 1,
            "phase": "低位",
            "score": 70,
        },
        "output": "卷腹时检测到你可能在用颈部发力，这样腹肌的锻炼效果会打折扣，还可能导致脖子酸痛。解决方法很简单：双手轻轻放在耳朵两侧，只做'放'的动作，绝对不要用手去'拉'头部。下巴微微收起，和胸口之间保持大约一拳的距离。然后把注意力100%集中在腹部——想象用你的腹肌把胸口往天花板方向卷起，而不是用头去带动。如果还是感觉脖子在用力，可以先交叉双臂放在胸前做。",
    },
    {
        "input": {
            "exercise": "开合跳",
            "detected_error": "落地缓冲不足",
            "severity": 1,
            "phase": "高位",
            "score": 65,
        },
        "output": "开合跳落地时缓冲不太够，能听到比较重的落地声对吧？这说明落地时膝盖和髋部没有充分弯曲来吸收冲击力。长期这样对膝关节和踝关节不太友好。调整技巧：落地时想象脚下踩着一个很薄很脆的东西，你要轻轻地踩上去——膝盖和髋部自然微屈，让整个脚掌从脚尖到脚跟像波浪一样滚动落地。可以先缩小跳跃幅度，专注于'轻落地'的感觉，等节奏掌握了再加大幅度。",
    },
]

PLANNING_FEWSHOT = [
    {
        "input": {
            "age": 25,
            "weight_kg": 70,
            "height_cm": 170,
            "gender": "男",
            "fitness_level": "beginner",
            "goal": "weight_loss",
            "equipment": "none",
            "days_per_week": 3,
            "medical_notes": "",
        },
        "output": """📋 个人减脂训练计划（4周）

## 基础信息
- 年龄：25岁 | 性别：男 | 170cm / 70kg
- 健身水平：初学者 | 目标：减脂塑形
- 器械：无（自重训练） | 周训练天数：3天

## 周训练安排

### 周一（全身基础训练）
| 动作 | 组数 | 次数 | 组间休息 | 要点 |
|------|------|------|----------|------|
| 开合跳 | 2组 | 20次 | 30秒 | 热身+有氧，手臂充分上举 |
| 深蹲 | 3组 | 12次 | 60秒 | 髋部先启动，膝盖对脚尖 |
| 跪姿俯卧撑 | 3组 | 8次 | 60秒 | 身体保持直线，不要塌腰 |
| 平板支撑 | 2组 | 20秒 | 30秒 | 收紧腹臀，身体一条直线 |
| 卷腹 | 2组 | 12次 | 45秒 | 不用颈部发力，腹部卷起 |

### 周三（全身耐力训练）
| 动作 | 组数 | 次数 | 组间休息 | 要点 |
|------|------|------|----------|------|
| 开合跳 | 2组 | 25次 | 20秒 | 保持节奏稳定 |
| 深蹲 | 3组 | 15次 | 45秒 | 加大下蹲幅度 |
| 跪姿俯卧撑 | 3组 | 10次 | 45秒 | 控制下降速度 |
| 平板支撑 | 3组 | 25秒 | 30秒 | 增加保持时间 |
| 卷腹 | 3组 | 15次 | 30秒 | 慢起慢放 |

### 周五（全身强化训练）
| 动作 | 组数 | 次数 | 组间休息 | 要点 |
|------|------|------|----------|------|
| 开合跳 | 3组 | 25次 | 20秒 | 尝试HIIT节奏 |
| 深蹲 | 3组 | 18次 | 30秒 | 减少休息增加密度 |
| 俯卧撑 | 2组 | 5次 | 60秒 | 尝试标准俯卧撑 |
| 平板支撑 | 3组 | 30秒 | 20秒 | 继续增加时间 |
| 卷腹 | 3组 | 18次 | 30秒 | 感受腹肌发力 |

## 营养建议
- 每日热量缺口：300-400大卡（目标摄入1800-2000大卡）
- 蛋白质：每公斤体重×1.5g ≈ 105g/天
- 戒糖、戒甜饮料、减少精制碳水
- 多喝水：每天2-2.5升
- 晚餐不晚于睡前3小时

## 注意事项
1. 每次训练前热身5分钟（开合跳+关节活动）
2. 训练后拉伸5-10分钟
3. 非训练日保持8000步以上的日常活动
4. 保证7-8小时睡眠
5. 任何不适立即停止，休息后评估""",
    },
    {
        "input": {
            "age": 28,
            "weight_kg": 68,
            "height_cm": 175,
            "gender": "男",
            "fitness_level": "intermediate",
            "goal": "hypertrophy",
            "equipment": "dumbbells",
            "days_per_week": 4,
            "medical_notes": "",
        },
        "output": """📋 个人增肌塑形训练计划（4周）

## 基础信息
- 年龄：28岁 | 性别：男 | 175cm / 68kg
- 健身水平：中级（1年经验） | 目标：增肌线条
- 器械：哑铃+自重 | 周训练天数：4天

## 周训练安排

### 周一（上肢推+核心）
| 动作 | 组数 | 次数 | 组间休息 |
|------|------|------|----------|
| 哑铃推举 | 4组 | 10次 | 60秒 |
| 标准俯卧撑 | 4组 | 15次 | 45秒 |
| 椅子臂屈伸 | 3组 | 12次 | 45秒 |
| 哑铃飞鸟 | 3组 | 12次 | 45秒 |
| 卷腹 | 4组 | 25次 | 30秒 |
| 俄罗斯转体 | 3组 | 20次/侧 | 20秒 |

### 周二（下肢+核心）
| 动作 | 组数 | 次数 | 组间休息 |
|------|------|------|----------|
| 哑铃深蹲 | 4组 | 12次 | 60秒 |
| 弓步蹲（持哑铃） | 3组 | 10次/侧 | 45秒 |
| 臀桥（哑铃负重） | 4组 | 15次 | 30秒 |
| 小腿提踵（持哑铃） | 3组 | 20次 | 20秒 |
| 平板支撑 | 3组 | 60秒 | 30秒 |

### 周四（上肢拉+核心）
| 动作 | 组数 | 次数 | 组间休息 |
|------|------|------|----------|
| 哑铃划船（单臂） | 4组 | 12次/侧 | 60秒 |
| 哑铃弯举 | 4组 | 10次 | 45秒 |
| 哑铃侧平举 | 3组 | 15次 | 30秒 |
| 反向飞鸟 | 3组 | 15次 | 30秒 |
| 鸟狗式 | 3组 | 12次/侧 | 20秒 |
| 死虫式 | 3组 | 12次/侧 | 20秒 |

### 周六（全身HIIT+弱点强化）
| 动作 | 组数 | 次数 | 组间休息 |
|------|------|------|----------|
| 波比跳 | 4组 | 8次 | 40秒 |
| 深蹲跳 | 3组 | 12次 | 40秒 |
| 登山者 | 3组 | 45秒 | 20秒 |
| 开合跳 | 3组 | 35次 | 20秒 |
| 拉伸 | - | 10分钟 | - |

## 渐进超负荷策略
- 每周尝试增加次数（+1-2 reps）或减少休息（-5秒）
- 每2周尝试增加一组
- 第4周为减载周：所有组数减半，专注动作质量

## 营养建议
- 每日热量盈余：300-400大卡（目标摄入2500-2700大卡）
- 蛋白质：每公斤体重×1.8g ≈ 122g/天
- 碳水以全谷物/薯类为主，训练前后补充
- 训练后30分钟内补充20-30g蛋白质

## 注意事项
1. 哑铃重量选择：能标准完成10-12次的重量
2. 每个动作控制节奏：发力1-2秒→顶峰1秒→还原2-3秒
3. 肩部热身必不可少（弹力带内外旋）
4. 每周至少1天完全休息""",
    },
]


# ============================================================
# Prompt Builder Classes
# ============================================================

@dataclass
class ErrorGuidancePrompt:
    """Prompt builder for structured error → natural language guidance."""

    system_prompt: str = SYSTEM_PROMPT_CORRECTION
    fewshot_examples: list[dict] = field(default_factory=lambda: CORRECTION_FEWSHOT)
    temperature: float = 0.7

    def build_system_message(self) -> dict:
        return {"role": "system", "content": self.system_prompt}

    def build_user_message(
        self,
        exercise: str,
        detected_error: str,
        severity: int,
        phase: str = "",
        score: float = 0,
        error_count: int = 0,
        consecutive_frames: int = 0,
    ) -> dict:
        """Build a user message with structured error info."""
        parts = [f"【动作纠错请求】"]

        parts.append(f"动作名称：{exercise}")
        parts.append(f"检测到的错误：{detected_error}")
        parts.append(f"严重程度：{'⚠ 危险' if severity >= 3 else '⚡ 需要注意' if severity >= 2 else '💡 轻微调整'}")
        parts.append(f"当前阶段：{phase}" if phase else "")
        parts.append(f"动作评分：{score:.0f}/100分" if score else "")
        parts.append(f"本次训练该错误已出现{error_count}次" if error_count else "")
        parts.append(f"连续检测到{consecutive_frames}帧" if consecutive_frames else "")

        parts.append("\n请给出专业的纠正指导。")

        content = "\n".join(p for p in parts if p)
        return {"role": "user", "content": content}

    def build_fewshot_messages(self) -> list[dict]:
        """Build few-shot example messages."""
        messages = []
        for ex in self.fewshot_examples:
            inp = ex["input"]
            user_msg = self.build_user_message(
                exercise=inp["exercise"],
                detected_error=inp["detected_error"],
                severity=inp["severity"],
                phase=inp.get("phase", ""),
                score=inp.get("score", 0),
            )
            messages.append(user_msg)
            messages.append({"role": "assistant", "content": ex["output"]})
        return messages

    def build_full_messages(
        self,
        exercise: str,
        detected_error: str,
        severity: int,
        phase: str = "",
        score: float = 0,
        use_fewshot: bool = True,
    ) -> list[dict]:
        """Build complete message list for LLM call."""
        messages = [self.build_system_message()]
        if use_fewshot:
            messages.extend(self.build_fewshot_messages())
        messages.append(self.build_user_message(
            exercise, detected_error, severity, phase, score,
        ))
        return messages


@dataclass
class PlanningPrompt:
    """Prompt builder for user profile → weekly workout plan."""

    system_prompt: str = SYSTEM_PROMPT_PLANNING
    fewshot_examples: list[dict] = field(default_factory=lambda: PLANNING_FEWSHOT)
    temperature: float = 0.7

    def build_system_message(self) -> dict:
        return {"role": "system", "content": self.system_prompt}

    def build_user_message(
        self,
        age: int,
        weight_kg: float,
        height_cm: float,
        gender: str,
        fitness_level: str,
        goal: str,
        equipment: str,
        days_per_week: int,
        medical_notes: str = "",
        preferences: Optional[list[str]] = None,
    ) -> dict:
        """Build a user message with structured user profile info."""
        level_labels = {"beginner": "初学者", "intermediate": "中级", "advanced": "高级"}
        goal_labels = {
            "strength": "增肌力量", "hypertrophy": "肌肉线条",
            "endurance": "耐力提升", "weight_loss": "减脂塑形", "general": "综合健康",
        }
        equipment_labels = {
            "none": "无器械（自重训练）", "mat": "瑜伽垫",
            "dumbbells": "哑铃", "resistance_band": "弹力带",
            "full_gym": "全器械",
        }

        parts = ["【训练计划生成请求】"]
        parts.append(f"年龄：{age}岁 | 性别：{gender} | 身高：{height_cm}cm | 体重：{weight_kg}kg")
        parts.append(f"健身水平：{level_labels.get(fitness_level, fitness_level)}")
        parts.append(f"训练目标：{goal_labels.get(goal, goal)}")
        parts.append(f"可用器械：{equipment_labels.get(equipment, equipment)}")
        parts.append(f"每周可训练天数：{days_per_week}天")

        if medical_notes:
            parts.append(f"⚠ 特殊注意事项：{medical_notes}")

        if preferences:
            parts.append(f"个人偏好：{'、'.join(preferences)}")

        parts.append("\n请制定一个4周的周度训练计划，包含每天的具体动作、组数、次数和要点。")

        content = "\n".join(parts)
        return {"role": "user", "content": content}

    def build_fewshot_messages(self) -> list[dict]:
        """Build few-shot example messages."""
        messages = []
        for ex in self.fewshot_examples:
            inp = ex["input"]
            user_msg = self.build_user_message(
                age=inp["age"],
                weight_kg=inp["weight_kg"],
                height_cm=inp["height_cm"],
                gender=inp["gender"],
                fitness_level=inp["fitness_level"],
                goal=inp["goal"],
                equipment=inp["equipment"],
                days_per_week=inp["days_per_week"],
                medical_notes=inp.get("medical_notes", ""),
            )
            messages.append(user_msg)
            messages.append({"role": "assistant", "content": ex["output"]})
        return messages

    def build_full_messages(
        self,
        age: int,
        weight_kg: float,
        height_cm: float,
        gender: str,
        fitness_level: str,
        goal: str,
        equipment: str,
        days_per_week: int,
        medical_notes: str = "",
        preferences: Optional[list[str]] = None,
        use_fewshot: bool = True,
    ) -> list[dict]:
        """Build complete message list for LLM call."""
        messages = [self.build_system_message()]
        if use_fewshot:
            messages.extend(self.build_fewshot_messages())
        messages.append(self.build_user_message(
            age, weight_kg, height_cm, gender,
            fitness_level, goal, equipment, days_per_week,
            medical_notes, preferences,
        ))
        return messages


class FewShotSelector:
    """Dynamically select the most relevant few-shot examples."""

    def __init__(self, examples: list[dict], max_examples: int = 3):
        self.examples = examples
        self.max_examples = max_examples

    def select_by_exercise(self, exercise: str) -> list[dict]:
        """Select examples matching the given exercise."""
        matching = [e for e in self.examples
                    if e["input"].get("exercise", "") == exercise]
        if matching:
            return matching[:self.max_examples]
        return random.sample(self.examples, min(self.max_examples, len(self.examples)))

    def select_by_profile(self, level: str, goal: str) -> list[dict]:
        """Select examples matching user profile."""
        matching = [e for e in self.examples
                    if e["input"].get("fitness_level") == level
                    or e["input"].get("goal") == goal]
        if len(matching) >= self.max_examples:
            return matching[:self.max_examples]
        remaining = [e for e in self.examples if e not in matching]
        matching.extend(random.sample(remaining, min(self.max_examples - len(matching), len(remaining))))
        return matching


class PromptBuilder:
    """Unified prompt builder with dynamic few-shot selection."""

    def __init__(self):
        self.correction_selector = FewShotSelector(CORRECTION_FEWSHOT)
        self.planning_selector = FewShotSelector(PLANNING_FEWSHOT)
        self.correction_prompt = ErrorGuidancePrompt()
        self.planning_prompt = PlanningPrompt()

    def build_correction_prompt(
        self,
        exercise: str,
        detected_error: str,
        severity: int,
        phase: str = "",
        score: float = 0,
    ) -> list[dict]:
        """Build a correction prompt with dynamic few-shot selection."""
        messages = [self.correction_prompt.build_system_message()]

        # Dynamically select relevant few-shot examples
        relevant = self.correction_selector.select_by_exercise(exercise)
        for ex in relevant:
            inp = ex["input"]
            messages.append(self.correction_prompt.build_user_message(
                inp["exercise"], inp["detected_error"],
                inp["severity"], inp.get("phase", ""), inp.get("score", 0),
            ))
            messages.append({"role": "assistant", "content": ex["output"]})

        messages.append(self.correction_prompt.build_user_message(
            exercise, detected_error, severity, phase, score,
        ))
        return messages

    def build_planning_prompt(
        self,
        age: int,
        weight_kg: float,
        height_cm: float,
        gender: str,
        fitness_level: str,
        goal: str,
        equipment: str,
        days_per_week: int,
        medical_notes: str = "",
        preferences: Optional[list[str]] = None,
    ) -> list[dict]:
        """Build a planning prompt with dynamic few-shot selection."""
        messages = [self.planning_prompt.build_system_message()]

        relevant = self.planning_selector.select_by_profile(fitness_level, goal)
        for ex in relevant:
            inp = ex["input"]
            messages.append(self.planning_prompt.build_user_message(
                inp["age"], inp["weight_kg"], inp["height_cm"],
                inp["gender"], inp["fitness_level"], inp["goal"],
                inp["equipment"], inp["days_per_week"],
                inp.get("medical_notes", ""),
            ))
            messages.append({"role": "assistant", "content": ex["output"]})

        messages.append(self.planning_prompt.build_user_message(
            age, weight_kg, height_cm, gender,
            fitness_level, goal, equipment, days_per_week,
            medical_notes, preferences,
        ))
        return messages

    def to_api_format(self, messages: list[dict]) -> dict:
        """Convert messages to OpenAI-compatible API format."""
        return {
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
        }

    def to_hf_format(self, messages: list[dict]) -> str:
        """Convert messages to HuggingFace chat template format."""
        text_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                text_parts.append(f"<|system|>\n{content}")
            elif role == "user":
                text_parts.append(f"<|user|>\n{content}")
            elif role == "assistant":
                text_parts.append(f"<|assistant|>\n{content}")
        return "\n".join(text_parts) + "\n<|assistant|>\n"
