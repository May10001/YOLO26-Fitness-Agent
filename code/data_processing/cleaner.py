"""
Data cleaning module for fitness guidance dataset.

Operations:
  1. Deduplication (exact + fuzzy)
  2. Text normalization (full-width → half-width, whitespace)
  3. Quality filtering (min length, coherence)
  4. Language detection (keep Chinese-only content)
  5. PII removal
"""

import json
import logging
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DataCleaner:
    """Clean and normalize fitness guidance data."""

    def __init__(
        self,
        min_text_length: int = 20,
        max_text_length: int = 4096,
        fuzzy_dedup_threshold: float = 0.85,
    ):
        self.min_text_length = min_text_length
        self.max_text_length = max_text_length
        self.fuzzy_dedup_threshold = fuzzy_dedup_threshold

    def clean_text(self, text: str) -> str:
        """Normalize a single text string."""
        if not text:
            return ""

        # Full-width to half-width for numbers and punctuation
        text = self._normalize_fullwidth(text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove control characters
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def _normalize_fullwidth(self, text: str) -> str:
        """Convert full-width characters to half-width."""
        result = []
        for ch in text:
            code = ord(ch)
            if 0xFF01 <= code <= 0xFF5E:  # Full-width punctuation
                result.append(chr(code - 0xFEE0))
            elif code == 0x3000:  # Full-width space
                result.append(" ")
            else:
                result.append(ch)
        return "".join(result)

    def deduplicate_exact(self, items: list[dict], key: str = "text") -> list[dict]:
        """Remove exact duplicates based on a key field."""
        seen = set()
        unique = []
        for item in items:
            text = item.get(key, "")
            if text not in seen:
                seen.add(text)
                unique.append(item)
        logger.info("去重: %d → %d (精确匹配)", len(items), len(unique))
        return unique

    def deduplicate_fuzzy(self, items: list[dict], key: str = "text") -> list[dict]:
        """Remove near-duplicates using sequence similarity."""
        unique = []
        seen_texts = []

        for item in items:
            text = item.get(key, "")
            is_dup = False
            for seen in seen_texts:
                if len(text) > 50 and len(seen) > 50:
                    ratio = SequenceMatcher(None, text[:200], seen[:200]).ratio()
                    if ratio > self.fuzzy_dedup_threshold:
                        is_dup = True
                        break
            if not is_dup:
                unique.append(item)
                seen_texts.append(text)

        logger.info("去重: %d → %d (模糊匹配, 阈值=%.2f)", len(items), len(unique), self.fuzzy_dedup_threshold)
        return unique

    def filter_by_length(self, items: list[dict], text_key: str = "text") -> list[dict]:
        """Filter items by text length."""
        filtered = []
        for item in items:
            text = item.get(text_key, "")
            if self.min_text_length <= len(text) <= self.max_text_length:
                filtered.append(item)
        logger.info("长度过滤: %d → %d (范围: %d-%d)", len(items), len(filtered), self.min_text_length, self.max_text_length)
        return filtered

    def filter_chinese_ratio(self, items: list[dict], text_key: str = "text",
                              min_ratio: float = 0.3) -> list[dict]:
        """Filter items with insufficient Chinese content."""
        filtered = []
        for item in items:
            text = item.get(text_key, "")
            if not text:
                continue
            chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
            ratio = chinese_chars / len(text) if text else 0
            if ratio >= min_ratio:
                filtered.append(item)
        logger.info("中文过滤: %d → %d (最小比例: %.1f)", len(items), len(filtered), min_ratio)
        return filtered

    def remove_pii(self, text: str) -> str:
        """Remove personally identifiable information."""
        # Phone numbers (Chinese)
        text = re.sub(r"1[3-9]\d{9}", "[PHONE]", text)
        # Email
        text = re.sub(r"[\w.-]+@[\w.-]+\.\w+", "[EMAIL]", text)
        # ID numbers
        text = re.sub(r"\d{17}[\dXx]", "[ID]", text)
        return text

    def clean_conversation(self, conv: list[dict]) -> Optional[list[dict]]:
        """Clean a single conversation (list of messages)."""
        cleaned = []
        for msg in conv:
            content = msg.get("content", "")
            content = self.clean_text(content)
            content = self.remove_pii(content)
            if not content:
                return None
            cleaned.append({**msg, "content": content})
        return cleaned

    def clean_dataset(self, conversations: list[list[dict]]) -> list[list[dict]]:
        """Full cleaning pipeline for conversation dataset."""
        logger.info("开始数据清洗, 原始数量: %d", len(conversations))

        # 1. Clean each conversation
        cleaned = []
        for conv in conversations:
            c = self.clean_conversation(conv)
            if c:
                cleaned.append(c)

        # 2. Convert to dict with text key for dedup
        items = [{"text": json.dumps(c, ensure_ascii=False), "messages": c} for c in cleaned]

        # 3. Length filter
        items = self.filter_by_length(items)

        # 4. Chinese ratio filter
        items = self.filter_chinese_ratio(items)

        # 5. Exact dedup
        items = self.deduplicate_exact(items)

        # 6. Fuzzy dedup
        items = self.deduplicate_fuzzy(items)

        logger.info("清洗完成, 最终数量: %d", len(items))
        return [item["messages"] for item in items]
