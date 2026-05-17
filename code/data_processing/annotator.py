"""
Data annotation module for fitness guidance dataset.

Annotates each sample with:
  - exercise_type: 动作类型 (深蹲/俯卧撑/平板支撑/卷腹/开合跳/弓步蹲/臀桥/综合)
  - error_type: 错误类型 (姿势错误/呼吸错误/节奏错误/幅度错误/代偿错误/无错误)
  - guidance_type: 指导类型 (动作纠错/表现反馈/安全警告/鼓励/训练规划/营养建议/恢复建议)
  - difficulty: 难度 (初级/中级/高级)
  - target_muscles: 目标肌群
  - metadata: 额外标注信息
"""

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 动作关键词映射
EXERCISE_KEYWORDS = {
    "深蹲": ["深蹲", "蹲", "squat", "下蹲"],
    "俯卧撑": ["俯卧撑", "push up", "push-up", "撑"],
    "平板支撑": ["平板支撑", "平板", "plank", "肘撑"],
    "卷腹": ["卷腹", "crunch", "仰卧起坐", "腹"],
    "开合跳": ["开合跳", "jumping jack", "跳"],
    "弓步蹲": ["弓步", "箭步", "lunge", "弓步蹲"],
    "臀桥": ["臀桥", "桥式", "glute bridge"],
    "哑铃弯举": ["弯举", "curl", "二头"],
    "哑铃推举": ["推举", "press", "肩推"],
    "波比跳": ["波比", "burpee"],
    "登山者": ["登山者", "登山", "mountain climber"],
    "死虫式": ["死虫", "dead bug"],
    "鸟狗式": ["鸟狗", "bird dog"],
    "综合": [],
}

# 错误类型关键词
ERROR_KEYWORDS = {
    "膝盖内扣": ["膝盖内扣", "膝内扣", "膝外翻", "膝盖往内"],
    "躯干前倾": ["前倾", "往前倾", "弓背", "弯腰", "塌腰"],
    "塌腰": ["塌腰", "髋部下塌", "腰塌", "下塌"],
    "耸肩": ["耸肩", "耸肩", "肩膀耸"],
    "颈部代偿": ["脖子疼", "颈部用力", "脖子用力", "颈部发力", "脖子发力"],
    "肘部外展": ["肘部外展", "肘打得太开", "肘部太开", "手臂太开"],
    "腰部离地": ["腰部离地", "腰离地", "腰拱起", "腰部拱"],
    "动作过快": ["太快", "过快", "快速", "速度太快", "用惯性"],
    "憋气": ["憋气", "不呼吸", "忘了呼吸"],
    "缓冲不足": ["落地", "响声", "声音大", "缓冲"],
    "幅度不足": ["幅度不够", "深度不够", "没到位", "幅度小"],
    "不对称": ["不对称", "左右不", "偏了", "不平衡", "一边"],
    "手腕疼": ["手腕", "手腕疼", "腕"],
    "膝盖超脚尖": ["超过脚尖", "超脚尖", "膝盖过脚尖"],
    "臀部上抬": ["屁股撅", "臀部抬高", "屁股太高"],
    "节奏不稳": ["节奏", "忽快忽慢", "不稳"],
}

# 指导类型关键词
GUIDANCE_KEYWORDS = {
    "动作纠错": ["纠正", "错误", "不对", "注意", "标准", "姿势", "动作"],
    "训练规划": ["计划", "每周", "周训练", "安排", "怎么练", "几天"],
    "营养建议": ["吃", "营养", "蛋白", "饮食", "热量", "卡路里", "喝"],
    "恢复建议": ["恢复", "休息", "睡眠", "酸痛", "拉伸"],
    "安全警告": ["受伤", "疼", "痛", "危险", "风险", "损伤"],
    "鼓励": ["加油", "坚持", "很棒", "出色", "进步"],
}

# 目标肌群映射
MUSCLE_KEYWORDS = {
    "股四头肌": ["股四头", "大腿前", "quad"],
    "臀大肌": ["臀大肌", "臀部", "臀肌", "glute"],
    "腘绳肌": ["腘绳", "腿后", "hamstring"],
    "胸大肌": ["胸大肌", "胸肌", "胸部", "chest", "pec"],
    "肱三头肌": ["肱三头", "三头", "手臂后", "tricep"],
    "三角肌": ["三角肌", "肩膀", "肩部", "shoulder", "delt"],
    "核心肌群": ["核心", "腹", "core", "ab", "腰腹"],
    "腹直肌": ["腹直肌", "腹肌", "abs"],
    "腹横肌": ["腹横肌", "深层核心"],
    "竖脊肌": ["竖脊肌", "下背", "lower back"],
    "肱二头肌": ["肱二头", "二头肌", "bicep"],
    "背阔肌": ["背阔肌", "背部", "lat"],
    "小腿肌群": ["小腿", "腓肠", "calf"],
    "全身": ["全身", "有氧", "心肺", "cardio"],
}


class DataAnnotator:
    """Annotate fitness data with structured labels."""

    def __init__(self):
        self.stats = Counter()

    def annotate_sample(self, sample: dict) -> dict:
        """Add annotation fields to a single sample."""
        text = self._extract_text(sample)

        exercise_type = self._classify_exercise(text)
        error_types = self._classify_errors(text)
        guidance_type = self._classify_guidance(text)
        difficulty = self._classify_difficulty(text)
        target_muscles = self._classify_muscles(text, exercise_type)

        annotated = dict(sample)
        annotated["annotation"] = {
            "exercise_type": exercise_type,
            "error_types": error_types,
            "guidance_type": guidance_type,
            "difficulty": difficulty,
            "target_muscles": target_muscles,
        }
        self.stats["exercise_" + exercise_type] += 1
        self.stats["guidance_" + guidance_type] += 1

        return annotated

    def _extract_text(self, sample: dict) -> str:
        """Extract all text from a sample."""
        parts = []
        if "messages" in sample:
            for msg in sample["messages"]:
                parts.append(msg.get("content", ""))
        elif "text" in sample:
            parts.append(sample["text"])
        elif "question" in sample:
            parts.append(sample.get("question", ""))
            parts.append(sample.get("answer", ""))
        elif "title" in sample:
            parts.append(sample.get("title", ""))
            parts.append(sample.get("answer", ""))
            parts.append(sample.get("detail", ""))
        return " ".join(parts)

    def _classify_exercise(self, text: str) -> str:
        """Classify the exercise type from text."""
        for ex_type, keywords in EXERCISE_KEYWORDS.items():
            if ex_type == "综合":
                continue
            for kw in keywords:
                if kw in text:
                    return ex_type
        return "综合"

    def _classify_errors(self, text: str) -> list[str]:
        """Classify error types mentioned in text."""
        errors = []
        for err_type, keywords in ERROR_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    errors.append(err_type)
                    break
        return errors if errors else ["无特定错误"]

    def _classify_guidance(self, text: str) -> str:
        """Classify the guidance type."""
        scores = {}
        for gtype, keywords in GUIDANCE_KEYWORDS.items():
            scores[gtype] = sum(1 for kw in keywords if kw in text)
        if not scores or max(scores.values()) == 0:
            return "综合指导"
        return max(scores, key=scores.get)

    def _classify_difficulty(self, text: str) -> str:
        """Classify difficulty level."""
        beginner_kw = ["新手", "初学者", "入门", "刚开始", "零基础", "第一次",
                        "简单", "基础", "初学", "小白", "减轻", "退阶", "跪姿"]
        advanced_kw = ["进阶", "高级", "变式", "增加难度", "单腿", "负重",
                        "大重量", "极限", "比赛", "专业"]

        beginner_score = sum(1 for kw in beginner_kw if kw in text)
        advanced_score = sum(1 for kw in advanced_kw if kw in text)

        if advanced_score > beginner_score:
            return "高级"
        elif beginner_score > 0:
            return "初级"
        else:
            return "中级"

    def _classify_muscles(self, text: str, exercise_type: str) -> list[str]:
        """Classify target muscles."""
        muscles = []
        for muscle, keywords in MUSCLE_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    muscles.append(muscle)
                    break

        # Fallback: use exercise → muscle mapping
        if not muscles:
            muscle_map = {
                "深蹲": ["股四头肌", "臀大肌", "腘绳肌", "核心肌群"],
                "俯卧撑": ["胸大肌", "肱三头肌", "三角肌", "核心肌群"],
                "平板支撑": ["腹横肌", "腹直肌", "竖脊肌", "三角肌"],
                "卷腹": ["腹直肌", "核心肌群"],
                "开合跳": ["全身", "心肺系统"],
                "弓步蹲": ["股四头肌", "臀大肌", "腘绳肌"],
                "臀桥": ["臀大肌", "腘绳肌", "核心肌群"],
            }
            muscles = muscle_map.get(exercise_type, ["全身"])

        return list(dict.fromkeys(muscles))  # dedup while preserving order

    def annotate_dataset(self, samples: list[dict]) -> list[dict]:
        """Annotate all samples in a dataset."""
        logger.info("开始标注, 样本数: %d", len(samples))
        annotated = [self.annotate_sample(s) for s in samples]
        logger.info("标注完成, 统计: %s", dict(self.stats.most_common(10)))
        return annotated

    def generate_error_guidance_pair(self, exercise: str, error: str) -> dict:
        """Generate a structured error→guidance pair for fine-tuning."""
        templates = self._get_error_templates()
        key = (exercise, error)
        if key in templates:
            return templates[key]
        return {
            "exercise": exercise,
            "error": error,
            "guidance": f"在{exercise}时注意避免{error}，保持标准动作姿势，必要时减少次数确保动作质量。",
        }

    def _get_error_templates(self) -> dict:
        """Pre-defined error→guidance templates for 5 core exercises."""
        return {
            ("深蹲", "膝盖内扣"): {
                "exercise": "深蹲",
                "error": "膝盖内扣",
                "severity": 2,
                "guidance": "检测到深蹲时膝盖内扣。下蹲时要有意识地将膝盖向外打开，与脚尖方向一致。可以在膝盖上方套弹力带练习，加强臀中肌，帮助膝盖保持正确位置。",
            },
            ("深蹲", "躯干前倾"): {
                "exercise": "深蹲",
                "error": "躯干过度前倾",
                "severity": 2,
                "guidance": "深蹲时身体前倾过多会增加腰椎压力。保持挺胸收腹，目视前方，收紧核心。如果脚踝灵活性不够，可以在脚后跟垫一个小重物改善下蹲角度。",
            },
            ("深蹲", "脚后跟离地"): {
                "exercise": "深蹲",
                "error": "脚后跟离地",
                "severity": 1,
                "guidance": "深蹲时脚后跟离地会导致重心不稳。将重心保持在足中部，如果小腿柔韧性不足导致脚后跟自然抬起，可以在脚后跟下垫一个薄片，同时每天做小腿和踝关节拉伸。",
            },
            ("俯卧撑", "塌腰"): {
                "exercise": "俯卧撑",
                "error": "塌腰/髋部下塌",
                "severity": 2,
                "guidance": "俯卧撑时髋部下塌是核心力量不足的表现。收紧腹部和臀部，想象从肩到脚踝是一条直线。如果无法保持标准姿势，先做跪姿俯卧撑或上斜俯卧撑降低难度。",
            },
            ("俯卧撑", "肘部外展"): {
                "exercise": "俯卧撑",
                "error": "肘部过度外展",
                "severity": 1,
                "guidance": "肘部打开角度过大（超过90°）会增加肩关节压力。肘部与身体保持约45°夹角，既能有效锻炼胸肌和肱三头肌，又能保护肩关节。",
            },
            ("平板支撑", "塌腰"): {
                "exercise": "平板支撑",
                "error": "髋部下塌",
                "severity": 2,
                "guidance": "平板支撑塌腰会让腰椎承受不必要的压力。收紧腹部（将肚脐向脊椎方向收）和臀部，身体从头到脚踝必须保持一条直线。动作一旦变形就立即停止，不要硬撑。",
            },
            ("平板支撑", "耸肩"): {
                "exercise": "平板支撑",
                "error": "耸肩",
                "severity": 1,
                "guidance": "平板支撑时肩胛骨要向下向后收紧，不要耸肩到耳朵。肘部保持在肩膀正下方，肩胛骨稳定地贴在后背上。",
            },
            ("卷腹", "颈部代偿"): {
                "exercise": "卷腹",
                "error": "颈部发力代偿",
                "severity": 1,
                "guidance": "卷腹时脖子疼说明在用颈部而非腹部发力。双手轻放在耳侧，绝对不要用手拉头部。下巴微收，眼睛看天花板，集中注意力用腹部力量卷起。如果仍脖子疼，将双臂交叉放在胸前。",
            },
            ("卷腹", "腰部离地"): {
                "exercise": "卷腹",
                "error": "腰部离地",
                "severity": 1,
                "guidance": "卷腹时腰部离开地面会让腰椎受力。减小卷起幅度，只需要肩胛骨离地即可。主动将下背部压向地面，先做死虫式等核心稳定性训练打好基础。",
            },
            ("开合跳", "缓冲不足"): {
                "exercise": "开合跳",
                "error": "落地缓冲不足",
                "severity": 1,
                "guidance": "开合跳落地声音大说明没有充分缓冲。落地时膝盖和髋部微屈吸收冲击力，想象脚掌从脚尖到脚跟滚动落地。减小跳跃高度，核心收紧控制身体稳定。",
            },
            ("开合跳", "手臂未充分展开"): {
                "exercise": "开合跳",
                "error": "手臂未举过头顶",
                "severity": 1,
                "guidance": "跳起时手臂要充分向上伸展过头顶，不要只举到肩膀高度。充分的手臂运动能增加运动幅度和燃脂效果。",
            },
        }
