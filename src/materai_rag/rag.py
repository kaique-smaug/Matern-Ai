from __future__ import annotations

from .config import Settings
from .models import AskResponse, Source
from .prompts import SYSTEM_PROMPT, USER_TEMPLATE
from .retrieval import ClinicalRetriever, RetrievedChunk
from .safety import assess_safety, emergency_message


class MaterAIRag:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.retriever = ClinicalRetriever(self.settings)

    @staticmethod
    def _source(chunk: RetrievedChunk) -> Source:
        metadata = chunk.metadata
        return Source(
            chunk_id=chunk.chunk_id,
            title=str(metadata.get("document_title", "Documento sem título")),
            source_file=str(metadata.get("source_file", "")),
            section_path=str(metadata.get("section_path", "")),
            page_start=int(metadata.get("page_start", 0) or 0),
            page_end=int(metadata.get("page_end", 0) or 0),
            url=str(metadata.get("source_drive_url", "")) or None,
            language=str(metadata.get("language", "")),
            relevance=round(chunk.relevance, 4),
        )

    def _format_context(self, chunks: list[RetrievedChunk]) -> str:
        parts: list[str] = []
        total = 0
        for index, chunk in enumerate(chunks, 1):
            m = chunk.metadata
            block = (
                f"[Fonte {index}]\n"
                f"Título: {m.get('document_title', '')}\n"
                f"Seção: {m.get('section_path', '')}\n"
                f"Páginas: {m.get('page_start', '')}-{m.get('page_end', '')}\n"
                f"Conteúdo:\n{chunk.document}\n"
            )
            if total + len(block) > self.settings.max_context_chars:
                break
            parts.append(block)
            total += len(block)
        return "\n---\n".join(parts)

    def ask(
        self,
        question: str,
        *,
        gestational_week: int | None = None,
        language: str | None = None,
        top_k: int | None = None,
    ) -> AskResponse:
        safety = assess_safety(question)
        if safety.emergency:
            return AskResponse(
                answer=emergency_message(),
                sources=[],
                emergency=True,
                grounded=False,
                metadata={"matched_signals": safety.matched_signals},
            )

        search_query = question
        if gestational_week:
            search_query += f" semana gestacional {gestational_week}"

        chunks = self.retriever.search(search_query, k=top_k, language=language)
        sources = [self._source(chunk) for chunk in chunks]
        if not chunks:
            return AskResponse(
                answer=(
                    "Não encontrei informação suficiente na base documental para responder com segurança. "
                    "Consulte sua equipe de pré-natal ou outro profissional de saúde."
                ),
                sources=[],
                grounded=False,
            )

        if not self.settings.openai_api_key:
            return AskResponse(
                answer=(
                    "A recuperação documental funcionou, mas a geração de resposta está desativada porque "
                    "OPENAI_API_KEY não foi configurada. Consulte os trechos e fontes retornados abaixo."
                ),
                sources=sources,
                grounded=True,
                metadata={"generation": "disabled"},
            )

        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=self.settings.openai_chat_model,
            api_key=self.settings.openai_api_key,
            temperature=0,
            max_retries=2,
        )
        user_prompt = USER_TEMPLATE.format(
            question=question,
            gestational_week=gestational_week or "não informada",
            context=self._format_context(chunks),
        )
        response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)])
        answer = response.content if isinstance(response.content, str) else str(response.content)
        return AskResponse(
            answer=answer,
            sources=sources,
            grounded=True,
            metadata={"model": self.settings.openai_chat_model, "retrieved_chunks": len(chunks)},
        )
