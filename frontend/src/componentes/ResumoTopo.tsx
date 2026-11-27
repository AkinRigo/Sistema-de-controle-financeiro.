// Resumo do topo: três cards (tenho + vai entrar − falta pagar) e a faixa do resultado.
// Os ícones não têm formulário próprio: levam para a aba e abrem a caixinha que já existe lá.
import type { ReactNode } from "react";
import { api } from "../api";
import { useCtx } from "../contexto";
import { dataCurta, dinheiro } from "../util";
import { itensDoMes } from "./Contas";
import { Seta, useRecolhido } from "./Recolher";

export type Vista = "bills" | "incomes" | "accounts";
type IrPara = (vista: Vista, chave?: string) => void;

const Lapis = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 20h4L19 9l-4-4L4 16z" /></svg>
);
const Lixeira = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>
);

function Card({ id, titulo, total, sinal, rotuloNovo, novo, vazio, children }: {
  id: string; titulo: string; total: string; sinal?: "mais" | "menos"; rotuloNovo: string; novo: () => void;
  vazio: string; children: ReactNode[];
}) {
  const [fechado, alternar] = useRecolhido(id);
  return (
    <section className={`bloco ${sinal ?? ""}${fechado ? " fechado" : ""}`}>
      <div className="bloco-cab">
        <div><h2>{titulo}</h2><span className="bloco-tot">{total}</span></div>
        <span className="bloco-acoes">
          <button className="bloco-novo" onClick={novo} aria-label={rotuloNovo} title={rotuloNovo}>+</button>
          <Seta aberto={!fechado} alternar={alternar} nome={titulo} />
        </span>
      </div>
      {!fechado && (children.length ? <ul className="bloco-lista">{children}</ul> : <p className="bloco-vazio">{vazio}</p>)}
    </section>
  );
}

function Item({ nome, detalhe, alerta, valor, editar, excluir }: {
  nome: string; detalhe?: string; alerta?: boolean; valor: string; editar: () => void; excluir: () => void;
}) {
  return (
    <li>
      <span className="nm">{nome}{detalhe && <small className={alerta ? "atr" : ""}>{detalhe}</small>}</span>
      <span className="v">{valor}</span>
      <span className="ico">
        <button onClick={editar} aria-label={`Editar ${nome}`} title="Editar"><Lapis /></button>
        <button className="del" onClick={excluir} aria-label={`Excluir ${nome}`} title="Excluir"><Lixeira /></button>
      </span>
    </li>
  );
}

export function ResumoTopo({ irPara }: { irPara: IrPara }) {
  const c = useCtx();
  const { dados } = c;
  const r = dados.resumo;
  const { abertos } = itensDoMes(dados.contas, r.abertas, r.pagas);
  const previstos = dados.ganhos.filter((g) => !g.recebido);

  return (
    <div className="resumo-topo">
      <div className="blocos">
        <Card id="card-bancos" titulo="Tenho nos bancos" total={dinheiro(r.tenho)} rotuloNovo="Adicionar banco"
          novo={() => irPara("accounts", "novoBanco")} vazio="Nenhum banco ainda.">
          {dados.bancos.map((b) => (
            <Item key={b.id} nome={b.nome} valor={dinheiro(b.saldo)}
              editar={() => irPara("accounts", "ajustar:" + b.id)} excluir={() => irPara("accounts", "remover:" + b.id)} />
          ))}
        </Card>

        <Card id="card-entrar" titulo="Vai entrar" sinal="mais" total={dinheiro(r.vai_entrar)} rotuloNovo="Adicionar ganho"
          novo={() => irPara("incomes", "novoGanho")} vazio="Nada previsto pra entrar.">
          {previstos.map((g) => (
            <Item key={g.id} nome={g.nome} valor={dinheiro(g.valor)}
              detalhe={g.atrasado ? "ainda não entrou" : (g.renda_id ? "renda fixa · " : "") + dataCurta(g.data)} alerta={g.atrasado}
              editar={() => irPara("incomes", "editarGanho:" + g.id)}
              excluir={() => c.executar(() => api.excluirGanho(g.id), `${g.nome} apagado.`)} />
          ))}
        </Card>

        <Card id="card-falta" titulo="Falta pagar" sinal="menos" total={dinheiro(r.falta_pagar)} rotuloNovo="Adicionar conta"
          novo={() => irPara("bills", "novaConta")} vazio="Nenhuma conta em aberto.">
          {abertos.map((x) => {
            const chave = x.conta.id + "@" + x.mes;
            const parcela = x.n && x.conta.total_parcelas ? `parcela ${x.n} de ${x.conta.total_parcelas} · ` : "";
            return (
              <Item key={chave} nome={x.conta.nome} valor={dinheiro(x.conta.valor)} alerta={x.atrasada}
                detalhe={x.atrasada ? "atrasada" : `${parcela}${x.conta.dia_vencimento ? `dia ${x.conta.dia_vencimento}` : "sem dia"}`}
                editar={() => irPara("bills", "editar:" + chave)} excluir={() => irPara("bills", "excluir:" + chave)} />
            );
          })}
        </Card>
      </div>

      {/* SUA VEZ: a faixa roxa do resultado entra aqui (veja as instruções no chat) */}
    </div>
  );
}
