"""AI Document Assistant with RAG chunk retrieval, local grounded analysis, and consent-gated LLM API."""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any, Optional

import httpx

from ..config import settings
from ..models import AICitation, AIQueryRequest, AIQueryResponse

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must", "this", "that", "these", "those", "it",
    "its", "they", "them", "their", "we", "our", "you", "your", "i", "me", "my", "as", "not",
    "no", "what", "which", "who", "whom", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "than", "too", "very", "just",
}


def chunk_pages(pages: list[dict[str, Any]], chunk_size: int = 1200, overlap: int = 200) -> list[dict[str, Any]]:
    """Split extracted pages into overlapping RAG chunks preserving page numbers."""
    chunks: list[dict[str, Any]] = []
    chunk_idx = 0
    step = max(200, chunk_size - overlap)

    for page in pages:
        page_num = int(page["page_number"])
        text = (page.get("text") or "").strip()
        if not text:
            continue
        if len(text) <= chunk_size:
            chunks.append({"chunk_index": chunk_idx, "page_number": page_num, "text": text})
            chunk_idx += 1
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            # Snap to whitespace boundary when possible
            if end < len(text):
                ws = text.rfind(" ", start + int(chunk_size * 0.6), end)
                if ws > start:
                    end = ws
            piece = text[start:end].strip()
            if piece:
                chunks.append({"chunk_index": chunk_idx, "page_number": page_num, "text": piece})
                chunk_idx += 1
            if end >= len(text):
                break
            start += step
    return chunks


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    raw = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    return [s.strip() for s in raw if len(s.strip()) >= 15]


def _retrieve_top_chunks(
    query: str, chunks: list[dict[str, Any]], top_k: int = 4
) -> list[tuple[dict[str, Any], float]]:
    if not chunks:
        return []
    q_tokens = _tokenize(query)
    if not q_tokens:
        return [(c, 0.1) for c in chunks[:top_k]]

    doc_tokens = [_tokenize(c["text"]) for c in chunks]
    n_docs = len(chunks)
    df: Counter[str] = Counter()
    for toks in doc_tokens:
        df.update(set(toks))

    def _tfidf_vec(toks: list[str]) -> dict[str, float]:
        tf = Counter(toks)
        total = max(1, len(toks))
        vec: dict[str, float] = {}
        for term, cnt in tf.items():
            idf = math.log((n_docs + 1) / (df.get(term, 0) + 1)) + 1.0
            vec[term] = (cnt / total) * idf
        return vec

    q_vec = _tfidf_vec(q_tokens)
    q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

    scored: list[tuple[dict[str, Any], float]] = []
    q_lower = query.lower().strip()
    for chunk, toks in zip(chunks, doc_tokens):
        c_vec = _tfidf_vec(toks)
        c_norm = math.sqrt(sum(v * v for v in c_vec.values())) or 1.0
        dot = sum(q_vec[t] * c_vec.get(t, 0.0) for t in q_vec)
        score = dot / (q_norm * c_norm)
        # Boost exact phrase matches
        if len(q_lower) >= 4 and q_lower in chunk["text"].lower():
            score = min(1.0, score + 0.35)
        scored.append((chunk, round(score, 4)))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def _extract_dates_and_names(text: str) -> dict[str, list[str]]:
    date_patterns = [
        r"\b(?:\d{4}-\d{2}-\d{2})\b",
        r"\b(?:\d{1,2}/\d{1,2}/\d{2,4})\b",
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b",
        r"\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b",
        r"\bQ[1-4]\s+\d{4}\b",
    ]
    dates_found: list[str] = []
    for pat in date_patterns:
        for m in re.findall(pat, text):
            val = m.strip()
            if val and val not in dates_found:
                dates_found.append(val)

    # Proper-noun multi-word capitalized phrases (names/organizations)
    excluded_starts = {
        "The", "This", "That", "These", "Those", "Page", "Table", "Slide", "Section",
        "Chapter", "Figure", "Summary", "Introduction", "Conclusion", "Overview",
        "January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December", "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday",
    }
    raw_names = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text)
    names_found: list[str] = []
    for n in raw_names:
        first = n.split()[0]
        if first in excluded_starts:
            continue
        if n not in names_found:
            names_found.append(n)

    emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))
    amounts = []
    for m in re.findall(r"(?:\$|€|£|₹)\s?\d[\d,]*(?:\.\d{1,2})?(?:\s?(?:million|billion|thousand|M|B|K))?", text):
        if m not in amounts:
            amounts.append(m)

    return {
        "dates": dates_found[:30],
        "names_and_entities": names_found[:30],
        "emails": emails[:20],
        "monetary_amounts": amounts[:20],
    }


class AIService:
    """Grounded Document AI Assistant (local RAG + optional external LLM with explicit consent)."""

    async def _call_external_llm(self, system_prompt: str, user_prompt: str) -> Optional[tuple[str, str]]:
        """Invoke configured OpenAI or Gemini API strictly when user consented."""
        if settings.openai_api_key:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json={
                        "model": settings.openai_model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip(), f"openai:{settings.openai_model}"

        if settings.gemini_api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    params={"key": settings.gemini_api_key},
                    json={
                        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                        "generationConfig": {"temperature": 0.2},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text, f"gemini:{settings.gemini_model}"

        return None

    async def query(
        self,
        doc: dict[str, Any],
        chunks: list[dict[str, Any]],
        req: AIQueryRequest,
    ) -> AIQueryResponse:
        full_text = (doc.get("full_text") or "").strip()
        tables = doc.get("tables", [])

        if not full_text and not tables:
            return AIQueryResponse(
                document_id=doc["id"],
                action=req.action,
                answer="No extractable text or tables were found in this document, so I cannot answer based on its contents.",
                found_in_document=False,
                provider_used="local-rag",
            )

        # Build RAG context for external LLM if explicitly consented and configured
        can_use_external = bool(req.allow_external_ai and (settings.openai_api_key or settings.gemini_api_key))

        if req.action == "extract_entities":
            entities = _extract_dates_and_names(full_text)
            lines = []
            if entities["dates"]:
                lines.append("Dates found:\n" + "\n".join(f"• {d}" for d in entities["dates"]))
            if entities["names_and_entities"]:
                lines.append("Names & Entities found:\n" + "\n".join(f"• {n}" for n in entities["names_and_entities"]))
            if entities["emails"]:
                lines.append("Email addresses:\n" + "\n".join(f"• {e}" for e in entities["emails"]))
            if entities["monetary_amounts"]:
                lines.append("Monetary figures:\n" + "\n".join(f"• {a}" for a in entities["monetary_amounts"]))
            found = bool(lines)
            answer = (
                "\n\n".join(lines)
                if found
                else "No specific dates, named entities, emails, or monetary values were detected in this document."
            )
            return AIQueryResponse(
                document_id=doc["id"],
                action=req.action,
                answer=answer,
                found_in_document=found,
                provider_used="local-extractor",
                structured_data=entities,
            )

        if req.action == "explain_tables":
            if not tables:
                return AIQueryResponse(
                    document_id=doc["id"],
                    action=req.action,
                    answer="This document does not contain any detected tables.",
                    found_in_document=False,
                    provider_used="local-rag",
                )
            parts = []
            for t in tables[:10]:
                headers = t.get("headers", [])
                rows = t.get("rows", [])
                title = t.get("title") or f"Table {t['table_index'] + 1}"
                sample_row = " | ".join(rows[0]) if rows else "(no data rows)"
                parts.append(
                    f"**{title}** (Page {t['page_number']}): {len(headers)} columns ({', '.join(h or '(blank)' for h in headers[:8])}) and {len(rows)} rows. First row sample: {sample_row}"
                )
            answer = "\n\n".join(parts)
            return AIQueryResponse(
                document_id=doc["id"],
                action=req.action,
                answer=answer,
                found_in_document=True,
                provider_used="local-table-analyzer",
                structured_data={"table_count": len(tables)},
            )

        if req.action in ("summarize", "key_points"):
            sentences = _split_sentences(full_text)
            top_chunks = chunks[:4]
            citations = [
                AICitation(
                    page_number=c["page_number"],
                    chunk_index=c["chunk_index"],
                    excerpt=c["text"][:180].replace("\n", " "),
                    score=1.0,
                )
                for c in top_chunks
            ]

            if can_use_external:
                try:
                    context = "\n\n---\n\n".join(f"[Page {c['page_number']}]\n{c['text']}" for c in chunks[:8])
                    task = "Provide a concise, accurate executive summary." if req.action == "summarize" else "Extract 5 to 7 concise key bullet points."
                    sys_prompt = "You are DOCREADER AI. Answer strictly using ONLY the provided document excerpts. Do not invent facts."
                    llm_res = await self._call_external_llm(sys_prompt, f"Task: {task}\n\nDocument:\n{context}")
                    if llm_res:
                        return AIQueryResponse(
                            document_id=doc["id"],
                            action=req.action,
                            answer=llm_res[0],
                            found_in_document=True,
                            provider_used=llm_res[1],
                            citations=citations,
                        )
                except Exception as exc:
                    logger.warning("External LLM failed, falling back to local summarizer: %s", exc)

            # Extractive TF-scoring summary
            if not sentences:
                fallback = full_text[:600]
                return AIQueryResponse(
                    document_id=doc["id"],
                    action=req.action,
                    answer=fallback,
                    found_in_document=True,
                    provider_used="local-rag",
                    citations=citations,
                )

            word_freq = Counter(_tokenize(full_text))
            scored_sents: list[tuple[int, float, str]] = []
            for idx, s in enumerate(sentences):
                toks = _tokenize(s)
                if not toks:
                    continue
                score = sum(word_freq[t] for t in toks) / (len(toks) ** 0.7)
                if idx < 3:
                    score *= 1.2
                scored_sents.append((idx, score, s))

            k = 4 if req.action == "summarize" else 6
            top = sorted(scored_sents, key=lambda x: x[1], reverse=True)[:k]
            top.sort(key=lambda x: x[0])

            if req.action == "key_points":
                answer = "\n".join(f"• {s}" for _, _, s in top)
            else:
                answer = " ".join(s for _, _, s in top)

            return AIQueryResponse(
                document_id=doc["id"],
                action=req.action,
                answer=answer,
                found_in_document=True,
                provider_used="local-rag",
                citations=citations,
            )

        if req.action == "explain_paragraph":
            target = (req.paragraph_text or req.question or "").strip()
            if not target:
                return AIQueryResponse(
                    document_id=doc["id"],
                    action=req.action,
                    answer="Please select or paste a paragraph from the document to explain.",
                    found_in_document=False,
                    provider_used="local-rag",
                )
            if can_use_external:
                try:
                    sys_prompt = "You are DOCREADER AI. Explain the given paragraph clearly in plain language using only its content and document context."
                    llm_res = await self._call_external_llm(sys_prompt, f"Paragraph to explain:\n{target}")
                    if llm_res:
                        return AIQueryResponse(
                            document_id=doc["id"],
                            action=req.action,
                            answer=llm_res[0],
                            found_in_document=True,
                            provider_used=llm_res[1],
                        )
                except Exception as exc:
                    logger.warning("External LLM failed on explain_paragraph: %s", exc)

            sents = _split_sentences(target) or [target]
            key_terms = [w for w, _ in Counter(_tokenize(target)).most_common(6)]
            explanation = (
                f"Plain breakdown ({len(target.split())} words):\n"
                + "\n".join(f"• {s}" for s in sents[:5])
                + (f"\n\nKey terms in this passage: {', '.join(key_terms)}." if key_terms else "")
            )
            return AIQueryResponse(
                document_id=doc["id"],
                action=req.action,
                answer=explanation,
                found_in_document=True,
                provider_used="local-rag",
            )

        # Default action: "ask" (RAG Q&A grounded strictly in uploaded document)
        question = (req.question or "").strip()
        if not question:
            return AIQueryResponse(
                document_id=doc["id"],
                action="ask",
                answer="Please enter a question about the document.",
                found_in_document=False,
                provider_used="local-rag",
            )

        retrieved = _retrieve_top_chunks(question, chunks, top_k=4)
        relevant = [(c, sc) for c, sc in retrieved if sc >= 0.08]

        if not relevant:
            return AIQueryResponse(
                document_id=doc["id"],
                action="ask",
                answer=(
                    "I could not find information answering that question in the uploaded document. "
                    "Try rephrasing with terms that appear in the text, or check the Search tab."
                ),
                found_in_document=False,
                provider_used="local-rag",
                citations=[],
            )

        citations = [
            AICitation(
                page_number=c["page_number"],
                chunk_index=c["chunk_index"],
                excerpt=c["text"][:200].replace("\n", " "),
                score=sc,
            )
            for c, sc in relevant
        ]

        if can_use_external:
            try:
                context = "\n\n---\n\n".join(f"[Page {c['page_number']}]\n{c['text']}" for c, _ in relevant)
                sys_prompt = (
                    "You are DOCREADER AI. Answer the user's question STRICTLY from the provided document excerpts. "
                    "Cite page numbers like (Page N). If the answer is not in the excerpts, explicitly say it cannot be found in the document."
                )
                llm_res = await self._call_external_llm(sys_prompt, f"Question: {question}\n\nExcerpts:\n{context}")
                if llm_res:
                    not_found = "cannot be found in the document" in llm_res[0].lower() or "not mentioned" in llm_res[0].lower()
                    return AIQueryResponse(
                        document_id=doc["id"],
                        action="ask",
                        answer=llm_res[0],
                        found_in_document=not not_found,
                        provider_used=llm_res[1],
                        citations=citations,
                    )
            except Exception as exc:
                logger.warning("External LLM failed on ask, falling back to local RAG: %s", exc)

        # Local extractive RAG answer: pick best matching sentences from top retrieved chunks
        q_toks = set(_tokenize(question))
        candidate_sents: list[tuple[float, int, str]] = []
        for chunk, chunk_score in relevant:
            for sent in _split_sentences(chunk["text"]):
                s_toks = set(_tokenize(sent))
                overlap = len(q_toks & s_toks)
                if overlap > 0:
                    s_score = (overlap / max(1, len(q_toks))) + (chunk_score * 0.5)
                    candidate_sents.append((s_score, chunk["page_number"], sent))

        candidate_sents.sort(key=lambda x: x[0], reverse=True)
        if candidate_sents:
            top_sents = candidate_sents[:3]
            answer_lines = [f"{sent} (Page {pg})" for _, pg, sent in top_sents]
            answer = "Based on the document:\n\n" + "\n\n".join(answer_lines)
        else:
            best_chunk, _ = relevant[0]
            answer = f"Relevant excerpt from Page {best_chunk['page_number']}:\n\n{best_chunk['text'][:500]}"

        return AIQueryResponse(
            document_id=doc["id"],
            action="ask",
            answer=answer,
            found_in_document=True,
            provider_used="local-rag",
            citations=citations,
        )


ai_service = AIService()
