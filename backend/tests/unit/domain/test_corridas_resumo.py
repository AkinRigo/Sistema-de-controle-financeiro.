"""Testes para estimativa de corridas e resumo mensal."""

from datetime import date

from painel.domain.entidades import Corridas, TipoConta
from painel.domain.regras.corridas import estimar_corridas
from painel.domain.regras.resumo import calcular_resumo
from painel.domain.valores import Mes
from unit.domain.factories import banco, conta, dinheiro, ganho, pagamento, usuario


def test_corridas_mes_passado_sao_zero() -> None:
    config = Corridas(dinheiro("70"), dinheiro("20"), True)

    assert estimar_corridas(config, Mes("2026-10"), date(2026, 11, 15)) == dinheiro("0")


def test_corridas_mes_atual_contam_apenas_dias_restantes_inclusive() -> None:
    config = Corridas(dinheiro("70"), dinheiro("20"), True)

    # 28, 29 e 30 de novembro: três dias, incluindo um sábado.
    assert estimar_corridas(config, Mes("2026-11"), date(2026, 11, 28)) == dinheiro("50")


def test_corridas_mes_futuro_consideram_todos_os_dias_e_sabados() -> None:
    config = Corridas(dinheiro("70"), dinheiro("20"), True)

    # Dezembro de 2026 tem 31 dias e quatro sábados.
    assert estimar_corridas(config, Mes("2026-12"), date(2026, 11, 25)) == dinheiro("390")


def test_corridas_desativadas_nao_entram_na_previsao() -> None:
    config = Corridas(dinheiro("70"), dinheiro("20"), False)

    assert estimar_corridas(config, Mes("2026-12"), date(2026, 11, 25)) == dinheiro("0")


def test_resumo_tem_sobra_positiva_e_considera_ganho_nao_recebido_anterior() -> None:
    fixa = conta(
        id="luz",
        nome="Luz",
        valor="100",
        tipo=TipoConta.FIXA,
        mes_inicio="2026-11",
    )
    compra_antiga = pagamento(
        id="pago-novembro-em-dezembro",
        conta_id="compra-novembro",
        mes_conta="2026-11",
        valor="30",
        data_pagamento=date(2026, 12, 3),
    )

    resumo = calcular_resumo(
        mes=Mes("2026-12"),
        usuario=usuario(desde="2026-11"),
        bancos=[banco(saldo="500")],
        contas=[fixa],
        pagamentos=[compra_antiga],
        ganhos=[
            ganho(id="antigo", valor="50", data=date(2026, 11, 20)),
            ganho(id="recebido", valor="20", data=date(2026, 12, 2), recebido=True),
            ganho(id="futuro", valor="80", data=date(2027, 1, 2)),
        ],
        hoje=date(2026, 12, 10),
        por_semana=dinheiro("0"),
        por_fim_de_semana=dinheiro("0"),
        contar_na_previsao=False,
    )

    assert resumo.tenho == dinheiro("500")
    assert resumo.vai_entrar == dinheiro("50")
    assert resumo.recebido == dinheiro("20")
    assert resumo.falta_pagar == dinheiro("200")
    assert resumo.ja_pago == dinheiro("30")
    assert [item.id for item in resumo.pagas] == ["pago-novembro-em-dezembro"]
    assert resumo.sobra == dinheiro("350")


def test_resumo_pode_ter_sobra_negativa() -> None:
    fixa = conta(
        id="aluguel",
        valor="20",
        tipo=TipoConta.FIXA,
        mes_inicio="2026-11",
    )

    resumo = calcular_resumo(
        mes=Mes("2026-11"),
        usuario=usuario(desde="2026-11"),
        bancos=[banco(saldo="10")],
        contas=[fixa],
        pagamentos=[],
        ganhos=[],
        hoje=date(2026, 11, 1),
        por_semana=dinheiro("0"),
        por_fim_de_semana=dinheiro("0"),
        contar_na_previsao=False,
    )

    assert resumo.falta_pagar == dinheiro("20")
    assert resumo.sobra == dinheiro("-10")


def test_resumo_soma_corridas_somente_quando_configuradas() -> None:
    args = {
        "mes": Mes("2026-12"),
        "usuario": usuario(),
        "bancos": [],
        "contas": [],
        "pagamentos": [],
        "ganhos": [],
        "hoje": date(2026, 11, 25),
        "por_semana": dinheiro("70"),
        "por_fim_de_semana": dinheiro("20"),
    }

    ligado = calcular_resumo(**args, contar_na_previsao=True)  # type: ignore[arg-type]
    desligado = calcular_resumo(**args, contar_na_previsao=False)  # type: ignore[arg-type]

    assert ligado.corridas == dinheiro("390")
    assert desligado.corridas == dinheiro("0")
