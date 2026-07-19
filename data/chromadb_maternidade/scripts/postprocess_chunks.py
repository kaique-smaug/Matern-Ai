from __future__ import annotations
import copy, hashlib, json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_corpus import split_long_text, token_len, slug

TITLE_OVERRIDES = {
    "0102-311X-csp-30-s1-0059.pdf": "Determinação da idade gestacional com base em informações do estudo Nascer no Brasil",
    "11_classificacao_de_risco_gestacional.pdf": "Classificação de risco gestacional",
    "12_cronograma_pre_natal_e_puerperio.pdf": "Cronograma de pré-natal e puerpério",
    "1_planejamento_familiar.pdf": "Planejamento familiar",
    "2_profissionais_e_formas_de_atendimento.pdf": "Profissionais e formas de atendimento",
    "1806-9339-rbgo-41-05-0001.pdf": "Pré-eclâmpsia/Eclâmpsia - Errata",
    "321-1249.pdf": "Suplementação de sulfato ferroso na gestação e anemia gestacional: revisão da literatura",
    "APOIO SOCIAL E EXPERIÊNCIA DA MATERNIDADE+.pdf": "Apoio social e experiência da maternidade",
    "Boletim_Care-IEPS-1-Saude-Materna-Mulher_Negra.pdf": "Boletim Cárè-IEPS nº 1/2022: Saúde materna da mulher negra",
    "Cartilha-Pacientes-Resumida.pdf": "Mola hidatiforme: aprendendo seus cuidados",
    "Consenso_Brasileiro_Manejo_DMG_2019.pdf": "Tratamento do diabetes mellitus gestacional no Brasil",
    "Hipertensao-na-Gravidez.pdf": "Hipertensão na gravidez",
    "Manual_dengue.pdf": "Manual de prevenção, diagnóstico e tratamento da dengue na gestação e no puerpério",
    "Mitos e tabus da maternidade.pdf": "Mitos e tabus da maternidade: um enfoque sobre o processo saúde-doença",
    "Nota Tecnica nº 2-2024.pdf": "Nota Técnica nº 2/2024: prevenção da gravidez na adolescência",
    "Nota_Tecnica_6_Calcio_na_gestacao_13_8_2020.pdf": "Nota Técnica nº 6/2020: cálcio na gestação",
    "O cuidado à mulher no contexto da maternidade caminhos .pdf": "O cuidado à mulher no contexto da maternidade: caminhos e desafios para a humanização",
    "PROTOCOLO-2023-2.pdf": "Pré-eclâmpsia - Protocolo 03/2023",
    "PUERPÉRIO IMEDIATO.pdf": "Puerpério imediato: desvendando o significado da maternidade",
    "SBP-AssistRNSalaParto-eCOVID-18mai20.pdf": "Assistência ao recém-nascido na sala de parto de mãe com COVID-19",
    "a4784.pdf": "Conceitos atuais sobre avaliação da maturidade pulmonar fetal",
    "admin,+Gerente+da+revista,+13.pdf": "Atendimento odontológico às gestantes: revisão da literatura",
    "cartao_da_gestante.pdf": "Cartão da Gestante do Ministério da Saúde - Brasil",
    "cartilha_de_orientacao_a_usuaria_do_sus.pdf": "Linha de cuidado à gestante, parturiente e puérpera no SUS/SP: cartilha de orientação à usuária",
    "linha_guia_mi-_gestacao_8a_ed_em_28.03.22.pdf": "Linha de cuidado materno-infantil do Paraná",
    "livro_cuidados_obstetricos.pdf": "Cuidados obstétricos em diabetes mellitus gestacional no Brasil",
    "manual_tecnico_do_pre_natal_parto_e_puerperio.pdf": "Pré-natal, parto e puerpério: manual técnico",
    "miolo_pcdt_tv_08_2019.pdf": "Protocolo clínico e diretrizes terapêuticas para prevenção da transmissão vertical de HIV, sífilis e hepatites virais",
    "nota-tecnica-conjunta-no-251-2024-coemm-cgesmu-dgci-saps-ms-e-cgan-deppros-saps-ms.pdf": "Nota Técnica Conjunta nº 251/2024 - Ministério da Saúde",
    "nota_tecnica_3_2022.pdf": "Nota Técnica nº 3/2022: atendimento odontológico de gestantes na Atenção Primária à Saúde",
    "publication.pdf": "Consenso de cuidado com a pele do recém-nascido",
    "rubeola-na-gestacao.pdf": "Rubéola na gestação - Protocolo FEBRASGO nº 96",
    "srmpxcuidadoseorientacoesnagestacaopartopuerperioeemcriancasate2anosfinal2907221-220805154316-87635feb.pdf": "Cuidados e orientações sobre monkeypox na gestação, parto, puerpério e em crianças até 2 anos",
    "testecoracaozinho-final.pdf": "Teste do coraçãozinho (oximetria de pulso) na triagem neonatal",
}

EXCLUDE_TERMS = ("referencias", "references", "bibliografia", "sumario", "indice", "ficha catalografica")


def normalized(s: str) -> str:
    import re, unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\W+", " ", s).strip()


def apply_title(row: dict) -> dict:
    r = copy.deepcopy(row)
    m = r["metadata"]
    new = TITLE_OVERRIDES.get(m["source_file"])
    if not new:
        return r
    old = m["document_title"]
    m["document_title"] = new
    parts = m["section_path"].split(" > ")
    if parts:
        parts[0] = new
    m["section_path"] = " > ".join(parts)
    if m.get("section") == old:
        m["section"] = new
    if m.get("subsection") == old:
        m["subsection"] = new
    r["document"] = f"Documento: {new}\nSeção: {m['section_path']}\n\n{r['text']}"
    return r


def refresh(row: dict, index: int) -> dict:
    r = copy.deepcopy(row)
    m = r["metadata"]
    text = r["text"].strip()
    content_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    m["chunk_index"] = index
    m["section_chunk_index"] = index
    m["char_count"] = len(text)
    m["token_count"] = token_len(text)
    m["content_sha256"] = content_sha
    r["id"] = f"{m['document_id']}-{slug(m['section_path'])}-{index:04d}-{content_sha[:8]}"
    r["document"] = f"Documento: {m['document_title']}\nSeção: {m['section_path']}\n\n{text}"
    return r


def merge_pair(a: dict, b: dict) -> dict:
    r = copy.deepcopy(a)
    ma, mb = r["metadata"], b["metadata"]
    r["text"] = (a["text"].rstrip() + "\n\n" + b["text"].lstrip()).strip()
    paths = []
    for p in (ma.get("section_path", ""), mb.get("section_path", "")):
        if p and p not in paths:
            paths.append(p)
    ma["section_path"] = " | ".join(paths)[:1800]
    sections = []
    for p in (ma.get("section", ""), mb.get("section", "")):
        if p and p not in sections:
            sections.append(p)
    ma["section"] = " | ".join(sections)[:800]
    subsections = []
    for p in (ma.get("subsection", ""), mb.get("subsection", "")):
        if p and p not in subsections:
            subsections.append(p)
    ma["subsection"] = " | ".join(subsections)[:800]
    ma["page_start"] = min(ma["page_start"], mb["page_start"])
    ma["page_end"] = max(ma["page_end"], mb["page_end"])
    ma["extraction_method"] = "ocr" if "ocr" in {ma.get("extraction_method"), mb.get("extraction_method")} else "native"
    return r


def postprocess(rows: list[dict], max_tokens: int = 650, min_tokens: int = 80) -> list[dict]:
    prepared = []
    for row in rows:
        row = apply_title(row)
        path_norm = normalized(row["metadata"].get("section_path", ""))
        if any(term in path_norm for term in EXCLUDE_TERMS):
            continue
        parts = split_long_text(row["text"], max_tokens)
        for part in parts:
            nr = copy.deepcopy(row)
            nr["text"] = part
            prepared.append(nr)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in prepared:
        grouped[r["metadata"]["source_file"]].append(r)

    final = []
    for source in sorted(grouped):
        group = sorted(grouped[source], key=lambda x: (x["metadata"]["chunk_index"], x["metadata"]["page_start"]))
        merged = []
        for r in group:
            if merged and token_len(r["text"]) < min_tokens and token_len(merged[-1]["text"] + "\n\n" + r["text"]) <= max_tokens:
                merged[-1] = merge_pair(merged[-1], r)
            else:
                merged.append(r)
        # Merge a leading/surviving small chunk forward when possible.
        out = []
        i = 0
        while i < len(merged):
            r = merged[i]
            if token_len(r["text"]) < min_tokens and i + 1 < len(merged):
                nxt = merged[i + 1]
                if token_len(r["text"] + "\n\n" + nxt["text"]) <= max_tokens:
                    out.append(merge_pair(r, nxt))
                    i += 2
                    continue
            out.append(r)
            i += 1
        for idx, r in enumerate(out):
            final.append(refresh(r, idx))
    return final


def main():
    base = Path('/mnt/data/chromadb_maternidade_work/output')
    rows = [json.loads(x) for x in (base/'chunks.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    final = postprocess(rows)
    with (base/'chunks.jsonl').open('w',encoding='utf-8') as f:
        for r in final:
            f.write(json.dumps(r,ensure_ascii=False)+'\n')
    report=json.loads((base/'processing_report.json').read_text(encoding='utf-8'))
    counts=defaultdict(int)
    for r in final: counts[r['metadata']['source_file']]+=1
    for d in report['documents']:
        if d['source_file'] in TITLE_OVERRIDES:
            d['document_title']=TITLE_OVERRIDES[d['source_file']]
        d['chunks_generated']=counts[d['source_file']]
    report['total_chunks']=len(final)
    report['configuration']['min_tokens_after_merge']=80
    report['configuration']['token_count_method']='approx_lexical_utf8'
    report['title_overrides_applied']=len(TITLE_OVERRIDES)
    (base/'processing_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('final chunks',len(final))

if __name__=='__main__':
    main()
