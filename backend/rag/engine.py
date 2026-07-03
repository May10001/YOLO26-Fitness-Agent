"""
Lightweight RAG engine for fitness knowledge Q&A.
Uses TF-IDF + cosine similarity for retrieval (no GPU/external API needed).

Index file is auto-built on first query if not present.
"""
import json
import pickle
import re
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "fitness_dataset.json"
INDEX_PATH = PROJECT_ROOT / "data" / "processed" / "rag_index.pkl"

# Lazy-loaded globals
_vectorizer = None
_doc_matrix = None
_doc_texts: list[str] = []
_doc_meta: list[dict] = []


def _tokenize(text: str) -> str:
    """Simple Chinese-friendly tokenization using character bigrams."""
    text = re.sub(r'[^一-鿿\w]', ' ', text)
    chars = text.replace(' ', '  ').strip()
    # Bigram for Chinese, space-split for English
    tokens = []
    for i in range(len(chars) - 1):
        seg = chars[i:i+2]
        if ' ' not in seg:
            tokens.append(seg)
    # Also include single chars
    tokens.extend([c for c in chars if c != ' '])
    return ' '.join(tokens)


def _chunk_text(text: str, max_len: int = 500) -> list[str]:
    """Split long text into chunks at sentence boundaries."""
    sentences = re.split(r'[。！？\n]+', text)
    chunks = []
    current = ''
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) > max_len and current:
            chunks.append(current.strip())
            current = s
        else:
            current += s + '。'
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


def build_index(force: bool = False):
    """Build (or load) the TF-IDF index from the fitness dataset."""
    global _vectorizer, _doc_matrix, _doc_texts, _doc_meta

    if not force and INDEX_PATH.exists():
        return _load_index()

    from sklearn.feature_extraction.text import TfidfVectorizer

    with open(DATASET_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    texts = []
    metas = []

    # Index correction samples
    for item in data.get('correction_samples', []):
        ex = item.get('exercise', '')
        err = item.get('error', '')
        out = item.get('output', '')
        trigger = item.get('trigger_condition', '')
        body = f"动作：{ex}。错误：{err}。触发条件：{trigger}。教练指导：{out}"
        for chunk in _chunk_text(body):
            texts.append(_tokenize(chunk))
            metas.append({
                'source': '动作纠错',
                'exercise': ex,
                'error': err,
                'text': chunk,
            })

    # Index planning samples
    for item in data.get('planning_samples', []):
        out = item.get('output', '')
        inp = item.get('input', {})
        goal = inp.get('goal', '')
        level = inp.get('fitness_level', '')
        body = f"训练计划。目标：{goal}。水平：{level}。计划内容：{out}"
        for chunk in _chunk_text(body, max_len=800):
            texts.append(_tokenize(chunk))
            metas.append({
                'source': '训练计划',
                'goal': goal,
                'level': level,
                'text': chunk,
            })

    _vectorizer = TfidfVectorizer(max_features=3000)
    _doc_matrix = _vectorizer.fit_transform(texts)
    _doc_texts = texts
    _doc_meta = metas

    # Save to disk
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, 'wb') as f:
        pickle.dump({
            'vectorizer': _vectorizer,
            'matrix': _doc_matrix,
            'texts': _doc_texts,
            'metas': _doc_meta,
        }, f)

    print(f"[RAG] Index built: {len(texts)} chunks from {len(data.get('correction_samples',[]))} corrections + {len(data.get('planning_samples',[]))} plans")
    return len(texts)


def _load_index() -> int:
    """Load pre-built index from disk."""
    global _vectorizer, _doc_matrix, _doc_texts, _doc_meta
    with open(INDEX_PATH, 'rb') as f:
        saved = pickle.load(f)
    _vectorizer = saved['vectorizer']
    _doc_matrix = saved['matrix']
    _doc_texts = saved['texts']
    _doc_meta = saved['metas']
    print(f"[RAG] Index loaded: {len(_doc_texts)} chunks")
    return len(_doc_texts)


def search(query: str, top_k: int = 5) -> list[dict]:
    """Search the index and return top-K results with relevance scores."""
    if _vectorizer is None:
        build_index()

    q_vec = _vectorizer.transform([_tokenize(query)])
    from sklearn.metrics.pairwise import cosine_similarity
    scores = cosine_similarity(q_vec, _doc_matrix)[0]

    top_idx = np.argsort(scores)[::-1][:top_k]

    results = []
    seen = set()
    for idx in top_idx:
        score = float(scores[idx])
        if score < 0.05:
            continue
        meta = dict(_doc_meta[idx])
        # Deduplicate very similar results
        key = meta['text'][:80]
        if key in seen:
            continue
        seen.add(key)
        meta['score'] = round(score, 3)
        results.append(meta)

    return results


def format_context(results: list[dict]) -> str:
    """Format search results as context for the LLM."""
    if not results:
        return "（未找到相关知识）"
    lines = []
    for i, r in enumerate(results, 1):
        src = r.get('source', '')
        lines.append(f"[{i}] ({src}) {r['text'][:600]}")
    return '\n\n'.join(lines)
