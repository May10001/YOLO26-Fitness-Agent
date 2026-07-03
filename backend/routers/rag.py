"""RAG fitness knowledge Q&A endpoint."""
import asyncio
from fastapi import APIRouter
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


@router.post("/rag/query")
async def rag_query(req: RAGQuery):
    """Search fitness knowledge base and answer with LLM."""

    # 1. Search RAG
    results = search(req.question)
    context = format_context(results)

    # 2. Call LLM with context
    config = load_api_config()
    if not config.get("use_remote") or not config.get("api_key"):
        # Fallback: return raw search results
        return {
            "answer": f"（API 未配置）根据知识库检索，以下信息可能对你有帮助：\n\n{context[:800]}",
            "sources": [{"source": r["source"], "snippet": r["text"][:150]} for r in results[:3]],
        }

    try:
        from openai import OpenAI

        def _call_api():
            client = OpenAI(
                api_key=config["api_key"],
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            completion = client.chat.completions.create(
                model=config.get("model_code", "qwen-plus"),
                messages=[
                    {"role": "system", "content": RAG_SYSTEM_PROMPT},
                    {"role": "user", "content": f"参考资料：\n{context}\n\n用户问题：{req.question}\n\n请基于参考资料回答。"},
                ],
                temperature=0.5,
                max_tokens=600,
            )
            return completion.choices[0].message.content

        reply = await asyncio.get_event_loop().run_in_executor(None, _call_api)

        return {
            "answer": reply,
            "sources": [{"source": r["source"], "snippet": r["text"][:150]} for r in results[:3]],
        }

    except Exception as e:
        return {"answer": f"AI 调用失败: {e}\n\n以下是知识库检索结果：\n\n{context[:800]}", "sources": []}
