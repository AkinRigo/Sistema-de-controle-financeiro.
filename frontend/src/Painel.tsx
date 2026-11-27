import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Usuario } from "./api";
import { Contexto, type Ctx, type Dados } from "./contexto";
import { Bancos } from "./componentes/Bancos";
import { Categorias } from "./componentes/Categorias";
import { Contas } from "./componentes/Contas";
import { Corridas } from "./componentes/Corridas";
import { Ganhos } from "./componentes/Ganhos";
import { ResumoTopo } from "./componentes/ResumoTopo";
import { Graficos } from "./componentes/Graficos";
import { Voz } from "./componentes/Voz";
import { Admin } from "./componentes/Admin";
import { LogoLinha } from "./componentes/Logo";
import { Rodape } from "./componentes/Rodape";
import { HOJE, MES_ATUAL, dinheiro, maiuscula, mesCompleto, nomeMes, somarMes } from "./util";

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
  // O resumo vem primeiro: ele gera os ganhos das rendas fixas até este mês,
  // e a lista de ganhos (pedida depois) já chega com eles.
  const resumo = await api.resumo(mes);
  const [usuario, contas, bancos, ganhos, rendas, corridas, categorias] = await Promise.all([
    api.eu(), api.contas(), api.bancos(), api.ganhosDoMes(mes), api.rendas(), api.corridas(mes), api.categorias(mes),
  ]);
  return { usuario, contas, bancos, ganhos, rendas, corridas, resumo, categorias };
}

export function Painel({ usuario, aoSair }: { usuario: Usuario; aoSair: () => void }) {
  const [mes, setMesBruto] = useState(MES_ATUAL);
  const [dados, setDados] = useState<Dados | null>(null);
  const [erroCarga, setErroCarga] = useState("");
  const [vista, setVista] = useState<Vista>("bills");
  const [tela, setTela] = useState<"painel" | "admin" | "graficos">("painel");
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
    // O backend reconhece o formato (este painel ou o antigo) e faz a conversão.
    let conteudo: unknown;
    try { conteudo = JSON.parse(await arquivo.text()); }
    catch { toast("Esse arquivo não parece um backup do painel."); return; }
    try {
      const r = await api.importar(conteudo);
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
  const vazio = !dados.contas.length && !dados.bancos.length && !dados.ganhos.length && !dados.rendas.length;
  const abertas = r.abertas.length;
  const ligado = dados.corridas.contar_na_previsao;

  // Dos cards do topo: abre a aba, a caixinha (editar/excluir) e rola até ela.
  const irPara = (v: Vista, chave?: string) => {
    setVista(v); setAberto(chave ?? null);
    setTimeout(() => document.getElementById("secoes")?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  const vistas: [Vista, string, string][] = [
    ["bills", `Contas de ${nm}`, abertas ? `${dinheiro(r.falta_pagar)} em aberto` : "tudo pago"],
    ["incomes", `Ganhos de ${nm}`, `${dinheiro(r.recebido)} recebido`],
    ["accounts", "Bancos", dinheiro(r.tenho)],
    ["debts", "Por categoria", `${dinheiro(r.divida_total)} devo`],
    ["sim", "Corridas", ligado ? `${dinheiro(r.corridas)} previsto` : "fora da previsão"],
  ];

  const ctx: Ctx = {
    dados, mes, setMes, executar, toast, aberto, abrir: setAberto, ultimoBanco, setUltimoBanco,
  };

  return (
    <Contexto.Provider value={ctx}>
      <header className="strip">
        <div className="marca"><h1 style={{ margin: 0, lineHeight: 0 }}><LogoLinha /></h1><div className="save">Conectado como {dados.usuario.nome || usuario.nome}</div></div>
        <div className="nav">
          {tela !== "admin" && (<>
            <button className="sbtn" onClick={() => setMes(somarMes(mes, -1))} aria-label="Mês anterior">‹</button>
            <div className="mon">{maiuscula(mesCompleto(mes))}</div>
            <button className="sbtn" onClick={() => setMes(somarMes(mes, 1))} aria-label="Próximo mês">›</button>
            {mes !== MES_ATUAL && <button className="sbtn" onClick={() => setMes(MES_ATUAL)}>Hoje</button>}
          </>)}
          <button className={`sbtn ${tela === "graficos" ? "on" : ""}`} onClick={() => { setTela(tela === "graficos" ? "painel" : "graficos"); scrollTo(0, 0); }}>
            {tela === "graficos" ? "Meu painel" : <><svg className="sbtn-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true"><path d="M5 20V11M12 20V5M19 20v-6" /></svg>Gráficos</>}
          </button>
          {dados.usuario.admin && (
            <button className={`sbtn ${tela === "admin" ? "on" : ""}`} onClick={() => setTela(tela === "admin" ? "painel" : "admin")}>
              {tela === "admin" ? "Meu painel" : "Admin"}
            </button>
          )}
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

      {tela === "admin" ? (
        <main className="wrap"><Admin toast={toast} /></main>
      ) : tela === "graficos" ? (
        <main className="wrap"><Graficos irPara={(v, chave) => { setTela("painel"); irPara(v, chave); }} /></main>
      ) : (
      <main className="wrap">
        {vazio && (
          <section className="welcome">
            <h2>Boas-vindas ao No Corre das Notas, {dados.usuario.nome.split(" ")[0]}!</h2>
            <p className="welcome-lead">Descubra para onde vão as suas notas. Escolha como começar:</p>
            <div className="welcome-opcoes">
              <div className="welcome-opcao">
                <b>Já controlava em outro lugar?</b>
                <span>Traga tudo de uma vez com o arquivo de backup (.json).</span>
                <button className="btn pri" onClick={escolherArquivo}>Importar meus dados</button>
              </div>
              <div className="welcome-opcao">
                <b>Começando do zero?</b>
                <span>Cadastre seus bancos e as contas do mês. Leva poucos minutos.</span>
                <div className="welcome-botoes">
                  <button className="btn" onClick={() => { setVista("accounts"); setAberto(null); }}>Cadastrar bancos</button>
                  <button className="btn" onClick={() => { setVista("bills"); setAberto(null); }}>Adicionar contas</button>
                </div>
              </div>
            </div>
          </section>
        )}

        <ResumoTopo irPara={irPara} />

        <nav className="sect" id="secoes" aria-label="Seções">
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
      )}
      {tela !== "admin" && <Voz />}
      <Rodape />
      <div className={`toast ${toastVisivel ? "show" : ""}`} role="status">{toastTexto}</div>
    </Contexto.Provider>
  );
}
