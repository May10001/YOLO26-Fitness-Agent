"""RAG fitness knowledge Q&A endpoint with streaming support."""
import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import load_api_config
from ..rag.engine import search, format_context

router = APIRouter(prefix="/api")

RAG_SYSTEM_PROMPT = """你是一个资深健身知识助手，基于提供的参考资料和运动科学知识回答用户问题。

## 回答要求
1. **详细充分**：每个回答至少150字，深入解释原理
2. **知识融合**：将参考资料与运动科学（解剖学、生物力学、训练学）结合
3. **结构化**：根因分析→解决方案→进阶知识，分层次展开
4. **可量化**：给出具体的角度、次数、时长、频率
5. **安全提示**：标注风险点和禁忌人群

## 格式
- 先基于参考资料给出核心答案
- 再补充相关的运动科学原理
- 最后提供可操作的进阶建议
- 如果参考资料无覆盖，明确说明并用你的专业知识补充

用中文回答，专业、鼓励、可执行。"""


class RAGQuery(BaseModel):
    question: str
    stream: bool = False


@router.post("/rag/query")
async def rag_query(req: RAGQuery):
    """Search fitness knowledge base and answer with LLM. Supports streaming."""
    results = search(req.question)
    context = format_context(results)
    sources = [{"source": r["source"], "snippet": r["text"][:150]} for r in results[:3]]

    config = load_api_config()
    if not config.get("use_remote") or not config.get("api_key"):
        return {"answer": f"（API 未配置）根据知识库检索，以下信息可能对你有帮助：\n\n{context[:800]}", "sources": sources}

    if req.stream:
        return StreamingResponse(
            _stream_rag(config, context, req.question, sources),
            media_type="text/event-stream",
        )

    try:
        reply = await _call_rag(config, context, req.question)
        return {"answer": reply, "sources": sources}
    except Exception as e:
        return {"answer": f"AI 调用失败: {e}\n\n{context[:800]}", "sources": []}


async def _call_rag(config: dict, context: str, question: str) -> str:
    from openai import OpenAI
    client = OpenAI(
        api_key=config["api_key"],
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    completion = client.chat.completions.create(
        model=config.get("model_code", "qwen-plus"),
        messages=[
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": f"参考资料：\n{context}\n\n用户问题：{question}\n\n请基于参考资料回答。"},
        ],
        temperature=0.5,
        max_tokens=1000,
    )
    return completion.choices[0].message.content


async def _stream_rag(config: dict, context: str, question: str, sources: list):
    from openai import OpenAI

    queue: asyncio.Queue = asyncio.Queue()

    def _run():
        try:
            client = OpenAI(
                api_key=config["api_key"],
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            stream = client.chat.completions.create(
                model=config.get("model_code", "qwen-plus"),
                messages=[
                    {"role": "system", "content": RAG_SYSTEM_PROMPT},
                    {"role": "user", "content": f"参考资料：\n{context}\n\n用户问题：{question}\n\n请基于参考资料回答。"},
                ],
                temperature=0.5,
                max_tokens=1000,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    queue.put_nowait(json.dumps({'text': delta.content}))
            queue.put_nowait(json.dumps({'sources': sources, 'done': True}))
        except Exception as e:
            queue.put_nowait(json.dumps({'error': str(e)}))

    asyncio.get_event_loop().run_in_executor(None, _run)

    while True:
        data = await queue.get()
        yield f"data: {data}\n\n"
        if '"done": true' in data or '"error"' in data:
            break
