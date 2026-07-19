from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyAssessment:
    emergency: bool
    matched_signals: tuple[str, ...]


EMERGENCY_PATTERNS: dict[str, re.Pattern[str]] = {
    "sangramento_intenso": re.compile(r"sangramento (?:forte|intenso|em grande quantidade)", re.I),
    "convulsao": re.compile(r"convuls(?:ão|oes|ões)|desmai(?:o|ou)", re.I),
    "falta_de_ar": re.compile(r"falta de ar (?:intensa|forte)|não consigo respirar", re.I),
    "dor_peito": re.compile(r"dor (?:forte )?no peito", re.I),
    "dor_cabeca_visao": re.compile(r"dor de cabeça (?:forte|intensa).*(?:visão|vista)", re.I | re.S),
    "movimentos_reduzidos": re.compile(r"(?:bebê|bebe).*(?:não mexe|parou de mexer|movimentos? diminu)", re.I),
    "ideacao_suicida": re.compile(r"(?:quero|penso em) (?:morrer|me matar)|suic[ií]dio", re.I),
}


def assess_safety(text: str) -> SafetyAssessment:
    matches = tuple(name for name, pattern in EMERGENCY_PATTERNS.items() if pattern.search(text))
    return SafetyAssessment(emergency=bool(matches), matched_signals=matches)


def emergency_message() -> str:
    return (
        "Os sintomas descritos podem exigir avaliação imediata. Procure agora um serviço de urgência "
        "obstétrica ou ligue para o SAMU (192). Não espere uma resposta online para decidir buscar ajuda. "
        "Se houver risco imediato, permaneça acompanhada e não dirija sozinha."
    )
