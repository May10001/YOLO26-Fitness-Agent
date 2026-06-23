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

### 测试远程 API 连通性

在配置 GUI 之前，先用命令行脚本验证远端模型可正常调用（无需本地 GPU）：

```bash
# 单次问答测试
python scripts/test_remote_api.py

# 指定问题
python scripts/test_remote_api.py -q "如何做标准俯卧撑？"

# 多轮对话模式（输入 /quit 退出）
python scripts/test_remote_api.py -m
```

脚本读取 `data/api_config.json` 中的配置，返回中文健身指导即表示连通成功。

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
│   ├── realtime_coach.py            # ★ 实时 LLM 教练引擎（触发判断+上下文+频率控制）
│   ├── coach_system_prompt.py       # ★ 微调教练模型系统提示词
│   ├── biomechanics/
│   │   └── knowledge_base.py        # ★ 生物力学知识库（10动作根因链+分层纠正cue）
│   ├── coaching/
│   │   └── diagnostic_context.py    # ★ 诊断上下文构建器 + 两段式输出解析
│   ├── guidance/
│   │   └── context_engine.py        # 逐帧教练指导引擎（规则驱动 + cue效果追踪）
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
├── scripts/
│   └── test_remote_api.py           # 远程 API 连通性测试脚本
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
| **实时 LLM 教练** | **逐帧接收评分/角度/错误，主动推送纠正指导到聊天面板** |
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

实时 LLM 教练触发生成
    │
    └── DetectionThread 每帧 → PoseAnalyzer → RealTimeCoach
          ├── 触发判断（严重错误/评分骤降/里程碑/个人最佳）
          ├── 频率控制（全局≥6s，按类型 8-30s 冷却）
          ├── 构建结构化上下文 → 远程 API → 聊天框主动推送
          └── 用户提问时自动附带当前训练数据
```

**远程模式优势**：无需本地 GPU，百炼托管 GPU 推理，最小实例数 0 自动缩零节省费用。

---

## 实时 LLM 教练

训练过程中，系统会将每帧的姿态数据（评分、关节角度、检测到的错误、训练统计）编码为结构化上下文，通过远程 API 发送给微调过的 Qwen2.5-7B 健身专家模型。模型会在聊天面板中**主动推送**专业指导。

### 触发规则

| 触发条件 | 冷却时间 | 说明 |
|---------|---------|------|
| 严重错误 (severity≥2 持续5帧+) | 8s | 如膝盖内扣、塌腰、关节过伸 |
| 评分骤降 (比最佳低15分+) | 10s | 动作质量显著下降时提醒 |
| 个人最佳 (超最佳5分+) | 15s | 突破自我时给予表扬 |
| 次数里程碑 (5/10/15/20/30/50/100) | 20s | 达到目标次数时鼓励 |
| 连续标准 10+ 次 | 30s | 长期保持标准姿势时肯定 |

**全局限制**：两次主动推送≥6秒，每会话最多 20 次，防止消息轰炸。

### 用户提问

训练中在聊天框输入问题（如"我的深蹲怎么样？"），系统会自动附带当前训练数据（动作名、次数、总分、最佳分、检测错误），让模型给出结合实时状态的个性化回答。

### 架构

```
RealTimeCoach
  ├── CoachContextBuilder   → AnalysisResult → 结构化中文上下文
  ├── CoachTriggerEvaluator → 触发规则 + 优先级排序
  └── RealTimeCoach         → 冷却管理 + 频率限制 + API 调用协调
```

### LLM 教练智能诊断升级（四步）

> 让 LLM 从"报数机器"升级为"会推理的教练"：先诊断根因，再给出可执行的动作 cue，并跟踪指导效果。

#### Step 1：上下文从裸角度 → 诊断数据

不再把"68°, 82°"直接丢给 LLM，而是构建结构化诊断快照（`DiagnosticContextBuilder`）：

| 维度 | 内容 | 示例 |
|------|------|------|
| 逐关节偏差 | 当前值、目标值、偏差、状态标签 | `左膝: 140° (目标 170°, 偏差 -30°, 状态: 不足)` |
| 标准差 σ | 滑动窗口（15 帧）标准差，衡量关节**稳定性** | `σ=1.0° (稳定)` vs `σ=8.9° (剧烈波动)` |
| 趋势序列 | 线性回归斜率 + 方向标签 + 最近 5 帧序列 | `改善中 (斜率 +0.35°/帧)` |
| 共现模式 | 多错误共现的 biomechanical 解读 | `膝内扣 + 弓背 → 臀中肌薄弱 + 核心不稳` |
| 维度诊断 | 识别角度/时序/对称中哪个拖低了总分 | `时序维度明显偏低 (12/30)，需重点改进` |

**标准差的意义**：LLM 可以区分三种本质不同的场景——

| 偏差 | σ | 诊断 | 策略 |
|------|---|------|------|
| 大 | 小 | 习惯性错误（稳定偏离） | 重建动作模式，换 cue 角度 |
| 大 | 大 | 疲劳/失控（偏离且波动） | 建议休息或降阶 |
| 小 | 大 | 本体感觉差（目标正确但不稳） | 强调控制节奏 |

实现文件：`code/coaching/diagnostic_context.py`（新增）、`code/pose_analyzer.py`（MovementScorer 新增 per_joint_history）

#### Step 2：Prompt 嵌入生物力学知识

每个动作的每个错误都配有完整的 biomechanical 知识图谱（`code/biomechanics/knowledge_base.py`）：

```
深蹲膝盖内扣:
  root_cause_chain: 臀中肌薄弱 → 股骨内旋 + 髋内收 → 膝盖向内侧偏移 → 增加 ACL/MCL 剪切应力
  correction_cues:
    Tier 1 (外部注意力): "膝盖向外推开" / "想象站在一张纸上把它撕开" / "髋关节向外旋"
    Tier 2 (内部注意力): "收紧臀中肌" / "大腿内侧不发力"
    Tier 3 (回归训练):   "弹力带深蹲（外展辅助）" / "箱式深蹲（限制幅度）"
  compensation_patterns: 足弓塌陷、骨盆前倾
```

- 覆盖全部 10 个动作的所有错误类型
- `CoachContextBuilder._build_biomechanics_block()` 动态注入当前检测到错误的生物力学知识
- COACH_SYSTEM_PROMPT 定义 Tier1→Tier2→Tier3 优先级策略（外部 cue 优先，无效时升级）

#### Step 3：LLM 两段式输出

系统 prompt 强制 LLM 按以下 XML 格式输出，由 `CoachingOutputParser` 解析：

```xml
<diagnosis>
{"root_cause": "根因分析", "confidence": 0.8,
 "affected_joints": ["左膝", "右膝"],
 "recommended_cues": [{"cue": "膝盖向外推开", "tier": 1, "focus": "external"}],
 "expected_effect": "缩小膝盖间距，减少 ACL 应力"}
</diagnosis>
<guidance>
你深蹲时膝盖有点往里扣了。试着想象脚下有张纸，发力时把纸向外撕开——这样膝盖自然会往外走。我们先慢一点，控制好再加速。
</guidance>
```

- `<diagnosis>`：内部诊断 JSON（根因、置信度、推荐 cue、预期效果）— 供系统追踪
- `<guidance>`：面向用户的自然语言指导文本 — 展示在聊天面板
- 解析后分别存入 `CoachAgentState.diagnosis_json` / `guidance_text` / `recommended_cues`

实现文件：`code/coach_system_prompt.py`、`code/coaching/diagnostic_context.py`（CoachingOutputParser）、`code/langgraph_agent/nodes.py`、`state.py`

#### Step 4：Cue 效果追踪

系统会记住上一次给了什么 cue，并自动检测是否有效：

- **记录**：每次发出 cue 时，`GuidanceState.record_cue()` 记录 {cue_text, tier, focus, target_error, timestamp}
- **检测**：30 帧 `RESOLVE_WINDOW` 内，如果目标错误消失 → 标记为有效；如果错误持续 → 标记为无效
- **反馈**：`_build_cue_effectiveness_block()` 将无效 cue 反馈注入 prompt：
  ```
  【上次指导效果】
  膝盖内扣: 上次提示"膝盖向外推开"→ 效果不佳（错误仍持续）
  已尝试过的 cue: 膝盖向外推开、收紧臀部 → 请尝试不同 cue 角度或升级 Tier
  ```
- **LLM 响应**：系统 prompt 指示：若 cue 无效，换一个不同角度或不同 tier 的 cue（如从外部注意力 → 内部注意力 → 回归训练）

实现文件：`code/guidance/context_engine.py`（GuidanceState 扩展）、`code/realtime_coach.py`（_build_cue_effectiveness_block）

#### 数据流总览

```
Webcam → YOLO26 → PoseAnalyzer → MovementScorer
                                      ├── per_joint_history (逐关节60帧)
                                      ├── angle_records (主角度+目标)
                                      └── score_history (分维度)
                                          ↓
                              DiagnosticContextBuilder.build()
                                      ├── 逐关节偏差 + σ + 稳定性
                                      ├── 角度趋势 (线性回归)
                                      ├── 共现模式 (biomechanics KB 查询)
                                      └── 维度诊断
                                          ↓
                              CoachContextBuilder
                                      ├── 诊断块 (_build_diagnostic_block)
                                      ├── 生物力学块 (_build_biomechanics_block)
                                      └── cue 效果块 (_build_cue_effectiveness_block)
                                          ↓
                              COACH_SYSTEM_PROMPT + 结构化上下文
                                          ↓
                              百炼 DashScope Qwen2.5-7B + LoRA
                                          ↓
                              CoachingOutputParser
                                      ├── <diagnosis> → diagnosis_json
                                      └── <guidance> → 聊天面板展示
                                          ↓
                              GuidanceState.record_cue() → 下次循环
```

## Web 前端（Vue 3 + FastAPI）

> 现代浏览器界面，替代 Tkinter 桌面 GUI。前端 Vue 3 + Vite + TypeScript + TailwindCSS，后端 FastAPI + WebSocket。这是目前主推的交互形态，后续升级请优先基于此。

### 启动全栈

```bash
# 终端 1：后端（必须在项目根目录运行）
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2：前端
cd frontend && npm install && npm run dev

# 浏览器打开 http://localhost:5173，授予摄像头权限
```

前端 dev server 通过 Vite 代理把 `/ws` 转发到后端 WebSocket、`/api` 转发到 REST（见 `frontend/vite.config.ts`）。

### 数据流

```
浏览器摄像头 (MediaStream)
  → useCamera.ts 抽帧 → base64 JPEG ~30fps
  → WebSocket /ws/detect → 后端 DetectorService (YOLO26 + PoseAnalyzer + ContextEngine)
  → JSON {keypoints, score, phase, count, errors, guidance, heatmap}
  → 更新 VideoStage / ScorePanel / JointHeatmap / CorrectionPanel

用户聊天 → POST /api/chat {message, pose_context}
  → 有 pose_context：LangGraph CoachAgent（教练提示词 → 百炼 DashScope）
  → 否则：通用 DashScope 调用，失败回退本地 FitnessAgent
```

### 后端模块（`backend/`）

| 文件 | 职责 |
|------|------|
| `main.py` | FastAPI 应用 + CORS，挂载 detect / chat 路由 |
| `routers/detect.py` | WebSocket `/ws/detect`，处理 `set_exercise` / `reset` / `frame` 消息，懒加载 DetectorService |
| `routers/chat.py` | REST `POST /api/chat`，有 pose_context 走 LangGraph CoachAgent，否则通用 DashScope / 回退本地 |
| `services/detector.py` | 封装 YOLO26 + PoseAnalyzer + ContextEngine，`process_frame()` 返回检测结果 |
| `services/agent_service.py` | FitnessAgent 懒加载单例，延迟 `transformers` 导入到首次聊天 |
| `schemas.py` | Pydantic 请求/响应模型 |

> 重型 ML 依赖（ultralytics / transformers / torch）全部延迟到首次使用，FastAPI 秒级启动，不在 import 时加载 GB 级模型。

### 前端组件（`frontend/src/components/`）

| 组件 | 职责 |
|------|------|
| `EntryScreen.vue` | ★ **入场页**：神经网络粒子 + 赛博地平线融合背景，鼠标吸附高亮交互，编排式逐层入场，点击光晕扩散淡出进入主界面 |
| `VideoStage.vue` | 主视频显示 + HUD（次数、阶段、计时） |
| `SkeletonOverlay.vue` | Canvas 骨架叠加，渐变骨骼 + 发光关节，错误关节标红 |
| `GaugeBar.vue` | CSS 仪表条（角度/时序/对称三维度评分） |
| `ScorePanel.vue` | 右栏总分 + 环形仪表 |
| `JointHeatmap.vue` | ★ 关节角度偏离条形图（good/warning/bad 三色） |
| `CorrectionPanel.vue` | 错误列表 + 严重度指示 |
| `AiCoach.vue` | AI 教练问答聊天 |
| `HistoryPanel.vue` | ★ 训练历史列表（从 `/api/session` 拉取） |
| `PlanPanel.vue` | ★ 用户画像表单 + 周度训练计划生成 |
| `ControlBar.vue` | 动作选择 + 开始/暂停/重置 |
| `DebugOverlay.vue` | 🐛 开发者调试面板：原始角度/评分明细/角度波形/实时调参滑块（D 键切换） |
| `RingGauge.vue` / `ParticleBackground.vue` | 环形进度 / 粒子背景 |

**Composables**：`useCamera.ts`（摄像头抽帧）、`useWebSocket.ts`（连接管理 + 重连）、`useTrainingState.ts`（idle/running/paused 状态机 + 计时）。

### 本轮前端更新（供后续成员了解进度）

- **新增入场页 `EntryScreen.vue`** — App 加载时全屏覆盖（`z-50`），点击 `enter` 事件后切换到训练界面。融合方案：发光地平线 + 压暗透视网格打底，神经网络粒子浮中层；鼠标 190px 内节点被拉向光标、连线变粗变亮（吸附+高亮）；编排式逐层入场（地平线→网格→粒子组网→标题→「点击进入」呼吸）；点击迸发橙玫光晕扩散并整体淡出。
  - 工程化：canvas 走 `requestAnimationFrame`，`onUnmounted` 清理 raf / 监听 / timer；支持 `prefers-reduced-motion` 降级（跳过编排与动画，直接显示）；关键帧加 `entry-` 前缀避免冲突。
  - 接入点：`App.vue` 的 `showEntry` ref 控制显隐。如需「仅首次访问显示」可改用 sessionStorage。
  - 设计稿存档：`frontend/entry-previews/`（4 种原始风格 + 2 种融合版 + `compare.html` 对比页），最终采用「融合A + 吸附高亮」。
- **新增 `HistoryPanel.vue` / `PlanPanel.vue` / `JointHeatmap.vue`** — 右栏 Tab 切换（AI教练 / 历史 / 计划），关节热力图独立展示。
- **修改** `App.vue`（入场页接入 + 会话生命周期 + 三维度评分聚合）、`useWebSocket.ts`（新增 guidance / coach 消息）、`types/index.ts`（`HeatmapData` / `PoseContext` 等类型）、`AiCoach.vue` / `ScorePanel.vue` / `CorrectionPanel.vue` / `VideoStage.vue`。

### 本轮后端修改记录（2025-06-14）

> Debug 调参面板、对称性调参、躯干角 Bug 修复、高分静默机制。

#### 0. Debug 调参面板（前端 + 后端）

**前端 `DebugOverlay.vue`**（新增）— 训练界面左下角的开发者调试面板，按 **D 键** 或点击 **🐛 DEBUG** 按钮切换显隐。包含四大模块：

| 模块 | 位置 | 内容 |
|------|------|------|
| 📐 原始角度 | 左上 | 左膝/右膝角度、目标角度、当前阶段、角度偏差、左右膝差异 |
| 📊 评分明细 | 右上 | 角度分/对称分/时序分 + 各自计算公式（含当前参数值） |
| 📈 角度波形 | 底部 | 近 30 帧 primary_angle 柱状波形，绿色=靠近目标/黄色=过渡区/红色=偏离，虚线标注 target_low / target_high |
| 🎛️ 实时调参 | 底部 | 5 个滑块：底部目标/顶部目标/对称容差/角度容差/平滑系数，拖动实时生效（200ms 防抖） |

**后端支持：**

- `backend/routers/config.py`（新增）— 运行时调参 API：
  - `GET /api/config/scoring` — 读取当前参数
  - `PUT /api/config/scoring` — 部分更新参数，立即生效无需重启
- `backend/schemas.py` — 新增 `ScoringConfig` 模型（`target_low` / `target_high` / `symmetry_max_diff` / `angle_tolerance` / `smooth_alpha`）
- `backend/services/detector.py` — 新增 `debug_info` 字段（每帧暴露原始评分内部变量）、`apply_tuning()` / `get_tuning_params()` 方法
- `code/pose_analyzer.py` — `PoseAnalyzer` 新增 `apply_tuning()` 方法，同步更新 `ExerciseStandard` 和 `MovementScorer` 两处的参数；`MovementScorer` 新增 `_angle_records` 列表（每帧存 (angle, dynamic_target) 对），`_dynamic_target()` 方法在过渡区用实际角度作为目标避免误罚，`angle_tolerance` 默认值从 10.0 调整为 12.5

**接入方式：** `App.vue` 用 `showDebug` ref 控制显隐，`DebugOverlay` 通过 props 接收 `debug` / `score` / `phase`，滑块变更调用 `PUT /api/config/scoring`。

#### 1. 对称性参数统一放宽

`code/pose_analyzer.py` — 所有 10 个动作的 `symmetry_max_diff`（左右关节最大允许差异）统一设为 **25.0°**。旧值 10~20° 偏严，正常对称差异就被扣分，体验不佳。

#### 2. 高分静默机制

`code/guidance/context_engine.py` — 新增 `SUPPRESS_SCORE_THRESHOLD = 80`。当用户总分 > 80 分时，以下提示自动静默：

| 提示类型 | 静默 |
|----------|------|
| ⚠ 安全警告 | ✅ 不显示 |
| ✏ 动作纠正 | ✅ 不显示 |
| 📊 表现反馈 | ✅ 不显示 |
| 💪 里程碑鼓励 | ❌ 正常显示 |

#### 3. 躯干角度比较方向修复（关键 Bug）

`code/pose_analyzer.py` — `trunk_angle` 的计算公式为「躯干与垂直线的夹角」，**180° = 直立，前倾越多角度越小**。但 5 个错误检测的阈值比较方向全部写反（用了 `> 小数值`，永远为真，每帧都在误报）：

| 错误 | 修复前 | 修复后 |
|------|--------|--------|
| 深蹲弓背 | `> 45.0` | `< 135.0` |
| 侧平举身体晃动 | `> 15.0` | `< 165.0` |
| 引体向上摆动 | `> 12.0` | `< 168.0` |
| 高抬腿身体后仰 | `> 18.0` | `< 162.0` |
| 肩推弓背 | `> 15.0` | `< 165.0` |

#### 4. 热力图躯干参考范围修正

`code/visualization.py` — `STANDARD_REFERENCE_ANGLES` 中躯干参考范围原本用「前倾度数」（如深蹲 `(10, 35)` = 前倾 10-35°），与实际 `trunk_angle`（0-180° 垂直夹角）单位不一致。已全部转为垂直夹角（`180° - 原值`），深蹲 trunk 从 `(10, 35)` → `(145, 170)`，中点 ≈ 157.5°。

#### 5. 前端服务端口

`frontend/src/` — API 和 WebSocket 地址统一指向 `localhost:8002`（`useWebSocket.ts`、`App.vue`、`DebugOverlay.vue`）。

#### 影响范围

| 文件 | 改动 |
|------|------|
| `code/pose_analyzer.py` | symmetry_max_diff 统一 25.0；5 个躯干角错误检测比较方向修复；新增 apply_tuning()、_angle_records / _dynamic_target()；angle_tolerance 10→12.5 |
| `code/guidance/context_engine.py` | 新增 SUPPRESS_SCORE_THRESHOLD=80，三个 _check_* 方法加高分判断 |
| `code/visualization.py` | 10 个动作 trunk 参考范围从"前倾度"转为"垂直夹角" |
| `backend/routers/config.py` | **新增** — GET/PUT `/api/config/scoring` 运行时调参接口 |
| `backend/schemas.py` | **新增** — `ScoringConfig` Pydantic 模型 |
| `backend/services/detector.py` | **新增** — debug_info 字段、apply_tuning()、get_tuning_params() |
| `backend/main.py` | 挂载 config_router |
| `tests/test_pose_analyzer.py` | 适配新阈值：弓背测试数据、热力图躯干角测试数据 |
| `frontend/src/components/DebugOverlay.vue` | **新增** — 开发者调试面板（角度/评分明细/波形/调参）；默认值适配 |
| `frontend/src/types/index.ts` | **新增** — `ScoringConfig`、`DebugData` 接口 |
| `frontend/src/composables/useWebSocket.ts` | WebSocket 地址→8002 |
| `frontend/src/App.vue` | API 地址→8002；集成 DebugOverlay（D 键切换） |

### 常见问题

- **端口 8000 被占用**：`lsof -ti:8000 | xargs kill -9`
- **No module named 'backend'**：必须在项目根目录运行 `uvicorn backend.main:app`，不要进 `backend/` 目录
- **WebSocket 代理连不上**：检查系统 SOCKS 代理是否拦截 localhost，必要时 `NO_PROXY=localhost`
- **摄像头黑屏**：确认浏览器已授权且无其他程序占用摄像头

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
