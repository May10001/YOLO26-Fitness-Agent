# LangGraph 健身教练 Agent 机制说明

## 1. 设计动机

在引入 LangGraph 之前，项目中存在三个各自独立、互不通信的组件：

| 组件 | 文件 | 问题 |
|---|---|---|
| 评分管道 | `pose_analyzer.py` → `AnalysisResult` | 产出评分数据，但没有传入 LLM |
| 教练上下文构建器 | `realtime_coach.py` → `CoachContextBuilder` | 能构建完美的 LLM 上下文，但从未被调用 |
| 聊天 API | `backend/routers/chat.py` → `POST /api/chat` | 调用千问大模型，但使用通用的 system prompt，不包含任何训练数据 |

**LangGraph Agent 的核心任务**：用一条形式化的状态图（StateGraph）将这三者串联起来，形成闭环：

```
评分数据 → 上下文构建 → 千问 LLM 调用 → 教练反馈文字
```

## 2. 整体架构

```
                         ┌──────────────────────────┐
                         │     PoseAnalyzer          │
                         │  (评分引擎，不改动)          │
                         └────────────┬─────────────┘
                                      │ AnalysisResult
                         ┌────────────▼─────────────┐
                         │   state_from_analysis()   │
                         │  (bridge — state.py)      │
                         └────────────┬─────────────┘
                                      │ CoachAgentState (TypedDict)
                                      ▼
              ┌──────────────────────────────────────────┐
              │        LangGraph StateGraph               │
              │                                           │
              │  ┌─────────────────────────────────────┐  │
              │  │ Node 1: select_system_prompt        │  │
              │  │ 选择 COACH_SYSTEM_PROMPT 变体         │  │
              │  └────────────────┬────────────────────┘  │
              │                   │ system_prompt         │
              │                   ▼                       │
              │  ┌─────────────────────────────────────┐  │
              │  │ Node 2: build_context               │  │
              │  │ 调用 CoachContextBuilder 格式化评分   │  │
              │  └────────────────┬────────────────────┘  │
              │                   │ context_prompt        │
              │                   ▼                       │
              │  ┌─────────────────────────────────────┐  │
              │  │ Node 3: call_dashscope              │  │
              │  │ 调用 DashScope 千问 API 获取回复     │  │
              │  └────────────────┬────────────────────┘  │
              │                   │ response              │
              └───────────────────┼───────────────────────┘
                                  ▼
                         教练反馈文字 (鼓励 / 纠正)
```

### 两种模式

| 模式 | `chat_mode` | system prompt | 触发方式 | 回复要求 |
|---|---|---|---|---|
| **Proactive** (主动推送) | `"proactive"` | `COACH_SYSTEM_PROMPT_PROACTIVE` (精简版) | 系统自动检测触发事件（严重错误、评分骤降等） | 1-3 句话，直接指出问题 |
| **Reactive** (被动回复) | `"reactive"` | `COACH_SYSTEM_PROMPT` (完整版) | 用户主动在聊天框提问 | 200 字以内，可更详细 |

## 3. 数据流详解

### 3.1 CoachAgentState —— 统一状态格式

**文件**：`code/langgraph_agent/state.py`

`CoachAgentState` 是一个 `TypedDict`，定义了在整个图中流转的全部字段。按用途分为三类：

**输入字段**（由外部调用者在调用图前填充）：

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `exercise_name` | `str` | 用户选择 | 动作中文名，如 `"深蹲"` |
| `score` | `dict` | `ScoreResult` | `{total, angle, temporal, symmetry}`，0-100 |
| `joint_angles` | `dict` | `JointAngles` | 11 个关节角度，如 `knee_left`, `hip_right`, `trunk_angle` |
| `phase` | `str` | `AnalysisResult.phase` | `"等待"` / `"低位"` / `"高位"` / `"保持"` / `"姿态调整"` |
| `rep_count` | `int` | `AnalysisResult.count` | 当前组已完成的次数 |
| `hold_time` | `float` | `AnalysisResult.hold_time` | 平板支撑等静态动作的保持秒数 |
| `errors` | `list[dict]` | `AnalysisResult.errors` | 每项 `{name, severity, message, suggestion}` |
| `best_score` | `float` | `GuidanceState.best_score` | 本次训练历史最佳分 |
| `consecutive_good_form` | `int` | `GuidanceState` | 连续标准动作帧数 |
| `consecutive_bad_form` | `int` | `GuidanceState` | 连续问题动作帧数 |
| `error_counts` | `dict` | `GuidanceState.error_counts` | 每类错误的累计次数 |
| `recent_scores` | `list[float]` | `GuidanceState.recent_scores` | 最近 30 帧评分 |
| `chat_mode` | `str` | 调用者决定 | `"proactive"` 或 `"reactive"` |
| `user_message` | `str` | 用户输入 | reactive 模式下的用户提问 |
| `api_config` | `dict` | `api_config.json` | `{use_remote, api_key, model_code}` |

**中间字段**（由图中节点计算生成）：

| 字段 | 来源节点 | 说明 |
|---|---|---|
| `system_prompt` | `select_system_prompt_node` | 选中的教练系统提示词 |
| `context_prompt` | `build_context_node` | 格式化后的结构化评分中文文本 |

**输出字段**（由图中节点返回）：

| 字段 | 来源节点 | 说明 |
|---|---|---|
| `response` | `call_dashscope_node` | QWEN 模型返回的教练回复 |
| `error` | 任意节点 | 错误信息，无错误时为空字符串 |

### 3.2 桥接函数

`state.py` 提供两个工厂函数，将已有的数据结构转换为 LangGraph 可消费的 `CoachAgentState`：

**`state_from_analysis(analysis_result, guidance_state, ...)`**

直接接收 `AnalysisResult` + `GuidanceState` 实例对象，序列化为 TypedDict。这是 Python 内部调用（如 `DetectorService` → `CoachAgent`）的主要入口。

**`state_from_dict(data, ...)`**

从 JSON 反序列化的 dict 构建状态。这是 HTTP API 调用（`POST /api/chat` 中的 `pose_context` JSON 字符串）的主要入口。

## 4. 三个图节点详解

**文件**：`code/langgraph_agent/nodes.py`

每个节点都是一个纯函数，签名为 `(CoachAgentState) -> dict`。返回的 dict 会被 LangGraph 自动合并回 state 中（类似 React 的 `setState`）。

### 4.1 Node 1: `select_system_prompt_node`

```python
def select_system_prompt_node(state: CoachAgentState) -> dict
```

**职责**：根据 `chat_mode` 字段选择合适的系统提示词。

- `chat_mode == "proactive"` → 返回 `COACH_SYSTEM_PROMPT_PROACTIVE`（精简版，约 150 字，更快更省 token）
- `chat_mode == "reactive"` → 返回 `COACH_SYSTEM_PROMPT`（完整版，约 400 字，包含 5 项职责和 6 条回复规范）

**输出**：`{"system_prompt": "..."}`

**为什么不在图中做条件分支**：LangGraph 支持 `add_conditional_edges`，但这里两个模式后续的 `build_context` 和 `call_dashscope` 节点完全相同，仅在内部逻辑上不同。将分支放在节点内部比放在图拓扑中更简洁，也更容易在将来添加新模式。

### 4.2 Node 2: `build_context_node`

```python
def build_context_node(state: CoachAgentState) -> dict
```

**职责**：将 state 中扁平化的 dict 数据重新组装为 `AnalysisResult` 和 `GuidanceState` 样式的对象，然后委托给已有的 `CoachContextBuilder` 进行格式化。

**实现细节**：

1. 从 `state["score"]` 重建 `SimpleNamespace` 对象（包含 `.total`, `.angle_score`, `.temporal_score`, `.symmetry_score` 属性）
2. 从 `state["joint_angles"]` 重建关节角度对象（包含 `.knee_left`, `.knee_right`, `.hip_left` 等属性）
3. 从 `state["errors"]` 重建错误对象列表（每项含 `.name`, `.severity`, `.suggestion`）
4. 从 `state` 的会话字段重建 `GuidanceState` 样式的对象（`.recent_scores`, `.best_score`, `.consecutive_good_form` 等）
5. 根据 `chat_mode` 调用 `CoachContextBuilder.build_proactive()` 或 `CoachContextBuilder.build_reactive()`

**为什么使用 `SimpleNamespace` 而不是导入 DataClass**：`CoachContextBuilder` 的三个方法（`build_proactive`、`build_reactive`、`_format_errors`）通过属性访问（`.score.total`）而非类型检查来消费数据。使用 `SimpleNamespace` 避免了为每个调用构造完整的 DataClass 实例（需要逐字段传参），降低了耦合度。

**输出**：`{"context_prompt": "【实时训练数据】\n动作：深蹲 (squat)\n完成次数：8 次 | ..."}`

**proactive 模式的上下文模板**（`COACH_CONTEXT_TEMPLATE`）包含 5 个信息块：

```
【实时训练数据】
动作：深蹲 (squat)
完成次数：8 次 | 当前阶段：低位

【动作评分】
总分：72/100 | 关节角度：28/40 | 时序：22/30 | 对称性：22/30
历史最佳：85/100 | 近10次均分：73.0/100

【检测到的错误】
💡 膝盖内扣(严重度1)：保持膝盖与脚尖方向一致

【关节角度数据】
左膝/右膝：95°/92° | 左髋/右髋：80°/78°
左肘/右肘：--°/--° | 躯干倾角：15°

【训练统计】
连续标准次数：0 | 连续问题次数：3
常见错误排行：膝盖内扣(5次)
```

**reactive 模式的上下文模板**（`COACH_REACTIVE_TEMPLATE`）更简洁：

```
【当前训练状态】
动作：深蹲 | 次数：8 | 总分：72/100 | 最佳：85/100
当前错误：膝盖内扣

【用户提问】
我的姿势怎么样？

请结合当前的训练数据，回答用户的问题。
```

### 4.3 Node 3: `call_dashscope_node`

```python
def call_dashscope_node(state: CoachAgentState) -> dict
```

**职责**：将 system prompt + context prompt 发送到阿里云 DashScope 上部署的 Qwen2.5-7B 模型。

**API 调用细节**：

```python
client = OpenAI(
    api_key=api_config["api_key"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
completion = client.chat.completions.create(
    model=api_config.get("model_code", "qwen-plus"),
    messages=[
        {"role": "system", "content": state["system_prompt"]},
        {"role": "user", "content": state["context_prompt"]},
    ],
    temperature=0.7,
    max_tokens=800,
)
reply = completion.choices[0].message.content
```

**错误处理**：
- 未配置远程 API → 返回 `{"error": "No remote API configured"}`
- context_prompt 为空 → 返回 `{"error": "No context prompt to send"}`
- API 调用异常 → 返回 `{"error": str(exception)}`

**输出**：`{"response": "你的深蹲整体不错...", "error": ""}`

**为什么复用 OpenAI SDK**：DashScope 提供 OpenAI 兼容接口，使用相同的 SDK 可以避免引入额外的阿里云 SDK 依赖。这与 `backend/routers/chat.py` 中的已有实现完全一致。

## 5. 图构建

**文件**：`code/langgraph_agent/graph.py`

```python
def create_coach_graph() -> StateGraph:
    builder = StateGraph(CoachAgentState)
    builder.add_node("select_system_prompt", select_system_prompt_node)
    builder.add_node("build_context", build_context_node)
    builder.add_node("call_dashscope", call_dashscope_node)
    builder.set_entry_point("select_system_prompt")
    builder.add_edge("select_system_prompt", "build_context")
    builder.add_edge("build_context", "call_dashscope")
    builder.add_edge("call_dashscope", END)
    return builder.compile()
```

**设计决策 —— 线性图而非分支图**：

LangGraph 支持 `add_conditional_edges` 根据 state 值做动态路由。此处选择线性拓扑的原因：
- proactive 和 reactive 模式的三个节点完全相同，差异仅在节点内部逻辑（选择哪个 prompt、选择哪个模板）
- 保持图拓扑简单，降低理解成本
- 为将来扩展预留空间（如在 `call_dashscope` 后添加条件路由到 retry 节点或本地模型降级节点）

## 6. CoachAgent 外观类

**文件**：`code/langgraph_agent/agent.py`

`CoachAgent` 是对 `create_coach_graph()` 的封装，提供三个层次的使用接口：

### 6.1 主动教练模式

```python
agent = CoachAgent()
result = agent.coach_proactive(
    analysis_result,   # pose_analyzer.AnalysisResult
    guidance_state,    # guidance.context_engine.GuidanceState
    exercise_name="深蹲",
)
# result["response"]: str  ← QWEN 返回的教练指导
# result["error"]: str     ← 错误信息（如有）
```

适用场景：`RealTimeCoach.evaluate_frame()` 检测到触发事件后，在后台线程调用此方法，将结果推送至前端。

### 6.2 被动聊天模式

```python
result = agent.coach_reactive(
    user_message="我的深蹲姿势怎么样？",
    analysis_result=current_analysis,  # 当前帧分析结果
    guidance_state=engine.state,       # 会话累计状态
    exercise_name="深蹲",
)
```

适用场景：用户在 AI 教练聊天面板主动提问时，附带当前训练数据作为上下文。

### 6.3 简化字符串接口

```python
reply = agent.chat(
    user_message="我的姿势怎么样？",
    pose_context_str='{"exercise_name":"深蹲","score":{"total":72,...},...}',
)
# reply: str  ← 直接返回回复文字
```

适用场景：HTTP API（`POST /api/chat`）调用，与已有 `FitnessAgent.chat()` 接口保持一致。

## 7. 与后端 API 的集成

**文件**：`backend/routers/chat.py`

在已有的 `POST /api/chat` 端点中增加了一个判断分支：

```python
if req.pose_context:
    # 新路径：LangGraph 教练代理
    from code.langgraph_agent.agent import CoachAgent
    agent = CoachAgent(api_config=config)
    reply = agent.chat(req.message, pose_context_str=req.pose_context)
else:
    # 原路径：通用 DashScope 调用（行为不变）
    client = OpenAI(...)
    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": req.message},
        ],
        ...
    )
```

**关键设计**：`pose_context` 字段在 `ChatRequest` 中早已存在（类型 `str | None`），之前未被远程 API 路径使用。现在它成为触发 LangGraph 路径的开关：
- `pose_context` 为空或未传 → 走原路径（通用对话）
- `pose_context` 有值 → 走 LangGraph 路径（教练专用提示词 + 结构化训练数据）

## 8. 与周边模块的关系

```
                        code/pose_analyzer.py
                        ┌─────────────────────┐
                        │ AnalysisResult       │
                        │ ScoreResult          │
                        │ JointAngles          │
                        │ ErrorInfo            │
                        └──────────┬──────────┘
                                   │ 不改动，只读取
                                   ▼
code/guidance/context_engine.py    code/realtime_coach.py
┌──────────────────────────────┐   ┌──────────────────────────┐
│ GuidanceState                │   │ CoachContextBuilder       │
│  .best_score                 │   │  .build_proactive()      │
│  .recent_scores              │   │  .build_reactive()       │
│  .consecutive_good_form      │   │ CoachTriggerEvaluator    │
│  .error_counts               │   │ RealTimeCoach            │
└──────────────┬───────────────┘   └───────────┬──────────────┘
               │ 不改动，只读取                 │ 不改动，被 LangGraph 调用
               ▼                               ▼
        code/langgraph_agent/
        ┌─────────────────────────────────────────────────────┐
        │ state.py   → CoachAgentState + 桥接函数              │
        │ nodes.py   → 3 个图节点                              │
        │ graph.py   → create_coach_graph()                    │
        │ agent.py   → CoachAgent 外观类                       │
        └────────────────────────┬────────────────────────────┘
                                 │
                                 ▼
                    backend/routers/chat.py
                    (通过 pose_context 字段触发 LangGraph 路径)
```

## 9. 测试方式

### 本地测试（无需 API）

```bash
# 测试模块导入 + state 构建 + 图编译
python -m code.langgraph_agent.agent
```

输出示例：
```
=== LangGraph CoachAgent self-test ===
API config loaded: remote=True, model=qwen2.5-7b-instruct-d1a1cabf17c2-yzqr

[Test 1] State construction...
  OK

[Test 2] Graph compilation...
  Graph compiled: nodes=['__start__', 'select_system_prompt', 'build_context', 'call_dashscope']
  OK

[Test 3] Skipped (no remote API configured).
  Set up data/api_config.json with DashScope credentials to test.

=== All local tests passed ===
```

### API 集成测试（需要 DashScope 配置 + openai 包）

```bash
# 1. 启动后端
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 2. 纯文本聊天（走原路径，不受影响）
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "如何做标准深蹲？"}'

# 3. 带训练数据的聊天（走 LangGraph 新路径）
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我的姿势怎么样？",
    "pose_context": "{\"exercise_name\":\"深蹲\",\"score\":{\"total\":72,\"angle\":28,\"temporal\":22,\"symmetry\":22},\"joint_angles\":{\"knee_left\":95,\"knee_right\":92,\"hip_left\":80,\"hip_right\":78,\"elbow_left\":null,\"elbow_right\":null,\"shoulder_left\":null,\"shoulder_right\":null,\"trunk_angle\":15,\"ankle_left\":null,\"ankle_right\":null},\"phase\":\"低位\",\"rep_count\":8,\"hold_time\":0,\"errors\":[{\"name\":\"膝盖内扣\",\"severity\":1,\"message\":\"检测到左膝内扣\",\"suggestion\":\"保持膝盖与脚尖方向一致\"}],\"best_score\":85,\"consecutive_good_form\":0,\"consecutive_bad_form\":3,\"error_counts\":{\"膝盖内扣\":5},\"recent_scores\":[72,70,68,75,72]}"
  }'
```

## 10. 扩展方向

当前实现是 LangGraph 的最小可用版本（MVP）。以下扩展方向已在架构中预留空间：

1. **条件路由降级**：在 `call_dashscope` 后添加条件边，API 失败时自动路由到本地模型节点
2. **检查点持久化**：引入 `MemorySaver` 或 `SqliteSaver`，使训练会话的 state 在服务重启后依然可恢复
3. **Human-in-the-loop**：在严重安全警告（severity=3）时 `interrupt` 图执行，等待人工确认后再推送
4. **并行节点**：将 `JointAngleHeatmap` 计算和 `build_context` 并行执行，减少端到端延迟
5. **流式输出**：使用 `graph.astream()` 替代 `graph.invoke()`，实现 Token 级别的流式推送至前端
