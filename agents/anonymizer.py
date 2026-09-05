"""
Anonimização determinística de documentos das usuárias (MaterAI).

Remove identificadores pessoais do texto extraído de laudos, receitas e
documentos ANTES de qualquer envio a serviço externo de inferência.

Princípios de projeto:

1.  Determinística. Só regex e comparação com os dados do perfil. Nunca
    usar um LLM para anonimizar: seria circular — o texto teria de ser
    enviado justamente para decidir o que não enviar.

2.  Falha fechada. Uma segunda passagem verifica que o nome, o CPF e a
    data de nascimento do perfil não sobreviveram. Se sobreviveram,
    levanta AnonymizationError e o documento é marcado como
    `nao_processavel`. Nada é enviado.

3.  Preserva o dado clínico. Nomes de analitos, valores, unidades,
    faixas de referência e a data do exame permanecem intactos. Datas
    só são removidas quando coincidem com a data de nascimento.

4.  Erra para o lado da remoção. Um token do nome que também seja
    palavra comum será removido junto. Perder uma palavra do laudo é
    barato; deixar passar um identificador, não.

Uso:

    from anonymizer import Anonymizer, PatientContext

    ctx = PatientContext(
        nome_completo="Daiane Batista da Silva",
        data_nascimento=date(1995, 3, 14),
        cpf="123.456.789-09",
    )
    resultado = Anonymizer().anonimizar(texto_bruto, ctx)
    resultado.texto            # seguro para envio
    resultado.contagem         # {"PACIENTE": 3, "CPF": 1, ...}

Referência: seção 7.4 do documento de escopo e arquitetura.
RF-29, RF-30, RF-31 · RN-10, RN-11
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

__all__ = [
    "PatientContext",
    "AnonymizationResult",
    "AnonymizationError",
    "Anonymizer",
]


# --------------------------------------------------------------------------
# Erros e estruturas
# --------------------------------------------------------------------------


class AnonymizationError(RuntimeError):
    """A verificação encontrou identificador remanescente. Nada deve ser enviado."""

    def __init__(self, achados: list[str]) -> None:
        self.achados = achados
        super().__init__(
            "Anonimização incompleta; envio bloqueado. "
            f"Identificadores remanescentes: {', '.join(achados)}"
        )


@dataclass(frozen=True)
class PatientContext:
    """Dados do perfil usados para localizar identificadores no documento."""

    nome_completo: str
    data_nascimento: date | None = None
    cpf: str | None = None

    def tokens_do_nome(self) -> list[str]:
        """Tokens significativos do nome, sem conectivos."""
        conectivos = {"de", "da", "do", "das", "dos", "e", "del", "di", "van", "von"}
        tokens = [
            t
            for t in re.split(r"\s+", _sem_acento(self.nome_completo).lower())
            if len(t) >= 3 and t not in conectivos
        ]
        return tokens


@dataclass
class AnonymizationResult:
    """Texto anonimizado e relatório de auditoria (RF-30)."""

    texto: str
    contagem: dict[str, int] = field(default_factory=dict)

    @property
    def total_removido(self) -> int:
        return sum(self.contagem.values())

    def resumo(self) -> str:
        if not self.contagem:
            return "nenhum identificador encontrado"
        return ", ".join(f"{k}={v}" for k, v in sorted(self.contagem.items()))


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


# Mapa para casar letras independentemente de acentuação, sem precisar
# normalizar o texto original (o que destruiria a formatação do laudo).
_VARIANTES = {
    "a": "aáàâãäAÁÀÂÃÄ",
    "e": "eéèêëEÉÈÊË",
    "i": "iíìîïIÍÌÎÏ",
    "o": "oóòôõöOÓÒÔÕÖ",
    "u": "uúùûüUÚÙÛÜ",
    "c": "cçCÇ",
    "n": "nñNÑ",
}


def _padrao_insensivel(token: str) -> str:
    """Converte um token em regex que ignora caixa e acentuação."""
    partes = []
    for ch in _sem_acento(token).lower():
        if ch in _VARIANTES:
            partes.append(f"[{_VARIANTES[ch]}]")
        elif ch.isalnum():
            partes.append(f"[{ch}{ch.upper()}]")
        else:
            partes.append(re.escape(ch))
    return "".join(partes)


def _cpf_valido(digitos: str) -> bool:
    """Valida os dois dígitos verificadores do CPF."""
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(digitos[i]) * (tamanho + 1 - i) for i in range(tamanho))
        resto = (soma * 10) % 11
        esperado = 0 if resto == 10 else resto
        if esperado != int(digitos[tamanho]):
            return False
    return True


# --------------------------------------------------------------------------
# Anonimizador
# --------------------------------------------------------------------------


class Anonymizer:
    """Remove identificadores pessoais de texto extraído de documentos."""

    # Rótulos que precedem um identificador. O rótulo é preservado (ajuda o
    # modelo a entender a estrutura); o valor à direita é substituído.
    ROTULOS_ID = (
        r"rg|r\.g\.|identidade|cns|cart[aã]o\s+nacional\s+de\s+sa[uú]de|"
        r"requisi[cç][aã]o|protocolo|matr[ií]cula|prontu[aá]rio|registro|"
        r"pedido|guia|ficha|amostra|atendimento|os|ordem\s+de\s+servi[cç]o|"
        r"conv[eê]nio|carteirinha|benefici[aá]rio"
    )

    ROTULOS_NOME = (
        r"paciente|nome\s+do\s+paciente|nome\s+da\s+paciente|nome\s+completo|nome|"
        r"cliente|respons[aá]vel"
    )

    ROTULOS_ENDERECO = r"endere[cç]o|logradouro|rua|avenida|av\.|travessa|bairro|munic[ií]pio"

    def __init__(self, laboratorios: Iterable[str] = ()) -> None:
        """
        laboratorios: nomes conhecidos de laboratórios a remover, além do
        que for detectado por rótulo. Opcional.
        """
        self._laboratorios = [l for l in laboratorios if l.strip()]

    # -- API pública -------------------------------------------------------

    def anonimizar(self, texto: str, ctx: PatientContext) -> AnonymizationResult:
        """
        Remove identificadores e verifica o resultado.

        Levanta AnonymizationError se a verificação falhar. O chamador deve
        tratar isso como bloqueio de envio (RF-31), nunca como aviso.
        """
        contagem: dict[str, int] = {}
        t = texto

        # A ordem importa: campos rotulados primeiro, para não competirem
        # com padrões genéricos; o nome por último, porque é o mais amplo.
        t = self._remover_emails(t, contagem)
        t = self._remover_cpf(t, contagem, ctx)
        t = self._remover_campos_rotulados(t, contagem)
        t = self._remover_profissional(t, contagem)
        t = self._remover_endereco(t, contagem)
        t = self._remover_telefone(t, contagem)
        t = self._remover_cep(t, contagem)
        t = self._remover_data_nascimento(t, contagem, ctx)
        t = self._remover_laboratorio(t, contagem)
        t = self._remover_nome(t, contagem, ctx)

        self.verificar(t, ctx)  # falha fechada
        return AnonymizationResult(texto=t, contagem=contagem)

    def verificar(self, texto: str, ctx: PatientContext) -> None:
        """
        Segunda passagem independente da remoção (RF-31).

        Confere que nome, CPF e data de nascimento do perfil não aparecem
        mais. É deliberadamente simples: se dependesse da mesma lógica da
        remoção, herdaria os mesmos pontos cegos.
        """
        achados: list[str] = []
        plano = _sem_acento(texto).lower()

        for token in ctx.tokens_do_nome():
            if re.search(rf"\b{re.escape(token)}\b", plano):
                achados.append(f"token do nome ({len(token)} caracteres)")
                break

        if ctx.cpf:
            digitos = re.sub(r"\D", "", ctx.cpf)
            if digitos and digitos in re.sub(r"\D", "", texto):
                achados.append("CPF")

        if ctx.data_nascimento:
            for variante in self._variantes_de_data(ctx.data_nascimento):
                if variante in texto:
                    achados.append("data de nascimento")
                    break

        if achados:
            # Nunca inclua o texto ou o valor encontrado na exceção: ela
            # pode acabar em log, e o objetivo é justamente não vazar.
            raise AnonymizationError(achados)

    # -- Regras ------------------------------------------------------------

    def _sub(self, padrao: str, subst: str, texto: str, contagem: dict, chave: str,
             flags: int = re.IGNORECASE) -> str:
        novo, n = re.subn(padrao, subst, texto, flags=flags)
        if n:
            contagem[chave] = contagem.get(chave, 0) + n
        return novo

    def _remover_emails(self, t: str, c: dict) -> str:
        return self._sub(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b", "[CONTATO]", t, c, "CONTATO")

    def _remover_cpf(self, t: str, c: dict, ctx: PatientContext) -> str:
        def troca(m: re.Match) -> str:
            digitos = re.sub(r"\D", "", m.group(0))
            rotulado = bool(m.group("rotulo"))
            if _cpf_valido(digitos) or rotulado:
                c["CPF"] = c.get("CPF", 0) + 1
                return f"{m.group('rotulo') or ''}[CPF]"
            return m.group(0)

        padrao = r"(?P<rotulo>CPF\s*[:\-]?\s*)?\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}\b"
        t = re.sub(padrao, troca, t, flags=re.IGNORECASE)

        # CPF do perfil, ainda que grafado de forma inesperada.
        if ctx.cpf:
            d = re.sub(r"\D", "", ctx.cpf)
            if len(d) == 11:
                flexivel = r"\D?".join(d)
                t = self._sub(flexivel, "[CPF]", t, c, "CPF")
        return t

    def _remover_campos_rotulados(self, t: str, c: dict) -> str:
        # Ex.: "Requisição: 88213-4"  ->  "Requisição: [ID]"
        t = self._sub(
            rf"\b(?P<rot>{self.ROTULOS_ID})\b(?P<sep>\s*[:\-—]?\s*(?:n?[ºo°]?\.?\s*)?)"
            r"(?P<val>[A-Za-z0-9][A-Za-z0-9./\-]{3,})",
            lambda m: f"{m.group('rot')}{m.group('sep')}[ID]",  # type: ignore[arg-type]
            t,
            c,
            "ID",
        )
        # Ex.: "Paciente: Daiane Batista da Silva" -> rótulo preservado.
        t = self._sub(
            rf"\b(?P<rot>{self.ROTULOS_NOME})\b(?P<sep>\s*[:\-—]\s*)"
            r"(?P<val>[^\n\r]{2,80})",
            lambda m: f"{m.group('rot')}{m.group('sep')}[PACIENTE]",  # type: ignore[arg-type]
            t,
            c,
            "PACIENTE",
        )
        return t

    def _remover_profissional(self, t: str, c: dict) -> str:
        t = self._sub(
            r"\bCRM\s*[-/:]?\s*[A-Z]{0,2}\s*[-/:]?\s*\d{3,7}(?:\s*[-/]\s*[A-Z]{2})?",
            "[PROFISSIONAL]",
            t,
            c,
            "PROFISSIONAL",
        )
        # "Dr. Fulano de Tal", "Dra. Beltrana Souza", "Resp. Técnico: ..."
        t = self._sub(
            r"\b(?:Dr|Dra|Drª|Prof)\.?\s+(?:[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ]+(?:\s+(?:de|da|do|dos|das|e)\s+)?\s*){1,4}",
            "[PROFISSIONAL] ",
            t,
            c,
            "PROFISSIONAL",
            flags=0,  # sensível à caixa: nomes próprios começam em maiúscula
        )
        t = self._sub(
            r"\b(?:respons[aá]vel\s+t[eé]cnic[oa]|m[eé]dic[oa]\s+respons[aá]vel|"
            r"bioqu[ií]mic[oa]|patologista)\s*[:\-]?\s*[^\n\r]{2,60}",
            "[PROFISSIONAL]",
            t,
            c,
            "PROFISSIONAL",
        )
        return t

    def _remover_endereco(self, t: str, c: dict) -> str:
        return self._sub(
            rf"\b(?:{self.ROTULOS_ENDERECO})\b\s*[:\-]?\s*[^\n\r]{{3,90}}",
            "[CONTATO]",
            t,
            c,
            "CONTATO",
        )

    def _remover_telefone(self, t: str, c: dict) -> str:
        return self._sub(
            r"(?:(?:tel|fone|telefone|celular|whats\w*)\s*[:\-]?\s*)?"
            r"(?:\(\d{2}\)\s?|\b\d{2}\s)?9?\d{4}[-.\s]\d{4}\b",
            "[CONTATO]",
            t,
            c,
            "CONTATO",
        )

    def _remover_cep(self, t: str, c: dict) -> str:
        # Exige o hífen ou o rótulo, para não capturar valores numéricos do laudo.
        return self._sub(r"(?:CEP\s*[:\-]?\s*)?\b\d{5}-\d{3}\b", "[CONTATO]", t, c, "CONTATO")

    def _remover_data_nascimento(self, t: str, c: dict, ctx: PatientContext) -> str:
        if not ctx.data_nascimento:
            return t
        for variante in self._variantes_de_data(ctx.data_nascimento):
            t = self._sub(re.escape(variante), "[DATA_NASC]", t, c, "DATA_NASC")
        # Rótulos explícitos, mesmo com data diferente da do perfil.
        t = self._sub(
            r"\b(?:data\s+de\s+nascimento|nascimento|dt\.?\s*nasc\.?|nasc\.)\s*[:\-]?\s*"
            r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}",
            "Data de nascimento: [DATA_NASC]",
            t,
            c,
            "DATA_NASC",
        )
        return t

    def _remover_laboratorio(self, t: str, c: dict) -> str:
        for nome in self._laboratorios:
            t = self._sub(_padrao_insensivel(nome), "[LABORATORIO]", t, c, "LABORATORIO", flags=0)
        t = self._sub(
            r"\b(?:laborat[oó]rio|unidade\s+de\s+coleta|posto\s+de\s+coleta)\s*[:\-]?\s*[^\n\r]{2,60}",
            "[LABORATORIO]",
            t,
            c,
            "LABORATORIO",
        )
        return t

    def _remover_nome(self, t: str, c: dict, ctx: PatientContext) -> str:
        tokens = ctx.tokens_do_nome()
        if not tokens:
            return t

        # Primeiro sequências de dois ou mais tokens (nome completo ou parcial,
        # em qualquer ordem), depois tokens isolados.
        sequencia = r"(?:\s+(?:de|da|do|dos|das|e)\s+|\s+)".join(
            f"(?:{'|'.join(_padrao_insensivel(tk) for tk in tokens)})" for _ in range(2)
        )
        t = self._sub(rf"\b{sequencia}(?:(?:\s+(?:de|da|do|dos|das|e)\s+|\s+)"
                      rf"(?:{'|'.join(_padrao_insensivel(tk) for tk in tokens)}))*\b",
                      "[PACIENTE]", t, c, "PACIENTE", flags=0)

        for token in tokens:
            t = self._sub(rf"\b{_padrao_insensivel(token)}\b", "[PACIENTE]", t, c, "PACIENTE", flags=0)

        # Colapsa repetições adjacentes geradas pelas duas passagens.
        t = re.sub(r"(?:\[PACIENTE\]\s*){2,}", "[PACIENTE] ", t)
        return t

    @staticmethod
    def _variantes_de_data(d: date) -> list[str]:
        return [
            d.strftime("%d/%m/%Y"),
            d.strftime("%d-%m-%Y"),
            d.strftime("%d.%m.%Y"),
            d.strftime("%d/%m/%y"),
            f"{d.day}/{d.month}/{d.year}",
            d.strftime("%Y-%m-%d"),
        ]


# --------------------------------------------------------------------------
# Verificação rápida em linha de comando
# --------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    exemplo = """LABORATÓRIO CENTRAL DE ANÁLISES
Rua das Acácias, 120 - Vila Mariana - CEP 04101-000
Tel: (11) 3456-7890  contato@labcentral.com.br

Paciente: Daiane Batista da Silva
Data de nascimento: 14/03/1995      CPF: 123.456.789-09
Requisição nº 88213-4               Convênio: 5541209988
Data da coleta: 12/03/2026

HEMOGRAMA COMPLETO
Hemoglobina .................. 11,2 g/dL      (VR: 11,0 - 15,0)
Hematócrito .................. 34,1 %         (VR: 33,0 - 45,0)
Plaquetas .................... 212.000 /mm3   (VR: 150.000 - 450.000)

GLICEMIA DE JEJUM ............ 88 mg/dL       (VR: 70 - 92)

Responsável técnico: Dra. Helena Marques - CRM-SP 123456
Silva, Daiane B. - via impressa
"""
    ctx = PatientContext(
        nome_completo="Daiane Batista da Silva",
        data_nascimento=date(1995, 3, 14),
        cpf="123.456.789-09",
    )
    res = Anonymizer(laboratorios=["Laboratório Central de Análises"]).anonimizar(exemplo, ctx)
    print(res.texto)
    print("-" * 60)
    print("Removidos:", res.resumo())
