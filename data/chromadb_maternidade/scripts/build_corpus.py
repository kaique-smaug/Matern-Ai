from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import statistics
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

import fitz
import numpy as np
import pytesseract
from PIL import Image

DRIVE_FOLDER_ID = "1XC0yi-EGAio8XciBUr2ZaXVF2egWbPla"
DRIVE_FOLDER_NAME = "docs - train IA"

DRIVE_IDS = {
    "6_cronograma_de_solicitacao_de__exames.pdf": "1-sQWMTP2ZzJ7x_v4tIPxQbGDI6ArthKa",
    "qs_14_puerpera_ae_hospitalar_alta_omplex.pdf": "1k9qzE9aNJIc0dGz7uQBCMvm4rHoeNlck",
    "qs_13_puerpera_ae_hospitalar_media_complex.pdf": "1qiQtYjxZ111_eOtSTHTqBa0l6Z2lsc81",
    "qs_11_puerpera_ab.pdf": "1tDZeGxblrmRmo4ee6kdj5O127ppMjsIN",
    "qs_10_alto__risco_ae_hospitalar_alta_complex.pdf": "1XtOcG5klTDy0rLYT6PIL2EmYgrQBAGPA",
    "qs_9_alto_risco_ae_amb_alta_complex.pdf": "1EXKFJDFz6fRTMH4GDtTD26o4mZlRsZvF",
    "qs_7_alto_risco_ae__amb_media_comp.pdf": "1g8ti8d4XmNiNf__ciFgHbVzM7aLzIecW",
    "qs_6_alto_risco_ab.pdf": "1ConCG__HFAEJie1dF24DHCyw21Oqm4e8",
    "qs_5_baixo_risco_ae_hosp_media_complex.pdf": "1vmXmCZ6oD9dfUvOd0VKSkMic3sBXgm-V",
    "qs_4_baixo_risco_ae_amb_media_complex.pdf": "1EiBFyZ9huCMX-JH4grQijHRB0Y0tMkf5",
    "qs_3_baixo_risco_ab.pdf": "19_NGYPBk2n4vgYaiED7c-wltUCPrWZFU",
    "qs_2_diag_gest_e_class_de_risco_ab.pdf": "1t1h2Z9m1664NAuPQRKoMqpu1UPhhI-__",
    "15_gestacao_no_trabalho_direitos.pdf": "1LG94gmG9WSlfBEbqJT29d13Vc9OGt9cB",
    "12_cronograma_pre_natal_e_puerperio.pdf": "1_JsO2YkFltq3dcdKG9VIYEHpBDdrX4zm",
    "11_classificacao_de_risco_gestacional.pdf": "1lnsUEb3hQk5jNVT1Hl12S0qcWQJ_7ua6",
    "10_diagnostico_de_gravidez.pdf": "1yIihHqQO75WRTUqGk8wxTYYN0T4zzu0b",
    "cartao_da_gestante.pdf": "1w_jwdyuWpsdIl5Lg-L5sqCIDQKXibvZH",
    "5_calendario_vacinal.pdf": "10zybCaJWIlbIHJbwUxuWqjHCV8eg3ROC",
    "4_med_esenciais_pre_natal_ao_parto_e_puerperio.pdf": "1OaAvHiQTHD_rzYfZYk6NGx_7NKCLGiFH",
    "2_profissionais_e_formas_de_atendimento.pdf": "1bHm3Nps2x8sg-AHjcN5SD8YoZuBFmwiK",
    "1_planejamento_familiar.pdf": "1wUbv2UQRXvF2RnwdQ4VE4BOfYi6WzNll",
    "cartilha_de_orientacao_a_usuaria_do_sus.pdf": "1Pxl5XiOBkqnv5XitOpZAHaxTDtFzpW6h",
    "manual_tecnico_do_pre_natal_parto_e_puerperio.pdf": "1A14GXd-BhNw785qcBnzlCfxfXXtwPYqW",
    "publication.pdf": "1NvkKZurIayNaFdND2qZPiRZ8UxVErLRy",
    "teste_rapido_gravidez_guia_tecnico.pdf": "1Aghb34oDsexsFVYw1fDjbjf1YKiVvs__",
    "1980-5497-rbepid-20-s1-00046.pdf": "17X-PEogYp4sKa0BjC33IU-JD-OsZnTMq",
    "05.pdf": "1uPZ8opDbrhKjPuZmjkjG8E1eaNiI8c5h",
    "SBP-AssistRNSalaParto-eCOVID-18mai20.pdf": "1_xnbVBxHJl1pdUe70ph8GG9X0iHYyqe8",
    "03.pdf": "1JbFK3BMc6nllog_lrPrZPAMv5wNRODKs",
    "document.pdf": "1FSKl6pJGWSrkY5YCEzYECsUyZFRJmvkd",
    "0102-311X-csp-30-s1-0059.pdf": "1SLHIx2jsDXKPWLm82ETTFfLy9n7XV-p5",
    "a4784.pdf": "1m2nOteAxao3tWEnKZTqhRqXnXCAltiuU",
    "Consenso_Brasileiro_Manejo_DMG_2019.pdf": "1oLDIpk6iO2nIM2E1cVbyaJGFcNO-Ckw3",
    "prematuridade-e-seu-impacto-sobre-o-desenvolvimento-psicossocial-e-emocional-da-crianca.pdf": "191N6_RvDb3_OJyZvRP4M7iMLlWt9NoQ-",
    "miolo_pcdt_tv_08_2019.pdf": "1Y4F0zIw-QxQAeXax6dirHrAbek7wdIX8",
    "Cartilha-Pacientes-Resumida.pdf": "1x_07632lr78TXzGH-GCHciLS8aUZMwS2",
    "livro_cuidados_obstetricos.pdf": "1qIYk0ceADHLVrePNN9uFNFy7PWsd_GOV",
    "manual_assistencia_gestante_puerpera_covid-19_2ed.pdf": "1ZsJLWMCGUDKiGjAnnyeaPy0cNyDbFjaO",
    "srmpxcuidadoseorientacoesnagestacaopartopuerperioeemcriancasate2anosfinal2907221-220805154316-87635feb.pdf": "1nfTCuqQHXAvNhesPsFaD8OxPclre7DnB",
    "scardoso,+143192+portugues.pdf": "1R5lnAKghZbqCG6b1c9UF8EPJ0irVqE7c",
    "admin,+Gerente+da+revista,+13.pdf": "1fAjcwEuMcbF4Z6L2aZAnsTjExmXEA7H9",
    "nota_tecnica_3_2022.pdf": "1ZooH6WUeWoHVX8kuCf5pG1LbyLrGvFzk",
    "PROTOCOLO-2023-2.pdf": "1dVtVWkUlkee_m1sEqZG5WeXPxo0_oO7I",
    "Boletim_Care-IEPS-1-Saude-Materna-Mulher_Negra.pdf": "1ijV9AjlDC0Fg6Qu5Edtq878YUxiB_ieE",
    "testecoracaozinho-final.pdf": "1ShpIaFQfcsS317T5mUlpqLBO_KIxZf_D",
    "1806-9339-rbgo-41-05-0001 (1).pdf": "1gXniTCBtSMVRBKoiqpg-o-wcvV19CvRi",
    "1806-9339-rbgo-41-05-0001.pdf": "1zWPXMbqmzgSc7VVKZeTAfb3d1-gg22IT",
    "TIY_Guia_digital_v6-nov2025.pdf": "1qR9DaX7JChhXzzf2V2P9tVuoTGNdGn9U",
    "Nota Tecnica nº 2-2024.pdf": "13dwIBRJUNovUykvq717t-DmklBAkK7z0",
    "primeirissima_infancia.pdf": "1Hi4VFScplHzqHHWL2B3N3NCZsxyhpj6n",
    "rubeola-na-gestacao.pdf": "1KqsF7FLDMazj0YDDJDD4Yy66aoZ9-M_i",
    "Nota_Tecnica_6_Calcio_na_gestacao_13_8_2020.pdf": "1R-sv4j3o1TWFkYrAz0OgV3YBpUZ3vB1q",
    "gestacao_mulheres_doenca_falciforme.pdf": "1T6_CR_PiNGO7kjRPf6etStp8QvrUJl8b",
    "15657-Texto do artigo-67152-1-10-20170313 (1).pdf": "1DjsRsNT0I_w12Rl8DmQqO1k0VGvYMKIQ",
    "15657-Texto do artigo-67152-1-10-20170313.pdf": "1apcrnrdTS68hEj777P80gPqvvUeRuLk3",
    "321-1249.pdf": "1wuRHPPme-CktnB4VhTL9zqTFjZ1zp8vy",
    "Manual_dengue.pdf": "19xOaT986sf_Wk2QW0q-hL6Eqh6wOrFle",
    "linha_guia_mi-_gestacao_8a_ed_em_28.03.22.pdf": "1ENQ_-tcsbIN_UvBlW6kPC_qGkKbV2XXL",
    "nota-tecnica-conjunta-no-251-2024-coemm-cgesmu-dgci-saps-ms-e-cgan-deppros-saps-ms.pdf": "1X8lau_h3aqTPAFq2AhFAV3fcOxQ0ocGf",
    "Hipertensao-na-Gravidez.pdf": "17u149Vh5SZJ_i17KNCrp6-rBxIpEs2Be",
    "Plano_de_Parto_para_os_34_Dsei.pdf": "1tgjizi3UZNI0B4t_2LUWvEQcoIUokk1y",
    "O cuidado à mulher no contexto da maternidade caminhos .pdf": "1fCMoy-jXyYRU7XC2FwiG3RSZ9TCQh7fP",
    "Significados atribuídos por puérperas adolescentes à maternidade autocuidado e cuidado com o bebê.pdf": "1AM3CxnDCjuArLiJTE0I-UOsAq08_DbIR",
    "MATERNIDADE SEGURA RELATO DE EXPERIÊNCIA.pdf": "1-cA73dyu6tijw6_2ua5WLaz09YhUsGjp",
    "Mitos e tabus da maternidade.pdf": "1c3dCX0W2j23mtd7Kv0l0zYqaIknCOYK3",
    "PUERPÉRIO IMEDIATO.pdf": "1dyIthL9oqCopfJdK4_APcMO373Vgai4U",
    "APOIO SOCIAL E EXPERIÊNCIA DA MATERNIDADE+.pdf": "1KN07yIdAcGilTBQaN_of4Zl25eiGHfc_",
}


KNOWN_HEADINGS = {
    "RESUMO", "ABSTRACT", "RESUMEN", "INTRODUÇÃO", "INTRODUCAO", "OBJETIVO", "OBJETIVOS",
    "METODOLOGIA", "MÉTODOS", "METODOS", "MÉTODO", "METODO", "RESULTADOS", "DISCUSSÃO",
    "DISCUSSAO", "CONCLUSÃO", "CONCLUSÕES", "CONCLUSAO", "CONCLUSOES", "CONSIDERAÇÕES FINAIS",
    "CONSIDERACOES FINAIS", "REFERÊNCIAS", "REFERENCIAS", "ANEXO", "ANEXOS", "APÊNDICE", "APENDICE",
    "APRESENTAÇÃO", "APRESENTACAO", "PREFÁCIO", "PREFACIO", "SUMÁRIO", "SUMARIO", "GLOSSÁRIO",
    "GLOSSARIO", "RECOMENDAÇÕES", "RECOMENDACOES", "DEFINIÇÃO", "DEFINICAO", "DIAGNÓSTICO",
    "DIAGNOSTICO", "TRATAMENTO", "PREVENÇÃO", "PREVENCAO", "CONDUTA", "MANEJO", "JUSTIFICATIVA",
    "CONTEXTO", "CONSIDERAÇÕES", "CONSIDERACOES", "AGRADECIMENTOS", "LIMITAÇÕES", "LIMITACOES"
}

@dataclass
class Item:
    text: str
    page: int
    kind: str = "paragraph"
    level: int = 0
    font_size: float = 0.0
    extraction_method: str = "native"


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\x02", "").replace("\ufeff", "")
    text = re.sub(r"([\wÀ-ÿ])-\s*\n\s*([\wÀ-ÿ])", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def norm_key(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\d+", "#", t)
    t = re.sub(r"\W+", " ", t).strip()
    return t


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def uppercase_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 0.0


def infer_doc_type(filename: str, title: str) -> str:
    s = f"{filename} {title}".lower()
    if "nota tecnica" in s or "nota_técnica" in s or "nota_tecnica" in s:
        return "nota_tecnica"
    if "protocolo" in s or "pcdt" in s or "consenso" in s or "linha_guia" in s:
        return "protocolo_clinico"
    if "manual" in s or "guia" in s or "livro" in s:
        return "manual_guia"
    if "cartilha" in s or "cartao" in s or "cartão" in s:
        return "cartilha_formulario"
    if re.search(r"\b(artigo|revista|rbgo|csp|rbepid)\b", s) or re.search(r"\d{4}-\d{4}", s):
        return "artigo_cientifico"
    return "documento_tecnico"


def render_ocr(page: fitz.Page, dpi: int = 250) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    text = pytesseract.image_to_string(img, lang="por+eng", config="--psm 6")
    return clean_text(text)


def weighted_median_size(doc: fitz.Document) -> float:
    vals = []
    # Font statistics stabilize quickly; sampling avoids a full extra layout pass
    # over very long manuals before the actual extraction pass.
    n = len(doc)
    if n <= 40:
        indices = range(n)
    else:
        indices = sorted(set(int(i * (n - 1) / 39) for i in range(40)))
    for idx in indices:
        page = doc[idx]
        try:
            data = page.get_text("dict", sort=True)
        except Exception:
            continue
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "").strip()
                    if txt:
                        vals.extend([round(float(span.get("size", 0)), 1)] * min(len(txt), 80))
    return float(statistics.median(vals)) if vals else 10.0


def extract_lines(doc: fitz.Document, body_size: float) -> tuple[list[list[dict]], set[str], list[str]]:
    pages: list[list[dict]] = []
    edge_counts: Counter[str] = Counter()
    methods = []
    native_texts = [clean_text(page.get_text("text", sort=True) or "") for page in doc]
    # OCR is reserved for PDFs that are predominantly scanned/graphical, not merely
    # for isolated covers or blank pages inside otherwise text-rich documents.
    enable_ocr = sum(len(t) for t in native_texts) < max(500, len(doc) * 100)
    for page_no, page in enumerate(doc, 1):
        height = page.rect.height
        raw_text = native_texts[page_no - 1]
        method = "native"
        if enable_ocr and len(raw_text) < 80:
            ocr_text = render_ocr(page)
            if len(ocr_text) > len(raw_text) + 30:
                raw_text = ocr_text
                method = "ocr"
        methods.append(method)
        if method == "ocr":
            lines = []
            for txt in [x.strip() for x in raw_text.splitlines() if x.strip()]:
                lines.append({"text": txt, "y0": 0.0, "y1": 0.0, "size": body_size, "bold": False, "page": page_no, "method": method})
            pages.append(lines)
            continue
        data = page.get_text("dict", sort=True)
        lines = []
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = clean_text("".join(s.get("text", "") for s in spans))
                if not text:
                    continue
                sizes = [float(s.get("size", body_size)) for s in spans if s.get("text", "").strip()]
                size = max(sizes) if sizes else body_size
                chars = sum(len(s.get("text", "")) for s in spans) or 1
                bold_chars = sum(len(s.get("text", "")) for s in spans if re.search(r"bold|black|demi|heavy", s.get("font", ""), re.I))
                bbox = line.get("bbox", [0, 0, 0, 0])
                rec = {"text": text, "y0": float(bbox[1]), "y1": float(bbox[3]), "size": size,
                       "bold": bold_chars / chars > 0.45, "page": page_no, "method": method}
                lines.append(rec)
                if rec["y1"] < height * 0.10 or rec["y0"] > height * 0.90:
                    k = norm_key(text)
                    if k and len(k) > 3:
                        edge_counts[k] += 1
        pages.append(lines)
    threshold = max(3, math.ceil(len(doc) * 0.22))
    repeated = {k for k, n in edge_counts.items() if n >= threshold}
    return pages, repeated, methods


def looks_like_reference(text: str) -> bool:
    if re.search(r"(?:https?://|www\.|\bdoi\b|\bet al\.?\b|dispon[ií]vel em|acesso em)", text, re.I):
        return True
    if "@" in text:
        return True
    if re.match(r"^\d{1,3}[.)]\s+", text) and re.search(r"\b(?:19|20)\d{2}\b", text):
        return True
    if re.search(r"\b(?:19|20)\d{2};\d", text) or re.search(r"\d+\(\d+\):\d", text):
        return True
    return False


def titlecase_ratio(text: str) -> float:
    words = re.findall(r"[A-Za-zÀ-ÿ]+", text)
    if not words:
        return 0.0
    return sum(w[:1].isupper() for w in words) / len(words)

def is_heading(line: dict, body_size: float) -> bool:
    text = line["text"].strip()
    if not text or len(text) > 160 or word_count(text) > 20 or looks_like_reference(text):
        return False
    simple = re.sub(r"[\s:.;,-]+$", "", text).upper()
    if simple in KNOWN_HEADINGS:
        return True
    if re.match(r"^(CAP[IÍ]TULO|SE[CÇ][AÃ]O|PARTE|M[ÓO]DULO)\s+[\dIVXLCDM]+\b", text, re.I):
        return True
    m = re.match(r"^(\d+(?:\.\d+){0,4})[\s.)-]+(\S.*)", text)
    if m and not text.endswith("."):
        depth = m.group(1).count('.')
        first_num = int(m.group(1).split('.')[0])
        # Require typography for simple numbered items; hierarchical numbers are
        # stronger evidence of a genuine section.
        if depth >= 1 and word_count(text) <= 16:
            return True
        if first_num <= 25 and word_count(text) <= 12 and (line["bold"] or line["size"] >= body_size + 0.5):
            return True
    if line["size"] >= body_size + 1.6 and word_count(text) <= 18 and not text.endswith(('.', ';', ',')):
        return True
    if line["bold"] and line["size"] >= body_size - 0.1 and word_count(text) <= 10 and len(text) <= 90 and not text.endswith('.'):
        if not re.match(r"^\d", text) and (text[:1].isupper() or uppercase_ratio(text) > .5):
            return True
    if uppercase_ratio(text) >= 0.82 and 1 <= word_count(text) <= 14 and not text.endswith('.'):
        return True
    return False

def heading_level(line: dict, body_size: float, toc_levels: dict[str, int]) -> int:
    key = norm_key(line["text"])
    if key in toc_levels:
        return max(1, min(4, toc_levels[key]))
    m = re.match(r"^(\d+(?:\.\d+){0,4})[\s.)-]+", line["text"])
    if m:
        return min(4, m.group(1).count('.') + 1)
    simple = re.sub(r"[\s:.;,-]+$", "", line["text"]).upper()
    if simple in KNOWN_HEADINGS:
        return 1
    delta = line["size"] - body_size
    if delta >= 5:
        return 1
    if delta >= 2.5:
        return 2
    if delta >= 1.0:
        return 3
    return 2 if line["bold"] or uppercase_ratio(line["text"]) > .75 else 3


def infer_title(doc: fitz.Document, filename: str, pages: list[list[dict]], body_size: float) -> str:
    meta = (doc.metadata or {}).get("title", "").strip()
    invalid_meta = (
        not meta or len(meta) <= 4 or
        meta.lower() in {"untitled", "microsoft word", "brasil", "document", "publication"} or
        re.search(r"(?:\.indd|\.pmd|processo-|microsoft word|\.docx?$)", meta, re.I)
    )
    if not invalid_meta:
        return clean_text(meta)
    first = pages[0] if pages else []
    candidates = [x for x in first if 4 <= len(x["text"]) <= 180 and word_count(x["text"]) <= 24 and x["size"] >= body_size + 1]
    if candidates:
        max_size = max(x["size"] for x in candidates)
        top = [x for x in candidates if x["size"] >= max_size - 0.5]
        top.sort(key=lambda x: x["y0"])
        parts = []
        for x in top[:3]:
            if word_count(" ".join(parts + [x["text"]])) <= 30:
                parts.append(x["text"])
        if parts:
            return clean_text(" ".join(parts))
    candidates2 = []
    for page_lines in pages[:3]:
        for line in page_lines:
            t = line["text"].strip()
            if 4 <= len(t) <= 220 and word_count(t) <= 28 and line["size"] >= body_size + 1:
                candidates2.append((line["size"], len(t), t))
    if candidates2:
        candidates2.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidates2[0][2]
    stem = Path(filename).stem
    return re.sub(r"[_+]+", " ", stem).strip()

def make_items(doc: fitz.Document, filename: str) -> tuple[str, list[Item], dict]:
    body = weighted_median_size(doc)
    pages, repeated, page_methods = extract_lines(doc, body)
    title = infer_title(doc, filename, pages, body)
    toc = doc.get_toc(simple=True) or []
    toc_by_page: defaultdict[int, list[tuple[int, str]]] = defaultdict(list)
    toc_levels = {}
    for level, text, page in toc:
        text = clean_text(text)
        if text and page >= 1:
            toc_by_page[int(page)].append((int(level), text))
            toc_levels[norm_key(text)] = int(level)

    items: list[Item] = []
    last_heading_key = ""
    in_references = False
    appendix_names = {"ANEXO", "ANEXOS", "APÊNDICE", "APENDICE"}
    for page_no, lines in enumerate(pages, 1):
        # Add TOC boundary when the title is not visible in page text.
        line_keys = {norm_key(x["text"]) for x in lines}
        for level, text in toc_by_page.get(page_no, []):
            k = norm_key(text)
            if k and k not in line_keys and k != last_heading_key:
                items.append(Item(text=text, page=page_no, kind="heading", level=max(1, min(4, level)), font_size=body + 2, extraction_method=page_methods[page_no-1]))
                last_heading_key = k

        para_parts: list[str] = []
        para_method = page_methods[page_no-1]
        def flush_para():
            nonlocal para_parts
            text = clean_text(" ".join(para_parts))
            if text:
                items.append(Item(text=text, page=page_no, kind="paragraph", extraction_method=para_method))
            para_parts = []

        for line in lines:
            text = line["text"].strip()
            k = norm_key(text)
            if not text:
                continue
            if k in repeated:
                continue
            # Drop isolated page numbers.
            if re.fullmatch(r"\d{1,4}", text):
                continue
            simple_heading = re.sub(r"[\s:.;,-]+$", "", text).upper()
            heading_candidate = is_heading(line, body)
            if in_references and simple_heading not in appendix_names:
                heading_candidate = False
            if heading_candidate:
                flush_para()
                level = heading_level(line, body, toc_levels)
                if k != last_heading_key:
                    items.append(Item(text=text, page=page_no, kind="heading", level=level, font_size=line["size"], extraction_method=line["method"]))
                    last_heading_key = k
                    if simple_heading in {"REFERÊNCIAS", "REFERENCIAS", "BIBLIOGRAFIA", "REFERENCES"}:
                        in_references = True
                    elif simple_heading in appendix_names:
                        in_references = False
            else:
                # Keep bullets and short form labels as independent paragraphs.
                if re.match(r"^[•▪●◦\-*]\s+", text) or (len(text) < 80 and text.endswith(':')):
                    flush_para()
                    items.append(Item(text=text, page=page_no, kind="paragraph", extraction_method=line["method"]))
                else:
                    para_parts.append(text)
                    if text.endswith(('.', '?', '!', ':')) and len(" ".join(para_parts)) > 280:
                        flush_para()
        flush_para()

    details = {
        "body_font_size": body,
        "toc_entries": len(toc),
        "ocr_pages": [i + 1 for i, m in enumerate(page_methods) if m == "ocr"],
        "native_pages": sum(m == "native" for m in page_methods),
    }
    return title, items, details


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9])", text)
    return [p.strip() for p in parts if p.strip()]


def token_len(text: str) -> int:
    """Approximate token count without a model download.

    Uses the larger of lexical-unit count and UTF-8 byte count / 4, which is
    conservative for Portuguese technical prose.
    """
    lexical = len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))
    byte_estimate = math.ceil(len(text.encode("utf-8")) / 4)
    return max(lexical, byte_estimate)


def split_long_text(text: str, max_tokens: int) -> list[str]:
    if token_len(text) <= max_tokens:
        return [text]
    sentences = split_sentences(text)
    if len(sentences) <= 1:
        units = re.findall(r"\S+\s*", text)
        result, cur = [], []
        for unit in units:
            if cur and token_len("".join(cur) + unit) > max_tokens:
                result.append("".join(cur).strip())
                cur = [unit]
            else:
                cur.append(unit)
        if cur:
            result.append("".join(cur).strip())
        return [x for x in result if x]
    result, cur = [], []
    for sent in sentences:
        if cur and token_len(" ".join(cur + [sent])) > max_tokens:
            result.append(" ".join(cur).strip())
            cur = [sent]
        elif token_len(sent) > max_tokens:
            if cur:
                result.append(" ".join(cur).strip()); cur = []
            units = re.findall(r"\S+\s*", sent)
            temp = []
            for unit in units:
                if temp and token_len("".join(temp) + unit) > max_tokens:
                    result.append("".join(temp).strip())
                    temp = [unit]
                else:
                    temp.append(unit)
            if temp:
                result.append("".join(temp).strip())
        else:
            cur.append(sent)
    if cur:
        result.append(" ".join(cur).strip())
    return [x for x in result if x]


def slug(text: str, maxlen: int = 50) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip('-')
    return (t[:maxlen].strip('-') or "sem-secao")


def chunk_document(path: Path, max_tokens: int, overlap_tokens: int) -> tuple[list[dict], dict]:
    file_bytes = path.read_bytes()
    sha = hashlib.sha256(file_bytes).hexdigest()
    doc_id = sha[:16]
    with fitz.open(path) as doc:
        title, items, details = make_items(doc, path.name)
        metadata_pdf = doc.metadata or {}
        pages_count = len(doc)

    drive_id = DRIVE_IDS.get(path.name, "")
    drive_url = f"https://drive.google.com/file/d/{drive_id}/view" if drive_id else ""
    doc_type = infer_doc_type(path.name, title)

    sections: list[dict] = []
    stack: dict[int, str] = {}
    current = {"path": [title], "paras": [], "pages": [], "methods": []}

    def flush_section():
        nonlocal current
        if current["paras"]:
            sections.append(current)
        current = {"path": [title] + [stack[k] for k in sorted(stack)], "paras": [], "pages": [], "methods": []}

    for item in items:
        if item.kind == "heading":
            flush_section()
            for k in list(stack):
                if k >= item.level:
                    del stack[k]
            stack[item.level] = item.text
            current = {"path": [title] + [stack[k] for k in sorted(stack)], "paras": [], "pages": [], "methods": []}
        else:
            if len(item.text) >= 2:
                current["paras"].append(item.text)
                current["pages"].append(item.page)
                current["methods"].append(item.extraction_method)
    flush_section()

    chunks: list[dict] = []
    global_idx = 0
    excluded_section_terms = {"referencias", "references", "bibliografia", "sumario", "indice", "contents", "ficha catalografica"}
    excluded_sections = 0
    for sec_idx, sec in enumerate(sections):
        normalized_path = {norm_key(x) for x in sec["path"]}
        if any(any(term in part for term in excluded_section_terms) for part in normalized_path):
            excluded_sections += 1
            continue
        paragraphs: list[tuple[str, int, str]] = []
        for text, page, method in zip(sec["paras"], sec["pages"], sec["methods"]):
            for part in split_long_text(text, max_tokens):
                paragraphs.append((part, page, method))
        if not paragraphs:
            continue

        cur: list[tuple[str, int, str]] = []
        section_chunks = []
        for para in paragraphs:
            candidate = "\n\n".join([x[0] for x in cur] + [para[0]])
            if cur and token_len(candidate) > max_tokens:
                section_chunks.append(cur)
                # Paragraph-aware overlap.
                overlap = []
                total = 0
                for prev in reversed(cur):
                    pt = token_len(prev[0])
                    if overlap and total + pt > overlap_tokens:
                        break
                    overlap.insert(0, prev)
                    total += pt
                    if total >= overlap_tokens:
                        break
                cur = overlap + [para]
                while token_len("\n\n".join(x[0] for x in cur)) > max_tokens and len(cur) > 1:
                    cur.pop(0)
            else:
                cur.append(para)
        if cur:
            section_chunks.append(cur)

        for sec_chunk_idx, group in enumerate(section_chunks):
            raw_text = clean_text("\n\n".join(x[0] for x in group))
            if token_len(raw_text) < 25:
                continue
            path_parts = [p for p in sec["path"] if p]
            section_path = " > ".join(path_parts)
            section = path_parts[1] if len(path_parts) > 1 else title
            subsection = path_parts[-1] if len(path_parts) > 2 else ""
            context_header = f"Documento: {title}\nSeção: {section_path}\n\n"
            document_text = context_header + raw_text
            pages = [x[1] for x in group]
            methods = [x[2] for x in group]
            content_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            cid = f"{doc_id}-{slug(section_path)}-{sec_chunk_idx:04d}-{content_sha[:8]}"
            metadata = {
                "document_id": doc_id,
                "source_file": path.name,
                "source_drive_file_id": drive_id,
                "source_drive_url": drive_url,
                "source_drive_folder": DRIVE_FOLDER_NAME,
                "source_drive_folder_id": DRIVE_FOLDER_ID,
                "document_title": title,
                "document_type": doc_type,
                "author": clean_text(metadata_pdf.get("author", "") or ""),
                "page_start": min(pages),
                "page_end": max(pages),
                "section": section,
                "subsection": subsection,
                "section_path": section_path,
                "section_index": sec_idx,
                "section_chunk_index": sec_chunk_idx,
                "chunk_index": global_idx,
                "char_count": len(raw_text),
                "token_count": token_len(raw_text),
                "token_count_method": "approx_lexical_utf8",
                "extraction_method": "ocr" if "ocr" in methods else "native",
                "document_sha256": sha,
                "content_sha256": content_sha,
                "language": "pt-BR",
            }
            chunks.append({"id": cid, "text": raw_text, "document": document_text, "metadata": metadata})
            global_idx += 1

    report = {
        "source_file": path.name,
        "drive_file_id": drive_id,
        "document_id": doc_id,
        "document_title": title,
        "document_type": doc_type,
        "sha256": sha,
        "size_bytes": path.stat().st_size,
        "pages": pages_count,
        "sections_detected": len(sections),
        "chunks_generated": len(chunks),
        "excluded_sections": excluded_sections,
        **details,
    }
    return chunks, report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", default="/mnt/data")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--max-tokens", type=int, default=650)
    ap.add_argument("--overlap-tokens", type=int, default=80)
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("*.pdf"))
    by_hash: defaultdict[str, list[Path]] = defaultdict(list)
    for p in files:
        by_hash[hashlib.sha256(p.read_bytes()).hexdigest()].append(p)

    canonical = []
    duplicate_records = []
    for sha, group in by_hash.items():
        group = sorted(group, key=lambda p: (" (1)" in p.name, len(p.name), p.name))
        canonical.append(group[0])
        for dup in group[1:]:
            duplicate_records.append({
                "duplicate_file": dup.name,
                "canonical_file": group[0].name,
                "sha256": sha,
                "duplicate_drive_file_id": DRIVE_IDS.get(dup.name, ""),
                "canonical_drive_file_id": DRIVE_IDS.get(group[0].name, ""),
            })

    all_chunks, reports, errors = [], [], []
    ordered = sorted(canonical)
    with ProcessPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(chunk_document, path, args.max_tokens, args.overlap_tokens): path for path in ordered}
        done = 0
        for fut in as_completed(futures):
            path = futures[fut]
            done += 1
            try:
                chunks, report = fut.result()
                all_chunks.extend(chunks)
                reports.append(report)
                print(f"[{done}/{len(ordered)}] {path.name}: {report['pages']} páginas, {len(chunks)} chunks", flush=True)
            except Exception as exc:
                errors.append({"source_file": path.name, "error": repr(exc)})
                print(f"ERRO {path.name}: {exc!r}", flush=True)
    reports.sort(key=lambda x: x['source_file'])
    all_chunks.sort(key=lambda x: (x['metadata']['source_file'], x['metadata']['chunk_index']))

    with (output_dir / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for row in all_chunks:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output_dir / "processing_report.json").write_text(json.dumps({
        "configuration": {"chunking": "section_chapter_hybrid", "max_tokens": args.max_tokens, "overlap_tokens": args.overlap_tokens},
        "source_folder": {"name": DRIVE_FOLDER_NAME, "id": DRIVE_FOLDER_ID},
        "pdf_files_found": len(files),
        "unique_pdf_files": len(canonical),
        "duplicate_files_ignored": len(duplicate_records),
        "total_pages": sum(x["pages"] for x in reports),
        "total_chunks": len(all_chunks),
        "documents": reports,
        "duplicates": duplicate_records,
        "errors": errors,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "duplicates.json").write_text(json.dumps(duplicate_records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"TOTAL: {len(all_chunks)} chunks, {len(reports)} documentos, {len(errors)} erros")

if __name__ == "__main__":
    main()
