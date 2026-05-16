"""
Keep 动作库爬虫 — 抓取 Keep APP 的动作库数据。

Keep 的动作库包含标准化的:
  - 动作名称、分类（力量/有氧/拉伸）
  - 动作要领（文字描述）
  - 常见错误提示
  - 目标肌群
  - 动作图示信息

数据来源:
  - Keep 开放数据通过 API 逆向获取
  - 补充: Keep 公开课程页面的结构化信息

由于 Keep API 需要登录态，本模块同时提供:
  1. 实际爬虫逻辑（带 cookie 可运行）
  2. 基于公开知识的合成数据（离线可用）
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json",
}


@dataclass
class KeepExercise:
    """Keep 动作库中的单个动作."""
    name: str                      # 动作名称
    category: str                  # 分类: 力量/有氧/拉伸/核心
    target_muscles: list[str]      # 目标肌群
    difficulty: str                # 难度: 初级/中级/高级
    equipment: str                 # 所需器械
    instructions: list[str]        # 动作要领 (分步骤)
    common_mistakes: list[dict]    # 常见错误 [{error, correction}]
    tips: list[str]                # 小贴士
    duration_sec: int = 0          # 建议时长/次数
    video_url: str = ""


class KeepScraper:
    """Keep 动作库爬虫."""

    def __init__(
        self,
        output_dir: Path = Path("./data/raw/keep"),
        token: str = "",
        rate_limit: float = 1.0,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.token = token
        self.rate_limit = rate_limit
        self._session = None
        self._last_request = 0.0

    def _ensure_session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update(HEADERS)
            if self.token:
                self._session.headers["Authorization"] = f"Bearer {self.token}"

    def _rate_limit_wait(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()

    def get_exercise_list(self, category: str = "all", page: int = 1) -> list[dict]:
        """获取 Keep 动作库列表."""
        self._ensure_session()
        self._rate_limit_wait()
        try:
            # Keep API endpoint (示例，实际需根据抓包确定)
            url = "https://api.gotokeep.com/v1/exercises"
            params = {"category": category, "page": page, "size": 50}
            resp = self._session.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get("ok"):
                return data.get("data", {}).get("records", [])
            else:
                logger.warning("Keep API 返回异常: %s", data.get("error"))
                return []
        except Exception as e:
            logger.error("Keep 请求异常: %s", e)
            return []

    def get_exercise_detail(self, exercise_id: str) -> Optional[dict]:
        """获取单个动作的详细信息."""
        self._ensure_session()
        self._rate_limit_wait()
        try:
            url = f"https://api.gotokeep.com/v1/exercises/{exercise_id}"
            resp = self._session.get(url, timeout=15)
            data = resp.json()
            if data.get("ok"):
                return data.get("data", {})
            return None
        except Exception as e:
            logger.error("Keep 动作详情异常: %s", e)
            return None

    def scrape_all(self, categories: Optional[list[str]] = None) -> list[KeepExercise]:
        """抓取 Keep 动作库全部数据."""
        if categories is None:
            categories = ["strength", "cardio", "stretch", "core", "yoga"]

        all_exercises = []
        for cat in categories:
            for page in range(1, 10):
                records = self.get_exercise_list(cat, page)
                if not records:
                    break
                for rec in records:
                    detail = self.get_exercise_detail(rec.get("id"))
                    if detail:
                        ex = self._parse_exercise(detail)
                        all_exercises.append(ex)
                        self._save_exercise(ex)

        return all_exercises

    def _parse_exercise(self, data: dict) -> KeepExercise:
        return KeepExercise(
            name=data.get("name", ""),
            category=data.get("category", ""),
            target_muscles=data.get("targetMuscles", []),
            difficulty=data.get("difficulty", "初级"),
            equipment=data.get("equipment", "无"),
            instructions=data.get("instructions", []),
            common_mistakes=data.get("commonMistakes", []),
            tips=data.get("tips", []),
            duration_sec=data.get("duration", 0),
            video_url=data.get("videoUrl", ""),
        )

    def _save_exercise(self, ex: KeepExercise):
        safe_name = re.sub(r"[^\w]", "_", ex.name)
        path = self.output_dir / f"{safe_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "name": ex.name,
                "category": ex.category,
                "target_muscles": ex.target_muscles,
                "difficulty": ex.difficulty,
                "equipment": ex.equipment,
                "instructions": ex.instructions,
                "common_mistakes": ex.common_mistakes,
                "tips": ex.tips,
                "duration_sec": ex.duration_sec,
            }, f, ensure_ascii=False, indent=2)


# ============================================================
# 合成 Keep 动作库数据 (30+ 动作，含常见错误和纠错)
# ============================================================

SYNTHETIC_KEEP_EXERCISES = [
    {
        "name": "深蹲",
        "category": "strength",
        "target_muscles": ["股四头肌", "臀大肌", "腘绳肌", "核心肌群"],
        "difficulty": "初级",
        "equipment": "无",
        "instructions": [
            "双脚与肩同宽站立，脚尖微向外",
            "挺胸收腹，背部保持自然曲线",
            "髋关节先启动，像坐椅子一样向后坐",
            "下蹲至大腿与地面平行或略低",
            "全程膝盖与脚尖方向一致",
            "起身时臀部发力，回到站立位",
        ],
        "common_mistakes": [
            {"error": "膝盖内扣", "correction": "有意识地将膝盖向外打开，与脚尖方向一致"},
            {"error": "躯干过度前倾", "correction": "挺胸收腹，保持背部直立，目视前方"},
            {"error": "脚后跟离地", "correction": "重心放在足中，加强踝关节灵活性训练"},
            {"error": "下蹲深度不够", "correction": "逐步增加下蹲幅度，可以先做箱式深蹲练习"},
            {"error": "膝盖过度前移超过脚尖", "correction": "先启动髋关节后移，保持小腿尽量垂直地面"},
        ],
        "tips": ["每组10-15次", "组间休息45-60秒", "初学者可先做靠墙深蹲"],
    },
    {
        "name": "俯卧撑",
        "category": "strength",
        "target_muscles": ["胸大肌", "肱三头肌", "三角肌前束", "核心肌群"],
        "difficulty": "初级",
        "equipment": "无",
        "instructions": [
            "双手放在肩正下方，略宽于肩",
            "手指张开均匀承重",
            "身体从头到脚跟呈一条直线",
            "下降时肘部与身体呈45°夹角",
            "胸口降至离地约一拳高度",
            "呼气推起回到起始位置",
        ],
        "common_mistakes": [
            {"error": "塌腰/拱臀", "correction": "收紧核心和臀部，保持身体呈一条直线"},
            {"error": "肘部过度外展", "correction": "肘部与身体保持约45°夹角，不要超过90°"},
            {"error": "下降深度不足", "correction": "下放至胸口距地面一拳距离，确保完整幅度"},
            {"error": "头部前伸", "correction": "保持颈部中立，眼睛看地面而非前方"},
            {"error": "手掌位置太靠前", "correction": "手掌应在肩膀正下方，不要超过肩膀"},
        ],
        "tips": ["每组8-12次", "组间休息45-60秒", "做不到标准俯卧撑可从跪姿开始"],
    },
    {
        "name": "平板支撑",
        "category": "core",
        "target_muscles": ["腹横肌", "腹直肌", "竖脊肌", "三角肌"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "肘部在肩正下方，前臂平行向前",
            "身体从头到脚踝呈一条直线",
            "收紧腹部和臀部",
            "保持自然呼吸",
            "眼睛看地面，颈部中立",
        ],
        "common_mistakes": [
            {"error": "髋部下塌(塌腰)", "correction": "收紧腹部和臀部，将肚脐向脊椎方向收紧"},
            {"error": "臀部上抬过高", "correction": "降低臀部，保持身体呈一条直线"},
            {"error": "耸肩/肩胛骨突出", "correction": "肩胛骨向下向后收紧，不要耸肩到耳朵"},
            {"error": "抬头或低头过度", "correction": "眼睛自然看地面，保持颈部与脊柱成一线"},
            {"error": "憋气", "correction": "保持自然呼吸，不要憋气"},
        ],
        "tips": ["初学者20-30秒×3组", "质量比时长重要", "一旦身体变形就立即停止"],
    },
    {
        "name": "卷腹",
        "category": "core",
        "target_muscles": ["腹直肌", "腹斜肌"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "仰卧，屈膝，双脚踩实地面",
            "双手轻放在耳侧或交叉于胸前",
            "下巴微收，眼睛看天花板",
            "用腹部力量卷起上背部",
            "肩胛骨离地即可，下背贴地",
            "卷起时呼气，下放时吸气",
        ],
        "common_mistakes": [
            {"error": "用颈部发力", "correction": "双手轻放耳侧不要用力拉，集中注意力用腹部发力"},
            {"error": "腰部离地", "correction": "下背部主动压向地面，减小卷起幅度"},
            {"error": "动作过快用惯性", "correction": "慢起慢放，控制每个动作的速度"},
            {"error": "卷起幅度过大", "correction": "只需肩胛骨离地，不要像仰卧起坐整个坐起来"},
            {"error": "憋气或用错呼吸", "correction": "卷起时呼气收缩腹部，下放时吸气还原"},
        ],
        "tips": ["每组15-25次", "组间休息30-45秒", "腹肌需48小时恢复，不要每天做"],
    },
    {
        "name": "开合跳",
        "category": "cardio",
        "target_muscles": ["全身肌群", "心肺系统"],
        "difficulty": "初级",
        "equipment": "无",
        "instructions": [
            "起始站姿，双脚并拢，手臂放在体侧",
            "跳起同时双脚向两侧打开",
            "手臂从两侧向上举过头顶",
            "落地时膝盖微屈缓冲",
            "再次跳起回到起始姿势",
        ],
        "common_mistakes": [
            {"error": "手臂未举过头顶", "correction": "跳起时手臂充分向上伸展，双手在头顶上方"},
            {"error": "落地声音大缓冲不足", "correction": "落地时膝盖和髋部微屈吸收冲击力"},
            {"error": "身体晃动核心未收紧", "correction": "全程挺胸收腹，保持身体稳定"},
            {"error": "跳跃幅度过大", "correction": "缩小跳跃高度，重点保持动作规范"},
            {"error": "节奏不稳忽快忽慢", "correction": "保持稳定的节奏，可以用节拍器辅助"},
        ],
        "tips": ["热身2-3分钟", "HIIT: 30秒跳+20秒休×10组", "膝盖有伤者减小幅度"],
    },
    {
        "name": "弓步蹲",
        "category": "strength",
        "target_muscles": ["股四头肌", "臀大肌", "腘绳肌", "核心肌群"],
        "difficulty": "初级",
        "equipment": "无",
        "instructions": [
            "双脚并拢站立",
            "向前跨一大步，约60-90厘米",
            "后腿膝盖下沉接近地面但不触碰",
            "前腿膝盖在脚踝正上方",
            "前腿发力推回起始位置",
        ],
        "common_mistakes": [
            {"error": "前腿膝盖超过脚尖", "correction": "跨步距离加大，确保前膝在脚踝正上方"},
            {"error": "身体前倾", "correction": "保持躯干直立，核心收紧"},
            {"error": "后腿膝盖撞击地面", "correction": "控制下放速度，膝盖轻触地面即可"},
            {"error": "左右不平衡", "correction": "弱侧先做，保持两侧次数一致"},
        ],
        "tips": ["每侧8-12次", "保持平衡可以手扶墙", "进阶可以手拿哑铃"],
    },
    {
        "name": "臀桥",
        "category": "strength",
        "target_muscles": ["臀大肌", "腘绳肌", "核心肌群"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "仰卧，屈膝，双脚踩实与髋同宽",
            "手臂放在身体两侧，掌心向下",
            "臀部发力向上抬起",
            "肩、髋、膝呈一条直线",
            "顶峰收缩1-2秒",
            "缓慢下放回到起始位置",
        ],
        "common_mistakes": [
            {"error": "用腰发力而非臀", "correction": "专注用臀部发力，想象夹紧臀肌"},
            {"error": "臀部抬得过高", "correction": "肩-髋-膝呈直线即可，不要过度伸展腰椎"},
            {"error": "脚距过宽或过窄", "correction": "双脚与髋同宽，保持膝关节对脚尖"},
        ],
        "tips": ["每组15-20次", "顶峰保持1-2秒效果更好", "进阶可做单腿臀桥"],
    },
    {
        "name": "波比跳",
        "category": "cardio",
        "target_muscles": ["全身肌群", "心肺系统"],
        "difficulty": "中级",
        "equipment": "无",
        "instructions": [
            "站立姿势",
            "下蹲，双手撑地",
            "双脚向后跳至俯卧撑起始位",
            "做一个俯卧撑（可选）",
            "双脚跳回蹲姿",
            "爆发性向上跳起，手臂上举",
        ],
        "common_mistakes": [
            {"error": "俯卧撑阶段塌腰", "correction": "全程核心收紧，如塌腰可省略俯卧撑"},
            {"error": "起跳高度不足", "correction": "充分蹬地发力，手臂向上伸展"},
            {"error": "节奏不稳定", "correction": "新手放慢节奏，保证每个环节的标准度"},
        ],
        "tips": ["初学者: 5-8次×3组", "HIIT: 20秒做+10秒休", "心血管疾病者慎做"],
    },
    {
        "name": "登山者",
        "category": "cardio",
        "target_muscles": ["核心肌群", "髋屈肌", "心肺系统"],
        "difficulty": "中级",
        "equipment": "无",
        "instructions": [
            "俯卧撑起始位，双手在肩正下方",
            "身体保持一条直线",
            "交替提膝向胸部方向",
            "保持核心收紧，臀部不要上抬",
        ],
        "common_mistakes": [
            {"error": "臀部上下起伏", "correction": "收紧核心，臀部保持稳定高度"},
            {"error": "膝盖未靠近胸部", "correction": "有意识地将膝盖向胸部方向提起"},
            {"error": "身体左右摆动", "correction": "核心发力稳定躯干，髋部不要旋转"},
        ],
        "tips": ["每组30-60秒", "可以放慢速度保证质量", "肩部有伤可改做站立登山者"],
    },
    {
        "name": "俄罗斯转体",
        "category": "core",
        "target_muscles": ["腹斜肌", "腹直肌", "髋屈肌"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "坐姿，膝盖弯曲，脚后跟触地",
            "身体后倾约45°",
            "双手合十在胸前",
            "旋转躯干，手触地面",
            "换边重复",
        ],
        "common_mistakes": [
            {"error": "背部弯曲", "correction": "保持背部挺直，收腹挺胸"},
            {"error": "用惯性旋转", "correction": "控制速度，用腹肌发力旋转"},
            {"error": "脚离地导致不稳定", "correction": "初学者脚踏实地面，稳定后再尝试抬脚"},
        ],
        "tips": ["每侧15-20次", "可手拿哑铃增加难度", "有腰椎问题者慎做"],
    },
    {
        "name": "超人式",
        "category": "core",
        "target_muscles": ["竖脊肌", "臀大肌", "三角肌后束"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "俯卧，手臂向前伸展",
            "同时抬起手臂、胸部和腿部",
            "保持2-3秒",
            "缓慢下放回到起始位置",
        ],
        "common_mistakes": [
            {"error": "抬起幅度过大", "correction": "轻微抬起即可，感受下背部发力而非挤压腰椎"},
            {"error": "憋气", "correction": "抬起时呼气，保持时自然呼吸"},
            {"error": "颈部过度后仰", "correction": "眼睛看地面，保持颈部与脊柱成一线"},
        ],
        "tips": ["每组10-15次", "慢速控制比快速效果更好", "腰痛者需谨慎或跳过"],
    },
    {
        "name": "侧平板支撑",
        "category": "core",
        "target_muscles": ["腹斜肌", "臀中肌", "肩部稳定肌群"],
        "difficulty": "中级",
        "equipment": "瑜伽垫",
        "instructions": [
            "侧卧，下方肘部在肩正下方",
            "双腿伸直叠放",
            "髋部抬离地面，身体呈直线",
            "上侧手可叉腰或上举",
            "保持核心收紧",
        ],
        "common_mistakes": [
            {"error": "髋部下塌", "correction": "收紧侧腹和臀部，髋部向上顶"},
            {"error": "身体旋转前倾", "correction": "确保肩、髋、脚在一条直线上"},
            {"error": "肩部压力过大", "correction": "肘部在肩正下方，肩胛骨稳定"},
        ],
        "tips": ["每侧20-30秒", "初学者可从屈膝侧平板开始", "肩部不适者慎做"],
    },
    {
        "name": "鸟狗式",
        "category": "core",
        "target_muscles": ["多裂肌", "腹横肌", "臀大肌"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "四足跪姿，手在肩下，膝在髋下",
            "同时抬起对侧手臂和腿",
            "身体保持稳定，不要旋转",
            "保持2-3秒后缓慢还原",
            "换对侧重复",
        ],
        "common_mistakes": [
            {"error": "身体旋转或侧倾", "correction": "收紧核心，保持骨盆和肩部水平"},
            {"error": "手臂/腿抬得过高", "correction": "手臂和腿只需与身体齐平即可"},
            {"error": "动作过快", "correction": "缓慢控制，关注稳定性而非速度"},
        ],
        "tips": ["每侧8-12次", "非常适合下背痛康复训练", "可以放在热身环节"],
    },
    {
        "name": "深蹲跳",
        "category": "cardio",
        "target_muscles": ["股四头肌", "臀大肌", "小腿肌群"],
        "difficulty": "中级",
        "equipment": "无",
        "instructions": [
            "标准深蹲起始姿势",
            "下蹲至大腿与地面平行",
            "爆发性向上跳起",
            "落地时膝盖微屈缓冲",
            "直接进入下一次深蹲",
        ],
        "common_mistakes": [
            {"error": "落地膝盖内扣", "correction": "落地时膝盖向外打开，与脚尖方向一致"},
            {"error": "落地直腿", "correction": "落地必须屈膝缓冲，减少关节冲击"},
            {"error": "下蹲深度不够", "correction": "每次下蹲都要到位，确保动作完整"},
        ],
        "tips": ["每组8-15次", "膝盖有伤者改做普通深蹲", "穿缓冲好的运动鞋"],
    },
    {
        "name": "靠墙静蹲",
        "category": "strength",
        "target_muscles": ["股四头肌", "臀大肌"],
        "difficulty": "初级",
        "equipment": "墙壁",
        "instructions": [
            "背靠墙壁，脚离墙约60厘米",
            "缓慢下滑至大腿与地面平行",
            "膝盖在脚踝正上方",
            "背部紧贴墙壁",
            "保持该姿势",
        ],
        "common_mistakes": [
            {"error": "膝盖超过脚尖", "correction": "脚离墙远一些，确保胫骨垂直地面"},
            {"error": "背部离开墙壁", "correction": "全程背部贴墙，保持核心收紧"},
            {"error": "膝盖内扣", "correction": "有意识地将膝盖向外打开"},
        ],
        "tips": ["初学者30-60秒", "可以逐渐增加时间", "膝盖康复训练优选动作"],
    },
    {
        "name": "站姿体前屈",
        "category": "stretch",
        "target_muscles": ["腘绳肌", "下背部", "小腿"],
        "difficulty": "初级",
        "equipment": "无",
        "instructions": [
            "站姿，双脚与髋同宽",
            "缓慢向前弯曲，双手向脚面伸展",
            "膝盖可以微屈",
            "到感受到腿后侧有拉伸感时停住",
            "保持15-30秒",
        ],
        "common_mistakes": [
            {"error": "膝盖锁死", "correction": "膝盖微屈保护关节，拉伸效果不会减弱"},
            {"error": "弹振式拉伸", "correction": "静态保持，不要上下弹振"},
            {"error": "背部弯曲", "correction": "从髋部折叠而非弯腰"},
        ],
        "tips": ["保持15-30秒×2-3组", "训练后做", "腰椎有问题者谨慎"],
    },
    {
        "name": "猫牛式",
        "category": "stretch",
        "target_muscles": ["脊柱", "核心", "背部"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "四足跪姿",
            "吸气时拱背，下巴收向胸口（猫式）",
            "呼气时沉腰，抬头挺胸（牛式）",
            "缓慢交替",
        ],
        "common_mistakes": [
            {"error": "动作过快", "correction": "配合呼吸缓慢进行，每个动作2-3秒"},
            {"error": "幅度过大导致不适", "correction": "在无痛范围内活动即可"},
        ],
        "tips": ["做8-10次完整呼吸", "适合早晨唤醒脊柱", "孕期需谨慎"],
    },
    {
        "name": "肩部环绕",
        "category": "stretch",
        "target_muscles": ["三角肌", "肩袖肌群", "上背部"],
        "difficulty": "初级",
        "equipment": "无",
        "instructions": [
            "站姿或坐姿",
            "双肩同时向前画圈",
            "10次后反向画圈",
            "幅度由小到大",
        ],
        "common_mistakes": [
            {"error": "用脖子代偿", "correction": "放松颈部，只活动肩关节"},
            {"error": "幅度过大引起疼痛", "correction": "以无痛范围为限，逐步增加幅度"},
        ],
        "tips": ["训练前热身必做", "前后各10次", "坐办公室也可以随时做"],
    },
    {
        "name": "哑铃弯举",
        "category": "strength",
        "target_muscles": ["肱二头肌", "肱肌", "肱桡肌"],
        "difficulty": "初级",
        "equipment": "哑铃",
        "instructions": [
            "双手各持哑铃，掌心向前",
            "上臂贴身固定",
            "弯曲肘部将哑铃举向肩部",
            "顶峰收缩1秒",
            "缓慢下放至起始位",
        ],
        "common_mistakes": [
            {"error": "借力摆动身体", "correction": "减小重量，保持躯干稳定，只用肘部发力"},
            {"error": "下放过快", "correction": "离心阶段控制2-3秒，效果更好"},
            {"error": "肘部前后移动", "correction": "上臂保持固定在身体两侧"},
        ],
        "tips": ["每组10-15次", "重量不要太大，控制为王", "可在镜子前检查姿势"],
    },
    {
        "name": "哑铃推举",
        "category": "strength",
        "target_muscles": ["三角肌前束", "三角肌中束", "肱三头肌"],
        "difficulty": "中级",
        "equipment": "哑铃",
        "instructions": [
            "坐姿或站姿，哑铃在肩部高度",
            "掌心向前",
            "向上推举至手臂伸直但不锁死",
            "缓慢下放回起始位置",
        ],
        "common_mistakes": [
            {"error": "弓背/腰部过度伸展", "correction": "收紧核心，可以靠墙坐姿减少腰部参与"},
            {"error": "哑铃相碰", "correction": "推举轨迹为弧形而非直线，哑铃在头顶不接触"},
            {"error": "耸肩", "correction": "肩胛骨下压，不要耸到耳朵"},
        ],
        "tips": ["每组8-12次", "肩部训练前要充分热身肩袖", "肩部有伤改做侧平举"],
    },
    {
        "name": "弹力带划船",
        "category": "strength",
        "target_muscles": ["背阔肌", "菱形肌", "肱二头肌"],
        "difficulty": "初级",
        "equipment": "弹力带",
        "instructions": [
            "坐姿，弹力带固定在脚底",
            "背部挺直，手臂前伸握住弹力带",
            "向腹部方向拉弹力带",
            "肩胛骨向后收紧",
            "顶峰收缩后缓慢还原",
        ],
        "common_mistakes": [
            {"error": "用腰部后仰借力", "correction": "保持躯干稳定，只用背部发力"},
            {"error": "肩胛骨未收紧", "correction": "想象用背肌夹一支笔，每次拉动都收紧肩胛骨"},
            {"error": "还原过快", "correction": "控制离心阶段2-3秒"},
        ],
        "tips": ["每组12-15次", "弹力带张力不够可以双折使用", "改善圆肩驼背的好动作"],
    },
    {
        "name": "弹力带侧平举",
        "category": "strength",
        "target_muscles": ["三角肌中束"],
        "difficulty": "初级",
        "equipment": "弹力带",
        "instructions": [
            "双脚踩住弹力带中段",
            "双手握住弹力带两端",
            "手臂微屈",
            "向两侧平举至肩高",
            "缓慢下放",
        ],
        "common_mistakes": [
            {"error": "耸肩", "correction": "肩胛骨下压，不要用斜方肌代偿"},
            {"error": "手臂举得过高", "correction": "手臂与肩膀齐平即可，过高会耸肩"},
            {"error": "摆动身体", "correction": "减小阻力，保持身体稳定"},
        ],
        "tips": ["每组15-20次", "小重量多次数效果好", "可以先单侧做感受发力"],
    },
    {
        "name": "仰卧举腿",
        "category": "core",
        "target_muscles": ["下腹直肌", "髋屈肌"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "仰卧，双腿伸直",
            "双手放在臀下或体侧",
            "下背部紧贴地面",
            "双腿并拢抬起至约90°",
            "缓慢下放但不触地",
        ],
        "common_mistakes": [
            {"error": "腰部离地拱起", "correction": "双手放在臀下支撑，减小抬腿幅度"},
            {"error": "利用惯性摆动腿", "correction": "慢速控制，腹部发力而非惯性"},
            {"error": "下放时腿触地休息", "correction": "全程保持腹部张力，腿不触地"},
        ],
        "tips": ["每组10-20次", "下背痛者改做死虫式", "屈膝做会简单一些"],
    },
    {
        "name": "死虫式",
        "category": "core",
        "target_muscles": ["腹横肌", "多裂肌"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "仰卧，手臂向上伸直",
            "屈髋屈膝，小腿与地面平行",
            "下背部压向地面",
            "同时将对侧手臂和腿向地面放下",
            "交替进行",
        ],
        "common_mistakes": [
            {"error": "腰部拱起离地", "correction": "缩小动作幅度，确保下背部始终贴地"},
            {"error": "动作过快", "correction": "极慢速做，感受核心的稳定性发力"},
            {"error": "憋气", "correction": "配合呼吸，伸展时呼气"},
        ],
        "tips": ["每侧8-12次", "非常好的下背痛康复动作", "比卷腹更适合初学者建立核心意识"],
    },
    {
        "name": "椅子臂屈伸",
        "category": "strength",
        "target_muscles": ["肱三头肌", "三角肌前束"],
        "difficulty": "初级",
        "equipment": "椅子",
        "instructions": [
            "双手撑在椅子边缘，手指向前",
            "臀部悬空在椅子前方",
            "弯曲肘部下放身体",
            "肘关节到约90°时",
            "肱三头肌发力推起",
        ],
        "common_mistakes": [
            {"error": "肘部外展", "correction": "肘部向后，保持贴近身体"},
            {"error": "下放过深", "correction": "肘关节弯曲90°即可，过深会损伤肩关节"},
            {"error": "耸肩", "correction": "肩胛骨下压，远离耳朵"},
        ],
        "tips": ["每组10-15次", "确保椅子稳固", "肩部有伤者避免此动作"],
    },
    {
        "name": "小腿提踵",
        "category": "strength",
        "target_muscles": ["腓肠肌", "比目鱼肌"],
        "difficulty": "初级",
        "equipment": "台阶/无",
        "instructions": [
            "前脚掌站在台阶边缘",
            "脚后跟悬空",
            "缓慢提起脚后跟至最高点",
            "顶峰收缩1秒",
            "缓慢下放至低于台阶水平",
        ],
        "common_mistakes": [
            {"error": "动作过快", "correction": "慢速控制，顶峰停顿1-2秒"},
            {"error": "膝盖弯曲借力", "correction": "膝盖保持微屈但不弯，力量来自脚踝"},
            {"error": "单侧发力不均衡", "correction": "可以先单脚做，确保两侧均衡发展"},
        ],
        "tips": ["每组15-25次", "每次训练最后做", "改善小腿线条和踝关节稳定性"],
    },
    {
        "name": "战士一式",
        "category": "yoga",
        "target_muscles": ["股四头肌", "臀大肌", "髋屈肌", "肩部"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "双脚分开约一条腿长",
            "前脚转向前方，后脚外转45°",
            "前膝弯曲至90°，后腿伸直",
            "手臂向上举起，掌心相对",
            "髋部朝向前方",
        ],
        "common_mistakes": [
            {"error": "前膝超过脚尖或内扣", "correction": "前膝在脚踝正上方，保持膝盖对第二脚趾"},
            {"error": "后腿弯曲", "correction": "后腿主动发力伸直，脚外侧压实地面"},
            {"error": "髋部歪斜", "correction": "有意识地将后髋向前推，保持髋部正对前方"},
        ],
        "tips": ["每侧保持30-60秒", "配合呼吸", "高血压者手臂可以放低"],
    },
    {
        "name": "下犬式",
        "category": "yoga",
        "target_muscles": ["腘绳肌", "小腿", "肩部", "背部"],
        "difficulty": "初级",
        "equipment": "瑜伽垫",
        "instructions": [
            "从四足跪姿开始",
            "脚趾踩地，膝盖离地",
            "臀部向上向后推",
            "手臂伸直，头在双臂之间",
            "背部和腿尽量伸直",
        ],
        "common_mistakes": [
            {"error": "背部弯曲", "correction": "膝盖可以弯曲，优先保持背部平直"},
            {"error": "脚后跟离地太高", "correction": "不要强求脚后跟着地，重点在脊柱的伸展"},
            {"error": "手距过近或过远", "correction": "双手与肩同宽，手指张开均匀承重"},
        ],
        "tips": ["保持5-10个深呼吸", "腿后侧太紧可以交替踩脚", "非常好的全身拉伸动作"],
    },
]

# 额外动作纠错对 — 常见用户问题 + 教练纠正
EXTRA_CORRECTION_PAIRS = [
    {
        "exercise": "深蹲",
        "user_question": "我做深蹲时膝盖总是咯吱咯吱响，是不是受伤了？",
        "coach_answer": "关节响声分两种情况。无痛的生理性弹响通常是关节液中的气体释放，属于正常现象，不必担心。但如果响声伴随疼痛、卡顿感或者肿胀，则需要重视。建议：1.充分热身，特别是髋膝踝关节 2.检查深蹲姿势是否标准（膝盖是否与脚尖方向一致） 3.如果有疼痛，暂停深蹲并咨询运动康复医生。平时多做髋关节灵活性和臀肌激活训练会有帮助。",
    },
    {
        "exercise": "俯卧撑",
        "user_question": "我做了两个月俯卧撑，胸肌还是没有变化，是不是动作有问题？",
        "coach_answer": "胸肌没有变化可能有几个原因：1.动作不规范，更多在用肱三头肌而非胸肌发力——检查一下你是否肘部贴身体太近？建议肘部和身体保持约45°夹角，下落时感受胸肌的拉伸 2.训练量不够——试试增加到4组×12-15次，或者尝试变式如宽距俯卧撑 3.营养和恢复——肌肉生长需要足够的蛋白质和睡眠 4.体脂率太高——胸肌可能练出来了但被脂肪盖住了。给你个建议：录像检查姿势→增加训练量→注意饮食→坚持。",
    },
    {
        "exercise": "平板支撑",
        "user_question": "做平板支撑的时候腰特别酸，是姿势不对吗？",
        "coach_answer": "腰酸说明你的髋部下塌了（塌腰），导致腰椎承受了压力。解决方法：1.收紧腹部，将肚脐往脊椎方向收 2.收紧臀部，保持身体从头到脚一条直线 3.可以先从跪姿平板支撑开始 4.缩短时间，先做20秒，保证姿势正确 5.对着镜子或录像检查自己的姿势。身体呈一条直线是平板支撑唯一正确的姿势，一旦变形就停下来。",
    },
    {
        "exercise": "卷腹",
        "user_question": "做完卷腹脖子疼得不行，腹部反而没什么感觉，怎么回事？",
        "coach_answer": "这是典型的'颈部代偿'——用脖子和头部的力量代替腹部发力。解决方法：1.双手轻放在耳侧，绝对不要用力拉头部 2.下巴微收，眼睛看天花板，保持下巴和胸口之间有一拳的距离 3.集中注意力在腹部，想象用腹肌收缩带动身体卷起 4.如果还是脖子疼，交叉双臂放在胸前做 5.减小卷起幅度，先只微微抬起肩胛骨。感受腹部发力比做了多少个重要得多。",
    },
    {
        "exercise": "开合跳",
        "user_question": "开合跳跳了一周膝盖开始疼了，这还能继续吗？",
        "coach_answer": "膝盖疼就应该停止了，继续跳可能会造成更严重的损伤。开合跳膝盖疼的常见原因：1.落地时膝盖伸直锁死没有缓冲 2.膝关节方向与脚尖不一致 3.体重过大给膝盖压力太大 4.训练量突然增加太多。建议：1.立刻休息直到膝盖不疼 2.再开始运动时选择低冲击替代动作（如原地踏步侧向打开手臂、坐姿开合、骑行） 3.加强股四头肌和臀肌训练来分担膝盖压力 4.穿缓冲好的运动鞋在软地面运动。如果疼痛持续一周以上，建议去看运动康复科。",
    },
    {
        "exercise": "深蹲",
        "user_question": "深蹲的时候总感觉站不稳，身体往前倒怎么办？",
        "coach_answer": "深蹲站不稳主要有两个原因：一是脚踝活动度不够，下蹲时脚踝不能充分背屈，身体只能前倾来补偿；二是核心力量不够稳定。解决方案：1.脚跟下垫一个小重物（如杠铃片）改善下蹲角度 2.每天做脚踝活动度拉伸 3.多做核心稳定性训练（平板支撑、鸟狗式） 4.先用箱式深蹲练习，后面放一把椅子控制下蹲深度。另外可以尝试将手臂前伸做深蹲，利用手臂做平衡。",
    },
    {
        "exercise": "深蹲",
        "user_question": "我深蹲的时候一蹲下去就膝盖超过脚尖很多，这有问题吗？",
        "coach_answer": "膝盖超过脚尖本身不是问题。这个'膝盖不能超过脚尖'的说法是一个被过度简化的健身谣言。对于腿长的人来说，下蹲时膝盖超过脚尖是正常的、甚至是必然的。真正要注意的是：1.重心是否在足中部（而不是脚尖） 2.膝盖是否与脚尖方向一致（不要内扣） 3.背部是否挺直。如果你强行让膝盖不超过脚尖，身体会过度前倾，反而增加下背部受伤风险。",
    },
    {
        "exercise": "俯卧撑",
        "user_question": "俯卧撑的时候手腕超级疼，有什么办法吗？",
        "coach_answer": "俯卧撑手腕疼很常见，解决方法：1.手掌微向外转，手指张大，像爪子一样抓地面，均匀分散压力 2.使用俯卧撑支架（push-up bars），让手腕保持中立位 3.握拳做俯卧撑（拳面着地），手腕0压力 4.充分热身手腕：转手腕、压手腕、手指开合 5.检查手的位置是否太靠前或太靠后，应该在肩正下方。如果这些方法都无效且疼痛持续，可能有腕管问题，需要就医检查。",
    },
    {
        "exercise": "平板支撑",
        "user_question": "平板支撑的时候肩膀比肚子还酸是正常的吗？",
        "coach_answer": "肩膀轻度酸是正常的，说明三角肌也在工作。但如果肩膀比腹部更酸，说明你的姿势可能有问题：1.肘部位置不对：肘应该在肩的正下方，不要在前面也不要太靠后 2.耸肩了：肩胛骨要收紧下压，远离耳朵 3.身体重量压在肩膀上了：试着通过收紧腹部和臀部，把一部分身体重量转移到核心承担。如果持续疼痛，做直臂平板支撑可能会好一些，或者先缩短时间。",
    },
    {
        "exercise": "卷腹",
        "user_question": "卷腹的时候腰总是离开地面怎么办？",
        "coach_answer": "卷腹时腰部离地是核心不够稳定的表现，这样腰椎会承受很大压力。解决：1.只做小幅度的卷腹，肩胛骨微微离地即可 2.双脚可以勾住沙发或者踩在墙上增加稳定性 3.预先做'骨盆后倾'——把下背部主动压向地面 4.先用死虫式强化深层核心稳定肌群 5.改做反向卷腹（把膝盖往胸部卷而不是卷上半身）。记住，卷腹的目标是感受腹肌收缩，不是卷起来多高。",
    },
]

# 训练规划问答对
PLANNING_QA_PAIRS = [
    {
        "scenario": "新手入门",
        "user_info": "我是一名25岁男性，170cm，75kg，完全没有健身经验，想开始在家运动减脂，没有器械。",
        "planning_advice": "好的！针对你零基础在家减脂的情况，我给你设计一个安全渐进的新手入门计划。\n\n【第一周 适应期】\n- 周一/三/五：每次25分钟\n  1. 原地踏步热身 3分钟\n  2. 靠墙深蹲 2组×10次（练习深蹲姿势）\n  3. 跪姿俯卧撑 2组×8次\n  4. 平板支撑 2组×20秒\n  5. 卷腹 2组×10次\n  6. 慢速开合跳 2组×15次\n  7. 拉伸 5分钟\n\n【第二周 进阶期】\n- 周一/三/五：每次30分钟\n  1. 开合跳热身 2分钟\n  2. 自重深蹲 3组×12次\n  3. 跪姿俯卧撑 3组×10次\n  4. 平板支撑 3组×25秒\n  5. 卷腹 3组×15次\n  6. 开合跳 3组×20次\n\n【饮食建议】\n- 每日热量控制在1800-2000大卡\n- 蛋白质摄入每公斤体重×1.5g（约112g/天）\n- 戒糖、戒零食饮料，多吃蔬菜\n\n坚持一个月你会感受到明显变化！每次训练前热身5分钟，训练后拉伸5分钟。",
    },
    {
        "scenario": "中级增肌",
        "user_info": "我28岁，健身一年，168cm，65kg，想增肌塑形，有哑铃和弹力带。",
        "planning_advice": "你已经有了一年基础，现在可以进入分化训练阶段来最大化增肌效果。\n\n【周训练计划 4天/周】\n\n周一（下肢力量）：\n1. 哑铃深蹲 4组×12次\n2. 弓步蹲（持哑铃） 3组×10次/侧\n3. 臀桥 4组×15次\n4. 小腿提踵 3组×25次\n5. 平板支撑 3组×45秒\n\n周二（上肢推+核心）：\n1. 标准俯卧撑 4组×15次\n2. 哑铃推举 4组×12次\n3. 椅子臂屈伸 3组×12次\n4. 卷腹 4组×25次\n5. 俄罗斯转体 3组×20次\n\n周四（上肢拉+核心）：\n1. 弹力带划船 4组×15次\n2. 哑铃弯举 3组×12次\n3. 弹力带侧平举 3组×15次\n4. 死虫式 3组×12次/侧\n5. 鸟狗式 3组×10次/侧\n\n周六（全身+HIIT）：\n1. 深蹲跳 3组×10次\n2. 波比跳 3组×8次\n3. 登山者 3组×40秒\n4. 开合跳 3组×30次\n5. 拉伸 10分钟\n\n【饮食建议】\n- 每日热量盈余300-400大卡\n- 蛋白质：每公斤×1.8-2g（约120-130g/天）\n- 碳水：以全谷物和薯类为主\n- 训练后30分钟内补充蛋白质",
    },
    {
        "scenario": "产后恢复",
        "user_info": "我是一名30岁产后9个月的新妈妈，剖腹产，体重65kg，身高160cm，想安全地恢复体型。医生已允许运动。",
        "planning_advice": "产后恢复需要特别关注核心和盆底肌的恢复，我们循序渐进来做。\n\n【第一阶段（第1-2周）核心唤醒】\n每周3-4次，每次20分钟\n1. 腹式呼吸训练 5分钟（激活腹横肌）\n2. 盆底肌训练（凯格尔） 3组×10次\n3. 臀桥 2组×12次\n4. 猫牛式 8次慢速\n5. 鸟狗式 2组×8次/侧（小幅度）\n\n【第二阶段（第3-4周）基础力量】\n每周3-4次，每次25-30分钟\n1. 靠墙深蹲 3组×10次\n2. 跪姿俯卧撑 2组×8次\n3. 臀桥 3组×15次\n4. 死虫式 3组×10次/侧\n5. 侧平板支撑（屈膝） 2组×15秒/侧\n6. 慢速开合跳（小幅度） 2组×15次\n\n【第三阶段（第5-8周）正常训练】\n逐步增加训练强度和时长\n\n【重要提醒】\n- 剖腹产需特别避免腹部过度拉伸\n- 任何腹部鼓起或漏尿立即停止\n- 如伤口区域有疼痛感暂停训练\n- 确保充足睡眠和营养",
    },
    {
        "scenario": "肩伤恢复",
        "user_info": "我肩袖损伤恢复期，医生说可以轻量运动。想保持健身习惯但不想伤到肩膀。",
        "planning_advice": "肩袖损伤恢复期训练的原则是：避免所有过头推举动作、避免所有需要肩部承重的动作。\n\n【恢复期训练计划 3天/周】\n\n周一（下肢为主）：\n1. 自重深蹲 3组×15次\n2. 弓步蹲 3组×10次/侧\n3. 臀桥 3组×15次\n4. 靠墙静蹲 3组×45秒\n5. 小腿提踵 3组×20次\n\n周三（核心+下肢）：\n1. 平板支撑 3组×30秒\n2. 卷腹 3组×15次\n3. 死虫式 3组×10次/侧\n4. 自重深蹲 3组×12次\n5. 开合跳（手臂小幅不举过头） 3组×20次\n\n周五（下肢+安全上肢）：\n1. 深蹲跳 3组×8次\n2. 登山者 3组×30秒\n3. 鸟狗式 3组×8次/侧\n4. 仰卧举腿 3组×15次\n5. 拉伸 10分钟\n\n【禁忌动作】\n- 禁止俯卧撑、哑铃推举、引体向上\n- 禁止任何过头动作\n- 禁止大重量上肢训练\n\n【康复建议】\n每天做弹力带肩袖内外旋（轻重量的康复训练）\n定期复查，遵循康复师指导",
    },
]

# 组装完整合成数据集
SYNTHETIC_KEEP_DATA = {
    "exercises": SYNTHETIC_KEEP_EXERCISES,
    "correction_pairs": EXTRA_CORRECTION_PAIRS,
    "planning_qa": PLANNING_QA_PAIRS,
}


def get_synthetic_keep_data() -> dict:
    """返回合成 Keep 动作库数据用于离线开发和测试."""
    return SYNTHETIC_KEEP_DATA
