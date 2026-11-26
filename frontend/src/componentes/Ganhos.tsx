import { useState } from "react";
import { api, type GanhoDoMes, type Renda } from "../api";
import { bancoPadrao, useCtx } from "../contexto";
import { HOJE, MES_ATUAL, dataCurta, dinheiro, lerDinheiro, mesCompleto, nomeMes, num, paraCampo } from "../util";
import { Cancelar, OpcoesBanco, valorDe } from "./comuns";
import { Corridas } from "./Corridas";

/** Tudo que entra: renda fixa, ganhos do mês e a estimativa de corridas. */
export function Ganhos() {
  const c = useCtx();
  const { dados, mes } = c;
  const lista = dados.ganhos; // o backend já escolhe quais entram no mês e marca os atrasados

  return (
    <>
      <RendasFixas />
      <section className="card panel on">
        <h2>Ganhos de {nomeMes(mes)}</h2>
        <p className="hint">“Já recebi” coloca o dinheiro no banco. “Vai entrar” conta na previsão.</p>
        <div>
          {lista.length ? lista.map((g) => <LinhaGanho key={g.id} g={g} />) : <div className="empty">Nenhum ganho neste mês ainda.</div>}
          {lista.length > 0 && (
            <div className="total"><span>Recebido em {nomeMes(mes)}</span><b>{dinheiro(dados.resumo.recebido)}</b></div>
          )}
        </div>
        <NovoGanho key={mes} />
      </section>
      <Corridas key={mes} />
    </>
  );
}

// ---------------- renda fixa ----------------

const inteiro = (v: string) => parseInt(v, 10);

function RendasFixas() {
  const c = useCtx();
  const rendas = c.dados.rendas;
  const total = rendas.reduce((s, r) => s + num(r.valor), 0);
  return (
    <section className="card panel on">
      <h2>Renda fixa</h2>
      <p className="hint">Salário, pensão, aluguel que você recebe… Cadastre uma vez: todo mês ela aparece sozinha como “vai entrar”. Quando cair, marque “Recebi” nos ganhos do mês.</p>
      <div>
        {rendas.length ? rendas.map((r) => <LinhaRenda key={r.id} r={r} />) : <div className="empty">Nenhuma renda fixa ainda.</div>}
        {rendas.length > 0 && <div className="total"><span>Entra todo mês</span><b>{dinheiro(total)}</b></div>}
      </div>
      <NovaRenda />
    </section>
  );
}

function LinhaRenda({ r }: { r: Renda }) {
  const c = useCtx();
  const nomeBanco = c.dados.bancos.find((b) => b.id === r.banco_id)?.nome;

  function salvar() {
    const nome = valorDe("rfNome").trim(), valor = lerDinheiro(valorDe("rfValor"));
    if (valor === null) { c.toast("Digite o valor."); return; }
    const banco = c.dados.bancos.length ? valorDe("rfBanco") || null : null;
    c.executar(() => api.editarRenda(r.id, { nome, valor, dia: inteiro(valorDe("rfDia")), banco_id: banco }),
      `${nome} atualizada. Vale a partir deste mês.`);
  }

  return (
    <div className="row noico">
      <div>
        <div className="nm">{r.nome}<span className="tag">todo mês</span></div>
        <div className="meta">cai dia {r.dia}{nomeBanco ? " · no " + nomeBanco : ""}</div>
      </div>
      <div className="val">{dinheiro(r.valor)}</div>
      <div className="acts">
        <button className="lnk" onClick={() => c.abrir("editarRenda:" + r.id)}>Editar</button>
        <button className="lnk red" onClick={() => c.abrir("excluirRenda:" + r.id)}>Excluir</button>
      </div>
      {c.aberto === "editarRenda:" + r.id && (
        <div className="box">
          <label className="f">Nome<input id="rfNome" defaultValue={r.nome} /></label>
          <label className="f">Valor (R$)<input id="rfValor" inputMode="decimal" defaultValue={paraCampo(r.valor)} /></label>
          <label className="f">Cai todo dia<input id="rfDia" type="number" min={1} max={31} defaultValue={r.dia} /></label>
          {c.dados.bancos.length > 0 && (
            <label className="f">Cai em qual banco<select id="rfBanco" defaultValue={r.banco_id ?? ""}><OpcoesBanco /></select></label>
          )}
          <button className="btn pri" onClick={salvar}>Salvar</button><Cancelar />
        </div>
      )}
      {c.aberto === "excluirRenda:" + r.id && (
        <div className="box">
          <p>Excluir <b>{r.nome}</b>? Os meses que ainda não entraram somem da previsão; o que você já recebeu continua registrado.</p>
          <button className="btn danger" onClick={() => c.executar(() => api.excluirRenda(r.id), `${r.nome} excluída.`)}>Excluir</button>
          <Cancelar />
        </div>
      )}
    </div>
  );
}

function NovaRenda() {
  const c = useCtx();
  const [nome, setNome] = useState("");
  const [valor, setValor] = useState("");
  const [dia, setDia] = useState("5");
  const [banco, setBanco] = useState(bancoPadrao(c));

  async function adicionar() {
    const v = lerDinheiro(valor);
    if (v === null) { c.toast("Digite o valor."); return; }
    const ok = await c.executar(
      () => api.criarRenda({ nome: nome.trim(), valor: v, dia: inteiro(dia), banco_id: c.dados.bancos.length ? banco || null : null }),
      `${nome.trim()} cadastrada: ${dinheiro(v)} todo mês, a partir de ${mesCompleto(MES_ATUAL)}.`);
    if (ok) { setNome(""); setValor(""); }
  }

  return (
    <details className="add">
      <summary>+ Adicionar renda fixa</summary>
      <div className="form">
        <label className="f">Nome<input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: salário, pensão" /></label>
        <label className="f">Valor por mês (R$)<input value={valor} onChange={(e) => setValor(e.target.value)} inputMode="decimal" placeholder="0,00" /></label>
        <label className="f">Cai todo dia<input value={dia} onChange={(e) => setDia(e.target.value)} type="number" min={1} max={31} /></label>
        {c.dados.bancos.length > 0 && (
          <label className="f">Cai em qual banco<select value={banco} onChange={(e) => setBanco(e.target.value)}><OpcoesBanco /></select></label>
        )}
        <button className="btn pri" onClick={adicionar}>Adicionar</button>
      </div>
    </details>
  );
}

// ---------------- ganhos do mês ----------------

function LinhaGanho({ g }: { g: GanhoDoMes }) {
  const c = useCtx();
  const atrasado = g.atrasado;
  const nomeBanco = c.dados.bancos.find((b) => b.id === g.banco_id)?.nome;
  const base = { nome: g.nome, valor: g.valor, data: g.data, recebido: g.recebido, banco_id: g.banco_id };

  function confirmarRecebimento() {
    const v = lerDinheiro(valorDe("recvVal"));
    if (v === null) { c.toast("Digite o valor."); return; }
    const banco = c.dados.bancos.length ? valorDe("recvAcc") || null : null;
    if (banco) c.setUltimoBanco(banco);
    const nb = c.dados.bancos.find((b) => b.id === banco)?.nome;
    // o backend credita o banco e acerta a data do recebimento
    c.executar(() => api.receberGanho(g.id, v, banco, c.mes),
      nb ? `${dinheiro(v)} somado ao ${nb}.` : "Marcado como recebido.");
  }

  function salvarEdicao() {
    const v = lerDinheiro(valorDe("ieVal")), data = valorDe("ieDate");
    if (v === null) { c.toast("Digite o valor."); return; }
    c.executar(() => api.editarGanho(g.id, { ...base, nome: valorDe("ieName").trim(), valor: v, data }), "Ganho atualizado.");
  }

  return (
    <div className="row noico">
      <div>
        <div className="nm">
          {g.nome}
          {g.renda_id && <span className="tag">renda fixa</span>}
          {g.recebido ? <span className="tag green">recebido</span>
            : atrasado ? <span className="tag red">ainda não entrou</span> : <span className="tag blue">vai entrar</span>}
        </div>
        <div className="meta">{dataCurta(g.data)}{g.recebido && nomeBanco ? " · caiu no " + nomeBanco : ""}</div>
      </div>
      <div className="val">{dinheiro(g.valor)}</div>
      <div className="acts">
        {g.recebido
          ? <button className="lnk" onClick={() => c.executar(() => api.desfazerRecebimento(g.id),
              nomeBanco ? `${dinheiro(g.valor)} tirado do ${nomeBanco}.` : "Voltou para “vai entrar”.")}>Não recebi ainda</button>
          : <button className="lnk" onClick={() => c.abrir("receber:" + g.id)}>Recebi</button>}
        <button className="lnk" onClick={() => c.abrir("editarGanho:" + g.id)}>Editar</button>
        <button className="lnk red" onClick={() => c.executar(() => api.excluirGanho(g.id),
          `Ganho apagado${g.recebido && nomeBanco ? `, ${dinheiro(g.valor)} tirado do ${nomeBanco}` : ""}.`)}>Apagar</button>
      </div>
      {c.aberto === "receber:" + g.id && (
        <div className="box">
          <p>Recebeu <b>{g.nome}</b>?</p>
          <label className="f">Valor que entrou (R$)<input id="recvVal" inputMode="decimal" defaultValue={paraCampo(g.valor)} autoFocus /></label>
          {c.dados.bancos.length > 0 && (
            <label className="f">Caiu em qual banco<select id="recvAcc" defaultValue={bancoPadrao(c)}><OpcoesBanco /></select></label>
          )}
          <button className="btn pri" onClick={confirmarRecebimento}>Confirmar</button><Cancelar />
        </div>
      )}
      {c.aberto === "editarGanho:" + g.id && (
        <div className="box">
          <label className="f">De onde<input id="ieName" defaultValue={g.nome} /></label>
          <label className="f">Valor (R$)<input id="ieVal" inputMode="decimal" defaultValue={paraCampo(g.valor)} /></label>
          <label className="f">Data<input id="ieDate" type="date" defaultValue={g.data} /></label>
          <button className="btn pri" onClick={salvarEdicao}>Salvar</button><Cancelar />
        </div>
      )}
    </div>
  );
}

function NovoGanho() {
  const c = useCtx();
  // Aberto pelo atalho "+ adicionar" do resumo: já vem aberto e em "Vai entrar".
  const peloAtalho = c.aberto === "novoGanho";
  const [valor, setValor] = useState("");
  const [nome, setNome] = useState("");
  const [data, setData] = useState(c.mes === MES_ATUAL ? HOJE : c.mes + "-01");
  const [recebido, setRecebido] = useState(!peloAtalho);
  const [banco, setBanco] = useState(bancoPadrao(c));

  async function registrar() {
    const v = lerDinheiro(valor);
    if (v === null) { c.toast("Digite o valor do ganho."); return; }
    const dataFinal = data || HOJE;
    const idBanco = recebido && c.dados.bancos.length ? banco || null : null;
    const nb = c.dados.bancos.find((b) => b.id === idBanco)?.nome;
    let msg = recebido ? (nb ? `${dinheiro(v)} somado ao ${nb}.` : `Ganho de ${dinheiro(v)} registrado.`) : `${dinheiro(v)} entrou na previsão.`;
    const outroMes = dataFinal.slice(0, 7) !== c.mes;
    if (outroMes) msg += ` Ele é de ${mesCompleto(dataFinal.slice(0, 7))}, então abri esse mês.`;
    const ok = await c.executar(
      () => api.criarGanho({ nome: nome.trim(), valor: v, data: dataFinal, recebido, banco_id: idBanco }), msg);
    if (!ok) return;
    if (idBanco) c.setUltimoBanco(idBanco);
    setValor(""); setNome("");
    if (outroMes) c.setMes(dataFinal.slice(0, 7));
  }

  return (
    <details className="add" open={peloAtalho || undefined}>
      <summary>+ Registrar ganho</summary>
      <div className="form">
        <label className="f">Valor (R$)<input value={valor} onChange={(e) => setValor(e.target.value)} inputMode="decimal" placeholder="0,00" /></label>
        <label className="f">De onde<input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: corridas, FGTS" /></label>
        <label className="f">Data<input type="date" value={data} onChange={(e) => setData(e.target.value)} /></label>
        <div className="seg" style={{ gridColumn: "1/-1" }}>
          <label><input type="radio" name="iSt" checked={recebido} onChange={() => setRecebido(true)} /> Já recebi</label>
          <label><input type="radio" name="iSt" checked={!recebido} onChange={() => setRecebido(false)} /> Vai entrar</label>
        </div>
        {recebido && c.dados.bancos.length > 0 && (
          <label className="f">Caiu em qual banco<select value={banco} onChange={(e) => setBanco(e.target.value)}><OpcoesBanco /></select></label>
        )}
        <button className="btn pri" onClick={registrar}>Registrar</button>
      </div>
    </details>
  );
}
