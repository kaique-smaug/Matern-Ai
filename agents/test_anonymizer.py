"""Testes da camada de anonimização. Executar com: python -m pytest -q"""

from __future__ import annotations

from datetime import date

import pytest

from anonymizer import Anonymizer, AnonymizationError, PatientContext

CTX = PatientContext(
    nome_completo="Daiane Batista da Silva",
    data_nascimento=date(1995, 3, 14),
    cpf="123.456.789-09",
)
ANON = Anonymizer()


def anon(texto: str, ctx: PatientContext = CTX) -> str:
    return ANON.anonimizar(texto, ctx).texto


# -- preservação do dado clínico ------------------------------------------


def test_preserva_analitos_valores_e_faixas():
    t = anon("Hemoglobina 11,2 g/dL (VR: 11,0 - 15,0)")
    assert "Hemoglobina" in t and "11,2" in t and "g/dL" in t and "11,0 - 15,0" in t


def test_preserva_data_do_exame():
    t = anon("Data da coleta: 12/03/2026\nData de nascimento: 14/03/1995")
    assert "12/03/2026" in t
    assert "14/03/1995" not in t


def test_preserva_valores_de_seis_digitos():
    # 212.000 não pode ser confundido com CPF nem com CEP.
    t = anon("Plaquetas 212.000 /mm3")
    assert "212.000" in t


# -- remoção de identificadores -------------------------------------------


def test_remove_nome_com_acento_e_caixa_variada():
    t = anon("DAIANE BATISTA DA SILVA\ndaiane batista da silva")
    assert "aiane" not in t.lower()


def test_remove_nome_em_ordem_invertida():
    t = anon("Silva, Daiane Batista")
    assert "Daiane" not in t and "Silva" not in t


def test_remove_cpf_valido_sem_rotulo():
    t = anon("Documento 123.456.789-09 anexo")
    assert "123.456.789" not in t


def test_remove_cpf_sem_pontuacao():
    t = anon("CPF 12345678909")
    assert "12345678909" not in t


def test_nao_remove_numero_de_11_digitos_invalido_como_cpf():
    # Sem rótulo e sem dígito verificador válido, deve permanecer.
    t = anon("Código interno 11111111112 do equipamento")
    assert "11111111112" in t


def test_remove_crm_e_nome_do_medico():
    t = anon("Responsável: Dra. Helena Marques - CRM-SP 123456")
    assert "Helena" not in t and "123456" not in t


def test_remove_telefone_email_e_cep():
    t = anon("Tel (11) 3456-7890 - contato@lab.com.br - CEP 04101-000")
    assert "3456-7890" not in t and "@lab.com.br" not in t and "04101-000" not in t


def test_remove_requisicao_rotulada():
    t = anon("Requisição nº 88213-4")
    assert "88213" not in t


# -- falha fechada ---------------------------------------------------------


def test_verificacao_bloqueia_quando_nome_sobrevive():
    """
    A verificação é independente da remoção. Se um texto chegar à
    verificação ainda com o nome, deve levantar erro em vez de passar.
    """
    with pytest.raises(AnonymizationError):
        ANON.verificar("Paciente Daiane Batista da Silva", CTX)


def test_verificacao_bloqueia_quando_cpf_sobrevive():
    with pytest.raises(AnonymizationError):
        ANON.verificar("registro 123 456 789 09 arquivado", CTX)


def test_excecao_nao_vaza_o_conteudo():
    """A mensagem de erro pode ir para log; não pode conter o identificador."""
    try:
        ANON.verificar("Daiane Batista da Silva", CTX)
    except AnonymizationError as exc:
        assert "Daiane" not in str(exc)
        assert "Silva" not in str(exc)
    else:  # pragma: no cover
        pytest.fail("deveria ter levantado AnonymizationError")


# -- casos de borda --------------------------------------------------------

def test_nome_curto_e_composto():
    ctx = PatientContext(nome_completo="Ana Lu Sá", data_nascimento=None, cpf=None)
    t = anon("Paciente: Ana Lu Sá\nAna compareceu ao exame.", ctx)
    assert "Ana" not in t


def test_texto_sem_identificadores_passa_intacto():
    original = "Glicemia de jejum 88 mg/dL. Valor de referência 70 a 92 mg/dL."
    assert anon(original) == original


def test_relatorio_de_contagem():
    res = ANON.anonimizar("Paciente: Daiane Batista da Silva - CPF 123.456.789-09", CTX)
    assert res.contagem.get("CPF", 0) >= 1
    assert res.total_removido >= 2
