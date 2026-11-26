import { useState } from "react";
import { api, type Conta, type ContaEntrada, type Pagamento, type Tipo } from "../api";
import { bancoPadrao, useCtx } from "../contexto";
import {
  CATEGORIAS, DIA_HOJE, MES_ATUAL, NOME_CATEGORIA, dataCurta, difMes, dinheiro, lerDinheiro,
  mesCompleto, nomeMes, num, numeroParcela, paraCampo, somarMes, sugerirCategoria,
} from "../util";
import { Cancelar, OpcoesBanco, OpcoesCategoria, marcado, valorDe } from "./comuns";

export interface Item {
  conta: Conta;
  mes: string; // mês da ocorrência
  n: number | null; // número da parcela
  atrasada: boolean;
  pagamento?: Pagamento;
}

const ordem = (x: Item) => (x.atrasada ? 0 : x.conta.juros_altos ? 1 : 2) * 100 + (x.conta.dia_vencimento || 60);
const tipoTexto = (x: Item) =>
  x.conta.tipo === "fixa" ? "todo mês" : x.conta.tipo === "unica" ? "uma vez" : `parcela ${x.n} de ${x.conta.total_parcelas}`;

export function itensDoMes(contas: Conta[], abertas: { conta_id: string; mes_origem: string; atrasada: boolean; numero_parcela: number | null }[], pagas: Pagamento[]) {
  const porId = new Map(contas.map((c) => [c.id, c]));
  const abertos: Item[] = abertas.flatMap((a) => {
    const conta = porId.get(a.conta_id);
    return conta ? [{ conta, mes: a.mes_origem, n: a.numero_parcela, atrasada: a.atrasada }] : [];
  });
  const pagos: Item[] = pagas.flatMap((p) => {
    const conta = porId.get(p.conta_id);
    return conta ? [{ conta, mes: p.mes_conta, n: numeroParcela(conta, p.mes_conta), atrasada: false, pagamento: p }] : [];
  });
  return { abertos, pagos };
}

export function Contas() {
  const c = useCtx();
  const { dados, mes } = c;
  const [aba, setAba] = useState<"open" | "paid">("open");
  const { abertos, pagos } = itensDoMes(dados.contas, dados.resumo.abertas, dados.resumo.pagas);
  const lista = aba === "open" ? [...abertos].sort((a, b) => ordem(a) - ordem(b)) : pagos;
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
          Já paguei · {pagos.length} · {dinheiro(pagos.reduce((s, x) => s + num(x.pagamento!.valor_pago), 0))}
        </button>
      </div>
      <div>
        {lista.length ? (
          CATEGORIAS.filter(([g]) => lista.some((x) => x.conta.categoria_efetiva === g)).map(([g, l]) => {
            const xs = lista.filter((x) => x.conta.categoria_efetiva === g);
            const total = xs.reduce((s, x) => s + num(x.pagamento ? x.pagamento.valor_pago : x.conta.valor), 0);
            return (
              <div key={g}>
                <div className="ghead"><span>{l}</span><b>{dinheiro(total)}</b></div>
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
  const { mes } = useCtx();
  if (x.atrasada) return <span className="tag red">atrasada · era de {nomeMes(x.mes)}</span>;
  const d = x.conta.dia_vencimento;
  if (!d) return null;
  if (mes === MES_ATUAL) {
    const dif = d - DIA_HOJE;
    if (dif < 0) return <span className="tag red">venceu dia {d}</span>;
    if (dif === 0) return <span className="tag amber">vence hoje</span>;
    if (dif <= 5) return <span className="tag amber">vence em {dif} dia{dif > 1 ? "s" : ""}</span>;
  }
  return <span className="tag">dia {d}</span>;
}

function LinhaConta({ x }: { x: Item }) {
  const c = useCtx();
  const { conta, pagamento: p } = x;
  const chave = conta.id + "@" + x.mes;
  const nomeBanco = (id: string | null) => c.dados.bancos.find((b) => b.id === id)?.nome;
  const credor = conta.credor && conta.credor !== NOME_CATEGORIA[conta.categoria_efetiva] ? conta.credor + " · " : "";

  function clicarCirculo() {
    if (!p) { c.abrir("pagar:" + chave); return; }
    const banco = nomeBanco(p.banco_id);
    c.executar(() => api.desfazerPagamento(p.id),
      `Pagamento desfeito${banco ? `, ${dinheiro(p.valor_pago)} voltou para ${banco}` : ""}.`);
  }

  async function confirmarPagamento() {
    const valor = lerDinheiro(valorDe("payVal"));
    if (valor === null || num(valor) < 0) { c.toast("Valor inválido."); return; }
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

/** Caixa de confirmação para excluir (ou, se fixa, parar de cobrar) uma conta. */
export function ExcluirConta({ conta }: { conta: Conta }) {
  const c = useCtx();
  const podeParar = conta.tipo === "fixa" && c.mes > conta.mes_inicio;
  return (
    <div className="box">
      <p>Excluir <b>{conta.nome}</b>?{podeParar ? " Ela é fixa: dá para parar de cobrar a partir deste mês e manter o histórico." : ""}</p>
      {podeParar && (
        <button className="btn pri" onClick={() => c.executar(
          () => api.editarConta(conta.id, { ...entradaDe(conta), mes_fim: somarMes(c.mes, -1) }),
          `${conta.nome} não aparece mais a partir de ${mesCompleto(c.mes)}.`)}>
          Parar a partir de {nomeMes(c.mes)}
        </button>
      )}
      <button className="btn danger" onClick={() => c.executar(() => api.excluirConta(conta.id), `${conta.nome} apagada.`)}>Apagar de vez</button>
      <Cancelar />
    </div>
  );
}

/** Item de referência para editar uma conta fora da lista do mês (ex.: aba Por categoria). */
export function itemParaEditar(conta: Conta, mes: string): Item {
  const m = conta.tipo === "unica" || mes < conta.mes_inicio ? conta.mes_inicio : mes;
  return { conta, mes: m, n: numeroParcela(conta, m), atrasada: false };
}

export function entradaDe(c: Conta): ContaEntrada {
  return {
    nome: c.nome, valor: c.valor, tipo: c.tipo, mes_inicio: c.mes_inicio, categoria: c.categoria,
    credor: c.credor, dia_vencimento: c.dia_vencimento, mes_fim: c.mes_fim,
    parcela_inicial: c.parcela_inicial, total_parcelas: c.total_parcelas,
    juros_altos: c.juros_altos, incerto: c.incerto,
  };
}

const diaValido = (v: string) => Math.min(31, Math.max(0, parseInt(v, 10) || 0));

export function EditarConta({ x }: { x: Item }) {
  const c = useCtx();
  const b = x.conta;
  const [tipo, setTipo] = useState<Tipo>(b.tipo);
  const n = b.tipo === "parcelada" ? x.n ?? b.parcela_inicial ?? 1 : 1;

  function salvar() {
    const nome = valorDe("eName").trim(), valor = lerDinheiro(valorDe("eValue"));
    if (!nome || valor === null || num(valor) < 0) { c.toast("Preencha o nome e um valor válido."); return; }
    let mesInicio = b.mes_inicio, mesFim = b.mes_fim;
    let parcela: number | null = null, total: number | null = null;
    if (tipo === "parcelada") {
      const tt = parseInt(valorDe("eTotal"), 10), nn = parseInt(valorDe("eN"), 10);
      if (!(tt >= 1 && nn >= 1 && nn <= tt)) { c.toast("Confira a parcela e o total."); return; }
      // "Parcela em <mês>" é relativa ao mês aberto; recalcula o início como no protótipo.
      if (b.tipo !== "parcelada" || mesInicio > x.mes) mesInicio = x.mes;
      parcela = nn - difMes(mesInicio, x.mes);
      if (parcela < 1) { mesInicio = x.mes; parcela = nn; }
      total = tt;
      mesFim = null;
    } else if (tipo === "unica") {
      const m = valorDe("eMonth");
      mesInicio = /^\d{4}-\d{2}$/.test(m) ? m : b.tipo === "unica" ? b.mes_inicio : x.mes;
      mesFim = null;
    } else if (b.tipo !== "fixa") {
      mesInicio = x.mes;
      mesFim = null;
    }
    const entrada: ContaEntrada = {
      nome, valor, tipo, mes_inicio: mesInicio, mes_fim: mesFim, parcela_inicial: parcela, total_parcelas: total,
      categoria: valorDe("eGroup") || b.categoria_efetiva, credor: valorDe("eCred").trim() || null,
      dia_vencimento: diaValido(valorDe("eDay")), juros_altos: marcado("eHigh"), incerto: marcado("eUnc"),
    };
    c.executar(() => api.editarConta(b.id, entrada), `${nome} atualizada.`);
  }

  return (
    <div className="box">
      <label className="f">Nome<input id="eName" defaultValue={b.nome} /></label>
      <label className="f">Categoria<select id="eGroup" defaultValue={b.categoria_efetiva}><OpcoesCategoria /></select></label>
      <label className="f">Para quem<input id="eCred" list="credList" defaultValue={b.credor ?? ""} /></label>
      <label className="f">Valor (R$)<input id="eValue" inputMode="decimal" defaultValue={paraCampo(b.valor)} /></label>
      <label className="f">Vence dia<input id="eDay" type="number" min={1} max={31} defaultValue={b.dia_vencimento || ""} /></label>
      <label className="f">Como é
        <select value={tipo} onChange={(e) => setTipo(e.target.value as Tipo)}>
          <option value="fixa">Todo mês (fixa)</option><option value="unica">Só uma vez</option><option value="parcelada">Parcelada</option>
        </select>
      </label>
      {tipo === "parcelada" && (<>
        <label className="f">Parcela em {nomeMes(x.mes)}<input id="eN" type="number" min={1} defaultValue={n} /></label>
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
  const [categoria, setCategoria] = useState("outros");
  const [mexeuCategoria, setMexeuCategoria] = useState(false);
  const [juros, setJuros] = useState(false);
  const [incerto, setIncerto] = useState(false);

  const mudar = (campo: keyof typeof vazio, v: string) => {
    const novo = { ...f, [campo]: v };
    setF(novo);
    if (!mexeuCategoria && (campo === "nome" || campo === "cred")) setCategoria(sugerirCategoria(novo.nome, novo.cred));
  };

  async function adicionar() {
    const nome = f.nome.trim(), valor = lerDinheiro(f.valor);
    if (!nome || valor === null || num(valor) < 0) { c.toast("Preencha o nome e um valor válido."); return; }
    let parcela: number | null = null, total: number | null = null;
    if (tipo === "parcelada") {
      total = parseInt(f.total, 10); parcela = parseInt(f.n, 10);
      if (!(total >= 1 && parcela >= 1 && parcela <= total)) { c.toast("Confira a parcela e o total de parcelas."); return; }
    }
    const ok = await c.executar(() => api.criarConta({
      nome, valor, tipo, mes_inicio: c.mes, mes_fim: null, categoria, credor: f.cred.trim() || null,
      dia_vencimento: diaValido(f.dia), parcela_inicial: parcela, total_parcelas: total, juros_altos: juros, incerto,
    }), `${nome} adicionada em ${mesCompleto(c.mes)}.`);
    if (ok) { setF(vazio); setCategoria("outros"); setMexeuCategoria(false); setJuros(false); setIncerto(false); aoAdicionar?.(); }
  }

  return (
    <details className="add">
      <summary>+ Adicionar conta ou dívida</summary>
      <div className="form">
        <label className="f">Nome<input value={f.nome} onChange={(e) => mudar("nome", e.target.value)} placeholder="Ex.: aluguel, cartão Nubank" /></label>
        <label className="f">Categoria
          <select value={categoria} onChange={(e) => { setCategoria(e.target.value); setMexeuCategoria(true); }}><OpcoesCategoria /></select>
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
