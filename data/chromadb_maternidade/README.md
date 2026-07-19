# ChromaDB — corpus de maternidade

Pacote gerado a partir dos PDFs da pasta **docs - train IA** no Google Drive. Os documentos foram divididos prioritariamente pela hierarquia de capítulos, seções e subseções. Seções extensas foram quebradas em limites naturais de parágrafo, com tamanho máximo aproximado de 650 tokens e sobreposição contextual de até 80 tokens.

## Conteúdo do pacote

- `chroma_db/`: coleção ChromaDB persistida e pronta para consulta.
- `tfidf_vectorizer.joblib`: vetorizador local usado pela coleção.
- `chunks.jsonl`: todos os chunks, textos indexados e metadados.
- `query_chromadb.py`: consulta à coleção.
- `rebuild_chromadb.py`: recriação completa da coleção a partir do JSONL.
- `collection_manifest.json`: configuração e estatísticas da coleção.
- `metadata_schema.json`: descrição dos campos.
- `processing_report.json`: relatório por documento.
- `duplicates.json`: PDFs idênticos que foram removidos da indexação.
- `scripts/`: scripts de extração e pós-processamento usados na construção.

## Estatísticas

- 67 PDFs encontrados.
- 65 documentos únicos indexados.
- 2 duplicatas exatas ignoradas.
- 1.733 páginas processadas.
- 2.177 chunks na coleção `maternidade_docs`.
- 1.536 dimensões por embedding.
- Distância cosseno.

## Instalação

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

## Consultar a coleção

```bash
python query_chromadb.py "quais são os sinais de pré-eclâmpsia?" -n 5
```

Filtros opcionais:

```bash
python query_chromadb.py \
  "quando realizar o teste oral de tolerância à glicose?" \
  --document-type documento_tecnico \
  --language pt \
  -n 5
```

Retorno em JSON:

```bash
python query_chromadb.py "vacinas recomendadas na gestação" --json
```

## Uso em Python

```python
from pathlib import Path

import chromadb
import joblib
import numpy as np

base_dir = Path("chromadb_maternidade")
vectorizer = joblib.load(base_dir / "tfidf_vectorizer.joblib")
client = chromadb.PersistentClient(path=str(base_dir / "chroma_db"))
collection = client.get_collection("maternidade_docs")

pergunta = "quais são os sinais de pré-eclâmpsia?"
query_embedding = (
    vectorizer.transform([pergunta])
    .toarray()
    .astype(np.float32)
    .tolist()
)

resultado = collection.query(
    query_embeddings=query_embedding,
    n_results=5,
    include=["documents", "metadatas", "distances"],
)
```

## Formato do `chunks.jsonl`

Cada linha representa um chunk:

```json
{
  "id": "identificador-unico",
  "text": "texto bruto extraído",
  "document": "texto enriquecido usado na indexação",
  "metadata": {
    "document_title": "Título do documento",
    "source_file": "arquivo.pdf",
    "page_start": 10,
    "page_end": 11,
    "section": "Pré-natal",
    "subsection": "Exames",
    "section_path": "Pré-natal > Exames"
  }
}
```

## Embeddings incluídos

A coleção pronta utiliza TF-IDF híbrido de palavras e caracteres, executado totalmente offline. Isso permite abrir e consultar o pacote sem chave de API e sem baixar modelos externos. O backend é adequado para busca lexical em português e preserva a rastreabilidade do conteúdo.

Para usar embeddings semânticos de outro provedor, mantenha `chunks.jsonl` como fonte e substitua somente a etapa de vetorização no `rebuild_chromadb.py`.

## Observações de qualidade

- Sumários, índices, fichas catalográficas e seções bibliográficas foram excluídos quando detectados.
- PDFs binariamente idênticos foram indexados uma única vez.
- OCR foi aplicado apenas onde o texto nativo era insuficiente.
- `page_start` e `page_end` usam numeração humana iniciada em 1.
- A contagem de tokens é aproximada e independente de um tokenizer específico de LLM.
- Para respostas médicas, o sistema consumidor deve exibir a fonte e aplicar políticas de segurança clínica; o corpus não substitui avaliação profissional.
