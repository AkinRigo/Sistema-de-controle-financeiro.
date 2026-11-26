import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Usuario } from "./api";
import { Contexto, type Ctx, type Dados } from "./contexto";
import { converterBackup } from "./importar";
import { Bancos } from "./componentes/Bancos";
import { Categorias, dividaTotal } from "./componentes/Categorias";
import { Contas } from "./componentes/Contas";
import { Corridas } from "./componentes/Corridas";
import { Ganhos } from "./componentes/Ganhos";
import { HOJE, MES_ATUAL, dinheiro, maiuscula, mesCompleto, nomeMes, num, somarMes } from "./util";

type Vista = "bills" | "incomes" | "accounts" | "debts" | "sim";
type Tema = "auto" | "light" | "dark";
const CHAVE_TEMA = "painel_tema";

function lerTema(): Tema {
  try { const t = localStorage.getItem(CHAVE_TEMA); return t === "light" || t === "dark" ? t : "auto"; } catch { return "auto"; }
}
function aplicarTema(t: Tema) {
  if (t === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = t;
  try { localStorage.setItem(CHAVE_TEMA, t); } catch { /* sem storage */ }
}

async function carregar(mes: string): Promise<Dados> {
  const [usuario, contas, bancos, ganhos, corridas, resumo, categorias] = await Promise.all([
    api.eu(), api.contas(), api.bancos(), api.ganhos(), api.corridas(), api.resumo(mes), api.categorias(mes),
  ]);
  return { usuario, contas, bancos, ganhos, corridas, resumo, categorias };
}

export function Painel({ usuario, aoSair }: { usuario: Usuario; aoSair: () => void }) {
  const [mes, setMesBruto] = useState(MES_ATUAL);
  const [dados, setDados] = useState<Dados | null>(null);
  const [erroCarga, setErroCarga] = useState("");
  const [vista, setVista] = useState<Vista>("bills");
  const [aberto, setAberto] = useState<string | null>(null);
  const [ultimoBanco, setUltimoBanco] = useState("");
  const [tema, setTema] = useState<Tema>(lerTema);
  const [toastTexto, setToastTexto] = useState("");
  const [toastVisivel, setToastVisivel] = useState(false);
  const [confirmaApagar, setConfirmaApagar] = useState(false);
  const toastTimer = useRef<number>();
  const menuRef = useRef<HTMLDetailsElement>(null);
  const arquivoRef = useRef<HTMLInputElement>(null);
  const mesRef = useRef(mes);
  mesRef.current = mes;

  useEffect(() => aplicarTema(tema), [tema]);

  const recarregar = useCallback(async () => {
    try { setDados(await carregar(mesRef.current)); setErroCarga(""); }
    catch (e) { setErroCarga((e as Error).message); }
  }, []);

  useEffect(() => { recarregar(); }, [mes, recarregar]);

  const toast = useCallback((t: string) => {
    setToastTexto(t); setToastVisivel(true);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToastVisivel(false), 3800);
  }, []);

  const executar = useCallback(async (acao: () => Promise<unknown>, mensagem?: string) => {
    try {
      await acao();
      setAberto(null);
      await recarregar();
      if (mensagem) toast(mensagem);
      return true;
    } catch (e) {
      toast((e as Error).message);
      return false;
    }
  }, [recarregar, toast]);

  const setMes = (m: string) => { setAberto(null); setMesBruto(m); };
  const fecharMenu = () => { if (menuRef.current) menuRef.current.open = false; };

  async function fazerBackup() {
    fecharMenu();
    try {
      const dadosBackup = await api.exportar();
      const blob = new Blob([JSON.stringify(dadosBackup, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `painel-financeiro-${HOJE}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      toast("Backup salvo.");
    } catch (e) { toast((e as Error).message); }
  }

  function escolherArquivo() { fecharMenu(); arquivoRef.current?.click(); }

  async function importarArquivo(arquivo: File) {
    let convertido: unknown;
    try { convertido = converterBackup(JSON.parse(await arquivo.text())); }
    catch { toast("Esse arquivo não parece um backup do painel."); return; }
    try {
      const r = await api.importar(convertido);
      setMesBruto(MES_ATUAL); setAberto(null);
      await recarregar();
      toast(`Importado: ${r.contas} contas, ${r.ganhos} ganhos, ${r.bancos} bancos.`);
    } catch (e) { toast((e as Error).message); }
  }

  async function apagarTudo() {
    setConfirmaApagar(false); fecharMenu();
    await executar(() => api.importar({ version: 2, since: MES_ATUAL }), "Tudo apagado.");
  }

  if (!dados) {
    return <div className="loading">{erroCarga ? `Não deu para carregar: ${erroCarga}` : "Carregando…"}</div>;
  }

  const r = dados.resumo;
  const nm = nomeMes(mes);
  const vazio = !dados.contas.length && !dados.bancos.length && !dados.ganhos.length;
  const sobra = num(r.sobra), falta = num(r.falta_pagar);
  const entra = num(r.tenho) + num(r.vai_entrar) + num(r.corridas);
  const pct = falta ? Math.min(100, Math.round((entra / falta) * 100)) : 100;
  const abertas = r.abertas.length, atrasadas = r.abertas.filter((a) => a.atrasada).length;
  const ligado = dados.corridas.contar_na_previsao;

  const vistas: [Vista, string, string][] = [
    ["bills", `Contas de ${nm}`, abertas ? `${dinheiro(r.falta_pagar)} em aberto` : "tudo pago"],
    ["incomes", `Ganhos de ${nm}`, `${dinheiro(r.recebido)} recebido`],
    ["accounts", "Bancos", dinheiro(r.tenho)],
    ["debts", "Por categoria", `${dinheiro(dividaTotal(dados.categorias))} devo`],
    ["sim", "Corridas", ligado ? `${dinheiro(r.corridas)} previsto` : "fora da previsão"],
  ];

  const ctx: Ctx = {
    dados, mes, setMes, executar, toast, aberto, abrir: setAberto, ultimoBanco, setUltimoBanco,
  };

  return (
    <Contexto.Provider value={ctx}>
      <header className="strip">
        <div><h1>Painel Financeiro</h1><div className="save">Conectado como {dados.usuario.nome || usuario.nome}</div></div>
        <div className="nav">
          <button className="sbtn" onClick={() => setMes(somarMes(mes, -1))} aria-label="Mês anterior">‹</button>
          <div className="mon">{maiuscula(mesCompleto(mes))}</div>
          <button className="sbtn" onClick={() => setMes(somarMes(mes, 1))} aria-label="Próximo mês">›</button>
          {mes !== MES_ATUAL && <button className="sbtn" onClick={() => setMes(MES_ATUAL)}>Hoje</button>}
          <details className="menu" ref={menuRef}>
            <summary className="sbtn" style={{ display: "flex", alignItems: "center" }}>Dados ▾</summary>
            <div className="pop">
              <button onClick={fazerBackup}>Fazer backup (JSON)</button>
              <button onClick={escolherArquivo}>Importar backup</button>
              <button onClick={() => setTema({ auto: "dark", dark: "light", light: "auto" }[tema] as Tema)}>
                Tema: {{ auto: "automático", light: "claro", dark: "escuro" }[tema]}
              </button>
              <button onClick={aoSair}>Sair</button>
              <button style={{ color: "var(--red)" }} onClick={() => setConfirmaApagar(true)}>Apagar todos os dados…</button>
              {confirmaApagar && (
                <div style={{ padding: 8, fontSize: 14 }}>
                  Isso apaga tudo. Fez backup?
                  <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                    <button className="btn danger" onClick={apagarTudo}>Apagar</button>
                    <button className="btn" onClick={() => setConfirmaApagar(false)}>Cancelar</button>
                  </div>
                </div>
              )}
            </div>
          </details>
          <input type="file" ref={arquivoRef} accept=".json,application/json" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) importarArquivo(f); }} />
        </div>
      </header>

      <main className="wrap">
        {vazio && (
          <section className="welcome">
            <h2>Vamos começar</h2>
            <p>Este painel é novo e ainda está vazio. Para trazer o que você já tinha:</p>
            <ol>
              <li>Abra o painel antigo (o arquivo <b>Painel_Financeiro_Mensal_Dividas.html</b>) ou o protótipo.</li>
              <li>Clique em <b>Backup JSON</b> lá em cima. Ele baixa um arquivo <b>.json</b>.</li>
              <li>Volte aqui e clique no botão abaixo para escolher esse arquivo.</li>
            </ol>
            <button className="btn pri" onClick={escolherArquivo}>Importar backup do painel antigo</button>
            <span className="hint" style={{ marginLeft: 10 }}>ou cadastre seus bancos e contas do zero, logo abaixo.</span>
          </section>
        )}

        <section className="hero">
          <div>
            {vazio ? (<>
              <div className="big">Nenhum dado ainda</div>
              <p className="sub">Importe o backup do painel antigo ou cadastre seus bancos e contas.</p>
            </>) : sobra >= 0 ? (<>
              <div className="big">Sobram <span className="pos">{dinheiro(sobra)}</span> no fim de {nm}</div>
              <p className="sub">{falta ? "Se tudo que está previsto entrar, entrar, dá para pagar todas as contas em aberto." : "Nenhuma conta em aberto neste mês."}</p>
            </>) : (<>
              <div className="big">Faltam <span className="neg">{dinheiro(-sobra)}</span> para fechar {nm}</div>
              <p className="sub">O dinheiro que você tem e espera receber não cobre as {abertas} contas em aberto. Veja abaixo o que pagar primeiro.</p>
            </>)}
            <div className={`meter ${pct < 100 ? "short" : ""}`}><i style={{ width: `${Math.max(0, pct)}%` }} /></div>
            <div className="meter-note">{falta ? `Seu dinheiro cobre ${Math.max(0, pct)}% das contas em aberto.` : ""}</div>
          </div>
          <div className="eq">
            <div><span className="op" /><span>Tenho nos bancos <small>{mes < MES_ATUAL ? "saldo de hoje" : "soma dos bancos, hoje"}</small></span><b>{dinheiro(r.tenho)}</b></div>
            <div><span className="op">+</span><span>Vai entrar <small>ganhos marcados como “vai entrar”</small></span><b>{dinheiro(r.vai_entrar)}</b></div>
            {ligado && (
              <div><span className="op">+</span><span>Corridas (estimativa) <small>{mes === MES_ATUAL ? "dias que faltam no mês" : "mês inteiro"}</small></span><b>{dinheiro(r.corridas)}</b></div>
            )}
            <div>
              <span className="op">−</span>
              <span>Falta pagar <small>{abertas} conta{abertas === 1 ? "" : "s"}{atrasadas ? `, ${atrasadas} atrasada${atrasadas > 1 ? "s" : ""} de meses anteriores` : ""}</small></span>
              <b>{dinheiro(r.falta_pagar)}</b>
            </div>
            <div><span className="op">=</span><span>{sobra >= 0 ? "Sobra" : "Falta"}</span><b className={sobra >= 0 ? "pos" : "neg"}>{dinheiro(Math.abs(sobra))}</b></div>
          </div>
        </section>

        <nav className="sect" aria-label="Seções">
          {vistas.map(([k, l, v]) => (
            <button key={k} className={vista === k ? "on" : ""} onClick={() => { setVista(k); setAberto(null); }}>
              <span>{l}</span><b>{v}</b>
            </button>
          ))}
        </nav>

        {vista === "bills" && <Contas />}
        {vista === "incomes" && <Ganhos />}
        {vista === "accounts" && <Bancos />}
        {vista === "debts" && <Categorias />}
        {vista === "sim" && <Corridas key={mes} />}
      </main>
      <div className={`toast ${toastVisivel ? "show" : ""}`} role="status">{toastTexto}</div>
    </Contexto.Provider>
  );
}
