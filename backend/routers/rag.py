"""RAG fitness knowledge Q&A endpoint with streaming support."""
import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import load_api_config
from ..rag.engine import search, format_context

router = APIRouter(prefix="/api")

RAG_SYSTEM_PROMPT = """你是一个健身知识助手，基于提供的参考资料回答用户的问题。

规则：
1. 优先使用参考资料中的专业知识回答
2. 如果参考资料没有覆盖问题，可以用你的健身知识补充，但要明确说明
3. 回答要具体、实用、可操作
4. 用中文回答，控制在200字以内
5. 如果用户问的是动作纠错相关，给出具体的步骤和cue点"""


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
        max_tokens=600,
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
                max_tokens=600,
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
