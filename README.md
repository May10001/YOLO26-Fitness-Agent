# YOLO26-Fitness-Agent

基于 YOLO26 姿态估计 + LLM 的智能健身教练助手。实时检测运动姿态、识别动作错误，并通过大语言模型生成自然语言纠正指导和个性化训练计划。

## 项目结构

```
YOLO26-Fitness-Agent/
├── code/                          # 核心代码
│   ├── agent.py                   # 主编排器 — 统一的 FitnessAgent 接口
│   ├── pose_analyzer.py           # 姿态分析引擎（角度提取/错误检测/评分/平滑）
│   ├── visualization.py           # 可视化对比（关节角度热力图）
│   ├── guidance/                  # 实时指导模块
│   │   └── context_engine.py      # 上下文感知的逐帧教练引擎
│   ├── planning/                  # 训练计划模块
│   │   ├── user_profile.py        # 用户画像（含 JSON 持久化）
│   │   └── plan_generator.py      # 基于规则的周度训练计划生成
│   ├── models/                    # LLM 模型封装
│   │   ├── fitness_assistant.py   # 健身领域助手（Qwen2.5 + LoRA）
│   │   ├── dialogue_assistant.py  # 通用对话助手
│   │   └── fine_tuning/           # 微调数据和训练器
│   ├── model_selection/           # 模型选型模块
│   │   └── compare.py             # 7 模型对比报告生成器
│   ├── data_collection/           # 数据采集模块
│   │   ├── bilibili_scraper.py    # B 站健身视频字幕爬虫
│   │   ├── keep_scraper.py        # Keep 动作库爬虫
│   │   └── zhihu_scraper.py       # 知乎健身问答爬虫
│   ├── data_processing/           # 数据处理模块
│   │   ├── cleaner.py             # 数据清洗（去重/过滤/正则化）
│   │   ├── annotator.py           # 自动标注（动作/错误/指导类型）
│   │   └── pipeline.py            # 端到端数据集构建管线
│   └── prompt_engineering/        # Prompt 工程模块
│       ├── templates.py           # 模板 + Few-shot 选择器
│       └── generator.py           # PromptGenerator 统一接口
├── data/                          # 数据目录
│   ├── model_comparison_report.md # 模型选型对比报告
│   ├── raw/                       # 原始抓取数据
│   └── processed/                 # 清洗后的 JSON/JSONL 数据集
├── tests/                         # 单元测试
│   └── test_pose_analyzer.py      # 姿态分析引擎测试（44 个用例）
├── workingout_monitoring.py       # Tkinter GUI 实时健身监测应用
└── requirements.txt               # 项目依赖
```

## 功能模块

### 1. 姿态分析引擎 (`code/pose_analyzer.py`)

- 17 个 COCO 关键点 → 10 个关节角度提取
- **10 个核心动作标准参数**：

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

- **三维度动作评分算法**（角度 40 分 + 时序 30 分 + 对称性 30 分）
- **时序平滑处理**：EMA 角度平滑 + 中值滤波 + 得分帧间平滑，减少单帧关键点抖动误差
- **10+ 类常见错误实时检测**（膝盖内扣/塌腰/弓背/颈部代偿/手臂不充分/身体摆动/臀桥不对称/身体后仰/肩推弓背/借力晃动）

### 2. 可视化对比 (`code/visualization.py`)

- **JointAngleHeatmap** — 标准动作 vs 用户关节角度热力图对比
- 偏离度矩阵计算（good / warning / bad 三级分类）
- ASCII 终端热力图输出（无需 matplotlib）
- 各动作标准参考角度范围定义

### 3. 实时指导引擎 (`code/guidance/context_engine.py`)

- 4 类指导消息：动作纠正、表现反馈、里程碑鼓励、安全警告
- 上下文状态追踪（连续帧、错误计数、最佳评分）
- 冷却机制避免重复提示

### 4. 训练计划生成 (`code/planning/plan_generator.py`)

- 基于用户画像的个性化周度计划
- 渐进式超负荷策略
- 5 种训练目标：增肌/塑形/耐力/减脂/综合健康
- 支持分化训练（上下肢/推拉腿/全身）

### 5. 数据采集管线 (`code/data_collection/`)

| 数据源 | 内容 | 爬虫状态 |
|--------|------|----------|
| B 站健身区 | 热门教程 CC 字幕 | API 框架 + 合成数据 |
| Keep 动作库 | 30+ 动作要领 + 常见错误 | API 框架 + 合成数据 |
| 知乎健身话题 | 高质量 Q&A | API 框架 + 合成数据 |

> 由于 B 站/Keep/知乎需要登录态，本仓库提供完整的爬虫框架和丰富的合成数据用于离线开发和测试。

### 6. 数据处理管线 (`code/data_processing/`)

- 文本清洗：全角→半角、空白规范化、控制字符过滤
- 精确 + 模糊去重（SequenceMatcher, 阈值 0.85）
- 中文比例过滤
- 自动标注：动作类型（28 类）、错误类型（20 类）、指导类型、难度、目标肌群
- **输出数据集**：1626 条样本（~1000 动作纠错 + 500 训练规划 + 130 问答）

### 7. Prompt 工程 (`code/prompt_engineering/`)

两个核心 Prompt 模板：

**ErrorGuidancePrompt** — 结构化错误 → 自然语言指导
```
输入: {exercise: "深蹲", error: "膝盖内扣", severity: 2, phase: "低位", score: 55}
输出: "深蹲时膝盖出现了内扣，这会让膝关节内侧副韧带承受额外的压力..."
```

**PlanningPrompt** — 用户画像 → 周度训练计划
```
输入: {age: 25, weight: 70, goal: "weight_loss", equipment: "none", ...}
输出: "📋 个人减脂训练计划（4周）\n## 周一（全身基础训练）\n..."
```

支持动态 Few-shot 选择、LLM 调用和规则回退。

### 8. 模型选型对比 (`code/model_selection/compare.py`)

对比了 7 个中文开源模型，评估维度：
- VRAM 需求（FP16/INT8/INT4）
- 推理速度（RTX 4060/4090）
- C-Eval / CMMLU / HumanEval-CN 基准
- 中文健身领域综合评分

详见 `data/model_comparison_report.md`。

## 快速开始

### 环境

```bash
pip install -r requirements.txt
```

### 实时健身监测（GUI）

```bash
python workingout_monitoring.py --model yolo26n-pose.pt
```

### 运行单元测试

```bash
python -m pytest tests/test_pose_analyzer.py -v
```

### 运行自测

```bash
python -m code.pose_analyzer     # 姿态分析引擎自测
python -m code.visualization     # 可视化模块自测
```

### 生成微调数据集

```bash
python -m code.data_processing.pipeline
# → data/processed/fitness_dataset.jsonl
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

### 可视化对比

```python
from code.visualization import JointAngleHeatmap, generate_ascii_heatmap
from code.pose_analyzer import JointAngles

hm = JointAngleHeatmap("深蹲")
angles = JointAngles(knee_left=90, knee_right=92, hip_left=82, hip_right=80)
hm.record_frame(angles)

# 终端热力图
matrix = hm.compute_deviation_matrix()
print(generate_ascii_heatmap(matrix))

# 偏离摘要
summary = hm.get_summary()
print(f"总偏离: {summary['overall_deviation']}°")
```

### 生成模型对比报告

```bash
python -m code.model_selection.compare
# → data/model_comparison_report.md
```

## 数据集格式

每条样本为 JSON 对象：

```json
{
  "id": "correction_0001",
  "type": "action_correction",
  "exercise": "深蹲",
  "error": "膝盖内扣",
  "severity": 2,
  "trigger_condition": "深蹲时膝盖向内扣，髌骨未对准第二脚趾",
  "input": {
    "exercise": "深蹲",
    "detected_error": "膝盖内扣",
    "severity": 2,
    "trigger": "深蹲时膝盖向内扣..."
  },
  "output": "深蹲时膝盖出现了内扣...",
  "annotation": {
    "exercise_type": "深蹲",
    "error_types": ["膝盖内扣"],
    "guidance_type": "动作纠错",
    "difficulty": "初级"
  }
}
```

## 模型选型建议

| 部署场景 | 推荐模型 | 量化 | 显存 | 推理延迟 |
|----------|----------|------|------|----------|
| 边缘端实时纠错 | Qwen2.5-1.5B | INT4 | ~1GB | <30ms |
| 移动端离线部署 | Qwen2.5-0.5B | INT4 | ~0.3GB | <50ms |
| 服务器规划生成 | Qwen2.5-7B | INT8 | ~8GB | <2s |
| 深度健身问答 | Qwen2.5-7B | FP16 | ~14GB | <3s |

## 依赖

```
torch>=2.0.0
transformers>=4.40.0
peft>=0.8.0
trl>=0.8.0
datasets>=2.18.0
ultralytics>=8.0.0
opencv-python>=4.8.0
numpy>=1.24.0
Pillow>=10.0.0
```

## License

本项目仅用于学术研究和学习目的。
