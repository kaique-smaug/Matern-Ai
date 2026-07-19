from __future__ import annotations

import argparse
import json

from .rag import MaterAIRag


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta o MaterAI RAG")
    parser.add_argument("question")
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument("--language", default=None)
    parser.add_argument("-k", "--top-k", type=int, default=None)
    args = parser.parse_args()

    response = MaterAIRag().ask(
        args.question,
        gestational_week=args.week,
        language=args.language,
        top_k=args.top_k,
    )
    print(json.dumps(response.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
