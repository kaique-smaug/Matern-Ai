# MaterAI RAG

Projeto RAG criado a partir dos **2.771 chunks** dos diretórios `docs - train IA` e `docs - train IA 2`, seguindo o escopo do relatório de qualificação **MaterAI** e a planilha de revisão de literatura.

## O que está incluído

- Base consolidada em `data/chunks.jsonl`.
- 2.771 chunks com documento, página, seção, idioma e URL do Drive.
- ChromaDB local.
- Busca offline TF-IDF ou embeddings semânticos OpenAI.
- Geração de respostas por `ChatOpenAI`/LangChain.
- API FastAPI e cliente CLI.
- Fontes rastreáveis em cada resposta.
- Verificação determinística de sinais de urgência.
- Base acadêmica separada em `data/literature_review.csv`.

## 1. Instalação

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate

pip install -e .
cp .env.example .env
```

No Windows, copie manualmente `.env.example` para `.env`.

## 2. Configuração

Edite `.env`:

```env
OPENAI_API_KEY=sua-chave
OPENAI_CHAT_MODEL=gpt-5-mini
EMBEDDING_PROVIDER=tfidf
```

O modo `tfidf` não usa API para vetorização. Para embeddings semânticos:

```env
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

## 3. Construção da coleção

Modo offline:

```bash
python -m materai_rag.ingest --provider tfidf
```

Modo semântico:

```bash
python -m materai_rag.ingest --provider openai
```

## 4. Consulta no terminal

```bash
materai "Quais exames são realizados no segundo trimestre?" --week 25 -k 6
```

Sem `OPENAI_API_KEY`, o sistema ainda recupera e devolve as fontes, mas não redige a resposta final.

## 5. API

```bash
uvicorn materai_rag.api:app --reload --port 8000
```

Consulta:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Quais são os sinais de pré-eclâmpsia?","gestational_week":30}'
```

Documentação interativa: `http://localhost:8000/docs`.

## Retorno

A API retorna:

- resposta textual;
- identificação de urgência;
- documento e arquivo de origem;
- seção e páginas;
- URL do Google Drive;
- relevância de cada chunk.

## Inclusão de novos documentos

Gere novos chunks no mesmo schema, acrescente-os a `data/chunks.jsonl` com IDs únicos e reconstrua a coleção:

```bash
python -m materai_rag.ingest --provider tfidf
```

Para embeddings OpenAI, execute o mesmo comando com `--provider openai`.

## Limites clínicos

O MaterAI é um sistema de apoio informacional. Não deve diagnosticar, interpretar exames individualmente, prescrever tratamentos ou substituir atendimento profissional. Em cenários de urgência, a regra determinística precede a recuperação e o modelo de linguagem.
