import { useCtx } from "../contexto";
import { NOME_CATEGORIA, dinheiro, nomeMes, num } from "../util";

export const dividaTotal = (cats: { ainda_devo: string }[]) => cats.reduce((s, c) => s + num(c.ainda_devo), 0);

export function Categorias() {
  const { dados, mes } = useCtx();
  const usadas = dados.categorias.filter(
    (r) => num(r.falta_pagar) || num(r.ja_pago) || num(r.ainda_devo) || num(r.fixas_por_mes),
  );
  const maior = Math.max(1, ...usadas.map((r) => num(r.falta_pagar) + num(r.ja_pago)));

  const itens = (chave: string) =>
    dados.contas.filter((c) => c.categoria_efetiva === chave).flatMap((c) => {
      const credor = c.credor && c.credor !== NOME_CATEGORIA[c.categoria_efetiva] ? " · " + c.credor : "";
      if (c.tipo === "fixa") {
        const ativa = c.mes_inicio <= mes && (!c.mes_fim || mes <= c.mes_fim);
        return ativa ? [{ id: c.id, rotulo: `${c.nome} · todo mês`, valor: c.valor }] : [];
      }
      if (!num(c.ainda_devo)) return [];
      const restam = num(c.valor) ? Math.round(num(c.ainda_devo) / num(c.valor)) : 0;
      const parcelas = c.tipo === "parcelada" ? ` · faltam ${restam} de ${c.total_parcelas} parcelas de ${dinheiro(c.valor)}` : "";
      return [{ id: c.id, rotulo: c.nome + credor + parcelas, valor: c.ainda_devo }];
    });

  return (
    <section className="card panel on">
      <h2>Por categoria</h2>
      <p className="hint">
        Quanto vai para cada lado. “Ainda devo” soma dívidas e parcelas futuras (contas fixas como aluguel não entram).
        Clique numa categoria para ver os itens. A barra mostra o mês: verde é o que já foi pago.
      </p>
      <div>
        {usadas.length ? (<>
          <div className="cat cat-h">
            <span>Categoria</span><span>Falta pagar em {nomeMes(mes)}</span><span>Já pago no mês</span>
            <span>Fixas por mês</span><span>Ainda devo (total)</span>
          </div>
          {usadas.map((r) => {
            const mesTotal = num(r.falta_pagar) + num(r.ja_pago);
            const lista = itens(r.chave);
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
                  <span data-l="Fixas/mês">{dinheiro(r.fixas_por_mes)}</span>
                  <span data-l="Ainda devo"><b>{dinheiro(r.ainda_devo)}</b></span>
                </summary>
                <ul>
                  {lista.length
                    ? lista.map((i) => <li key={i.id}><span>{i.rotulo}</span><b>{dinheiro(i.valor)}</b></li>)
                    : <li><span>Nada em aberto.</span></li>}
                </ul>
              </details>
            );
          })}
        </>) : <div className="empty">Nenhuma conta cadastrada.</div>}
      </div>
      <div className="total"><span>Dívida total (todas as categorias)</span><b>{dinheiro(dividaTotal(dados.categorias))}</b></div>
    </section>
  );
}
