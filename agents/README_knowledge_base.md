# MaterAI — módulo de base de conhecimento e privacidade

Quatro scripts que implementam as decisões das seções 7.4, 10.2, 10.3 e 19 do
documento de escopo e arquitetura.

| Arquivo | Papel | Depende de |
|---|---|---|
| `anonymizer.py` | Remove identificadores antes de qualquer envio externo | só a biblioteca padrão |
| `reindex_dense.py` | Reconstrói a coleção densa a partir do `chunks.jsonl` | chromadb, sentence-transformers |
| `retriever.py` | Busca híbrida denso + TF-IDF com fusão RRF e limiar | chromadb, sentence-transformers, scikit-learn |
| `calibrate_threshold.py` | Determina o limiar por evidência | retriever.py |

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

O `sentence-transformers` baixa o modelo (~280 MB) na primeira execução e o
guarda em cache. Depois disso funciona offline.

## Ordem de execução

```bash
# 1. Auditoria do corpus — resolve a divergência de contagem de chunks
python reindex_dense.py --auditar

# 2. Reindexação densa
python reindex_dense.py --force

# 3. Conjunto de avaliação (revise as perguntas antes de calibrar)
python calibrate_threshold.py --criar-exemplo

# 4. Calibração do limiar, com exportação para o artigo
python calibrate_threshold.py --csv resultados_limiar.csv

# 5. Consulta manual, para inspecionar o comportamento
python retriever.py "meu bebê não está mexendo hoje"
python retriever.py "posso comer sushi grávida" --sem-limiar
```

Depois do passo 4, atualize `LIMIAR_DENSO_PADRAO` em `retriever.py` com o valor
encontrado e registre a tabela na seção 19.3 do escopo.

## Anonimizador

```python
from datetime import date
from anonymizer import Anonymizer, AnonymizationError, PatientContext

ctx = PatientContext(
    nome_completo=usuaria.nome_completo,
    data_nascimento=usuaria.data_nascimento,
    cpf=usuaria.cpf,
)

try:
    resultado = Anonymizer().anonimizar(texto_extraido, ctx)
except AnonymizationError as exc:
    documento.status_processamento = "nao_processavel"
    logger.warning("anonimização bloqueou envio: %s", exc.achados)
    return                      # RF-31: nada é enviado

documento.identificadores_removidos = resultado.total_removido   # RF-30
resposta = llm.extrair_analitos(resultado.texto)                 # seguro
```

O `except` não é opcional. Sem ele, a exceção sobe e a tarefa em background
morre silenciosamente, deixando o documento preso em `processando`.

## Pontos que costumam dar errado

**Prefixos do E5.** Passagens indexadas com `passage: `, consultas com `query: `.
Omitir não gera erro — o modelo funciona e recupera pior, sem aviso. Os dois
scripts já fazem isso; a armadilha aparece se alguém escrever uma consulta nova
por fora.

**Distância x similaridade.** ChromaDB com `hnsw:space=cosine` devolve
*distância*. `retriever.py` converte com `1 - dist`. Comparar distância com o
limiar inverte a lógica inteira.

**Limiar não é transferível.** O 0,78 inicial vale para o E5. Não reaproveite
números observados no TF-IDF: as escalas são diferentes, e os cossenos do E5 se
concentram na faixa alta.

**Nunca use LLM para anonimizar.** Seria circular — o texto teria de ser enviado
para decidir o que não enviar.

## Testes

```bash
pip install pytest
python -m pytest test_anonymizer.py -q
```

17 casos, cobrindo preservação do dado clínico, remoção de identificadores,
falha fechada e o cuidado de a exceção não vazar o conteúdo. Ao encontrar um
formato de laudo que escape, acrescente um caso aqui antes de corrigir a regra.
