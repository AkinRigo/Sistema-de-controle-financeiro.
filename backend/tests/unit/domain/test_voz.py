from datetime import date

import pytest

from painel.domain.regras.voz import ContextoDeVoz, Opcao, montar_pedido, validar_resposta
from painel.domain.valores import Mes
from unit.domain.factories import dinheiro

HOJE = date(2026, 11, 26)
MES = Mes("2026-11")
LUZ = Opcao("c-luz", "Luz", dinheiro("180"))
ALUGUEL = Opcao("c-aluguel", "Aluguel", dinheiro("1300"))
CARTAO_NU = Opcao("c-cnu", "Cartão Nubank", dinheiro("2100"))
CARTAO_CX = Opcao("c-ccx", "Cartão Caixa", dinheiro("640"))
FREELA = Opcao("g-freela", "Freela do site", dinheiro("300"))
PAGA_NET = Opcao("p-net", "Internet", dinheiro("120"))
NUBANK = Opcao("b-nu", "Nubank", dinheiro("1900"))
CAIXA = Opcao("b-caixa", "Caixa", dinheiro("480"))
CTX = ContextoDeVoz(
    contas=(LUZ, ALUGUEL, CARTAO_NU, CARTAO_CX),
    ganhos=(FREELA,),
    bancos=(NUBANK, CAIXA),
    pagas=(PAGA_NET,),
)
SO_NUBANK = ContextoDeVoz(contas=(LUZ,), ganhos=(FREELA,), bancos=(NUBANK,))


def _v(acao, ctx=CTX, **campos):
    return validar_resposta({"acao": acao, **campos}, ctx, HOJE, MES)


# ---------- pagar / receber / desfazer ----------


def test_pagar_conta_com_valor_e_banco():
    p = _v("pagar_conta", item_id="c-luz", valor="175.50", banco_id="b-nu")
    assert p.acao == "pagar_conta" and p.item == LUZ and p.banco == NUBANK
    assert p.valor == dinheiro("175.50")


def test_sem_valor_usa_o_da_conta_e_sem_banco_fica_em_aberto():
    p = _v("pagar_conta", item_id="c-aluguel")
    assert p.valor == dinheiro("1300") and p.banco is None


def test_com_um_banco_so_ele_e_escolhido():
    assert _v("pagar_conta", SO_NUBANK, item_id="c-luz").banco == NUBANK


def test_receber_ganho_procura_nos_ganhos():
    p = _v("receber_ganho", item_id="g-freela", valor="300,00")
    assert p.acao == "receber_ganho" and p.item == FREELA and p.valor == dinheiro("300")


def test_fala_ambigua_traz_as_opcoes():
    p = _v("pagar_conta", opcoes_ids=["c-cnu", "c-ccx", "id-falso"])
    assert p.acao == "pagar_conta" and p.item is None and p.opcoes == (CARTAO_NU, CARTAO_CX)


def test_uma_opcao_so_vira_o_item():
    assert _v("pagar_conta", opcoes_ids=["c-cnu", "id-falso"]).item == CARTAO_NU


def test_desfazer_pagamento_procura_nas_pagas():
    p = _v("desfazer_pagamento", item_id="p-net")
    assert p.acao == "desfazer_pagamento" and p.item == PAGA_NET and p.valor == dinheiro("120")
    assert _v("desfazer_pagamento", opcoes_ids=["p-net", "c-luz"]).item == PAGA_NET


# ---------- a IA errando: o backend não pode aceitar ----------


@pytest.mark.parametrize(
    ("acao", "campos"),
    [
        ("nao_entendi", {}),
        ("apagar_tudo", {}),  # ação que não existe
        (None, {}),  # resposta vazia
        ("pagar_conta", {"item_id": "id-inventado"}),
        ("pagar_conta", {"item_id": "g-freela"}),  # id de ganho usado como conta
        ("receber_ganho", {"item_id": "c-luz"}),  # id de conta usado como ganho
        ("desfazer_pagamento", {"item_id": "c-luz"}),  # conta não paga
    ],
)
def test_resposta_estranha_vira_nao_entendi(acao, campos):
    p = _v(acao, **campos)
    assert p.acao == "nao_entendi" and p.mensagem and p.item is None


@pytest.mark.parametrize("valor", ["-50", "0", "abc"])
def test_valor_invalido_vira_nao_entendi(valor):
    p = _v("pagar_conta", item_id="c-luz", valor=valor)
    assert p.acao == "nao_entendi" and "valor" in p.mensagem


def test_banco_inventado_e_ignorado():
    assert _v("pagar_conta", item_id="c-luz", banco_id="b-falso").banco is None


# ---------- novo ganho ----------


def test_novo_ganho_completo():
    p = _v("novo_ganho", valor="500", nome="bico", data="2026-12-10")
    assert p.acao == "novo_ganho" and p.valor == dinheiro("500")
    assert p.nome == "Bico" and p.data == date(2026, 12, 10)


def test_novo_ganho_so_com_valor_entra_hoje_com_nome_padrao():
    p = _v("novo_ganho", valor="300")
    assert p.nome == "Entrada" and p.data == HOJE


@pytest.mark.parametrize("data", ["2020-01-01", "2030-01-01", "amanhã", None])
def test_novo_ganho_data_absurda_ou_invalida_vira_hoje(data):
    assert _v("novo_ganho", valor="300", data=data).data == HOJE


@pytest.mark.parametrize("valor", [None, "-5", "abc"])
def test_novo_ganho_sem_valor_pergunta_quanto(valor):
    p = _v("novo_ganho", valor=valor)
    assert p.acao == "nao_entendi" and "Quanto vai entrar" in p.mensagem


# ---------- nova conta ----------


def test_conta_fixa_que_ja_venceu_comeca_no_mes_seguinte():
    p = _v("nova_conta", nome="internet", valor="120", tipo_conta="fixa", dia=10)
    assert p.acao == "nova_conta" and p.nome == "Internet" and p.tipo_conta == "fixa"
    assert p.dia == 10 and p.mes_inicio == Mes("2026-12") and p.parcelas is None


def test_conta_que_ainda_vai_vencer_comeca_neste_mes():
    p = _v("nova_conta", nome="Gás", valor="90", tipo_conta="unica", dia=28)
    assert p.mes_inicio == MES


def test_conta_parcelada_comeca_neste_mes():
    p = _v("nova_conta", nome="geladeira", valor="300", tipo_conta="parcelada", parcelas=10, dia=5)
    assert p.tipo_conta == "parcelada" and p.parcelas == 10 and p.mes_inicio == MES


def test_conta_sem_tipo_nem_dia_e_unica_e_sem_vencimento():
    p = _v("nova_conta", nome="Mecânico", valor="400", tipo_conta="estranho", dia=99)
    assert p.tipo_conta == "unica" and p.dia == 0 and p.mes_inicio == MES


@pytest.mark.parametrize(
    ("campos", "trecho"),
    [
        ({"valor": "100"}, "nome da conta"),
        ({"nome": "Luz", "valor": "abc"}, "valor de Luz"),
        ({"nome": "TV", "valor": "100", "tipo_conta": "parcelada", "parcelas": 1}, "quantas vezes"),
        ({"nome": "TV", "valor": "100", "tipo_conta": "parcelada"}, "quantas vezes"),
    ],
)
def test_nova_conta_incompleta(campos, trecho):
    p = _v("nova_conta", **campos)
    assert p.acao == "nao_entendi" and trecho in p.mensagem


# ---------- bancos ----------


def test_novo_banco():
    p = _v("novo_banco", nome="inter", valor="500")
    assert p.acao == "novo_banco" and p.nome == "Inter" and p.valor == dinheiro("500")
    assert _v("novo_banco", nome="C6").valor == dinheiro("0")


@pytest.mark.parametrize(
    ("campos", "trecho"),
    [
        ({}, "nome do banco"),
        ({"nome": "nubank"}, "já tem"),
        ({"nome": "Inter", "valor": "-1"}, "saldo"),
    ],
)
def test_novo_banco_recusado(campos, trecho):
    p = _v("novo_banco", **campos)
    assert p.acao == "nao_entendi" and trecho in p.mensagem


def test_somar_no_banco_calcula_o_saldo_novo():
    p = _v("somar_banco", banco_id="b-nu", valor="200")
    assert p.acao == "somar_banco" and p.banco == NUBANK and p.saldo_novo == dinheiro("2100")


def test_ajustar_saldo_aceita_zero():
    p = _v("ajustar_saldo", banco_id="b-caixa", valor="0")
    assert p.acao == "ajustar_saldo" and p.saldo_novo == dinheiro("0")
    assert _v("ajustar_saldo", SO_NUBANK, valor="1500").banco == NUBANK  # banco único


@pytest.mark.parametrize(
    ("acao", "campos", "trecho"),
    [
        ("somar_banco", {"valor": "200"}, "Qual banco"),  # dois bancos, nenhum citado
        ("somar_banco", {"banco_id": "b-nu"}, "Qual o valor"),
        ("somar_banco", {"banco_id": "b-nu", "valor": "0"}, "Qual o valor"),
        ("ajustar_saldo", {"banco_id": "b-nu", "valor": "abc"}, "Qual o valor"),
    ],
)
def test_saldo_incompleto(acao, campos, trecho):
    p = _v(acao, **campos)
    assert p.acao == "nao_entendi" and trecho in p.mensagem


def test_transferir():
    p = _v("transferir", banco_id="b-nu", banco_destino_id="b-caixa", valor="300")
    assert p.acao == "transferir" and p.banco == NUBANK and p.banco_destino == CAIXA


@pytest.mark.parametrize(
    ("campos", "trecho"),
    [
        ({"banco_id": "b-nu", "valor": "300"}, "pra qual"),
        ({"banco_id": "b-nu", "banco_destino_id": "b-nu", "valor": "300"}, "pra qual"),
        ({"banco_id": "b-nu", "banco_destino_id": "b-caixa"}, "Quanto"),
    ],
)
def test_transferir_incompleto(campos, trecho):
    p = _v("transferir", **campos)
    assert p.acao == "nao_entendi" and trecho in p.mensagem


# ---------- consultas ----------


@pytest.mark.parametrize("acao", ["consultar_sobra", "consultar_falta", "consultar_banco"])
def test_consultas(acao):
    assert _v(acao).acao == acao


def test_consultar_banco_citado():
    assert _v("consultar_banco", banco_id="b-caixa").banco == CAIXA


# ---------- o pedido que vai para a IA ----------


def test_pedido_traz_a_frase_hoje_e_os_ids():
    pedido = montar_pedido("paguei a luz", CTX, HOJE)
    assert '"paguei a luz"' in pedido and "Hoje é 2026-11-26" in pedido
    for o in (LUZ, ALUGUEL, FREELA, NUBANK, CAIXA, PAGA_NET):
        assert f"id={o.id}" in pedido


def test_pedido_sem_nada_cadastrado():
    pedido = montar_pedido("oi", ContextoDeVoz((), (), ()), HOJE)
    assert pedido.count("(nenhum)") == 4
