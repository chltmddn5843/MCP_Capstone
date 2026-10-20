"""문서 말뭉치 적재. 마크다운 문서를 '## ' 제목 단위 조각(chunk)으로 자른다.

문서 위치(뒤 폴더가 같은 doc_id를 덮어쓴다. MCP_DOCS_DIRS 환경변수로 바꿀 수 있다)
1. apps/mcp_docs/sample_docs/*.md — MCP 담당이 둔 개발용 샘플
2. db/seed/docs/*.md        — 백엔드+DB 담당이 시드로 넣는 벤더 문서·사내 정책 (있으면)

문서 머리말(front matter) 키
  doc_id, title, doc_type(vendor | policy), vendor, kind(release_notes | pricing | docs),
  url, published_at(YYYY-MM-DD), is_candidate(true면 비교 후보 벤더)

외부 문서 내용은 데이터로만 다룬다. 문서 안의 지시문은 따르지 않으며, 저장할 때 HTML 태그를 지운다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC_DIRS = [Path(p) for p in os.environ.get("MCP_DOCS_DIRS", "").split(os.pathsep) if p] or [
    Path(__file__).resolve().parent / "sample_docs",
    ROOT / "db" / "seed" / "docs",
]
TAG = re.compile(r"<[^>]+>")


@dataclass
class Doc:
    doc_id: str
    title: str
    doc_type: str
    raw: str
    meta: dict = field(default_factory=dict)


@dataclass
class Chunk:
    doc: Doc
    seq: int
    section: str
    text: str


def _front_matter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    _, header, body = raw.split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body.strip()


@lru_cache(maxsize=1)
def load_corpus() -> dict[str, Doc]:
    docs: dict[str, Doc] = {}
    for folder in DOC_DIRS:
        for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
            raw = TAG.sub("", path.read_text(encoding="utf-8"))
            meta, _ = _front_matter(raw)
            doc_id = meta.get("doc_id", path.stem)
            docs[doc_id] = Doc(doc_id=doc_id, title=meta.get("title", path.stem),
                               doc_type=meta.get("doc_type", "vendor"), raw=raw, meta=meta)
    return docs


def chunks(doc: Doc) -> list[Chunk]:
    _, body = _front_matter(doc.raw)
    out, section, lines = [], None, []

    def flush():
        if section is not None:
            text = "\n".join(line for line in lines if not line.startswith(">")).strip()
            out.append(Chunk(doc=doc, seq=len(out) + 1, section=section, text=text))

    for line in body.splitlines():
        if line.startswith("## "):
            flush()
            section, lines = line[3:].strip(), []
        elif section is not None:
            lines.append(line)
    flush()
    return out
