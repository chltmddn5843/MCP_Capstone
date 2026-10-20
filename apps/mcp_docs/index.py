"""SQLite FTS5 전문 검색 색인. 서버가 뜰 때 말뭉치를 메모리 DB에 한 번 색인한다.

한국어는 띄어쓰기·조사 때문에 단어 단위 토큰이 잘 맞지 않아 trigram 토크나이저를 쓴다.
- 3글자 이상 검색어: 3글자 조각으로 나눠 FTS5 MATCH(OR), bm25 점수 사용
- 2글자 검색어(예: 파일, 비교): trigram으로 못 찾으므로 본문 부분 일치로 점수를 더한다
최종 점수는 0~1로 바꿔 돌려준다.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache

from apps.mcp_docs.corpus import Chunk, chunks, load_corpus


@dataclass
class Hit:
    chunk: Chunk
    score: float


class FtsIndex:
    def __init__(self) -> None:
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE VIRTUAL TABLE docs USING fts5(section, body, doc_id UNINDEXED, "
                        "seq UNINDEXED, tokenize='trigram')")
        self.chunks: dict[tuple[str, int], Chunk] = {}
        for doc in load_corpus().values():
            for chunk in chunks(doc):
                self.chunks[(doc.doc_id, chunk.seq)] = chunk
                self.db.execute("INSERT INTO docs VALUES (?, ?, ?, ?)", (chunk.section, chunk.text, doc.doc_id, chunk.seq))

    @staticmethod
    def _terms(query: str) -> tuple[str | None, list[str]]:
        words = [w for w in re.split(r"\s+", re.sub(r'["*()]', " ", query)) if w]
        grams = sorted({w[i:i + 3] for w in words if len(w) >= 3 for i in range(len(w) - 2)})
        short = [w for w in words if len(w) == 2]
        return (" OR ".join(f'"{g}"' for g in grams) or None), short

    def search(self, query: str, *, doc_type: str | None = None, vendor: str | None = None,
               kind: str | None = None, candidates_only: bool = False, limit: int = 5) -> list[Hit]:
        match, short = self._terms(query)
        relevance: dict[tuple[str, int], float] = {}
        if match:
            for doc_id, seq, rank in self.db.execute(
                    "SELECT doc_id, seq, bm25(docs) FROM docs WHERE docs MATCH ?", (match,)):
                relevance[(doc_id, seq)] = max(-rank, 0.0)   # bm25는 음수일수록 가깝다
        for key, chunk in self.chunks.items():
            found = sum(2 if word in chunk.section else 1 if word in chunk.text else 0 for word in short)  # 제목 일치 가중
            if found:
                relevance[key] = relevance.get(key, 0.0) + found

        hits = []
        for key, value in sorted(relevance.items(), key=lambda kv: kv[1], reverse=True):
            chunk = self.chunks[key]
            meta = chunk.doc.meta
            if doc_type and chunk.doc.doc_type != doc_type:
                continue
            if vendor and meta.get("vendor", "").lower() != vendor.lower():
                continue
            if kind and meta.get("kind") != kind:
                continue
            if candidates_only and meta.get("is_candidate") != "true":
                continue
            hits.append(Hit(chunk=chunk, score=round(value / (1 + value), 4)))
            if len(hits) >= limit:
                break
        return hits


@lru_cache(maxsize=1)
def get_index() -> FtsIndex:
    return FtsIndex()
