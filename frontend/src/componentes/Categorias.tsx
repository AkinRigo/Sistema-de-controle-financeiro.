// Totais e itens por categoria vêm prontos da API (GET /categorias/{mes}).
import { Fragment } from "react";
import type { ItemCategoria } from "../api";
import { useCtx } from "../contexto";
import { dinheiro, nomeMes, num } from "../util";
import { EditarConta, ExcluirConta, NovaConta, type Item } from "./Contas";
import { Secao } from "./Recolher";

function rotulo(i: ItemCategoria, nomeCategoria: string) {
  const credor = i.credor && i.credor !== nomeCategoria ? " · " + i.credor : "";
  if (i.tipo === "fixa") return `${i.nome}${credor} · todo mês`;
  if (i.tipo === "parcelada") {
    return `${i.nome}${credor} · faltam ${i.parcelas_restantes} de ${i.total_parcelas} parcelas de ${dinheiro(i.valor_parcela)}`;
  }
  return i.nome + credor;
}

export function Categorias() {
  const c = useCtx();
  const { dados, mes } = c;
  // só mostra categorias com algum valor
  const usadas = dados.categorias.filter(
    (r) => num(r.falta_pagar) || num(r.ja_pago),
  );
  const maior = Math.max(1, ...usadas.map((r) => num(r.falta_pagar) + num(r.ja_pago)));
  const totalPendente =
    usadas.reduce((total, r) => total + Math.round(num(r.falta_pagar) * 100), 0) / 100;
  const contaPorId = new Map(dados.contas.map((x) => [x.id, x]));

  return (
    <Secao id="categorias" titulo="Por categoria" resumo={`${dinheiro(totalPendente)} a pagar`}>
      <p className="hint">
        Valores da competência selecionada. Clique numa categoria para ver as contas e parcelas ainda não pagas.
        A barra mostra o que já foi pago e o que falta pagar no mês.
      </p>
      <div>
        {usadas.length ? (<>
          <div className="cat cat-h">
            <span>Categoria</span><span>Falta pagar em {nomeMes(mes)}</span><span>Já pago no mês</span>
          </div>
          {usadas.map((r) => {
            const mesTotal = num(r.falta_pagar) + num(r.ja_pago);
            return (
              <details className="cat-d" key={r.chave}>
                <summary className="cat">
                  <span className="cn">
                    {r.nome}
                    <i className="cbar">
                      <i style={{ width: `${Math.round((mesTotal / maior) * 100)}%` }}>
                        <i style={{ width: `${mesTotal ? Math.round((num(r.ja_pago) / mesTotal) * 100) : 0}%` }} />
                      </i>
                    </i>
                  </span>
                  <span data-l="Falta pagar" className={num(r.falta_pagar) ? "neg" : ""}>{dinheiro(r.falta_pagar)}</span>
                  <span data-l="Já pago">{dinheiro(r.ja_pago)}</span>
                </summary>
                <ul>
                  {r.itens.length
                    ? r.itens.map((i) => {
                        const conta = contaPorId.get(i.conta_id);
                        const ref: Item | null = conta
                          ? { conta, mes: i.mes_referencia, n: i.parcela_no_mes, atrasada: false }
                          : null;
                        return (
                          <Fragment key={i.conta_id}>
                            <li>
                              <span>{rotulo(i, r.nome)}</span>
                              <span className="acoes">
                                <b>{dinheiro(i.valor)}</b>
                                <button className="lnk" onClick={() => c.abrir("editarCat:" + i.conta_id)}>Editar</button>
                                <button className="lnk red" onClick={() => c.abrir("excluirCat:" + i.conta_id)}>Excluir</button>
                              </span>
                            </li>
                            {ref && c.aberto === "editarCat:" + i.conta_id && <li className="caixa"><EditarConta x={ref} /></li>}
                            {conta && c.aberto === "excluirCat:" + i.conta_id && <li className="caixa"><ExcluirConta conta={conta} /></li>}
                          </Fragment>
                        );
                      })
                    : <li><span>Nada em aberto.</span></li>}
                </ul>
              </details>
            );
          })}
        </>) : <div className="empty">Nenhuma conta cadastrada.</div>}
      </div>
      <div className="total"><span>Total em aberto nesta competência</span><b>{dinheiro(totalPendente)}</b></div>
      <div className="total"><span>Dívida total (todas as categorias)</span><b>{dinheiro(dados.resumo.divida_total)}</b></div>
      <NovaConta />
    </Secao>
  );
}
