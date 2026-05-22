# YOLO26-Fitness-Agent

基于 YOLO26 姿态估计 + Qwen2.5-7B LoRA 微调大模型的智能健身教练助手。

实时检测运动姿态、识别动作错误、三维度评分，并通过百炼云端部署的 7B 健身专家模型生成自然语言纠正指导。

## 快速开始

### 环境

```bash
pip install -r requirements.txt openai dashscope
```

### 启动健身应用

```bash
python -m code.workout_app --model yolo26n-pose.pt
```

首次运行会自动下载 YOLO26 pose 模型（7.5MB）。

### 配置 AI 聊天（组员共用一个远程 API）

启动后在设置面板中：

1. 勾选「启用远程 API 模式」
2. 填入以下信息：

| 设置项 | 值 |
|--------|-----|
| API Key | `sk-427b5295e2884e1183491ee9ab8b5e16` |
| 模型 Code | `qwen2.5-7b-instruct-d1a1cabf17c2-yzqr` |

状态栏显示 **「7B 远程 API 就绪」** 即配置成功。

> 也可以取消勾选远程模式，启动本地模型（需安装 torch, transformers，首次加载会从 HuggingFace 下载）。

---

## 项目结构

```
YOLO26-Fitness-Agent/
├── code/
│   ├── workout_app.py               # ★ 主应用：多线程实时健身监控 GUI
│   ├── pose_analyzer.py             # 姿态分析引擎（角度/错误/评分/平滑）
│   ├── visualization.py             # 关节角度热力图对比
│   ├── agent.py                     # FitnessAgent 统一接口
│   ├── guidance/
│   │   └── context_engine.py        # 逐帧教练指导引擎
│   ├── planning/
│   │   ├── user_profile.py          # 用户画像（JSON 持久化）
│   │   └── plan_generator.py        # 周度训练计划生成
│   ├── models/
│   │   ├── base_model.py            # Qwen2.5 多规格基座模型加载器
│   │   ├── fitness_assistant.py     # 健身领域助手（支持 LoRA）
│   │   ├── dialogue_assistant.py    # 通用对话助手
│   │   └── fine_tuning/
│   │       ├── trainer.py           # LoRA 微调训练器
│   │       ├── prepare_data.py      # 数据集格式转换
│   │       └── fitness_data.py      # 内置手写数据集
│   ├── model_selection/             # 模型选型模块
│   ├── data_collection/             # B 站/Keep/知乎 数据采集
│   ├── data_processing/             # 数据处理管线（清洗/标注/构建）
│   └── prompt_engineering/          # Prompt 工程（模板 + Few-shot）
├── data/
│   ├── api_config.example.json      # 远程 API 配置模板
│   ├── processed/                   # 1626 条健身数据集
│   └── training_history/            # 训练历史会话记录
├── doc/                             # 论文模版
├── tests/
│   └── test_pose_analyzer.py        # 姿态分析单元测试（44 用例）
├── ft.md                            # 服务器微调操作指南
├── FINE_TUNING.md                   # LoRA 微调技术文档
├── 免部署-上传LoRA权重调用指南.md     # 百炼免部署调用指南
└── requirements.txt
```

---

## 主应用功能 (`code/workout_app.py`)

| 功能 | 说明 |
|------|------|
| 实时姿态检测 | YOLO26 17 关键点 → 骨架叠加 + 关节点标注 |
| 10 种动作支持 | 深蹲/俯卧撑/平板支撑/卷腹/开合跳/引体向上/臀桥/高抬腿/肩推/侧平举 |
| 三维度评分 | 关节角度 40 分 + 时序一致性 30 分 + 对称性 30 分 |
| 错误实时检测 | 膝盖内扣/塌腰/弓背/颈部代偿/肘外展/身体摆动等 10+ 类 |
| 开始/暂停/停止 | 状态机控制，暂停时冻结检测线程 |
| 训练历史 | JSON 持久化，弹窗 Treeview 查看 |
| **AI 聊天助手** | **Qwen2.5-7B LoRA 健身专家，百炼云端推理免部署** |
| 多线程架构 | 检测线程 + UI 线程分离，目标 ≥30fps |
| 离线模式 | 本地 YOLO + 可选本地 LLM，无网络也能用 |

---

## 10 个动作标准参数

| # | 动作 | 主监测关节 | 低位→高位 | 计数触发 |
|---|------|-----------|----------|----------|
| 1 | 深蹲 | knee_angle | 90°→170° | 高位 |
| 2 | 俯卧撑 | elbow_angle | 90°→170° | 高位 |
| 3 | 平板支撑 | elbow_angle | 90°→90° | 计时 |
| 4 | 卷腹 | trunk_angle | 40°→5° | 高位 |
| 5 | 开合跳 | spread_state | 0→1 | 高位 |
| 6 | 引体向上 | elbow_angle | 160°→55° | 高位 |
| 7 | 臀桥 | hip_angle | 100°→175° | 高位 |
| 8 | 高抬腿 | hip_angle | 170°→95° | 高位 |
| 9 | 肩推 | elbow_angle | 70°→170° | 高位 |
| 10 | 侧平举 | shoulder_angle | 10°→90° | 高位 |

---

## AI 聊天架构

```
workout_app 聊天面板
    │
    ├── 远程模式（推荐）→ OpenAI 兼容 API → 阿里云百炼 → Qwen2.5-7B + LoRA
    │
    └── 本地模式 → BaseModel → Qwen2.5 0.5B~7B（需 torch, transformers）
```

**远程模式优势**：无需本地 GPU，百炼托管 GPU 推理，最小实例数 0 自动缩零节省费用。

---

## 运行测试

```bash
# 姿态分析自测
python -m code.pose_analyzer

# 可视化模块自测
python -m code.visualization

# 单元测试（需 pytest）
python -m pytest tests/test_pose_analyzer.py -v
```

---

## 示例代码

### 使用 FitnessAgent 统一接口

```python
from code.agent import FitnessAgent
from code.planning.user_profile import UserProfile, FitnessLevel, FitnessGoal

agent = FitnessAgent()

# 加载用户
profile = agent.load_user_profile("用户")

# 获取姿态分析指导
result = analyzer.analyze_frame(keypoints, confidences)
guidance = agent.get_guidance(result)

# 对话问答
reply = agent.chat("深蹲时膝盖能不能超过脚尖？")

# 生成训练计划
plan = agent.generate_plan()
print(plan)
```

### 使用 Prompt 生成器

```python
from code.prompt_engineering import PromptGenerator

gen = PromptGenerator()

# 动作纠错
result = gen.generate_correction("深蹲", "膝盖内扣", severity=2)
print(result.output_text)

# 训练计划
result = gen.generate_plan(
    age=25, weight_kg=70, height_cm=170, gender="男",
    fitness_level="beginner", goal="weight_loss",
    equipment="none", days_per_week=3,
)
print(result.output_text)
```

### 可视化热力图

```python
from code.visualization import JointAngleHeatmap, generate_ascii_heatmap
from code.pose_analyzer import JointAngles

hm = JointAngleHeatmap("深蹲")
angles = JointAngles(knee_left=90, knee_right=92, hip_left=82, hip_right=80)
hm.record_frame(angles)

matrix = hm.compute_deviation_matrix()
print(generate_ascii_heatmap(matrix))

summary = hm.get_summary()
print(f"总偏离: {summary['overall_deviation']}°")
```

### 本地模型推理

```python
from code.models.base_model import BaseModel

model = BaseModel.get_instance(model_size="0.5B")
reply = model.chat([
    {"role": "system", "content": "你是专业的健身教练。请用中文回答。"},
    {"role": "user", "content": "深蹲膝盖内扣怎么办？"},
])
print(reply)
```

### 加载微调 LoRA 适配器

```python
from code.models.base_model import BaseModel

model = BaseModel.get_instance(
    model_size="0.5B",
    lora_path="lora_fitness_adapter/0.5B_20260521_170305/adapter"
)
reply = model.chat([
    {"role": "user", "content": "俯卧撑手腕疼怎么调整？"},
])
print(reply)
```

### 调用百炼远程 API（OpenAI 兼容）

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-xxxxxxxxxxxxxxxxxxxx",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

completion = client.chat.completions.create(
    model="qwen2.5-7b-instruct-d1a1cabf17c2-yzqr",
    messages=[
        {"role": "system", "content": "你是专业的健身教练。"},
        {"role": "user", "content": "减脂期每天应该摄入多少蛋白质？"},
    ],
    temperature=0.7,
    max_tokens=500,
)

print(completion.choices[0].message.content)
```

### 用户画像与训练计划

```python
from code.planning.user_profile import UserProfile, FitnessLevel, FitnessGoal, Equipment
from code.planning.plan_generator import PlanGenerator

profile = UserProfile(
    name="张三",
    age=25, weight_kg=72, height_cm=175,
    fitness_level=FitnessLevel.INTERMEDIATE,
    goal=FitnessGoal.STRENGTH,
    equipment=Equipment.DUMBBELLS,
)
profile.save()

plan = PlanGenerator(profile).generate_weekly_plan()
print(plan.to_text())
```

### 生成微调数据集

```bash
# 生成数据集（从爬虫数据 + 合成数据）
python -m code.data_processing.pipeline
# → data/processed/fitness_dataset.jsonl (1626 条)

# 转换为训练格式
python -m code.models.fine_tuning.prepare_data
# → data/processed/training_data.jsonl (1464 条)
# → data/processed/eval_data.jsonl (162 条)
```

### 微调训练

```bash
# 本地快速测试（0.5B + 内置数据 + 1 epoch，CPU 约 5 分钟）
HF_ENDPOINT=https://hf-mirror.com python -m code.models.fine_tuning.trainer \
    --model 0.5B --use-builtin-data --epochs 1 --batch-size 1

# 完整微调（1.5B + 全量数据 + 3 epoch，需 GPU）
HF_ENDPOINT=https://hf-mirror.com python -m code.models.fine_tuning.trainer \
    --model 1.5B --epochs 3 --batch-size 2
```

> 服务器微调详细指南见 [ft.md](ft.md)。组员已微调的 7B LoRA 适配器在 [ModelScope](https://www.modelscope.cn/models/gwendii/Qwen2.5-7B-fitness/files)。

---

## 数据集

| 类型 | 数量 | 内容 |
|------|------|------|
| 动作纠错 | ~1000 | 10 动作 × 多种错误 × 模板变体 |
| 训练规划 | ~500 | 多种用户画像的周度计划 |
| 健身问答 | ~86 | 手写专业对话 |
| 知识数据 | ~28 | Keep 动作库合成数据 |

数据集格式：

```json
{
  "id": "correction_0001",
  "type": "action_correction",
  "exercise": "深蹲",
  "error": "膝盖内扣",
  "severity": 2,
  "input": {"exercise": "深蹲", "detected_error": "膝盖内扣", "severity": 2},
  "output": "深蹲时膝盖出现了内扣..."
}
```

---

## 模型选型

| 部署场景 | 推荐模型 | 显存 | 调用方式 |
|----------|----------|------|----------|
| **远程 API（推荐）** | Qwen2.5-7B + LoRA | 0（百炼托管） | OpenAI 兼容 |
| 边缘端实时 | Qwen2.5-0.5B | ~1GB | 本地加载 |
| 消费级 GPU | Qwen2.5-1.5B | ~3GB | 本地 / QLoRA |
| 服务器质量 | Qwen2.5-7B | ~14GB | 本地 / 云端 |

---

## 依赖

```
torch>=2.0.0          # 本地模型推理（可选，远程模式不需要）
transformers>=4.40.0
peft>=0.8.0
trl>=0.8.0
datasets>=2.18.0
ultralytics>=8.0.0
opencv-python>=4.8.0
numpy>=1.24.0
Pillow>=10.0.0
openai                 # 百炼远程 API 调用
dashscope              # 百炼 SDK（可选）
```

## License

本项目仅用于学术研究和学习目的。
