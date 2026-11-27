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
FGTS = Opcao("g-fgts", "FGTS", dinheiro("1800"))
CELULAR = Opcao("k-cel", "Celular", dinheiro("260"))
CAD_ALUGUEL = Opcao("k-aluguel", "Aluguel", dinheiro("1300"))
CTX = ContextoDeVoz(
    contas=(LUZ, ALUGUEL, CARTAO_NU, CARTAO_CX),
    ganhos=(FREELA, FGTS),
    bancos=(NUBANK, CAIXA),
    pagas=(PAGA_NET,),
    cadastro=(CELULAR, CAD_ALUGUEL),
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


# ---------- editar ----------


def test_editar_conta_so_o_que_foi_pedido():
    p = _v("editar_conta", item_id="k-aluguel", valor="1400")
    assert p.acao == "editar_conta" and p.item == CAD_ALUGUEL and p.valor == dinheiro("1400")
    assert p.dia == 0 and p.nome == ""
    p = _v("editar_conta", item_id="k-cel", dia=5, nome="celular")  # mesmo nome: não renomeia
    assert p.dia == 5 and p.nome == "" and p.valor is None


def test_editar_ganho_data():
    p = _v("editar_ganho", item_id="g-fgts", data="2026-11-30")
    assert p.acao == "editar_ganho" and p.item == FGTS and p.data == date(2026, 11, 30)


@pytest.mark.parametrize(
    ("acao", "campos", "trecho"),
    [
        ("editar_conta", {"item_id": "k-cel"}, "O que você quer mudar em Celular"),
        ("editar_conta", {"item_id": "k-cel", "dia": 99}, "o dia"),
        ("editar_ganho", {"item_id": "g-fgts", "data": "2040-01-01"}, "a data"),
        ("editar_conta", {"item_id": "k-cel", "valor": "abc"}, "valor novo"),
        ("editar_conta", {"item_id": "c-luz", "valor": "10"}, "Não entendi"),  # só cadastradas
        ("editar_ganho", {"opcoes_ids": ["g-fgts", "g-freela"]}, "O que você quer mudar em isso"),
    ],
)
def test_editar_sem_mudanca_ou_invalido(acao, campos, trecho):
    p = _v(acao, **campos)
    assert p.acao == "nao_entendi" and trecho in p.mensagem


def test_editar_com_opcoes_guarda_a_mudanca():
    p = _v("editar_ganho", opcoes_ids=["g-fgts", "g-freela"], valor="100")
    assert p.opcoes == (FGTS, FREELA) and p.valor == dinheiro("100")


def test_editar_banco_renomeia():
    p = _v("editar_banco", banco_id="b-nu", nome="nu")
    assert p.acao == "editar_banco" and p.banco == NUBANK and p.nome == "Nu"


@pytest.mark.parametrize(
    ("campos", "trecho"),
    [
        ({"nome": "Nu"}, "Qual banco"),
        ({"banco_id": "b-nu"}, "nome novo"),
        ({"banco_id": "b-nu", "nome": "NUBANK"}, "nome novo"),
        ({"banco_id": "b-nu", "nome": "caixa"}, "já tem"),
    ],
)
def test_editar_banco_recusado(campos, trecho):
    p = _v("editar_banco", **campos)
    assert p.acao == "nao_entendi" and trecho in p.mensagem


# ---------- apagar ----------


def test_apagar_conta_traz_o_mes_de_parar():
    p = _v("apagar_conta", item_id="k-cel")
    assert p.acao == "apagar_conta" and p.item == CELULAR and p.parar_em == Mes("2026-12")
    assert _v("apagar_conta", item_id="c-luz").acao == "nao_entendi"


def test_apagar_ganhos_varios_e_um():
    p = _v("apagar_ganho", opcoes_ids=["g-freela", "g-fgts"])
    assert p.opcoes == (FREELA, FGTS) and p.mensagem == "Apagar estes ganhos?"
    assert _v("apagar_ganho", item_id="g-fgts").item == FGTS


def test_apagar_banco_so_o_citado():
    assert _v("apagar_banco", banco_id="b-caixa").banco == CAIXA
    p = _v("apagar_banco", SO_NUBANK)  # banco único não é apagado sem ser citado
    assert p.acao == "nao_entendi" and "Qual banco" in p.mensagem


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
    assert pedido.count("(nenhum)") == 5


def test_banco_no_campo_item_id_tambem_vale():
    assert _v("editar_banco", item_id="b-nu", nome="Nu").banco == NUBANK
    assert _v("apagar_banco", item_id="b-caixa").banco == CAIXA
    assert _v("apagar_banco", item_id="c-luz").acao == "nao_entendi"  # id de conta não é banco
