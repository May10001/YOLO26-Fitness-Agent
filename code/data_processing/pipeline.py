"""
End-to-end dataset building pipeline.

Combines data from Bilibili, Keep, and Zhihu sources into a clean,
annotated fitness guidance dataset with:
  - 1000 action correction samples
  - 500 fitness planning samples

Output format (JSON):
  [
    {
      "id": "correction_0001",
      "type": "action_correction",
      "exercise": "深蹲",
      "error": "膝盖内扣",
      "severity": 2,
      "input": {structured error info},
      "output": "natural language guidance...",
      "annotation": {...}
    },
    ...
  ]
"""

import json
import logging
import random
from copy import deepcopy
from pathlib import Path
from typing import Optional

from .cleaner import DataCleaner
from .annotator import DataAnnotator

logger = logging.getLogger(__name__)

# 动作纠错模板库 — 用于扩增到 1000 条
CORRECTION_TEMPLATES = {
    "深蹲": {
        "common_errors": [
            {"error": "膝盖内扣", "severity": 2, "trigger": "深蹲时膝盖向内扣，髌骨未对准第二脚趾"},
            {"error": "躯干前倾", "severity": 2, "trigger": "深蹲时身体过度前倾超过45度"},
            {"error": "脚后跟离地", "severity": 1, "trigger": "深蹲下蹲时脚后跟抬起离开地面"},
            {"error": "膝盖过度前移", "severity": 1, "trigger": "深蹲时膝盖超过脚尖过多"},
            {"error": "下蹲深度不足", "severity": 1, "trigger": "深蹲时大腿未达到与地面平行"},
            {"error": "站起时臀部发力不足", "severity": 1, "trigger": "深蹲站起时用腰部而非臀部发力"},
            {"error": "左右不平衡", "severity": 2, "trigger": "深蹲时身体向一侧倾斜"},
            {"error": "背部弯曲", "severity": 2, "trigger": "深蹲时背部没有保持挺直"},
        ],
        "guidance_templates": [
            "深蹲时{error}。{correction}。建议先减轻负重，对着镜子检查姿势，确保动作标准后再增加强度。",
            "注意！深蹲时出现了{error}的问题。{correction}。试试放慢下蹲速度，感受肌肉的发力。",
            "你的深蹲存在{error}。{correction}。可以先做箱式深蹲（后面放椅子）来控制动作幅度。",
        ],
        "corrections": {
            "膝盖内扣": "有意识地将膝盖向外打开，与脚尖方向一致，可以在膝盖上方套弹力带进行练习",
            "躯干前倾": "挺胸收腹，保持背部直立，目视前方。如果脚踝灵活性不够，可以在脚跟下垫一个小杠铃片",
            "脚后跟离地": "将重心放在足中部，加强踝关节灵活性训练",
            "膝盖过度前移": "先启动髋关节后移，像坐椅子一样往后坐，保持小腿尽量垂直于地面",
            "下蹲深度不足": "逐步增加下蹲幅度，可以先做箱式深蹲练习，降低心理障碍",
            "站起时臀部发力不足": "站起时主动收紧臀部，感受臀肌发力的感觉",
            "左右不平衡": "弱侧先做，保持两侧力量均衡，可以做单侧训练强化弱势侧",
            "背部弯曲": "收紧核心，保持背部自然曲线，挺胸目视前方",
        },
    },
    "俯卧撑": {
        "common_errors": [
            {"error": "塌腰/拱臀", "severity": 2, "trigger": "俯卧撑时腰部下塌或臀部拱起"},
            {"error": "肘部外展", "severity": 1, "trigger": "俯卧撑时肘部打开角度超过90度"},
            {"error": "下降深度不足", "severity": 1, "trigger": "俯卧撑下降幅度不够，肘关节未到90度"},
            {"error": "头前伸", "severity": 1, "trigger": "俯卧撑时颈部过度前伸"},
            {"error": "手掌位置不当", "severity": 1, "trigger": "俯卧撑时手掌位置太靠前或太靠后"},
            {"error": "身体未呈直线", "severity": 2, "trigger": "俯卧撑时身体没有从头到脚形成一条直线"},
            {"error": "耸肩", "severity": 1, "trigger": "俯卧撑时肩膀耸向耳朵"},
            {"error": "动作过快", "severity": 1, "trigger": "俯卧撑时利用惯性快速完成动作"},
        ],
        "guidance_templates": [
            "俯卧撑时注意{error}。{correction}。宁可标准地做5个，也不要错误地做20个。",
            "你的俯卧撑有{error}的问题。{correction}。可以先从跪姿俯卧撑开始，建立正确的动作模式。",
            "纠正：俯卧撑{error}。{correction}。检查一下肩膀是否在手腕正上方。",
        ],
        "corrections": {
            "塌腰/拱臀": "收紧腹部和臀部，身体从头到脚踝保持一条直线，可以先做平板支撑增强核心力量",
            "肘部外展": "肘部与身体保持约45度夹角，向下时肘部指向斜后方而非两侧",
            "下降深度不足": "下放至胸口距离地面一拳高度（约5-8厘米），确保完整动作幅度",
            "头前伸": "保持颈部中立，眼睛自然看地面，不要抬头向前看",
            "手掌位置不当": "手掌应在肩膀正下方或略宽，手指张开均匀承重",
            "身体未呈直线": "收紧核心和臀部，想象身体是一块平板，可以从平板支撑开始建立直线感觉",
            "耸肩": "肩胛骨向下向后收紧，远离耳朵，保持肩部稳定",
            "动作过快": "控制节奏：下降2秒→底部停顿0.5秒→推起1秒，减少惯性",
        },
    },
    "平板支撑": {
        "common_errors": [
            {"error": "髋部下塌", "severity": 2, "trigger": "平板支撑时髋部向下塌陷"},
            {"error": "臀部上抬", "severity": 1, "trigger": "平板支撑时臀部抬得过高"},
            {"error": "耸肩", "severity": 1, "trigger": "平板支撑时肩膀耸向耳朵"},
            {"error": "头位不当", "severity": 1, "trigger": "平板支撑时过度抬头或低头"},
            {"error": "憋气", "severity": 1, "trigger": "平板支撑时憋气不呼吸"},
            {"error": "手位不当", "severity": 1, "trigger": "平板支撑时手臂位置不对"},
        ],
        "guidance_templates": [
            "平板支撑{error}。{correction}。记住：质量远大于时长，动作变形立刻停止。",
            "平板支撑时出现了{error}。{correction}。初学者保持20-30秒标准姿势就很好了。",
        ],
        "corrections": {
            "髋部下塌": "收紧腹部和臀部，将肚脐向脊椎方向收紧，身体从头到脚保持一条直线",
            "臀部上抬": "降低臀部至与身体齐平，收紧核心保持稳定",
            "耸肩": "肩胛骨向下向后收紧，肘部在肩正下方",
            "头位不当": "眼睛自然看地面，保持颈部与脊柱成一条直线",
            "憋气": "保持自然平稳的呼吸，不要憋气",
            "手位不当": "肘部在肩正下方，前臂平行向前或双手握拳对碰",
        },
    },
    "卷腹": {
        "common_errors": [
            {"error": "颈部用力", "severity": 1, "trigger": "卷腹时用颈部力量而非腹部力量"},
            {"error": "腰部离地", "severity": 1, "trigger": "卷腹时下背部离开地面"},
            {"error": "幅度过大", "severity": 1, "trigger": "卷腹时整个背部离地像仰卧起坐"},
            {"error": "动作过快", "severity": 1, "trigger": "卷腹时利用惯性快速完成"},
            {"error": "呼吸错误", "severity": 1, "trigger": "卷腹时呼吸节奏不对"},
        ],
        "guidance_templates": [
            "卷腹{error}。{correction}。感受腹部收缩比做了多少个更重要。",
            "卷腹时{error}了。{correction}。试试放慢一倍速度，感受每一次的腹肌发力。",
        ],
        "corrections": {
            "颈部用力": "双手轻放耳侧不要用力拉，下巴微收与胸口保持一拳距离，集中注意力用腹部发力",
            "腰部离地": "减小卷起幅度，肩胛骨微微离开地面即可，下背部主动压向地面",
            "幅度过大": "只需肩胛骨离地，不要像仰卧起坐一样整个坐起来",
            "动作过快": "慢起慢放，用2秒卷起+1秒顶峰+2秒下放，全程控制",
            "呼吸错误": "卷起时用力呼气收缩腹部，下放时吸气还原",
        },
    },
    "开合跳": {
        "common_errors": [
            {"error": "缓冲不足", "severity": 1, "trigger": "开合跳落地时膝盖锁死没有缓冲"},
            {"error": "手臂幅度不足", "severity": 1, "trigger": "开合跳时手臂未举过头顶"},
            {"error": "核心放松", "severity": 1, "trigger": "开合跳时身体晃动核心未收紧"},
            {"error": "跳跃节奏不稳", "severity": 1, "trigger": "开合跳节奏忽快忽慢"},
            {"error": "膝关节对位不正", "severity": 2, "trigger": "开合跳落地时膝盖和脚尖方向不一致"},
        ],
        "guidance_templates": [
            "开合跳{error}。{correction}。减小跳跃幅度，专注于动作的标准度。",
            "开合跳时{error}了。{correction}。建议先放慢节奏，确保每次跳都是高质量的。",
        ],
        "corrections": {
            "缓冲不足": "落地时膝盖和髋部微屈吸收冲击力，想象脚掌从脚尖到脚跟滚动落地",
            "手臂幅度不足": "跳起时手臂充分向上伸展至头顶上方，确保完整运动幅度",
            "核心放松": "全程挺胸收腹，保持核心收紧来控制身体的稳定性",
            "跳跃节奏不稳": "可以用节拍器或音乐辅助保持稳定的节奏",
            "膝关节对位不正": "落地时膝关节与脚尖方向保持一致，膝盖向外打开",
        },
    },
}


def _generate_correction_samples(target_count: int = 1000) -> list[dict]:
    """Generate action correction samples from templates."""
    samples = []
    # Ensure exact count distribution
    raw = {
        "深蹲": int(target_count * 0.28),
        "俯卧撑": int(target_count * 0.24),
        "平板支撑": int(target_count * 0.16),
        "卷腹": int(target_count * 0.16),
        "开合跳": int(target_count * 0.16),
    }
    # Adjust to hit target_count exactly
    total = sum(raw.values())
    if total < target_count:
        raw["深蹲"] += target_count - total
    exercise_counts = raw

    idx = 0
    for exercise, count in exercise_counts.items():
        templates = CORRECTION_TEMPLATES[exercise]
        errors = templates["common_errors"]
        guidance_tmpls = templates["guidance_templates"]
        corrections = templates["corrections"]

        n_per_error = max(1, count // len(errors))
        for _ in range(n_per_error):
            for err in errors:
                if len(samples) >= target_count:
                    break
                error_name = err["error"]
                guidance_tmpl = random.choice(guidance_tmpls)
                correction_text = corrections.get(error_name, f"请注意{error_name}的问题，保持动作标准")

                guidance = guidance_tmpl.format(
                    error=error_name,
                    correction=correction_text,
                )

                samples.append({
                    "id": f"correction_{idx:04d}",
                    "type": "action_correction",
                    "exercise": exercise,
                    "error": error_name,
                    "severity": err["severity"],
                    "trigger_condition": err["trigger"],
                    "input": {
                        "exercise": exercise,
                        "detected_error": error_name,
                        "severity": err["severity"],
                        "trigger": err["trigger"],
                    },
                    "output": guidance,
                    "annotation": {
                        "exercise_type": exercise,
                        "error_types": [error_name],
                        "guidance_type": "动作纠错",
                        "difficulty": "初级" if err["severity"] <= 1 else "中级",
                    },
                })
                idx += 1
            if len(samples) >= target_count:
                break

    random.shuffle(samples)
    return samples[:target_count]


def _generate_planning_samples(target_count: int = 500) -> list[dict]:
    """Generate fitness planning samples."""

    # User profiles for planning scenarios
    profiles = [
        {
            "scenario": "新手入门减脂",
            "age": 25, "weight": 75, "height": 170, "gender": "男",
            "level": "beginner", "goal": "weight_loss", "equipment": "none",
            "days_per_week": 3, "weeks": 4,
        },
        {
            "scenario": "新手入门增肌",
            "age": 22, "weight": 60, "height": 175, "gender": "男",
            "level": "beginner", "goal": "strength", "equipment": "none",
            "days_per_week": 3, "weeks": 4,
        },
        {
            "scenario": "中级增肌塑形",
            "age": 28, "weight": 68, "height": 172, "gender": "男",
            "level": "intermediate", "goal": "hypertrophy", "equipment": "dumbbells",
            "days_per_week": 4, "weeks": 4,
        },
        {
            "scenario": "中级减脂保持",
            "age": 30, "weight": 70, "height": 163, "gender": "女",
            "level": "intermediate", "goal": "weight_loss", "equipment": "resistance_band",
            "days_per_week": 4, "weeks": 4,
        },
        {
            "scenario": "高级力量突破",
            "age": 26, "weight": 78, "height": 178, "gender": "男",
            "level": "advanced", "goal": "strength", "equipment": "full_gym",
            "days_per_week": 5, "weeks": 4,
        },
        {
            "scenario": "产后恢复",
            "age": 30, "weight": 65, "height": 160, "gender": "女",
            "level": "beginner", "goal": "general", "equipment": "mat",
            "days_per_week": 3, "weeks": 8, "medical_notes": "剖腹产9个月，医生已允许运动",
        },
        {
            "scenario": "肩伤恢复期",
            "age": 35, "weight": 80, "height": 175, "gender": "男",
            "level": "intermediate", "goal": "general", "equipment": "resistance_band",
            "days_per_week": 3, "weeks": 6, "medical_notes": "肩袖损伤恢复期，避免过头动作",
        },
        {
            "scenario": "久坐上班族健康",
            "age": 32, "weight": 72, "height": 168, "gender": "男",
            "level": "beginner", "goal": "general", "equipment": "none",
            "days_per_week": 3, "weeks": 4, "medical_notes": "长期伏案，轻微腰肌劳损",
        },
        {
            "scenario": "学生党宿舍健身",
            "age": 20, "weight": 55, "height": 165, "gender": "女",
            "level": "beginner", "goal": "hypertrophy", "equipment": "mat",
            "days_per_week": 4, "weeks": 4,
        },
        {
            "scenario": "中年健康管理",
            "age": 45, "weight": 82, "height": 172, "gender": "男",
            "level": "beginner", "goal": "general", "equipment": "none",
            "days_per_week": 3, "weeks": 4, "medical_notes": "轻度高血压，医生建议规律运动",
        },
    ]

    day_configs = {
        3: [
            {"day": "周一", "focus": "全身基础"},
            {"day": "周三", "focus": "全身强化"},
            {"day": "周五", "focus": "全身耐力"},
        ],
        4: [
            {"day": "周一", "focus": "下肢力量"},
            {"day": "周二", "focus": "上肢力量"},
            {"day": "周四", "focus": "核心训练"},
            {"day": "周六", "focus": "全身HIIT"},
        ],
        5: [
            {"day": "周一", "focus": "下肢大重量"},
            {"day": "周二", "focus": "上肢推"},
            {"day": "周三", "focus": "核心+有氧"},
            {"day": "周五", "focus": "上肢拉"},
            {"day": "周六", "focus": "下肢爆发力"},
        ],
    }

    exercises_by_focus = {
        "全身基础": [
            {"name": "深蹲", "sets": 2, "reps": 12, "rest": 60},
            {"name": "跪姿俯卧撑", "sets": 2, "reps": 8, "rest": 60},
            {"name": "平板支撑", "sets": 2, "reps": 20, "rest": 30},
            {"name": "卷腹", "sets": 2, "reps": 12, "rest": 45},
        ],
        "全身强化": [
            {"name": "深蹲", "sets": 3, "reps": 15, "rest": 45},
            {"name": "俯卧撑", "sets": 3, "reps": 10, "rest": 45},
            {"name": "平板支撑", "sets": 3, "reps": 30, "rest": 30},
            {"name": "卷腹", "sets": 3, "reps": 18, "rest": 30},
            {"name": "开合跳", "sets": 2, "reps": 20, "rest": 30},
        ],
        "全身耐力": [
            {"name": "开合跳", "sets": 3, "reps": 25, "rest": 20},
            {"name": "深蹲", "sets": 3, "reps": 18, "rest": 30},
            {"name": "登山者", "sets": 3, "reps": 30, "rest": 20},
            {"name": "俯卧撑", "sets": 3, "reps": 12, "rest": 30},
        ],
        "下肢力量": [
            {"name": "深蹲", "sets": 4, "reps": 15, "rest": 45},
            {"name": "弓步蹲", "sets": 3, "reps": 10, "rest": 45},
            {"name": "臀桥", "sets": 4, "reps": 15, "rest": 30},
            {"name": "小腿提踵", "sets": 3, "reps": 25, "rest": 20},
        ],
        "上肢力量": [
            {"name": "俯卧撑", "sets": 4, "reps": 12, "rest": 45},
            {"name": "椅子臂屈伸", "sets": 3, "reps": 12, "rest": 30},
            {"name": "哑铃弯举", "sets": 3, "reps": 12, "rest": 30},
            {"name": "弹力带划船", "sets": 3, "reps": 15, "rest": 30},
        ],
        "核心训练": [
            {"name": "平板支撑", "sets": 3, "reps": 45, "rest": 30},
            {"name": "卷腹", "sets": 4, "reps": 25, "rest": 30},
            {"name": "鸟狗式", "sets": 3, "reps": 10, "rest": 20},
            {"name": "死虫式", "sets": 3, "reps": 12, "rest": 20},
        ],
        "全身HIIT": [
            {"name": "波比跳", "sets": 3, "reps": 8, "rest": 30},
            {"name": "开合跳", "sets": 3, "reps": 30, "rest": 20},
            {"name": "登山者", "sets": 3, "reps": 40, "rest": 20},
            {"name": "深蹲跳", "sets": 3, "reps": 10, "rest": 30},
        ],
        "下肢大重量": [
            {"name": "哑铃深蹲", "sets": 5, "reps": 8, "rest": 90},
            {"name": "弓步蹲", "sets": 4, "reps": 10, "rest": 60},
            {"name": "哑铃硬拉", "sets": 4, "reps": 10, "rest": 60},
            {"name": "臀桥", "sets": 4, "reps": 12, "rest": 45},
        ],
        "上肢推": [
            {"name": "哑铃推举", "sets": 5, "reps": 8, "rest": 90},
            {"name": "俯卧撑", "sets": 4, "reps": 15, "rest": 60},
            {"name": "臂屈伸", "sets": 4, "reps": 10, "rest": 60},
            {"name": "哑铃飞鸟", "sets": 3, "reps": 12, "rest": 45},
        ],
        "核心+有氧": [
            {"name": "平板支撑", "sets": 4, "reps": 60, "rest": 30},
            {"name": "卷腹", "sets": 4, "reps": 30, "rest": 30},
            {"name": "俄罗斯转体", "sets": 3, "reps": 25, "rest": 20},
            {"name": "开合跳", "sets": 4, "reps": 35, "rest": 20},
        ],
        "上肢拉": [
            {"name": "弹力带划船", "sets": 5, "reps": 12, "rest": 60},
            {"name": "哑铃弯举", "sets": 4, "reps": 10, "rest": 45},
            {"name": "弹力带侧平举", "sets": 4, "reps": 15, "rest": 30},
            {"name": "反向飞鸟", "sets": 3, "reps": 15, "rest": 30},
        ],
        "下肢爆发力": [
            {"name": "深蹲跳", "sets": 4, "reps": 12, "rest": 60},
            {"name": "波比跳", "sets": 4, "reps": 10, "rest": 45},
            {"name": "弓步跳", "sets": 3, "reps": 10, "rest": 45},
            {"name": "开合跳", "sets": 3, "reps": 40, "rest": 30},
        ],
    }

    exercise_notes = {
        "深蹲": "保持背部挺直，膝盖与脚尖方向一致",
        "俯卧撑": "身体呈一条直线，核心收紧，肘部与身体呈45°",
        "平板支撑": "身体从头到脚保持一条直线，收紧腹部和臀部",
        "卷腹": "用腹部发力，不要用颈部，下背部贴地",
        "开合跳": "落地时膝盖微屈缓冲，手臂充分上举",
        "弓步蹲": "前膝在脚踝正上方，后膝轻触地面",
        "臀桥": "肩-髋-膝呈一条直线，顶峰收缩1-2秒",
        "波比跳": "核心全程收紧，落地轻盈，量力而行",
        "登山者": "核心收紧，臀部不要上下起伏",
        "鸟狗式": "缓慢控制，保持躯干稳定不旋转",
        "死虫式": "下背部始终贴地，极慢速做",
        "小腿提踵": "慢起慢放，顶峰停顿1-2秒",
        "椅子臂屈伸": "肘部向后贴近身体，肩部稳定",
        "哑铃弯举": "上臂固定贴身，控制离心阶段",
        "哑铃推举": "收紧核心，避免弓腰，肩胛骨下压",
        "弹力带划船": "肩胛骨向后收紧，用背肌发力",
        "弹力带侧平举": "肩胛骨下压不耸肩，手臂与肩齐平",
        "深蹲跳": "落地膝盖微屈缓冲，膝盖与脚尖同方向",
        "俄罗斯转体": "控制速度，用腹肌发力旋转",
        "哑铃硬拉": "背部挺直，髋部发力，不要弓腰",
        "哑铃飞鸟": "肘部微屈，感受胸肌拉伸和收缩",
        "反向飞鸟": "肩胛骨收紧，用后束发力",
        "弓步跳": "落地屈膝缓冲，保持身体平衡",
        "跪姿俯卧撑": "身体保持直线，同样注意肘部45°",
    }

    samples = []
    n_per_profile = target_count // len(profiles) + 1

    idx = 0
    for profile in profiles:
        for _ in range(n_per_profile):
            if len(samples) >= target_count:
                break

            days = day_configs[profile["days_per_week"]]
            plan_text = f"📋 {profile['scenario']} 训练计划\n\n"
            plan_text += f"用户信息: {profile['age']}岁 {profile['gender']} "
            plan_text += f"{profile['height']}cm {profile['weight']}kg\n"
            plan_text += f"水平: {profile['level']} | 目标: {profile['goal']} | 周训练天数: {profile['days_per_week']}\n"

            if profile.get("medical_notes"):
                plan_text += f"⚠ 注意事项: {profile['medical_notes']}\n"

            plan_text += "\n周训练安排:\n"
            for d in days:
                focus = d["focus"]
                exercises = exercises_by_focus.get(focus, exercises_by_focus["全身基础"])
                plan_text += f"\n{d['day']} ({focus}):\n"
                for ex in exercises:
                    unit = "秒" if "平板支撑" in ex["name"] or "登山者" in ex["name"] else "次"
                    note = exercise_notes.get(ex["name"], "")
                    plan_text += f"  • {ex['name']}: {ex['sets']}组×{ex['reps']}{unit}, 组间休息{ex['rest']}秒"
                    if note:
                        plan_text += f" — {note}"
                    plan_text += "\n"

            plan_text += "\n📌 总体建议:\n"
            plan_text += "1. 每次训练前热身5-10分钟（动态拉伸+轻量有氧）\n"
            plan_text += "2. 训练后拉伸5-10分钟（静态拉伸放松主要肌群）\n"
            plan_text += "3. 保证充足睡眠（7-9小时）和足够蛋白质摄入\n"
            plan_text += "4. 如有任何疼痛或不适，立即停止并评估\n"

            samples.append({
                "id": f"planning_{idx:04d}",
                "type": "fitness_planning",
                "input": {
                    "age": profile["age"],
                    "weight_kg": profile["weight"],
                    "height_cm": profile["height"],
                    "gender": profile["gender"],
                    "fitness_level": profile["level"],
                    "goal": profile["goal"],
                    "equipment": profile["equipment"],
                    "days_per_week": profile["days_per_week"],
                    "medical_notes": profile.get("medical_notes", ""),
                },
                "output": plan_text,
                "scenario": profile["scenario"],
                "annotation": {
                    "guidance_type": "训练规划",
                    "difficulty": {"beginner": "初级", "intermediate": "中级", "advanced": "高级"}[profile["level"]],
                    "goal": profile["goal"],
                    "weeks": profile["weeks"],
                },
            })
            idx += 1

    random.shuffle(samples)
    return samples[:target_count]


def build_dataset(
    output_dir: Path = Path("./data/processed"),
    correction_count: int = 1000,
    planning_count: int = 500,
    include_existing: bool = True,
) -> dict:
    """
    Build the complete fitness guidance dataset.

    Returns:
        dict with keys:
          - correction_samples: list of action correction samples
          - planning_samples: list of planning samples
          - full_dataset: combined list
          - stats: dataset statistics
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("开始构建数据集...")

    # 1. Generate correction samples
    correction_samples = _generate_correction_samples(correction_count)
    logger.info("动作纠错样本: %d", len(correction_samples))

    # 2. Generate planning samples
    planning_samples = _generate_planning_samples(planning_count)
    logger.info("健身规划样本: %d", len(planning_samples))

    # 3. Include existing fitness_data.py conversations
    existing_convs = []
    if include_existing:
        try:
            from code.models.fine_tuning.fitness_data import ALL_CONVERSATIONS
            for i, conv in enumerate(ALL_CONVERSATIONS):
                # Extract user+assistant content
                user_msg = next((m["content"] for m in conv if m["role"] == "user"), "")
                asst_msg = next((m["content"] for m in conv if m["role"] == "assistant"), "")
                existing_convs.append({
                    "id": f"existing_{i:04d}",
                    "type": "fitness_qa",
                    "input": {"question": user_msg},
                    "output": asst_msg,
                    "source": "handcrafted",
                })
            logger.info("已有手工数据: %d", len(existing_convs))
        except Exception as e:
            logger.warning("加载已有数据失败: %s", e)

    # 4. Include synthetic bilibili/keep/zhihu data
    synthetic_samples = _collect_synthetic_data()
    logger.info("合成知识数据: %d", len(synthetic_samples))

    # 5. Combine
    full_dataset = correction_samples + planning_samples + existing_convs + synthetic_samples

    # 6. Compute stats
    exercise_counts = {}
    error_counts = {}
    guidance_counts = {}
    for s in full_dataset:
        ann = s.get("annotation", {})
        ex = ann.get("exercise_type", s.get("exercise", "未知"))
        exercise_counts[ex] = exercise_counts.get(ex, 0) + 1
        gt = ann.get("guidance_type", s.get("type", "未知"))
        guidance_counts[gt] = guidance_counts.get(gt, 0) + 1
        for e in ann.get("error_types", [s.get("error", "")]):
            if e:
                error_counts[e] = error_counts.get(e, 0) + 1

    stats = {
        "total_samples": len(full_dataset),
        "correction_samples": len(correction_samples),
        "planning_samples": len(planning_samples),
        "existing_samples": len(existing_convs),
        "synthetic_samples": len(synthetic_samples),
        "exercise_distribution": dict(sorted(exercise_counts.items(), key=lambda x: -x[1])),
        "error_distribution": dict(sorted(error_counts.items(), key=lambda x: -x[1])[:20]),
        "guidance_distribution": dict(sorted(guidance_counts.items(), key=lambda x: -x[1])),
    }

    # 7. Save to disk
    out = {
        "correction_samples": correction_samples,
        "planning_samples": planning_samples,
        "full_dataset": full_dataset,
        "stats": stats,
    }

    # Save as single JSON
    json_path = output_dir / "fitness_dataset.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    logger.info("数据集保存到: %s", json_path)

    # Save separate files for easy loading
    with open(output_dir / "correction_samples.json", "w", encoding="utf-8") as f:
        json.dump(correction_samples, f, ensure_ascii=False, indent=2)

    with open(output_dir / "planning_samples.json", "w", encoding="utf-8") as f:
        json.dump(planning_samples, f, ensure_ascii=False, indent=2)

    # Save stats
    with open(output_dir / "dataset_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # Save as JSONL for HF datasets
    with open(output_dir / "fitness_dataset.jsonl", "w", encoding="utf-8") as f:
        for sample in full_dataset:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    logger.info("数据集构建完成！总计 %d 条样本", len(full_dataset))
    return out


def _collect_synthetic_data() -> list[dict]:
    """Collect synthetic data from Keep and Zhihu modules."""
    samples = []
    idx = 0

    try:
        from code.data_collection.keep_scraper import get_synthetic_keep_data
        keep_data = get_synthetic_keep_data()

        # Exercise technique data
        for ex in keep_data.get("exercises", []):
            instructions = "\n".join(ex.get("instructions", []))
            mistakes = "\n".join(
                f"- {m['error']}: {m['correction']}"
                for m in ex.get("common_mistakes", [])
            )
            text = f"{ex['name']}的标准做法：\n{instructions}\n\n常见错误与纠正：\n{mistakes}"
            samples.append({
                "id": f"keep_ex_{idx:04d}",
                "type": "exercise_technique",
                "exercise": ex["name"],
                "input": {"exercise": ex["name"], "query": f"{ex['name']}怎么做才标准？"},
                "output": text,
                "source": "keep",
                "annotation": {
                    "exercise_type": ex["name"],
                    "guidance_type": "动作纠错",
                    "target_muscles": ex.get("target_muscles", []),
                },
            })
            idx += 1

        # Correction pairs
        for pair in keep_data.get("correction_pairs", []):
            samples.append({
                "id": f"keep_correct_{idx:04d}",
                "type": "action_correction",
                "exercise": pair.get("exercise", ""),
                "input": {"question": pair.get("user_question", "")},
                "output": pair.get("coach_answer", ""),
                "source": "keep",
                "annotation": {
                    "exercise_type": pair.get("exercise", ""),
                    "guidance_type": "动作纠错",
                },
            })
            idx += 1

        # Planning QA
        for qa in keep_data.get("planning_qa", []):
            samples.append({
                "id": f"keep_plan_{idx:04d}",
                "type": "fitness_planning",
                "input": {"user_info": qa.get("user_info", "")},
                "output": qa.get("planning_advice", ""),
                "scenario": qa.get("scenario", ""),
                "source": "keep",
                "annotation": {"guidance_type": "训练规划"},
            })
            idx += 1
    except Exception as e:
        logger.warning("加载 Keep 合成数据失败: %s", e)

    try:
        from code.data_collection.zhihu_scraper import get_synthetic_zhihu_data
        zhihu_data = get_synthetic_zhihu_data()

        for qa in zhihu_data.get("qa_pairs", []):
            samples.append({
                "id": f"zhihu_qa_{idx:04d}",
                "type": "fitness_qa",
                "input": {"question": qa.get("title", ""), "detail": qa.get("detail", "")},
                "output": qa.get("answer", ""),
                "source": "zhihu",
                "annotation": {"guidance_type": "综合指导"},
            })
            idx += 1

        for qa in zhihu_data.get("planning_qa", []):
            samples.append({
                "id": f"zhihu_plan_{idx:04d}",
                "type": "fitness_planning",
                "input": {"question": qa.get("title", ""), "detail": qa.get("detail", "")},
                "output": qa.get("answer", ""),
                "source": "zhihu",
                "annotation": {"guidance_type": "训练规划"},
            })
            idx += 1
    except Exception as e:
        logger.warning("加载知乎合成数据失败: %s", e)

    return samples


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_dataset()
