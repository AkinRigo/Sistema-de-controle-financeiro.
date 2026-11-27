// Setinha no canto para minimizar um card ou painel. Fechado, fica só o título (e um resumo).
// O que a pessoa fechou fica guardado neste aparelho (localStorage); se não der pra guardar,
// funciona igual, só não lembra depois.
import { useState, type ReactNode } from "react";
import { useCtx } from "../contexto";

const CHAVE = "painel_recolhidos";

function lerRecolhidos(): string[] {
  try { return JSON.parse(localStorage.getItem(CHAVE) ?? "[]"); } catch { return []; }
}

export function useRecolhido(id: string): [boolean, () => void] {
  const [fechado, setFechado] = useState(() => lerRecolhidos().includes(id));
  function alternar() {
    const novo = !fechado;
    setFechado(novo);
    try {
      const resto = lerRecolhidos().filter((x) => x !== id);
      localStorage.setItem(CHAVE, JSON.stringify(novo ? [...resto, id] : resto));
    } catch { /* sem storage: só não lembra */ }
  }
  return [fechado, alternar];
}

export function Seta({ aberto, alternar, nome }: { aberto: boolean; alternar: () => void; nome: string }) {
  return (
    <button type="button" className={`seta${aberto ? "" : " fechada"}`} onClick={alternar}
      aria-expanded={aberto} aria-label={`${aberto ? "Minimizar" : "Abrir"} ${nome}`} title={aberto ? "Minimizar" : "Abrir"}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
    </button>
  );
}

/** Painel de baixo com setinha. `chaves`: caixinhas (c.aberto) que, se abertas, mostram o painel
 *  mesmo minimizado — assim o "+" e o lápis dos cards do topo sempre acham o formulário. */
export function Secao({ id, titulo, resumo, chaves = [], children }: {
  id: string; titulo: ReactNode; resumo?: string; chaves?: string[]; children: ReactNode;
}) {
  const c = useCtx();
  const [fechado, alternar] = useRecolhido(id);
  const forcado = !!c.aberto && chaves.some((p) => c.aberto!.startsWith(p));
  const aberto = !fechado || forcado;
  return (
    <section className={`card panel on${aberto ? "" : " fechado"}`}>
      <div className="sec-cab">
        <div><h2>{titulo}</h2>{!aberto && resumo && <p className="sec-resumo">{resumo}</p>}</div>
        <Seta aberto={aberto} alternar={alternar} nome={typeof titulo === "string" ? titulo : "painel"} />
      </div>
      {aberto && children}
    </section>
  );
}
