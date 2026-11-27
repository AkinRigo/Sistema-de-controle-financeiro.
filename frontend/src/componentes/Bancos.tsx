import { useState } from "react";
import { api, type Banco } from "../api";
import { useCtx } from "../contexto";
import { dinheiro, lerDinheiro, paraCampo } from "../util";
import { Cancelar, valorDe } from "./comuns";

export function Bancos() {
  const c = useCtx();
  const [nome, setNome] = useState("");
  const [saldo, setSaldo] = useState("");

  async function adicionar() {
    const v = lerDinheiro(saldo || "0");
    if (!nome.trim() || v === null) { c.toast("Digite o nome do banco e o saldo."); return; }
    if (await c.executar(() => api.criarBanco(nome.trim(), v), `${nome.trim()} adicionado.`)) { setNome(""); setSaldo(""); }
  }

  return (
    <section className="card panel on">
      <h2>Meus bancos</h2>
      <p className="hint">O saldo de cada conta. Ganhos recebidos somam aqui; contas pagas descontam.</p>
      <div>
        {c.dados.bancos.length
          ? c.dados.bancos.map((b) => <LinhaBanco key={b.id} b={b} />)
          : <div className="empty">Cadastre seus bancos com o saldo que aparece no app de cada um.</div>}
      </div>
      <div className="total"><span>Total nos bancos</span><b>{dinheiro(c.dados.resumo.tenho)}</b></div>
      <details className="add">
        <summary>+ Adicionar banco</summary>
        <div className="form">
          <label className="f">Banco<input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Nubank" /></label>
          <label className="f">Saldo agora (R$)<input value={saldo} onChange={(e) => setSaldo(e.target.value)} inputMode="decimal" placeholder="0,00" /></label>
          <button className="btn pri" onClick={adicionar}>Adicionar</button>
        </div>
      </details>
    </section>
  );
}

export function LinhaBanco({ b }: { b: Banco }) {
  const c = useCtx();
  function salvar() {
    const v = lerDinheiro(valorDe("adjVal"));
    if (v === null) { c.toast("Saldo inválido."); return; }
    const nome = valorDe("adjName").trim() || b.nome;
    c.executar(() => api.editarBanco(b.id, nome, v), `Saldo do ${nome} ajustado.`);
  }
  return (
    <div className="row noico">
      <div><div className="nm">{b.nome}</div></div>
      <div className="val">{dinheiro(b.saldo)}</div>
      <div className="acts">
        <button className="lnk" onClick={() => c.abrir("ajustar:" + b.id)}>Ajustar saldo</button>
        <button className="lnk red" onClick={() => c.abrir("remover:" + b.id)}>Remover</button>
      </div>
      {c.aberto === "ajustar:" + b.id && (
        <div className="box">
          <p>Digite o saldo que aparece agora no app do banco.</p>
          <label className="f">Nome<input id="adjName" defaultValue={b.nome} /></label>
          <label className="f">Saldo (R$)<input id="adjVal" inputMode="decimal" defaultValue={paraCampo(b.saldo)} autoFocus /></label>
          <button className="btn pri" onClick={salvar}>Salvar</button><Cancelar />
        </div>
      )}
      {c.aberto === "remover:" + b.id && (
        <div className="box">
          <p>Remover <b>{b.nome}</b>? Os pagamentos já feitos continuam registrados.</p>
          <button className="btn danger" onClick={() => c.executar(() => api.excluirBanco(b.id), "Banco removido.")}>Remover</button>
          <Cancelar />
        </div>
      )}
    </div>
  );
}
