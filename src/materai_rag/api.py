from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .config import Settings
from .models import AskRequest, AskResponse
from .rag import MaterAIRag

app = FastAPI(
    title="MaterAI RAG API",
    version="1.0.0",
    description="Assistente informacional fundamentado em documentos de saúde materna.",
)

_settings = Settings()
_rag: MaterAIRag | None = None


@app.on_event("startup")
def startup() -> None:
    global _rag
    try:
        _rag = MaterAIRag(_settings)
    except Exception:
        _rag = None


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok" if _rag else "not_ready",
        "collection": _settings.collection_name,
        "embedding_provider": _settings.embedding_provider,
    }


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    if _rag is None:
        raise HTTPException(status_code=503, detail="Coleção não construída. Execute a ingestão primeiro.")
    return _rag.ask(
        payload.question,
        gestational_week=payload.gestational_week,
        language=payload.language,
        top_k=payload.top_k,
    )
