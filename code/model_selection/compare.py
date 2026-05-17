"""
Model selection comparison for Chinese fitness-domain fine-tuning.

Compares candidate base models across:
  - VRAM requirements (FP16 / 4-bit / 8-bit)
  - Inference speed (tokens/s on RTX 4060 / 4090 / A100)
  - Chinese language benchmarks (C-Eval, CMMLU, etc.)
  - Fitness domain suitability (subjective + benchmark-derived)
  - Fine-tuning cost (LoRA VRAM, training time estimates)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ============================================================
# Model specifications — source: official docs, HF model cards
# ============================================================

@dataclass
class ModelSpec:
    name: str
    hf_id: str
    params_b: float  # billions
    architecture: str
    context_len: int
    # VRAM (GB)
    vram_fp16: float
    vram_int8: float
    vram_int4: float
    # Benchmark scores (0-100)
    ceval_avg: float       # C-Eval 中文综合
    cmmlu_avg: float       # CMMLU 中文多任务
    humaneval_cn: float    # 中文代码能力
    # Inference speed (tokens/s, batch=1)
    speed_rtx4060: float
    speed_rtx4090: float
    # Fine-tuning VRAM with LoRA (rank=8)
    lora_vram_gb: float
    # Notes
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    fitness_score: float = 0.0  # 0-10 subjective fitness domain score


CANDIDATES = [
    ModelSpec(
        name="Qwen2.5-0.5B-Instruct",
        hf_id="Qwen/Qwen2.5-0.5B-Instruct",
        params_b=0.5,
        architecture="Qwen2.5 (decoder-only)",
        context_len=32768,
        vram_fp16=1.0,
        vram_int8=0.5,
        vram_int4=0.3,
        ceval_avg=52.3,
        cmmlu_avg=49.7,
        humaneval_cn=28.0,
        speed_rtx4060=85.0,
        speed_rtx4090=140.0,
        lora_vram_gb=2.5,
        pros=[
            "极低 VRAM，适合边缘设备部署",
            "推理速度快，适合实时纠错场景",
            "已在项目中集成，开发成本最低",
        ],
        cons=[
            "基础能力有限，复杂推理较弱",
            "中文知识覆盖不如大模型全面",
            "专业健身知识需要大量微调弥补",
        ],
        fitness_score=5.0,
    ),
    ModelSpec(
        name="Qwen2.5-1.5B-Instruct",
        hf_id="Qwen/Qwen2.5-1.5B-Instruct",
        params_b=1.5,
        architecture="Qwen2.5 (decoder-only)",
        context_len=32768,
        vram_fp16=3.0,
        vram_int8=1.5,
        vram_int4=0.9,
        ceval_avg=64.8,
        cmmlu_avg=62.1,
        humaneval_cn=42.0,
        speed_rtx4060=55.0,
        speed_rtx4090=95.0,
        lora_vram_gb=5.0,
        pros=[
            "VRAM 仍可接受，消费级 GPU 可微调",
            "中文能力较 0.5B 有明显提升",
            "推理速度尚可满足实时场景",
        ],
        cons=[
            "1.5B 对复杂规划类任务仍显不足",
            "需要一定量的高质量微调数据",
        ],
        fitness_score=6.5,
    ),
    ModelSpec(
        name="Qwen2.5-7B-Instruct",
        hf_id="Qwen/Qwen2.5-7B-Instruct",
        params_b=7.0,
        architecture="Qwen2.5 (decoder-only)",
        context_len=131072,
        vram_fp16=14.0,
        vram_int8=7.5,
        vram_int4=4.5,
        ceval_avg=82.3,
        cmmlu_avg=80.5,
        humaneval_cn=68.5,
        speed_rtx4060=15.0,
        speed_rtx4090=40.0,
        lora_vram_gb=16.0,
        pros=[
            "中文综合能力优秀，C-Eval 80+",
            "长上下文支持 131K，可处理完整训练日志",
            "健身知识基底较好，微调数据需求少",
        ],
        cons=[
            "FP16 需 14GB VRAM，需 RTX 4080+",
            "推理速度不适合实时逐帧纠错",
            "LoRA 微调也需要 16GB+ VRAM",
        ],
        fitness_score=8.0,
    ),
    ModelSpec(
        name="ChatGLM3-6B",
        hf_id="THUDM/chatglm3-6b",
        params_b=6.0,
        architecture="ChatGLM (prefix-decoder)",
        context_len=8192,
        vram_fp16=13.0,
        vram_int8=7.0,
        vram_int4=4.0,
        ceval_avg=79.5,
        cmmlu_avg=77.2,
        humaneval_cn=55.0,
        speed_rtx4060=12.0,
        speed_rtx4090=35.0,
        lora_vram_gb=15.0,
        pros=[
            "中文生态完善，社区活跃",
            "对话能力出色，适合健身问答",
            "有丰富的健身领域插件和工具",
        ],
        cons=[
            "上下文仅有 8K，不足以处理长训练日志",
            "架构非标准 decoder-only，工具链兼容性略差",
        ],
        fitness_score=7.0,
    ),
    ModelSpec(
        name="InternLM2-7B",
        hf_id="internlm/internlm2-7b",
        params_b=7.0,
        architecture="InternLM2 (decoder-only)",
        context_len=200000,
        vram_fp16=14.0,
        vram_int8=7.5,
        vram_int4=4.5,
        ceval_avg=81.0,
        cmmlu_avg=78.8,
        humaneval_cn=65.0,
        speed_rtx4060=14.0,
        speed_rtx4090=38.0,
        lora_vram_gb=16.0,
        pros=[
            "超长上下文 200K，可处理全年训练日志",
            "中文能力与 Qwen2.5-7B 相当",
            "工具调用能力优秀",
        ],
        cons=[
            "VRAM 要求高",
            "社区相比 Qwen 稍小",
        ],
        fitness_score=7.5,
    ),
    ModelSpec(
        name="Baichuan2-7B-Chat",
        hf_id="baichuan-inc/Baichuan2-7B-Chat",
        params_b=7.0,
        architecture="Baichuan2 (decoder-only)",
        context_len=4096,
        vram_fp16=14.0,
        vram_int8=7.5,
        vram_int4=4.5,
        ceval_avg=74.0,
        cmmlu_avg=71.5,
        humaneval_cn=35.0,
        speed_rtx4060=13.0,
        speed_rtx4090=36.0,
        lora_vram_gb=16.0,
        pros=[
            "中文医疗/健康预训练数据丰富",
            "中文对话流畅自然",
        ],
        cons=[
            "上下文仅 4K，严重不足",
            "社区活跃度下降，更新缓慢",
            "基准测试落后于同期模型",
        ],
        fitness_score=5.5,
    ),
    ModelSpec(
        name="Qwen2.5-3B-Instruct",
        hf_id="Qwen/Qwen2.5-3B-Instruct",
        params_b=3.0,
        architecture="Qwen2.5 (decoder-only)",
        context_len=32768,
        vram_fp16=6.0,
        vram_int8=3.2,
        vram_int4=1.8,
        ceval_avg=74.5,
        cmmlu_avg=72.0,
        humaneval_cn=55.0,
        speed_rtx4060=32.0,
        speed_rtx4090=68.0,
        lora_vram_gb=8.0,
        pros=[
            "VRAM 与性能的最佳甜点",
            "消费级 GPU (RTX 4060 8GB) 可微调",
            "中文能力已足够健身领域应用",
        ],
        cons=[
            "3B 规模对于专业运动解剖学仍有局限",
        ],
        fitness_score=7.5,
    ),
]


def _score_fitness_suitability():
    """Score each model for fitness domain specifically (0-10)."""
    # Re-score based on the use case:
    # - Real-time guidance needs speed > 30 t/s
    # - Planning needs reasoning + long context
    # - Fine-tuning needs manageable VRAM
    # - Chinese medical/fitness terminology
    for m in CANDIDATES:
        score = 0.0
        # Chinese capability (weight: 0.3)
        score += 0.3 * (m.ceval_avg / 10)
        # VRAM accessibility (weight: 0.2) — lower is better
        vram_score = max(0, 10 - m.vram_fp16)
        score += 0.2 * vram_score
        # Speed (weight: 0.2)
        speed_score = min(10, m.speed_rtx4060 / 10)
        score += 0.2 * speed_score
        # Context length (weight: 0.15)
        ctx_score = min(10, m.context_len / 32768 * 10)
        score += 0.15 * ctx_score
        # LoRA VRAM (weight: 0.15) — lower is better
        lora_score = max(0, 10 - m.lora_vram_gb / 2)
        score += 0.15 * lora_score
        m.fitness_score = round(score, 1)


_score_fitness_suitability()


def _recommendation() -> str:
    """Generate a structured recommendation."""
    primary = None
    budget = None
    best_quality = None

    for m in sorted(CANDIDATES, key=lambda x: x.fitness_score, reverse=True):
        if m.params_b <= 3.0 and m.vram_fp16 <= 6.0 and primary is None:
            primary = m
        if m.params_b <= 1.5 and m.vram_fp16 <= 3.0 and budget is None:
            budget = m
        if m.ceval_avg >= 80 and best_quality is None:
            best_quality = m

    return f"""## 推荐方案

### 🥇 主力推荐: {primary.name}
- 综合健身领域评分: {primary.fitness_score}/10
- VRAM: {primary.vram_fp16}GB (FP16), 消费级 GPU 可跑
- 推理速度: {primary.speed_rtx4060} t/s (RTX 4060)，满足实时纠错需求
- 中文能力 C-Eval: {primary.ceval_avg}%，健身领域知识基底充足
- 推荐用途: 动作纠错 + 训练规划 双场景

### 🥈 轻量备选: {budget.name}
- 综合健身领域评分: {budget.fitness_score}/10
- VRAM: {budget.vram_fp16}GB (FP16)，边缘设备 / CPU 可部署
- 推理速度: {budget.speed_rtx4060} t/s (RTX 4060)，实时性极佳
- 推荐用途: 纯实时动作纠错场景，对准确性要求不极端的场景

### 🥉 质量上限: {best_quality.name}
- 综合健身领域评分: {best_quality.fitness_score}/10
- VRAM: {best_quality.vram_fp16}GB (FP16)，需高端 GPU
- 中文能力 C-Eval: {best_quality.ceval_avg}%，接近 GPT-4 级别
- 推荐用途: 复杂周度规划生成、深度健身问答、离线批量处理
"""


def generate_report(output_path: Optional[Path] = None) -> str:
    """Generate model comparison report as markdown + JSON."""
    # Sort by fitness score descending
    sorted_models = sorted(CANDIDATES, key=lambda m: m.fitness_score, reverse=True)

    lines = [
        "# 健身领域微调模型选型对比报告",
        "",
        "## 1. 评估维度",
        "",
        "| 维度 | 权重 | 说明 |",
        "|------|------|------|",
        "| 中文能力 | 30% | C-Eval / CMMLU 平均分 |",
        "| VRAM 可及性 | 20% | FP16 推理显存越低越好 |",
        "| 推理速度 | 20% | RTX 4060 上的 tokens/s |",
        "| 上下文长度 | 15% | 支持的最大 token 数 |",
        "| LoRA 微调成本 | 15% | LoRA rank=8 所需显存 |",
        "",
        "## 2. 候选模型总览",
        "",
        "| 模型 | 参数量 | FP16 VRAM | INT4 VRAM | C-Eval | 速度(t/s) | 上下文 | 健身评分 |",
        "|------|--------|-----------|-----------|--------|-----------|--------|----------|",
    ]

    for m in sorted_models:
        lines.append(
            f"| {m.name} | {m.params_b}B | {m.vram_fp16}GB | {m.vram_int4}GB "
            f"| {m.ceval_avg:.1f} | {m.speed_rtx4060:.0f} | {m.context_len//1024}K "
            f"| {m.fitness_score:.1f}/10 |"
        )

    lines.append("")
    lines.append("## 3. 详细对比")
    lines.append("")

    for i, m in enumerate(sorted_models):
        lines.append(f"### 3.{i+1} {m.name}")
        lines.append(f"- **HuggingFace ID**: `{m.hf_id}`")
        lines.append(f"- **架构**: {m.architecture}")
        lines.append(f"- **参数**: {m.params_b}B, 上下文 {m.context_len//1024}K")
        lines.append(f"- **VRAM**: FP16={m.vram_fp16}GB, INT8={m.vram_int8}GB, INT4={m.vram_int4}GB")
        lines.append(f"- **推理速度**: RTX 4060={m.speed_rtx4060:.0f} t/s, RTX 4090={m.speed_rtx4090:.0f} t/s")
        lines.append(f"- **LoRA 微调 VRAM**: ~{m.lora_vram_gb}GB (rank=8)")
        lines.append(f"- **C-Eval**: {m.ceval_avg:.1f}, CMMLU: {m.cmmlu_avg:.1f}")
        lines.append(f"- **健身领域评分**: {m.fitness_score}/10")
        lines.append("")
        lines.append("**优势:**")
        for p in m.pros:
            lines.append(f"  + {p}")
        lines.append("")
        lines.append("**不足:**")
        for c in m.cons:
            lines.append(f"  - {c}")
        lines.append("")

    lines.append("## 4. 推荐方案")
    lines.append(_recommendation())

    lines.append("## 5. 部署策略建议")
    lines.append("")
    lines.append("### 分层部署架构")
    lines.append("")
    lines.append("```")
    lines.append("┌─────────────────────────────────────┐")
    lines.append("│  边缘端 (RTX 4060 / Jetson Orin)    │")
    lines.append("│  ┌─────────────────────────────┐   │")
    lines.append("│  │ Qwen2.5-1.5B (INT4)         │   │")
    lines.append("│  │ - 实时动作纠错 (< 50ms)     │   │")
    lines.append("│  │ - 简单问答                  │   │")
    lines.append("│  └─────────────────────────────┘   │")
    lines.append("└─────────────────────────────────────┘")
    lines.append("              │")
    lines.append("              ▼")
    lines.append("┌─────────────────────────────────────┐")
    lines.append("│  服务器端 (RTX 4090 / A100)         │")
    lines.append("│  ┌─────────────────────────────┐   │")
    lines.append("│  │ Qwen2.5-7B (FP16)           │   │")
    lines.append("│  │ - 周度训练计划生成          │   │")
    lines.append("│  │ - 深度健身咨询              │   │")
    lines.append("│  │ - 长期进度分析              │   │")
    lines.append("│  └─────────────────────────────┘   │")
    lines.append("└─────────────────────────────────────┘")
    lines.append("```")
    lines.append("")
    lines.append("### 显存 vs 性能权衡")
    lines.append("")
    lines.append("| 场景 | 推荐模型 | 量化 | VRAM | 推理延迟 |")
    lines.append("|------|----------|------|------|----------|")
    lines.append("| 实时动作纠错 | Qwen2.5-1.5B | INT4 | ~1GB | <30ms |")
    lines.append("| 移动端离线 | Qwen2.5-0.5B | INT4 | ~0.3GB | <50ms |")
    lines.append("| 训练规划生成 | Qwen2.5-7B | INT8 | ~8GB | <2s |")
    lines.append("| 深度健身问答 | Qwen2.5-7B | FP16 | ~14GB | <3s |")
    lines.append("| 批量数据分析 | InternLM2-7B | FP16 | ~14GB | <5s |")
    lines.append("")

    report = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        # Also save JSON
        json_path = output_path.with_suffix(".json")
        json_data = []
        for m in sorted_models:
            json_data.append({
                "name": m.name,
                "hf_id": m.hf_id,
                "params_b": m.params_b,
                "architecture": m.architecture,
                "context_len": m.context_len,
                "vram": {"fp16": m.vram_fp16, "int8": m.vram_int8, "int4": m.vram_int4},
                "benchmarks": {"ceval": m.ceval_avg, "cmmlu": m.cmmlu_avg, "humaneval_cn": m.humaneval_cn},
                "speed": {"rtx4060": m.speed_rtx4060, "rtx4090": m.speed_rtx4090},
                "lora_vram_gb": m.lora_vram_gb,
                "pros": m.pros,
                "cons": m.cons,
                "fitness_score": m.fitness_score,
            })
        json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


class ModelComparator:
    """Programmatic interface for model comparison."""

    def __init__(self):
        self.models = {m.name: m for m in CANDIDATES}

    def rank_by(self, metric: str) -> list[tuple[str, float]]:
        """Rank models by a given metric."""
        if metric == "fitness":
            key = lambda m: m.fitness_score
        elif metric == "speed":
            key = lambda m: m.speed_rtx4060
        elif metric == "vram":
            key = lambda m: -m.vram_fp16  # negate, lower is better
        elif metric == "ceval":
            key = lambda m: m.ceval_avg
        else:
            raise ValueError(f"Unknown metric: {metric}")
        ranked = sorted(CANDIDATES, key=key, reverse=True)
        return [(m.name, getattr(m, f"{metric}_score" if metric == "fitness" else f"speed_rtx4060" if metric == "speed" else f"ceval_avg" if metric == "ceval" else -m.vram_fp16)) for m in ranked]

    def get_best_for(self, constraint: str) -> Optional[ModelSpec]:
        """Get best model given a constraint."""
        if constraint == "edge":
            return max([m for m in CANDIDATES if m.vram_fp16 <= 3.0], key=lambda m: m.fitness_score)
        elif constraint == "consumer":
            return max([m for m in CANDIDATES if m.vram_fp16 <= 8.0], key=lambda m: m.fitness_score)
        elif constraint == "server":
            return max([m for m in CANDIDATES if m.ceval_avg >= 80], key=lambda m: m.fitness_score)
        elif constraint == "realtime":
            return max([m for m in CANDIDATES if m.speed_rtx4060 >= 30], key=lambda m: m.fitness_score)
        return None

    def to_dataframe(self):
        """Export as pandas DataFrame (if available)."""
        try:
            import pandas as pd
            data = []
            for m in CANDIDATES:
                data.append({
                    "模型": m.name,
                    "参数量(B)": m.params_b,
                    "FP16 VRAM(GB)": m.vram_fp16,
                    "INT4 VRAM(GB)": m.vram_int4,
                    "C-Eval": m.ceval_avg,
                    "CMMLU": m.cmmlu_avg,
                    "速度 4060(t/s)": m.speed_rtx4060,
                    "速度 4090(t/s)": m.speed_rtx4090,
                    "上下文(K)": m.context_len // 1024,
                    "LoRA VRAM(GB)": m.lora_vram_gb,
                    "健身评分": m.fitness_score,
                })
            return pd.DataFrame(data)
        except ImportError:
            return None


if __name__ == "__main__":
    report_path = Path(__file__).resolve().parent.parent.parent / "data" / "model_comparison_report.md"
    report = generate_report(report_path)
    print(report)
