# Arquitetura do MaterAI RAG

## Objetivo

O sistema oferece apoio informacional a gestantes e mães, sem substituir atendimento médico. A solução segue o escopo do relatório de qualificação: Python, linguagem natural, API de LLM, LangChain e recuperação em ChromaDB.

## Fluxo

1. A pergunta passa por uma verificação determinística de sinais de urgência.
2. A consulta é enriquecida com a semana gestacional, quando informada.
3. O retriever busca chunks clínicos no ChromaDB.
4. O contexto é limitado e identificado como `Fonte N`.
5. O modelo gera resposta apenas com base nesses trechos.
6. A API devolve resposta, páginas, seção, documento e URL de origem.

## Separação das bases

- `chunks.jsonl`: conteúdo clínico e institucional usado no RAG.
- `literature_review.csv`: referências acadêmicas usadas para justificar e avaliar o projeto; não entram na orientação clínica.

## Segurança

- Bloqueio de diagnóstico e prescrição no prompt.
- Resposta emergencial independente do LLM para sinais críticos.
- Recusa fundamentada quando não há contexto suficiente.
- Fontes e páginas em todas as respostas recuperadas.
- Aviso de que o sistema não substitui avaliação profissional.
