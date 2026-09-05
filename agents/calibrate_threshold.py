"""
Calibração do limiar de similaridade (MaterAI).

Executa o conjunto de avaliação contra o retriever com o limiar desligado,
registra a maior pontuação obtida por pergunta e varre valores candidatos,
mostrando o que cada um faria.

Critério de decisão, conforme a seção 19.3 do documento de escopo:

    escolha o MENOR limiar que rejeite ao menos 90% das perguntas
    fora do escopo, aceitando perder algumas respondíveis.

O viés é assimétrico de propósito. Limiar alto demais faz o agente dizer
"não tenho essa informação" quando poderia responder — a usuária fica sem
resposta e busca em outro lugar, que é o que já faria hoje. Limiar baixo
demais faz o agente responder sobre saúde materna com fundamentação
irrelevante, com a mesma fluência de uma resposta correta, e a usuária não
tem como distinguir. O primeiro erro é chato; o segundo é o motivo de
existir a seção 6 do documento.

Uso:

    python calibrate_threshold.py --criar-exemplo    # gera o conjunto inicial
    python calibrate_threshold.py                    # roda a calibração
    python calibrate_threshold.py --csv saida.csv    # exporta para o artigo
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_PADRAO = BASE_DIR / "eval_set.json"

TAXA_ALVO_REJEICAO = 0.90  # regra dos 90% da seção 19.3


# Conjunto inicial. Metade em linguagem técnica, metade coloquial — a
# auditoria mostrou que essa diferença é a que mais afeta a recuperação, e
# ignorá-la produziria uma calibração otimista demais.
EXEMPLO = {
    "respondiveis": [
        {"pergunta": "quais são os sinais de pré-eclâmpsia?", "registro": "tecnico"},
        {"pergunta": "quando realizar o teste oral de tolerância à glicose?", "registro": "tecnico"},
        {"pergunta": "qual o calendário vacinal recomendado na gestação?", "registro": "tecnico"},
        {"pergunta": "qual o cronograma de consultas de pré-natal?", "registro": "tecnico"},
        {"pergunta": "como é feita a classificação de risco gestacional?", "registro": "tecnico"},
        {"pergunta": "quais exames são solicitados no primeiro trimestre?", "registro": "tecnico"},
        {"pergunta": "o que caracteriza o diabetes mellitus gestacional?", "registro": "tecnico"},
        {"pergunta": "como se dá a prevenção da transmissão vertical do HIV?", "registro": "tecnico"},
        {"pergunta": "quais são os cuidados no puerpério imediato?", "registro": "tecnico"},
        {"pergunta": "como se calcula a idade gestacional?", "registro": "tecnico"},
        {"pergunta": "estou com muita dor de cabeça e enxergando pontinhos brilhantes", "registro": "coloquial"},
        {"pergunta": "meu bebê não está mexendo hoje, isso é normal?", "registro": "coloquial"},
        {"pergunta": "meu pé e minha mão incharam de repente, devo me preocupar?", "registro": "coloquial"},
        {"pergunta": "como sei que entrei em trabalho de parto?", "registro": "coloquial"},
        {"pergunta": "quantas vezes vou ter que ir ao médico durante a gravidez?", "registro": "coloquial"},
        {"pergunta": "que vacinas eu preciso tomar grávida?", "registro": "coloquial"},
        {"pergunta": "estou com muito enjoo, quando isso passa?", "registro": "coloquial"},
        {"pergunta": "a primeira semana com o bebê em casa, o que esperar?", "registro": "coloquial"},
        {"pergunta": "posso amamentar se estiver tomando remédio?", "registro": "coloquial"},
        {"pergunta": "que exame de sangue eu faço no começo da gravidez?", "registro": "coloquial"},
    ],
    "fora_do_escopo": [
        {"pergunta": "posso comer sushi grávida?", "registro": "coloquial"},
        {"pergunta": "posso pintar o cabelo na gravidez?", "registro": "coloquial"},
        {"pergunta": "grávida pode andar de avião?", "registro": "coloquial"},
        {"pergunta": "quanto de café posso tomar por dia?", "registro": "coloquial"},
        {"pergunta": "posso fazer academia pesada grávida?", "registro": "coloquial"},
        {"pergunta": "qual o melhor carrinho de bebê?", "registro": "coloquial"},
        {"pergunta": "como escolher o nome do bebê?", "registro": "coloquial"},
        {"pergunta": "quanto custa um parto particular?", "registro": "coloquial"},
        {"pergunta": "posso usar salto alto no oitavo mês?", "registro": "coloquial"},
        {"pergunta": "que série assistir durante a licença maternidade?", "registro": "coloquial"},
        {"pergunta": "qual a taxa de câmbio do dólar hoje?", "registro": "tecnico"},
        {"pergunta": "como configurar um servidor nginx com proxy reverso?", "registro": "tecnico"},
        {"pergunta": "quais os sintomas de infarto agudo do miocárdio em homens?", "registro": "tecnico"},
        {"pergunta": "qual o tratamento de fratura exposta de tíbia?", "registro": "tecnico"},
        {"pergunta": "como funciona a declaração de imposto de renda?", "registro": "tecnico"},
        {"pergunta": "qual o protocolo de quimioterapia para linfoma?", "registro": "tecnico"},
        {"pergunta": "quais raças de cachorro são hipoalergênicas?", "registro": "tecnico"},
        {"pergunta": "como calcular juros compostos?", "registro": "tecnico"},
        {"pergunta": "qual a dosagem de insulina para diabetes tipo 1 em adultos?", "registro": "tecnico"},
        {"pergunta": "como tratar acne severa com isotretinoína?", "registro": "tecnico"},
    ],
}


@dataclass
class Observacao:
    pergunta: str
    grupo: str
    registro: str
    melhor_denso: float
    melhor_lexical: float


def criar_exemplo(caminho: Path) -> None:
    if caminho.exists():
        raise SystemExit(f"{caminho} já existe; apague antes de recriar.")
    caminho.write_text(json.dumps(EXEMPLO, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Conjunto de avaliação criado em {caminho}")
    print("Revise e ajuste as perguntas antes de calibrar — o resultado depende delas.")


def coletar(caminho: Path) -> list[Observacao]:
    from retriever import RetrieverHibrido

    dados = json.loads(caminho.read_text(encoding="utf-8"))
    retriever = RetrieverHibrido()
    obs: list[Observacao] = []

    for grupo in ("respondiveis", "fora_do_escopo"):
        for item in dados[grupo]:
            r = retriever.buscar(item["pergunta"], aplicar_limiar=False)
            obs.append(
                Observacao(
                    pergunta=item["pergunta"],
                    grupo=grupo,
                    registro=item.get("registro", "?"),
                    melhor_denso=r.melhor_denso,
                    melhor_lexical=r.melhor_lexical,
                )
            )
            print(
                f"  {item['pergunta'][:52]:<54} denso={r.melhor_denso:.3f} "
                f"lexical={r.melhor_lexical:.3f}"
            )
    return obs


def varrer(obs: list[Observacao], limiar_lexical: float) -> list[dict]:
    """Para cada limiar candidato, calcula o que ele faria com o conjunto."""
    respondiveis = [o for o in obs if o.grupo == "respondiveis"]
    fora = [o for o in obs if o.grupo == "fora_do_escopo"]

    def rejeita(o: Observacao, limiar: float) -> bool:
        return o.melhor_denso < limiar and o.melhor_lexical < limiar_lexical

    linhas = []
    candidatos = [round(0.60 + i * 0.01, 2) for i in range(31)]  # 0,60 a 0,90
    for limiar in candidatos:
        rej_fora = sum(rejeita(o, limiar) for o in fora)
        rej_resp = sum(rejeita(o, limiar) for o in respondiveis)
        linhas.append({
            "limiar": limiar,
            "rejeicao_correta": rej_fora / len(fora) if fora else 0.0,
            "rejeicao_indevida": rej_resp / len(respondiveis) if respondiveis else 0.0,
            "fora_rejeitadas": rej_fora,
            "fora_total": len(fora),
            "resp_perdidas": rej_resp,
            "resp_total": len(respondiveis),
        })
    return linhas


def escolher(linhas: list[dict]) -> dict | None:
    """Menor limiar que atinge a taxa-alvo de rejeição das fora do escopo."""
    for linha in linhas:  # já em ordem crescente
        if linha["rejeicao_correta"] >= TAXA_ALVO_REJEICAO:
            return linha
    return None


def imprimir(linhas: list[dict], escolhido: dict | None) -> None:
    print()
    print("=" * 74)
    print("VARREDURA DE LIMIAR")
    print("=" * 74)
    print(f"{'limiar':>7} | {'rejeita fora do escopo':>24} | {'perde respondíveis':>22}")
    print("-" * 74)
    for linha in linhas:
        if round(linha["limiar"] * 100) % 5 != 0 and linha is not escolhido:
            continue  # imprime de 0,05 em 0,05 e o escolhido
        marca = "  <== escolhido" if linha is escolhido else ""
        print(
            f"{linha['limiar']:>7.2f} | "
            f"{linha['fora_rejeitadas']:>3}/{linha['fora_total']:<3} "
            f"({linha['rejeicao_correta']:>5.0%}){'':>9} | "
            f"{linha['resp_perdidas']:>3}/{linha['resp_total']:<3} "
            f"({linha['rejeicao_indevida']:>5.0%}){marca}"
        )
    print()
    if escolhido:
        print(f"Limiar recomendado: {escolhido['limiar']:.2f}")
        print(
            f"  Rejeita {escolhido['rejeicao_correta']:.0%} das perguntas fora do escopo "
            f"e perde {escolhido['rejeicao_indevida']:.0%} das respondíveis."
        )
        print("  Atualize LIMIAR_DENSO_PADRAO em retriever.py e a seção 19.3 do escopo.")
    else:
        print(
            f"Nenhum limiar até 0,90 atingiu {TAXA_ALVO_REJEICAO:.0%} de rejeição.\n"
            "  Isso indica que as pontuações dos dois grupos não se separam bem.\n"
            "  Investigue antes de subir o limiar: pode haver problema na indexação\n"
            "  (prefixos passage:/query: ausentes) ou perguntas 'fora do escopo'\n"
            "  que o corpus na verdade responde."
        )


def exportar(linhas: list[dict], obs: list[Observacao], caminho: Path) -> None:
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["limiar", "rejeicao_correta", "rejeicao_indevida"])
        for linha in linhas:
            w.writerow([linha["limiar"],
                        f"{linha['rejeicao_correta']:.4f}",
                        f"{linha['rejeicao_indevida']:.4f}"])
        w.writerow([])
        w.writerow(["pergunta", "grupo", "registro", "melhor_denso", "melhor_lexical"])
        for o in obs:
            w.writerow([o.pergunta, o.grupo, o.registro,
                        f"{o.melhor_denso:.4f}", f"{o.melhor_lexical:.4f}"])
    print(f"Tabela exportada para {caminho} — pronta para o artigo.")


def main() -> int:
    p = argparse.ArgumentParser(description="Calibração do limiar de similaridade.")
    p.add_argument("--conjunto", type=Path, default=ARQUIVO_PADRAO)
    p.add_argument("--criar-exemplo", action="store_true")
    p.add_argument("--limiar-lexical", type=float, default=0.35)
    p.add_argument("--csv", type=Path)
    args = p.parse_args()

    if args.criar_exemplo:
        criar_exemplo(args.conjunto)
        return 0

    if not args.conjunto.exists():
        raise SystemExit(
            f"{args.conjunto} não encontrado. Rode primeiro:\n"
            "  python calibrate_threshold.py --criar-exemplo"
        )

    print("Coletando pontuações (limiar desligado)...\n")
    obs = coletar(args.conjunto)
    linhas = varrer(obs, args.limiar_lexical)
    escolhido = escolher(linhas)
    imprimir(linhas, escolhido)

    if args.csv:
        exportar(linhas, obs, args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
