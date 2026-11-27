"""Uma chamada só para a tela do mês (como o /painel de cada tela do LogysERP).

Antes a tela fazia 8 requisições (resumo, eu, contas, bancos, ganhos, rendas, corridas e
categorias), em duas rodadas, e cada uma ia ao banco de novo. Aqui os dados são lidos UMA vez
e tudo é montado em memória, com as mesmas funções das rotas separadas (o resultado é igual).
"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from painel.api.deps import HojeDep, SessaoDep, UsuarioDep
from painel.api.rotas.auth import _saida as _usuario_saida
from painel.api.rotas.cadastros import _banco_saida, _conta_saida, _ganho_saida, obter_corridas
from painel.api.rotas.relatorios import _categorias_saida, _Dados, _resumir, _resumo_saida
from painel.api.rotas.rendas import _saida as _renda_saida
from painel.api.rotas.rendas import garantir_rendas
from painel.api.schemas import (
    BancoSaida,
    CategoriaSaida,
    ContaSaida,
    CorridasSaida,
    GanhoDoMesSaida,
    MesTexto,
    RendaSaida,
    ResumoSaida,
    UsuarioSaida,
)
from painel.domain.regras.painel import ganhos_do_mes
from painel.domain.valores import Mes
from painel.infra import mapeamento
from painel.infra.modelos import (
    BancoModelo,
    ContaModelo,
    GanhoModelo,
    PagamentoModelo,
    RendaFixaModelo,
)

router = APIRouter(tags=["relatórios"])


class PainelSaida(BaseModel):
    usuario: UsuarioSaida
    resumo: ResumoSaida
    contas: list[ContaSaida]
    bancos: list[BancoSaida]
    ganhos: list[GanhoDoMesSaida]
    rendas: list[RendaSaida]
    corridas: CorridasSaida
    categorias: list[CategoriaSaida]


@router.get("/painel/{mes}", response_model=PainelSaida)
def painel_do_mes(
    mes: MesTexto, sessao: SessaoDep, usuario: UsuarioDep, hoje: HojeDep
) -> PainelSaida:
    garantir_rendas(sessao, usuario, Mes(mes))  # cria os ganhos das rendas fixas até este mês

    def todos(modelo):
        return list(sessao.scalars(select(modelo).where(modelo.usuario_id == usuario.id)))

    bancos, contas, pagamentos = todos(BancoModelo), todos(ContaModelo), todos(PagamentoModelo)
    ganhos, rendas = todos(GanhoModelo), todos(RendaFixaModelo)

    dados = _Dados(
        usuario=mapeamento.usuario(usuario),
        bancos=[mapeamento.banco(b) for b in bancos],
        contas=[mapeamento.conta(c) for c in contas],
        pagamentos=[mapeamento.pagamento(p) for p in pagamentos],
        ganhos=[mapeamento.ganho(g) for g in ganhos],
    )
    desde = Mes(usuario.desde)
    ganho_modelo = {g.id: g for g in ganhos}

    return PainelSaida(
        usuario=_usuario_saida(usuario),
        resumo=_resumo_saida(dados, _resumir(dados, usuario, mes, hoje), hoje),
        contas=[
            _conta_saida(mapeamento.conta(c), c.incerto, desde, dados.pagamentos)
            for c in sorted(contas, key=lambda c: c.nome)
        ],
        bancos=[_banco_saida(b) for b in sorted(bancos, key=lambda b: b.nome)],
        ganhos=[
            GanhoDoMesSaida(
                **_ganho_saida(ganho_modelo[x.ganho.id]).model_dump(), atrasado=x.atrasado
            )
            for x in ganhos_do_mes(dados.ganhos, Mes(mes))
        ],
        rendas=[_renda_saida(r) for r in sorted(rendas, key=lambda r: (r.dia, r.nome))],
        corridas=obter_corridas(usuario, hoje, mes),
        categorias=_categorias_saida(dados, mes),
    )
