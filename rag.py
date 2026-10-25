"""LabSlot RAG pipeline.

1. Ingest every ``docs/*.txt`` file and chunk it into blank-line separated blocks.
2. Index chunks with TF-IDF (unigrams + bigrams) and retrieve by cosine similarity.
3. Ground answer generation with the Google GenAI SDK (``google-genai``).
   Without an API key (or if the call fails) LabSlot falls back to an offline
   extractive answer assembled from the retrieved chunks.

A deterministic pre-filter enforces the scope guardrails before any model call.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()

DOCS_DIR = Path(__file__).resolve().parent / "docs"

SYSTEM_PROMPT = """You are LabSlot, the Research Equipment Assistant.

You answer questions about research equipment (the microscope MIC-01, the 3D printer PRN-01
and the document scanner SCN-01), their training requirements, session limits, booking hours,
workspace rules, and how to report damaged or malfunctioning equipment.

STRICT RULES
1. Answer ONLY from the CONTEXT passages provided. Do not invent equipment, rules, times or limits.
2. If the context does not contain the answer, say you do not have that information in the LabSlot
   knowledge documents and suggest asking the laboratory supervisor.
3. Damaged or malfunctioning equipment must be reported to the laboratory supervisor. Never give
   repair advice; unauthorized repairs are not allowed.
4. You CANNOT check live availability or see who has booked equipment, and you CANNOT reserve,
   book, change or cancel slots. Politely decline such requests and explain that passing the
   LabSlot checks does not confirm availability.
5. Decline technical disassembly, repair, calibration or operating-procedure instructions. LabSlot
   checks administrative booking conditions only.
6. Be concise (at most four sentences). Cite the source file names you used in square brackets,
   for example [equipment_catalogue.txt].
"""

REFUSAL_LIVE = (
    "I cannot check live availability or tell you whether equipment is already booked. "
    "LabSlot only checks administrative booking conditions, and passing those checks does not "
    "confirm equipment availability. Please contact the laboratory supervisor for current availability."
)
REFUSAL_RESERVE = (
    "I cannot reserve or book equipment slots, or change and cancel bookings. "
    "LabSlot can only check whether a requested session meets the administrative booking rules "
    "(training, maximum duration and 9 AM-5 PM hours); passing them does not confirm availability."
)
REFUSAL_TECHNICAL = (
    "I cannot provide disassembly, repair, calibration or technical operating instructions. "
    "LabSlot checks administrative booking conditions only. Unauthorized repairs are not allowed: "
    "report damaged or malfunctioning equipment to the laboratory supervisor."
)

_DAY_WORDS = (
    r"today|tomorrow|tonight|now|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"this week|next week|this weekend|this morning|this afternoon|\d{1,2}(?::\d{2})?\s*(?:am|pm)"
)

_GUARDRAILS = [
    (
        "live_availability",
        REFUSAL_LIVE,
        [
            r"\b(already|currently|still)\b.{0,25}\b(booked|reserved|taken|occupied|in use|free|available)\b",
            rf"\b(is|are|was|will)\b.{{0,50}}\b(booked|reserved|taken|occupied|free|available)\b.{{0,40}}\b({_DAY_WORDS})\b",
            r"\bcheck\b.{0,20}\b(availability|calendar|schedule)\b",
            r"\b(what|which)\b.{0,20}\b(slots?|times?)\b.{0,20}\b(open|free|available)\b",
            r"\b(open|free|available) slots?\b",
        ],
    ),
    (
        "reservation",
        REFUSAL_RESERVE,
        [
            r"\b(can|could|would|will) you\b.{0,20}\b(reserve|book|schedule|cancel)\b",
            r"^\s*(please\s+)?(reserve|book|schedule|cancel)\b",
            r"\bbook me\b",
            r"\bmake (a |the )?(booking|reservation)\b",
            r"\bconfirm my (booking|reservation|slot)\b",
        ],
    ),
    (
        "technical_procedure",
        REFUSAL_TECHNICAL,
        [
            r"\bdisassembl\w*",
            r"\b(take|taking) (it |the \w+ )?apart\b",
            r"\bdismantl\w*",
            r"\bhow\b.{0,25}\b(repair|fix|calibrate|unjam|clear a jam|replace)\b",
            r"\b(operating|operation) (procedure|instructions?|steps)\b",
        ],
    ),
]


def check_scope(question):
    """Return (reason, refusal_text) when the question is out of scope, else None."""
    text = question.lower()
    for reason, refusal, patterns in _GUARDRAILS:
        if any(re.search(pattern, text) for pattern in patterns):
            return reason, refusal
    return None


def chunk_text(text, source, max_chars=400, overlap_lines=1):
    """Split a document into chunks: one per blank-line block, split further by line if long.

    Every chunk is prefixed with the document title so retrieval keeps context.
    """
    blocks = [
        [line.strip() for line in block.splitlines() if line.strip()]
        for block in re.split(r"\n\s*\n", text.strip())
    ]
    blocks = [b for b in blocks if b]
    if not blocks:
        return []
    title = blocks[0][0]
    if len(blocks[0]) == 1:
        blocks = blocks[1:]  # the title stands alone; it is prepended to every chunk

    chunks = []
    for lines in blocks:
        pieces, current, fresh = [], [], 0
        for line in lines:
            if current and fresh and sum(len(x) + 1 for x in current) + len(line) > max_chars:
                pieces.append(current)
                current = current[-overlap_lines:] if overlap_lines else []
                fresh = 0
            current.append(line)
            fresh += 1
        if current and fresh:
            pieces.append(current)
        for piece in pieces:
            chunks.append(
                {
                    "source": source,
                    "index": len(chunks),
                    "text": f"{title}\n" + "\n".join(piece),
                }
            )
    return chunks


def load_chunks(docs_dir=DOCS_DIR):
    chunks = []
    for path in sorted(Path(docs_dir).glob("*.txt")):
        for chunk in chunk_text(path.read_text(encoding="utf-8"), path.name):
            chunk["id"] = len(chunks)
            chunks.append(chunk)
    if not chunks:
        raise RuntimeError(f"No knowledge documents found in {docs_dir}")
    return chunks


class RAGEngine:
    def __init__(self, docs_dir=DOCS_DIR, top_k=3, min_score=0.08):
        self.top_k = top_k
        self.min_score = min_score
        self.chunks = load_chunks(docs_dir)
        self.vectorizer = TfidfVectorizer(
            lowercase=True, stop_words="english", ngram_range=(1, 2), sublinear_tf=True
        )
        self.matrix = self.vectorizer.fit_transform([c["text"] for c in self.chunks])
        self._client = None

    # ---------------------------------------------------------------- retrieval
    def retrieve(self, query):
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix).ravel()
        order = scores.argsort()[::-1][: self.top_k]
        return [
            {**self.chunks[i], "score": round(float(scores[i]), 4)}
            for i in order
            if scores[i] >= self.min_score
        ]

    # --------------------------------------------------------------- generation
    def _generate_with_gemini(self, question, hits):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None
        from google import genai  # imported lazily so offline use needs no SDK
        from google.genai import types

        if self._client is None:
            self._client = genai.Client(api_key=api_key)
        context = "\n\n".join(f"[{h['source']}]\n{h['text']}" for h in hits)
        response = self._client.models.generate_content(
            model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=f"CONTEXT:\n{context}\n\nQUESTION: {question}",
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.1),
        )
        return (response.text or "").strip() or None

    @staticmethod
    def _extractive_answer(hits):
        top = hits[0]["score"]
        selected = [h for h in hits if h["score"] >= 0.8 * top][:2]
        parts = []
        for hit in selected:
            body = hit["text"].split("\n", 1)[1]  # drop the repeated document title
            parts.append(body.replace("\n", ". ").replace("..", ".") + f" [{hit['source']}]")
        return "From the LabSlot knowledge documents: " + " ".join(parts)

    # ------------------------------------------------------------------- public
    def answer(self, question):
        question = (question or "").strip()
        if not question:
            return {"answer": "Please enter a question about LabSlot equipment or policies.",
                    "citations": [], "mode": "empty"}

        scope = check_scope(question)
        if scope:
            return {"answer": scope[1], "citations": [], "mode": f"guardrail:{scope[0]}"}

        hits = self.retrieve(question)
        if not hits:
            return {
                "answer": "I could not find that in the LabSlot knowledge documents. "
                          "Please ask the laboratory supervisor.",
                "citations": [],
                "mode": "no_context",
            }

        mode, text = "gemini", None
        try:
            text = self._generate_with_gemini(question, hits)
        except Exception as exc:  # network / quota / SDK problems must not break the UI
            mode = f"extractive (Gemini unavailable: {type(exc).__name__})"
        if text is None:
            text = self._extractive_answer(hits)
            if mode == "gemini":
                mode = "extractive"

        citations = [
            {"source": h["source"], "chunk": h["index"], "score": h["score"], "text": h["text"]}
            for h in hits
        ]
        return {"answer": text, "citations": citations, "mode": mode}


_engine = None


def get_engine():
    """Return the process-wide RAG engine, building the index on first use."""
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine


if __name__ == "__main__":
    engine = get_engine()
    print(f"LabSlot RAG index ready: {len(engine.chunks)} chunks from {DOCS_DIR}")
    for q in ["Which training module is required for the 3D printer?",
              "What should users do with malfunctioning equipment?",
              "Is MIC-01 already booked tomorrow?"]:
        print(f"\nQ: {q}\nA: {engine.answer(q)['answer']}")
