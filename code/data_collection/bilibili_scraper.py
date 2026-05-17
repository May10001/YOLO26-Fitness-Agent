"""
B站健身教程字幕爬虫 — 抓取健身区热门视频的 CC 字幕。

数据来源:
  - B站健身分区: https://api.bilibili.com/x/web-interface/...
  - CC 字幕接口: https://api.bilibili.com/x/player/v2?bvid=...

注意: B站 API 需要 cookie 和 UA，实际部署需替换为真实凭证。
      本模块同时包含合成数据生成逻辑用于离线测试。
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 健身区常见 UP 主 bvid 列表 (公开视频 ID)
FITNESS_BVIDS = [
    # 叔贵健身
    "BV1yK4y1S7gR", "BV1KX4y1z7mE", "BV1e54y1B7VL",
    # NowFitness
    "BV1pG4y1m7F3", "BV18L411X7kQ",
    # 闫帅奇
    "BV19v4y1H7wM", "BV1RD4y1k7qL",
    # 帅soserious
    "BV1RG4y167rH", "BV1PM4y1H7vN",
    # 韩小四April
    "BV1sK4y1j7Ew", "BV15v411k7RV",
]

FITNESS_SEARCH_KEYWORDS = [
    "健身动作 教学",
    "深蹲 正确姿势",
    "俯卧撑 教学",
    "平板支撑 正确做法",
    "卷腹 教学",
    "开合跳 正确姿势",
    "哑铃 动作教学",
    "拉伸 教学",
    "健身 入门 教程",
    "居家健身 教学",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


@dataclass
class BilibiliSubtitle:
    """B站视频字幕条目."""
    bvid: str
    title: str
    author: str
    duration_sec: int
    view_count: int
    subtitle_text: str  # 完整字幕文本
    segments: list[dict] = field(default_factory=list)  # 分段字幕 [{start, end, text}]
    tags: list[str] = field(default_factory=list)


class BilibiliScraper:
    """B站健身视频字幕爬虫."""

    def __init__(
        self,
        output_dir: Path = Path("./data/raw/bilibili"),
        cookie: str = "",
        rate_limit: float = 1.5,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cookie = cookie
        self.rate_limit = rate_limit
        self._last_request = 0.0
        self._session = None

    def _ensure_session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update(HEADERS)
            if self.cookie:
                self._session.headers["Cookie"] = self.cookie

    def _rate_limit_wait(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()

    def search_fitness_videos(self, keyword: str, max_pages: int = 3) -> list[dict]:
        """搜索健身相关视频，返回 bvid 列表和元信息."""
        self._ensure_session()
        results = []
        for page in range(1, max_pages + 1):
            self._rate_limit_wait()
            try:
                url = "https://api.bilibili.com/x/web-interface/search/type"
                params = {
                    "search_type": "video",
                    "keyword": keyword,
                    "page": page,
                    "page_size": 20,
                }
                resp = self._session.get(url, params=params, timeout=15)
                data = resp.json()
                if data.get("code") != 0:
                    logger.warning("B站搜索失败: code=%s, msg=%s", data.get("code"), data.get("message"))
                    continue
                for item in data.get("data", {}).get("result", []):
                    results.append({
                        "bvid": item.get("bvid"),
                        "title": item.get("title", ""),
                        "author": item.get("author", ""),
                        "duration": self._parse_duration(item.get("duration", "0:00")),
                        "view_count": item.get("play", 0),
                        "tags": item.get("tag", "").split(","),
                        "description": item.get("description", ""),
                    })
            except Exception as e:
                logger.error("搜索请求异常: %s", e)
        return results

    def get_subtitle(self, bvid: str) -> Optional[BilibiliSubtitle]:
        """获取单个视频的 CC 字幕."""
        self._ensure_session()
        self._rate_limit_wait()
        try:
            # 1. 获取视频信息
            info_url = "https://api.bilibili.com/x/web-interface/view"
            params = {"bvid": bvid}
            resp = self._session.get(info_url, params=params, timeout=15)
            data = resp.json()
            if data.get("code") != 0:
                logger.warning("获取视频信息失败: bvid=%s, code=%s", bvid, data.get("code"))
                return None
            vdata = data.get("data", {})

            # 2. 获取字幕列表
            player_url = "https://api.bilibili.com/x/player/v2"
            player_params = {"bvid": bvid, "cid": vdata.get("cid", 0)}
            self._rate_limit_wait()
            player_resp = self._session.get(player_url, params=player_params, timeout=15)
            player_data = player_resp.json()

            subtitle_text = ""
            segments = []

            sub_list = player_data.get("data", {}).get("subtitle", {}).get("subtitles", [])
            if sub_list:
                sub_url = sub_list[0].get("subtitle_url", "")
                if sub_url and not sub_url.startswith("http"):
                    sub_url = "https:" + sub_url
                if sub_url:
                    self._rate_limit_wait()
                    sub_resp = self._session.get(sub_url, timeout=15)
                    sub_data = sub_resp.json()
                    for item in sub_data.get("body", []):
                        seg = {
                            "start": item.get("from", 0),
                            "end": item.get("to", 0),
                            "text": item.get("content", ""),
                        }
                        segments.append(seg)
                        subtitle_text += seg["text"] + "\n"

            return BilibiliSubtitle(
                bvid=bvid,
                title=vdata.get("title", ""),
                author=vdata.get("owner", {}).get("name", ""),
                duration_sec=vdata.get("duration", 0),
                view_count=vdata.get("stat", {}).get("view", 0),
                subtitle_text=subtitle_text.strip(),
                segments=segments,
                tags=vdata.get("tname", "").split("/") if vdata.get("tname") else [],
            )
        except Exception as e:
            logger.error("获取字幕异常: bvid=%s, err=%s", bvid, e)
            return None

    def scrape_all(self, max_videos: int = 100) -> list[BilibiliSubtitle]:
        """抓取健身区热门视频字幕."""
        all_videos = []
        seen_bvids = set()

        # 从搜索关键词获取
        for kw in FITNESS_SEARCH_KEYWORDS:
            if len(all_videos) >= max_videos:
                break
            logger.info("搜索关键词: %s", kw)
            videos = self.search_fitness_videos(kw, max_pages=2)
            for v in videos:
                if v["bvid"] not in seen_bvids and len(all_videos) < max_videos:
                    seen_bvids.add(v["bvid"])
                    all_videos.append(v)

        # 从已知 UP 主获取
        for bvid in FITNESS_BVIDS:
            if bvid not in seen_bvids and len(all_videos) < max_videos:
                seen_bvids.add(bvid)
                all_videos.append({"bvid": bvid})

        # 逐视频抓取字幕
        subtitles = []
        for v in all_videos:
            logger.info("抓取字幕: bvid=%s, title=%s", v.get("bvid"), v.get("title", "")[:40])
            sub = self.get_subtitle(v["bvid"])
            if sub and sub.subtitle_text:
                subtitles.append(sub)
                self._save_subtitle(sub)
            if len(subtitles) >= max_videos // 2:
                break

        return subtitles

    def _save_subtitle(self, sub: BilibiliSubtitle):
        path = self.output_dir / f"{sub.bvid}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "bvid": sub.bvid,
                "title": sub.title,
                "author": sub.author,
                "duration_sec": sub.duration_sec,
                "view_count": sub.view_count,
                "subtitle_text": sub.subtitle_text,
                "segments": sub.segments,
                "tags": sub.tags,
            }, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _parse_duration(dur_str: str) -> int:
        parts = dur_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0


# ============================================================
# 合成字幕数据 (离线测试/数据增强)
# ============================================================

SYNTHETIC_BILIBILI_SUBTITLES = [
    {
        "exercise": "深蹲",
        "title": "深蹲标准动作教学 | 学会这5个要点告别膝盖疼",
        "segments": [
            "大家好，今天教大家深蹲的正确姿势",
            "第一个要点，双脚与肩同宽，脚尖微微向外打开15到30度",
            "第二个要点，下蹲的时候髋关节先启动，像坐椅子一样往后坐",
            "很多人做深蹲犯的第一个错误就是膝盖过度前移，超过脚尖太多，这样会给膝关节带来很大压力",
            "膝盖应该和脚尖保持同一个方向，一定不要膝盖内扣",
            "第三个要点，全程保持背部挺直，收紧核心",
            "如果你发现自己下蹲时身体前倾很厉害，说明你的脚踝灵活性可能不够",
            "可以先在脚跟下面垫一个小杠铃片来改善",
            "第四个要点，下蹲到大腿与地面平行或者稍微低一点就可以了",
            "第五个要点，站起的时候臀部用力收紧，回到起始位置",
            "常见的错误动作：第一是膝盖内扣，第二是弓背，第三是脚后跟离地",
            "如果你有这些问题，一定要先用轻重量或者自重把动作练标准",
            "好的，接下来我给大家演示几组标准深蹲",
        ],
    },
    {
        "exercise": "俯卧撑",
        "title": "俯卧撑从零开始 | 3个退阶动作帮你完成第一个标准俯卧撑",
        "segments": [
            "俯卧撑是上肢训练的黄金动作，但是很多人做不标准",
            "今天我们来讲俯卧撑的正确姿势和常见错误",
            "双手放在肩膀正下方，比肩膀稍微宽一点点",
            "手指张开，均匀地压在地面上",
            "身体从头到脚跟要形成一条直线，核心收紧",
            "很多人犯的第一个错误就是塌腰，腰往下塌了",
            "这说明你的核心力量不够，可以先做跪姿俯卧撑",
            "第二个常见错误是肘部打开太宽，超过了90度",
            "肘部应该和身体保持大约45度的夹角",
            "这样既能有效锻炼胸肌和肱三头肌，又能防止肩关节受伤",
            "下降的时候吸气，胸口快要碰到地面的时候停住",
            "然后呼气推起来，注意不要锁死肘关节",
            "如果你一个标准俯卧撑都做不了，我教你三个退阶动作",
            "第一，先从墙上俯卧撑开始，站姿推墙",
            "第二，进阶到跪姿俯卧撑，膝盖着地",
            "第三，做上斜俯卧撑，手放在椅子或者台阶上",
            "坚持练习两到四周，你就能完成第一个标准俯卧撑了",
        ],
    },
    {
        "exercise": "平板支撑",
        "title": "平板支撑你真的做对了吗？90%的人都犯了这3个错误",
        "segments": [
            "平板支撑看起来简单，但其实大部分人做的都不标准",
            "今天我们来讲平板支撑的正确姿势",
            "首先，肘部放在肩膀正下方，前臂平行向前",
            "双手可以平放也可以握拳，看个人习惯",
            "头部保持中立位，眼睛看地面，不要抬头也不要低头",
            "身体从肩膀到脚踝要形成一条直线",
            "最常见的第一个错误就是塌腰，髋部往下掉",
            "这样腰椎会承受很大压力，不仅没效果还容易受伤",
            "解决方法就是收紧腹部和臀部，想象把肚脐往脊椎方向收",
            "第二个错误是屁股撅得太高，像个山峰一样",
            "这样核心几乎没有参与发力",
            "第三个错误是耸肩，肩膀耸到耳朵旁边",
            "肩胛骨要往下往后收紧",
            "平板支撑的时间不是越久越好，质量比数量重要得多",
            "初学者能坚持20到30秒就很好了",
            "一旦感觉身体开始变形了就应该停下来，不要硬撑",
        ],
    },
    {
        "exercise": "卷腹",
        "title": "卷腹vs仰卧起坐哪个更好？科学解释+标准动作教学",
        "segments": [
            "很多人练腹肌还在做仰卧起坐，其实卷腹更科学更安全",
            "今天来讲卷腹的正确做法",
            "仰卧在瑜伽垫上，屈膝，双脚踩实地面",
            "双手轻轻放在耳朵两侧，注意是放不是拉",
            "下巴微收，眼睛看天花板",
            "用腹部的力量卷起上背部，肩胛骨离开地面就可以了",
            "下背部始终保持贴地，不要离开地面",
            "卷起到最高点的时候呼气，感受腹肌的收缩",
            "然后控制着慢慢下放，吸气",
            "最常见的错误就是用颈部发力，做完了脖子疼肚子没感觉",
            "如果你有这个问题，试试把双手交叉放在胸前",
            "第二个常见错误是卷起幅度太大，整个背都起来了",
            "卷腹只需要肩胛骨离地，不需要像仰卧起坐那样整个坐起来",
            "第三个错误就是做得太快，用惯性完成动作",
            "卷腹的核心是控制，快起慢放",
            "建议做3到4组，每组15到25次",
        ],
    },
    {
        "exercise": "开合跳",
        "title": "开合跳燃脂效果最好的方式 | HIIT入门动作教学",
        "segments": [
            "开合跳是最方便的有氧运动之一，随时随地都能做",
            "今天来讲开合跳的正确姿势和注意事项",
            "起始姿势：双脚并拢，手臂自然放在身体两侧",
            "跳起的时候双脚向两侧打开，同时手臂从两侧向上举起",
            "手臂要举过头顶，双手在头顶上方",
            "落地的时膝盖要微屈缓冲，不要直腿落地",
            "这样会减轻膝关节的冲击力",
            "再跳起回到起始姿势，双脚并拢，手臂回到体侧",
            "常见错误第一：手臂没有举过头顶，只举到肩膀高度",
            "这样就减少了运动幅度，燃脂效果打折扣",
            "第二：落地声音很大，说明缓冲不够",
            "长期这样对膝关节和踝关节都不好",
            "第三：核心没有收紧，身体晃动太大",
            "全程保持挺胸收腹，控制身体的稳定性",
            "开合跳作为热身做2到3分钟就够了",
            "作为HIIT训练可以做30秒全力跳加20秒休息的间歇",
            "膝盖有伤的同学要慎重，可以减小跳跃幅度",
        ],
    },
]


def get_synthetic_bilibili_data() -> list[dict]:
    """返回合成 B 站字幕数据用于离线开发和测试."""
    return SYNTHETIC_BILIBILI_SUBTITLES
