import { useState } from "react";
import { api } from "../api";
import { useCtx } from "../contexto";
import { dinheiro, lerDinheiro, mesCompleto, num, paraCampo } from "../util";
import { Secao } from "./Recolher";

export function Corridas() {
  const c = useCtx();
  const atual = c.dados.corridas;
  const [semana, setSemana] = useState(num(atual.por_semana) ? paraCampo(atual.por_semana) : "");
  const [fds, setFds] = useState(num(atual.por_fim_de_semana) ? paraCampo(atual.por_fim_de_semana) : "");

  function salvar(mudancas: Partial<{ semana: string; fds: string; ligado: boolean }>) {
    const s = lerDinheiro(mudancas.semana ?? semana) ?? "0.00";
    const f = lerDinheiro(mudancas.fds ?? fds) ?? "0.00";
    const ligado = mudancas.ligado ?? atual.contar_na_previsao;
    c.executar(() => api.salvarCorridas({ por_semana: s, por_fim_de_semana: f, contar_na_previsao: ligado }));
  }

  const temValor = num(atual.por_semana) || num(atual.por_fim_de_semana);
  const estimativa = atual.estimativa_mes; // calculada pelo backend para o mês aberto

  return (
    <Secao id="corridas" titulo="Estimativa de corridas"
      resumo={estimativa ? `${dinheiro(estimativa)} estimado neste mês` : "Sem estimativa"}>
      <p className="hint">Quanto você acha que tira com a moto. Fica separado dos ganhos reais.</p>
      <div className="form">
        <label className="f">Por semana, dias úteis (R$)
          <input value={semana} onChange={(e) => setSemana(e.target.value)} onBlur={() => salvar({})} inputMode="decimal" placeholder="0,00" />
        </label>
        <label className="f">Por fim de semana (R$)
          <input value={fds} onChange={(e) => setFds(e.target.value)} onBlur={() => salvar({})} inputMode="decimal" placeholder="0,00" />
        </label>
      </div>
      <label className="ck" style={{ marginTop: 6 }}>
        <input type="checkbox" checked={atual.contar_na_previsao} onChange={(e) => salvar({ ligado: e.target.checked })} /> Contar na previsão do mês
      </label>
      {temValor ? (
        <p className="hint" style={{ margin: "4px 0 0" }}>
          Estimativa para {mesCompleto(c.mes)}: {dinheiro(estimativa)}{atual.contar_na_previsao ? " (entrando na previsão)" : " (fora da previsão)"}.
        </p>
      ) : null}
    </Secao>
  );
}
