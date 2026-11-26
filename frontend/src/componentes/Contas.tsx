// Tela das contas do mês. Só exibe o que a API devolve: ordem, parcelas, vencimento,
// início/fim ao editar e "parar a partir de" são decididos no backend.
import { useState } from "react";
import { api, type Aberta, type Conta, type ContaEntrada, type Pagamento, type Tipo } from "../api";
import { bancoPadrao, useCtx } from "../contexto";
import { dataCurta, dinheiro, lerDinheiro, mesCompleto, nomeMes, paraCampo } from "../util";
import { Cancelar, OpcoesBanco, OpcoesCategoria, marcado, useNomeCategoria, valorDe } from "./comuns";

export interface Item {
  conta: Conta;
  mes: string; // mês de referência (da ocorrência, ou onde a edição se aplica)
  n: number | null; // número da parcela nesse mês (vem da API)
  atrasada: boolean;
  situacao?: Aberta["situacao_vencimento"];
  venceEm?: number | null;
  pagamento?: Pagamento;
}

const tipoTexto = (x: Item) =>
  x.conta.tipo === "fixa" ? "todo mês" : x.conta.tipo === "unica" ? "uma vez" : `parcela ${x.n} de ${x.conta.total_parcelas}`;

function itensDoMes(contas: Conta[], abertas: Aberta[], pagas: Pagamento[]) {
  const porId = new Map(contas.map((c) => [c.id, c]));
  const abertos: Item[] = abertas.flatMap((a) => {
    const conta = porId.get(a.conta_id);
    return conta
      ? [{ conta, mes: a.mes_origem, n: a.numero_parcela, atrasada: a.atrasada, situacao: a.situacao_vencimento, venceEm: a.vence_em_dias }]
      : [];
  });
  const pagos: Item[] = pagas.flatMap((p) => {
    const conta = porId.get(p.conta_id);
    return conta ? [{ conta, mes: p.mes_conta, n: p.numero_parcela, atrasada: false, pagamento: p }] : [];
  });
  return { abertos, pagos };
}

export function Contas() {
  const c = useCtx();
  const { dados, mes } = c;
  const [aba, setAba] = useState<"open" | "paid">("open");
  const { abertos, pagos } = itensDoMes(dados.contas, dados.resumo.abertas, dados.resumo.pagas);
  const lista = aba === "open" ? abertos : pagos; // já vem na ordem certa da API
  const nm = nomeMes(mes);

  return (
    <section className="card panel on">
      <h2>Contas de {nm}</h2>
      <p className="hint">Clique no círculo quando pagar. O valor sai do banco que você escolher.</p>
      <div className="tabs">
        <button className={`tab ${aba === "open" ? "on" : ""}`} onClick={() => setAba("open")}>
          Falta pagar · {abertos.length} · {dinheiro(dados.resumo.falta_pagar)}
        </button>
        <button className={`tab ${aba === "paid" ? "on" : ""}`} onClick={() => setAba("paid")}>
          Já paguei · {pagos.length} · {dinheiro(dados.resumo.ja_pago)}
        </button>
      </div>
      <div>
        {lista.length ? (
          dados.categorias.filter((g) => lista.some((x) => x.conta.categoria_efetiva === g.chave)).map((g) => {
            const xs = lista.filter((x) => x.conta.categoria_efetiva === g.chave);
            return (
              <div key={g.chave}>
                <div className="ghead">
                  <span>{g.nome}</span>
                  <b>{dinheiro(aba === "open" ? g.falta_pagar : g.ja_pago)}</b>
                </div>
                {xs.map((x) => <LinhaConta key={x.conta.id + "@" + x.mes} x={x} />)}
              </div>
            );
          })
        ) : (
          <div className="empty">
            {aba === "open"
              ? dados.contas.length ? "Tudo pago neste mês. 🎉" : "Nenhuma conta cadastrada. Use “Adicionar conta” abaixo."
              : "Nenhuma conta paga neste mês ainda."}
          </div>
        )}
      </div>
      <NovaConta aoAdicionar={() => setAba("open")} />
      <datalist id="credList">
        {[...new Set(dados.contas.map((x) => x.credor).filter(Boolean))].map((n) => <option key={n} value={n!} />)}
      </datalist>
    </section>
  );
}

function TagVencimento({ x }: { x: Item }) {
  if (x.atrasada) return <span className="tag red">atrasada · era de {nomeMes(x.mes)}</span>;
  const d = x.conta.dia_vencimento;
  switch (x.situacao) {
    case "venceu": return <span className="tag red">venceu dia {d}</span>;
    case "hoje": return <span className="tag amber">vence hoje</span>;
    case "em_breve": return <span className="tag amber">vence em {x.venceEm} dia{x.venceEm === 1 ? "" : "s"}</span>;
    default: return d ? <span className="tag">dia {d}</span> : null;
  }
}

function LinhaConta({ x }: { x: Item }) {
  const c = useCtx();
  const nomeCategoria = useNomeCategoria();
  const { conta, pagamento: p } = x;
  const chave = conta.id + "@" + x.mes;
  const nomeBanco = (id: string | null) => c.dados.bancos.find((b) => b.id === id)?.nome;
  const credor = conta.credor && conta.credor !== nomeCategoria(conta.categoria_efetiva) ? conta.credor + " · " : "";

  function clicarCirculo() {
    if (!p) { c.abrir("pagar:" + chave); return; }
    const banco = nomeBanco(p.banco_id);
    c.executar(() => api.desfazerPagamento(p.id),
      `Pagamento desfeito${banco ? `, ${dinheiro(p.valor_pago)} voltou para ${banco}` : ""}.`);
  }

  async function confirmarPagamento() {
    const valor = lerDinheiro(valorDe("payVal"));
    if (valor === null) { c.toast("Digite o valor pago."); return; }
    const banco = c.dados.bancos.length ? valorDe("payAcc") || null : null;
    if (banco) c.setUltimoBanco(banco);
    const nb = nomeBanco(banco);
    await c.executar(() => api.pagar({ conta_id: conta.id, mes_conta: x.mes, valor_pago: valor, banco_id: banco }),
      `${conta.nome} paga${nb ? `: ${dinheiro(valor)} saiu do ${nb}` : ""}.`);
  }

  return (
    <div className={`row ${p ? "paid" : ""}`}>
      <button className={`check ${p ? "done" : ""}`} onClick={clicarCirculo}
        aria-label={`${p ? "Desfazer pagamento de" : "Pagar"} ${conta.nome}`}>✓</button>
      <div>
        <div className="nm">
          {conta.nome}
          {conta.juros_altos && <span className="tag red">juros altos</span>}
          {conta.incerto && <span className="tag amber">valor incerto</span>}
          {!p && <TagVencimento x={x} />}
        </div>
        <div className="meta">
          {credor}{tipoTexto(x)}
          {p && ` · pago ${dataCurta(p.data_pagamento)}${nomeBanco(p.banco_id) ? " com " + nomeBanco(p.banco_id) : ""}`}
        </div>
      </div>
      <div className="val">{dinheiro(p ? p.valor_pago : conta.valor)}</div>
      <div className="acts">
        <button className="lnk" onClick={() => c.abrir("editar:" + chave)}>Editar</button>
        <button className="lnk red" onClick={() => c.abrir("excluir:" + chave)}>Excluir</button>
      </div>

      {c.aberto === "pagar:" + chave && !p && (
        <div className="box">
          <p>Pagar <b>{conta.nome}</b>{x.atrasada ? ` (de ${nomeMes(x.mes)})` : ""}</p>
          <label className="f">Valor pago (R$)<input id="payVal" inputMode="decimal" defaultValue={paraCampo(conta.valor)} autoFocus /></label>
          {c.dados.bancos.length > 0 && (
            <label className="f">Saiu de qual banco<select id="payAcc" defaultValue={bancoPadrao(c)}><OpcoesBanco /></select></label>
          )}
          <button className="btn pri" onClick={confirmarPagamento}>Confirmar pagamento</button><Cancelar />
        </div>
      )}

      {c.aberto === "excluir:" + chave && <ExcluirConta conta={conta} />}
      {c.aberto === "editar:" + chave && <EditarConta x={x} />}
    </div>
  );
}

/** Excluir, ou (se fixa) parar de cobrar a partir do mês aberto — o backend valida. */
export function ExcluirConta({ conta }: { conta: Conta }) {
  const c = useCtx();
  const fixa = conta.tipo === "fixa";
  return (
    <div className="box">
      <p>Excluir <b>{conta.nome}</b>?{fixa ? " Ela é fixa: dá para parar de cobrar a partir deste mês e manter o histórico." : ""}</p>
      {fixa && (
        <button className="btn pri" onClick={() => c.executar(() => api.pararConta(conta.id, c.mes),
          `${conta.nome} não aparece mais a partir de ${mesCompleto(c.mes)}.`)}>
          Parar a partir de {nomeMes(c.mes)}
        </button>
      )}
      <button className="btn danger" onClick={() => c.executar(() => api.excluirConta(conta.id), `${conta.nome} apagada.`)}>Apagar de vez</button>
      <Cancelar />
    </div>
  );
}

const inteiro = (v: string) => (v.trim() === "" ? 0 : parseInt(v, 10));

export function EditarConta({ x }: { x: Item }) {
  const c = useCtx();
  const b = x.conta;
  const [tipo, setTipo] = useState<Tipo>(b.tipo);

  function salvar() {
    const valor = lerDinheiro(valorDe("eValue"));
    if (valor === null) { c.toast("Digite o valor."); return; }
    const entrada: ContaEntrada = {
      nome: valorDe("eName").trim(), valor, tipo,
      mes_inicio: tipo === "unica" ? valorDe("eMonth") || b.mes_inicio : b.mes_inicio,
      mes_fim: tipo === "fixa" ? b.mes_fim : null,
      parcela_inicial: tipo === "parcelada" ? b.parcela_inicial : null,
      total_parcelas: tipo === "parcelada" ? inteiro(valorDe("eTotal")) : null,
      categoria: valorDe("eGroup"), credor: valorDe("eCred").trim() || null,
      dia_vencimento: inteiro(valorDe("eDay")), juros_altos: marcado("eHigh"), incerto: marcado("eUnc"),
      // o backend converte "parcela N neste mês" e "virou fixa" no início certo
      mes_referencia: x.mes,
      parcela_no_mes: tipo === "parcelada" ? inteiro(valorDe("eN")) : null,
    };
    c.executar(() => api.editarConta(b.id, entrada), `${entrada.nome} atualizada.`);
  }

  return (
    <div className="box">
      <label className="f">Nome<input id="eName" defaultValue={b.nome} /></label>
      <label className="f">Categoria<select id="eGroup" defaultValue={b.categoria}><OpcoesCategoria /></select></label>
      <label className="f">Para quem<input id="eCred" list="credList" defaultValue={b.credor ?? ""} /></label>
      <label className="f">Valor (R$)<input id="eValue" inputMode="decimal" defaultValue={paraCampo(b.valor)} /></label>
      <label className="f">Vence dia<input id="eDay" type="number" min={1} max={31} defaultValue={b.dia_vencimento || ""} /></label>
      <label className="f">Como é
        <select value={tipo} onChange={(e) => setTipo(e.target.value as Tipo)}>
          <option value="fixa">Todo mês (fixa)</option><option value="unica">Só uma vez</option><option value="parcelada">Parcelada</option>
        </select>
      </label>
      {tipo === "parcelada" && (<>
        <label className="f">Parcela em {nomeMes(x.mes)}<input id="eN" type="number" min={1} defaultValue={x.n ?? b.parcela_inicial ?? 1} /></label>
        <label className="f">De quantas<input id="eTotal" type="number" min={1} defaultValue={b.total_parcelas ?? 2} /></label>
      </>)}
      {tipo === "unica" && <label className="f">Mês da conta<input id="eMonth" type="month" defaultValue={b.mes_inicio} /></label>}
      <label className="ck"><input type="checkbox" id="eHigh" defaultChecked={b.juros_altos} /> Juros altos</label>
      <label className="ck"><input type="checkbox" id="eUnc" defaultChecked={b.incerto} /> Valor incerto</label>
      <button className="btn pri" onClick={salvar}>Salvar</button><Cancelar />
    </div>
  );
}

export function NovaConta({ aoAdicionar }: { aoAdicionar?: () => void }) {
  const c = useCtx();
  const vazio = { nome: "", cred: "", valor: "", dia: "", n: "1", total: "2" };
  const [f, setF] = useState(vazio);
  const [tipo, setTipo] = useState<Tipo>("fixa");
  const [categoria, setCategoria] = useState(""); // "" = o backend escolhe pelo nome
  const [juros, setJuros] = useState(false);
  const [incerto, setIncerto] = useState(false);
  const mudar = (campo: keyof typeof vazio, v: string) => setF({ ...f, [campo]: v });

  async function adicionar() {
    const valor = lerDinheiro(f.valor);
    if (valor === null) { c.toast("Digite o valor."); return; }
    const nome = f.nome.trim();
    const ok = await c.executar(() => api.criarConta({
      nome, valor, tipo, mes_inicio: c.mes, mes_fim: null, categoria, credor: f.cred.trim() || null,
      dia_vencimento: inteiro(f.dia), parcela_inicial: null,
      total_parcelas: tipo === "parcelada" ? inteiro(f.total) : null, juros_altos: juros, incerto,
      mes_referencia: c.mes, parcela_no_mes: tipo === "parcelada" ? inteiro(f.n) : null,
    }), `${nome} adicionada em ${mesCompleto(c.mes)}.`);
    if (ok) { setF(vazio); setCategoria(""); setJuros(false); setIncerto(false); aoAdicionar?.(); }
  }

  return (
    <details className="add">
      <summary>+ Adicionar conta ou dívida</summary>
      <div className="form">
        <label className="f">Nome<input value={f.nome} onChange={(e) => mudar("nome", e.target.value)} placeholder="Ex.: aluguel, cartão Nubank" /></label>
        <label className="f">Categoria
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)}><OpcoesCategoria /></select>
        </label>
        <label className="f">Para quem (opcional)<input value={f.cred} onChange={(e) => mudar("cred", e.target.value)} list="credList" placeholder="Ex.: Santander, um amigo" /></label>
        <label className="f">Valor (R$)<input value={f.valor} onChange={(e) => mudar("valor", e.target.value)} inputMode="decimal" placeholder="0,00" /></label>
        <label className="f">Vence dia<input value={f.dia} onChange={(e) => mudar("dia", e.target.value)} type="number" min={1} max={31} placeholder="opcional" /></label>
        <label className="f">Como é
          <select value={tipo} onChange={(e) => setTipo(e.target.value as Tipo)}>
            <option value="fixa">Todo mês (fixa)</option><option value="unica">Só uma vez</option><option value="parcelada">Parcelada</option>
          </select>
        </label>
        {tipo === "parcelada" && (<>
          <label className="f">Parcela deste mês<input value={f.n} onChange={(e) => mudar("n", e.target.value)} type="number" min={1} /></label>
          <label className="f">De quantas<input value={f.total} onChange={(e) => mudar("total", e.target.value)} type="number" min={1} /></label>
        </>)}
        <label className="ck"><input type="checkbox" checked={juros} onChange={(e) => setJuros(e.target.checked)} /> Tem juros altos</label>
        <label className="ck"><input type="checkbox" checked={incerto} onChange={(e) => setIncerto(e.target.checked)} /> Valor ainda incerto</label>
        <button className="btn pri" onClick={adicionar}>Adicionar</button>
      </div>
      <p className="hint" style={{ marginTop: 8 }}>Vai entrar a partir de {mesCompleto(c.mes)} (o mês que está aberto lá em cima).</p>
    </details>
  );
}
