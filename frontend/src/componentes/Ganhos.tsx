import { useState } from "react";
import { api, type Ganho } from "../api";
import { bancoPadrao, useCtx } from "../contexto";
import { HOJE, MES_ATUAL, dataCurta, dinheiro, lerDinheiro, mesCompleto, nomeMes, num, paraCampo } from "../util";
import { Cancelar, OpcoesBanco, valorDe } from "./comuns";

export function Ganhos() {
  const c = useCtx();
  const { dados, mes } = c;
  const lista = dados.ganhos
    .filter((g) => g.data.slice(0, 7) === mes || (!g.recebido && g.data.slice(0, 7) < mes))
    .sort((a, b) => b.data.localeCompare(a.data));

  return (
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
  );
}

function LinhaGanho({ g }: { g: Ganho }) {
  const c = useCtx();
  const atrasado = !g.recebido && g.data.slice(0, 7) < c.mes;
  const nomeBanco = c.dados.bancos.find((b) => b.id === g.banco_id)?.nome;
  const base = { nome: g.nome, valor: g.valor, data: g.data, recebido: g.recebido, banco_id: g.banco_id };

  function confirmarRecebimento() {
    const v = lerDinheiro(valorDe("recvVal"));
    if (v === null || num(v) <= 0) { c.toast("Valor inválido."); return; }
    const banco = c.dados.bancos.length ? valorDe("recvAcc") || null : null;
    if (banco) c.setUltimoBanco(banco);
    const data = g.data > HOJE || g.data.slice(0, 7) < c.mes ? HOJE : g.data;
    const nb = c.dados.bancos.find((b) => b.id === banco)?.nome;
    c.executar(() => api.editarGanho(g.id, { ...base, valor: v, data, recebido: true, banco_id: banco }),
      nb ? `${dinheiro(v)} somado ao ${nb}.` : "Marcado como recebido.");
  }

  function salvarEdicao() {
    const v = lerDinheiro(valorDe("ieVal")), data = valorDe("ieDate");
    if (v === null || num(v) <= 0 || !data) { c.toast("Confira valor e data."); return; }
    c.executar(() => api.editarGanho(g.id, { ...base, nome: valorDe("ieName").trim() || "Ganho", valor: v, data }), "Ganho atualizado.");
  }

  return (
    <div className="row noico">
      <div>
        <div className="nm">
          {g.nome}
          {g.recebido ? <span className="tag green">recebido</span>
            : atrasado ? <span className="tag red">ainda não entrou</span> : <span className="tag blue">vai entrar</span>}
        </div>
        <div className="meta">{dataCurta(g.data)}{g.recebido && nomeBanco ? " · caiu no " + nomeBanco : ""}</div>
      </div>
      <div className="val">{dinheiro(g.valor)}</div>
      <div className="acts">
        {g.recebido
          ? <button className="lnk" onClick={() => c.executar(() => api.editarGanho(g.id, { ...base, recebido: false, banco_id: null }),
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
  const [valor, setValor] = useState("");
  const [nome, setNome] = useState("");
  const [data, setData] = useState(c.mes === MES_ATUAL ? HOJE : c.mes + "-01");
  const [recebido, setRecebido] = useState(true);
  const [banco, setBanco] = useState(bancoPadrao(c));

  async function registrar() {
    const v = lerDinheiro(valor);
    if (v === null || num(v) <= 0) { c.toast("Digite o valor do ganho."); return; }
    const dataFinal = data || HOJE;
    const idBanco = recebido && c.dados.bancos.length ? banco || null : null;
    const nb = c.dados.bancos.find((b) => b.id === idBanco)?.nome;
    let msg = recebido ? (nb ? `${dinheiro(v)} somado ao ${nb}.` : `Ganho de ${dinheiro(v)} registrado.`) : `${dinheiro(v)} entrou na previsão.`;
    const outroMes = dataFinal.slice(0, 7) !== c.mes;
    if (outroMes) msg += ` Ele é de ${mesCompleto(dataFinal.slice(0, 7))}, então abri esse mês.`;
    const ok = await c.executar(
      () => api.criarGanho({ nome: nome.trim() || "Ganho", valor: v, data: dataFinal, recebido, banco_id: idBanco }), msg);
    if (!ok) return;
    if (idBanco) c.setUltimoBanco(idBanco);
    setValor(""); setNome("");
    if (outroMes) c.setMes(dataFinal.slice(0, 7));
  }

  return (
    <details className="add">
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
