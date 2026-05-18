# 健身领域 LoRA 微调指南

## 一、模型选型决策

基于 `code/model_selection/compare.py` 对 7 个中文开源模型的量化对比，最终选定 **Qwen2.5 系列**作为微调基座，按场景分为四档：

| 模型 | 参数量 | FP16显存 | C-Eval | 健身评分 | 推荐场景 |
|------|--------|---------|--------|---------|---------|
| Qwen2.5-0.5B | 0.5B | 1.0 GB | 52.3 | 5.0/10 | 边缘设备 / CPU训练 |
| **Qwen2.5-1.5B** ★ | 1.5B | 3.0 GB | 64.8 | 6.5/10 | **主力推荐：消费级GPU可微调** |
| Qwen2.5-3B | 3.0B | 6.0 GB | 74.5 | 7.5/10 | VRAM与性能最佳甜点 |
| Qwen2.5-7B | 7.0B | 14.0 GB | 82.3 | 8.0/10 | 服务器端深度问答 |

**选型理由**：
- 排除 ChatGLM3-6B：上下文仅 8K，架构非标准 decoder-only
- 排除 Baichuan2-7B：上下文仅 4K，社区活跃度下降
- 排除 InternLM2-7B：能力与 Qwen2.5-7B 相当但社区更小
- 选定 Qwen2.5 系列：统一架构可平滑升级，社区活跃，中文能力领先

**默认选择 1.5B**：3GB 显存意味着 RTX 4060 (8GB) 可用 QLoRA 微调，CPU 也能跑 fp32 训练。

---

## 二、数据集

### 数据集位置

已生成的数据集：

| 文件 | 路径 | 说明 |
|------|------|------|
| 管线原始输出 | `data/processed/fitness_dataset.jsonl` | 1626 条混合类型样本 |
| 训练集 | `data/processed/training_data.jsonl` | 转为 chat messages 格式 |
| 验证集 | `data/processed/eval_data.jsonl` | 10% 留出评估 |

### 数据集构成

| 类型 | 数量 | 内容 |
|------|------|------|
| 动作纠错 (action_correction) | ~1000 | 5个核心动作 × 多种错误 × 模板变体 |
| 训练规划 (fitness_planning) | ~500 | 10种用户画像的周度计划 |
| 健身问答 (fitness_qa) | ~130 | 手写的 65+ 组专业对话 |
| 知识数据 (exercise_technique) | ~30 | Keep 动作库合成数据 |

覆盖领域：动作技术、常见错误、训练计划、营养、恢复、伤病预防。

### 数据格式转换

管线输出是结构化 JSON，微调需要 chat messages 格式。转换由 `prepare_data.py` 完成：

```
管线格式:
{"type": "action_correction", "input": {...}, "output": "...", ...}

        ↓ prepare_data.py

训练格式:
{"messages": [
    {"role": "system", "content": "你是一名专业的健身教练..."},
    {"role": "user", "content": "我在做深蹲时检测到膝盖内扣..."},
    {"role": "assistant", "content": "深蹲时膝盖出现了内扣..."}
]}
```

---

## 三、如何运行微调

### 前置条件

```bash
pip install torch transformers peft trl datasets bitsandbytes
```

### 第一步：生成数据集（如果尚未生成）

```bash
python -m code.data_processing.pipeline
# → data/processed/fitness_dataset.jsonl
# → data/processed/correction_samples.json
# → data/processed/planning_samples.json
```

### 第二步：转换数据格式

```bash
python -m code.models.fine_tuning.prepare_data
# → data/processed/training_data.jsonl  (~1460 条)
# → data/processed/eval_data.jsonl      (~160 条)
```

### 第三步：运行微调

```bash
# 默认：1.5B 模型，完整管线数据集，3 epochs
python -m code.models.fine_tuning.trainer

# 轻量测试（用小数据集快速验证流程）
python -m code.models.fine_tuning.trainer --model 0.5B --use-builtin-data --epochs 1

# 服务器端高质量版本
python -m code.models.fine_tuning.trainer --model 7B --epochs 3 --batch-size 4

# CPU 训练（仅 0.5B 可行，非常慢）
python -m code.models.fine_tuning.trainer --model 0.5B --epochs 1 --batch-size 1
```

### 微调参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model` | 1.5B | 模型规格：0.5B / 1.5B / 3B / 7B |
| `--epochs` | 3 | 训练轮数 |
| `--batch-size` | 2 | 每设备批次大小 |
| `--learning-rate` | 2e-4 | 峰值学习率（cosine衰减） |
| `--use-builtin-data` | false | 使用手写小数据集而非完整管线数据 |
| `--resume` | - | 从 checkpoint 恢复训练 |

### LoRA 配置

```
rank (r) = 16
alpha = 32
dropout = 0.05
target_modules = [q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj]
```

### 硬件自适应策略

训练器会自动检测硬件并选择合适的加载方式：

| 条件 | 策略 |
|------|------|
| GPU ≥14GB + ≤3B模型 | fp16 + LoRA |
| GPU <14GB 或 7B模型 | 4-bit QLoRA (nf4, double quant) |
| CPU | fp32 + LoRA（仅 0.5B/1.5B 可行） |

---

## 四、如何使用微调后的模型

### 方式一：通过 FitnessAssistant

```python
from code.models.fitness_assistant import FitnessAssistant

# 加载微调后的健身助手
assistant = FitnessAssistant(
    lora_path="./lora_fitness_adapter/1.5B_20260517_120000/adapter",
    model_size="1.5B",
)

reply = assistant.chat("深蹲时膝盖内扣怎么办？")
print(reply)
```

### 方式二：通过 FitnessAgent 统一接口

```python
from code.agent import FitnessAgent

agent = FitnessAgent(
    lora_path="./lora_fitness_adapter/1.5B_20260517_120000/adapter",
    model_size="1.5B",
)

# 对话问答
reply = agent.chat("我身高170体重80公斤，想减脂，该怎么练？")

# 生成训练计划
plan = agent.generate_plan()
print(plan)
```

### 方式三：直接加载 BaseModel

```python
from code.models.base_model import BaseModel

model = BaseModel.get_instance(
    lora_path="./lora_fitness_adapter/1.5B_20260517_120000/adapter",
    model_size="1.5B",
)

reply = model.chat([
    {"role": "system", "content": "你是一名专业的健身教练..."},
    {"role": "user", "content": "如何纠正俯卧撑塌腰？"},
])
```

---

## 五、产出物结构

微调完成后，输出目录结构：

```
lora_fitness_adapter/
└── 1.5B_20260517_120000/
    ├── adapter/                  # LoRA 权重 + tokenizer
    │   ├── adapter_config.json
    │   ├── adapter_model.safetensors
    │   ├── tokenizer.json
    │   ├── tokenizer_config.json
    │   └── training_config.json  # 训练参数记录
    ├── checkpoint-100/           # 中间 checkpoint
    └── checkpoint-200/
```

`training_config.json` 记录了完整的训练参数，确保可复现。

---

## 六、预期效果

| 维度 | 微调前 (base 1.5B) | 微调后 (LoRA) |
|------|-------------------|---------------|
| 动作纠错指导 | 通用回答，缺乏细节 | 针对具体错误给出专业、可操作建议 |
| 训练计划 | 泛泛而谈 | 结合用户画像的个性化周度计划 |
| 中文健身术语 | 基本正确 | 准确使用健身领域中文术语 |
| 安全性 | 可能给出不安全建议 | 系统提示词约束 + 微调数据中的安全规范 |

---

## 七、后续优化方向

1. **数据扩充**：接入真实 B站/Keep/知乎 数据替换合成数据
2. **多轮对话**：当前数据集主要是单轮，可加入多轮纠正对话
3. **RLHF 对齐**：收集用户反馈进行偏好对齐
4. **量化部署**：微调后用 GPTQ/AWQ 量化适配边缘设备
5. **评估基准**：建立健身领域专用评估集，量化微调收益
