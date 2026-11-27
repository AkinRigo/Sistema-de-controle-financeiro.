// Comando de voz: o navegador transcreve, o backend entende e confere, a pessoa confirma.
// A tela não decide nada: mostra a proposta do backend e chama as rotas que já existem.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type ItemVoz, type PropostaVoz } from "../api";
import { bancoPadrao, useCtx, type Ctx } from "../contexto";
import { dataCurta, dinheiro, mesCompleto, nomeMes } from "../util";
import { OpcoesBanco } from "./comuns";

// ---------------- reconhecimento de fala (Web Speech API) ----------------
interface Resultado { isFinal: boolean; 0: { transcript: string } }
interface Reconhecedor {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: ((e: { results: ArrayLike<Resultado> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; stop(): void;
}
type Construtor = new () => Reconhecedor;
const janela = window as unknown as { SpeechRecognition?: Construtor; webkitSpeechRecognition?: Construtor };
const Reconhecimento = janela.SpeechRecognition ?? janela.webkitSpeechRecognition;

const ERROS: Record<string, string> = {
  "not-allowed": "O navegador bloqueou o microfone. Clique no cadeado da barra de endereço e permita o microfone.",
  "no-speech": "Não ouvi nada. Tenta de novo, mais perto do microfone.",
  "audio-capture": "Não achei nenhum microfone ligado.",
  network: "Sem conexão com o serviço de voz do navegador.",
};

// ---------------- cada ação: o que mostrar e o que fazer ao confirmar ----------------
type Linha = [rotulo: string, valor: ReactNode];
interface Extra { banco: string; nome: string; marcados: string[] }
type Botao = [rotulo: string, executar: (p: PropostaVoz, c: Ctx) => Promise<boolean>];
interface Acao {
  titulo: string;
  usaBanco?: string; // rótulo do seletor de banco (pagar/receber)
  usaNome?: string; // rótulo do campo de nome editável
  perigo?: boolean; // apagar: botão vermelho "Apagar"
  varios?: boolean; // com opções, marca várias (apagar ganhos) em vez de escolher uma
  botoes?: (p: PropostaVoz) => Botao[] | null; // em vez de "Confirmar" (apagar conta de todo mês)
  linhas: (p: PropostaVoz) => Linha[];
  executar: (p: PropostaVoz, c: Ctx, x: Extra) => Promise<boolean>;
}
const tipoTexto = (p: PropostaVoz) =>
  p.tipo_conta === "fixa" ? "todo mês" : p.tipo_conta === "parcelada" ? `${p.parcelas}x de ${dinheiro(p.valor)}` : "uma vez";
const nomeBanco = (c: Ctx, id: string) => c.dados.bancos.find((b) => b.id === id)?.nome;

const ACOES: Partial<Record<PropostaVoz["acao"], Acao>> = {
  pagar_conta: {
    titulo: "Pagar conta", usaBanco: "Saiu de",
    linhas: (p) => [["Conta", p.item?.nome], ["Valor", dinheiro(p.valor)]],
    executar: (p, c, x) => c.executar(
      () => api.pagar({ conta_id: p.item!.conta_id!, mes_conta: p.item!.mes_conta!, valor_pago: p.valor!, banco_id: x.banco || null }),
      `${p.item!.nome} paga${nomeBanco(c, x.banco) ? `: ${dinheiro(p.valor)} saiu do ${nomeBanco(c, x.banco)}` : ""}.`),
  },
  desfazer_pagamento: {
    titulo: "Desfazer pagamento",
    linhas: (p) => [["Conta", p.item?.nome], ["Valor pago", dinheiro(p.valor)], ["Efeito", "volta pra “Falta pagar” e o dinheiro volta pro banco"]],
    executar: (p, c) => c.executar(() => api.desfazerPagamento(p.item!.id), `Pagamento de ${p.item!.nome} desfeito.`),
  },
  receber_ganho: {
    titulo: "Marcar como recebido", usaBanco: "Caiu em",
    linhas: (p) => [["Ganho", p.item?.nome], ["Valor", dinheiro(p.valor)]],
    executar: (p, c, x) => c.executar(() => api.receberGanho(p.item!.id, p.valor!, x.banco || null, c.mes),
      nomeBanco(c, x.banco) ? `${dinheiro(p.valor)} somado ao ${nomeBanco(c, x.banco)}.` : `${p.item!.nome} recebido.`),
  },
  novo_ganho: {
    titulo: "Novo ganho (vai entrar)", usaNome: "De onde vem",
    linhas: (p) => [["Valor", dinheiro(p.valor)], ["Quando", p.data ? dataCurta(p.data) : "hoje"]],
    executar: (p, c, x) => c.executar(() => api.criarGanho({ nome: x.nome, valor: p.valor!, data: p.data!, recebido: false, banco_id: null }),
      `${x.nome}: ${dinheiro(p.valor)} vai entrar.`),
  },
  nova_conta: {
    titulo: "Nova conta", usaNome: "Nome",
    linhas: (p) => [["Valor", tipoTexto(p)], ["Vence", p.dia ? `dia ${p.dia}` : "sem dia"],
      ["Começa", p.mes_inicio ? mesCompleto(p.mes_inicio) : ""], ["Categoria", "automática"]],
    executar: (p, c, x) => c.executar(() => api.criarConta({
      nome: x.nome, valor: p.valor!, tipo: p.tipo_conta || "unica", mes_inicio: p.mes_inicio!, mes_fim: null, categoria: "",
      credor: null, dia_vencimento: p.dia, parcela_inicial: null, total_parcelas: p.parcelas, juros_altos: false, incerto: false,
      mes_referencia: p.mes_inicio, parcela_no_mes: p.tipo_conta === "parcelada" ? 1 : null,
    }), `${x.nome} cadastrada.`),
  },
  novo_banco: {
    titulo: "Novo banco", usaNome: "Banco",
    linhas: (p) => [["Saldo agora", dinheiro(p.valor)]],
    executar: (p, c, x) => c.executar(() => api.criarBanco(x.nome, p.valor!), `${x.nome} adicionado.`),
  },
  somar_banco: {
    titulo: "Somar ao saldo do banco",
    linhas: (p) => [["Banco", p.banco?.nome], ["Somar", `+ ${dinheiro(p.valor)}`], ["Saldo fica", dinheiro(p.saldo_novo)]],
    executar: (p, c) => c.executar(() => api.editarBanco(p.banco!.id, p.banco!.nome, p.saldo_novo!), `${dinheiro(p.valor)} somado ao ${p.banco!.nome}.`),
  },
  ajustar_saldo: {
    titulo: "Ajustar saldo do banco",
    linhas: (p) => [["Banco", p.banco?.nome], ["Era", dinheiro(p.banco?.saldo)], ["Fica", dinheiro(p.saldo_novo)]],
    executar: (p, c) => c.executar(() => api.editarBanco(p.banco!.id, p.banco!.nome, p.saldo_novo!), `Saldo do ${p.banco!.nome} ajustado.`),
  },
  transferir: {
    titulo: "Transferir entre bancos",
    linhas: (p) => [["De", p.banco?.nome], ["Para", p.banco_destino?.nome], ["Valor", dinheiro(p.valor)]],
    executar: (p, c) => c.executar(() => api.transferir(p.banco!.id, p.banco_destino!.id, p.valor!),
      `${dinheiro(p.valor)} passou do ${p.banco!.nome} pro ${p.banco_destino!.nome}.`),
  },
  // ---- editar: só muda o que o backend mandou; o resto fica como está ----
  editar_conta: {
    titulo: "Editar conta",
    linhas: (p) => mudancas([["Conta", p.item?.nome], ["Valor fica", p.valor && dinheiro(p.valor)],
      ["Vence", p.dia ? `dia ${p.dia}` : null], ["Nome novo", p.nome]]),
    executar: (p, c) => {
      const b = c.dados.contas.find((x) => x.id === p.item!.id);
      if (!b) { c.toast("Não achei essa conta."); return Promise.resolve(false); }
      return c.executar(() => api.editarConta(b.id, {
        nome: p.nome || b.nome, valor: p.valor ?? b.valor, tipo: b.tipo, mes_inicio: b.mes_inicio, categoria: b.categoria,
        credor: b.credor, dia_vencimento: p.dia || b.dia_vencimento, mes_fim: b.mes_fim, parcela_inicial: b.parcela_inicial,
        total_parcelas: b.total_parcelas, juros_altos: b.juros_altos, incerto: b.incerto,
      }), `${p.nome || b.nome} atualizada.`);
    },
  },
  editar_ganho: {
    titulo: "Editar ganho",
    linhas: (p) => mudancas([["Ganho", p.item?.nome], ["Valor fica", p.valor && dinheiro(p.valor)],
      ["Entra em", p.data && dataCurta(p.data)], ["Nome novo", p.nome]]),
    executar: (p, c) => {
      const g = c.dados.ganhos.find((x) => x.id === p.item!.id);
      if (!g) { c.toast("Não achei esse ganho."); return Promise.resolve(false); }
      return c.executar(() => api.editarGanho(g.id, { nome: p.nome || g.nome, valor: p.valor ?? g.valor,
        data: p.data ?? g.data, recebido: g.recebido, banco_id: g.banco_id }), `${p.nome || g.nome} atualizado.`);
    },
  },
  editar_banco: {
    titulo: "Editar banco",
    linhas: (p) => [["Banco", p.banco?.nome], ["Nome novo", p.nome], ["Saldo", `${dinheiro(p.banco?.saldo)} (não muda)`]],
    executar: (p, c) => c.executar(() => api.editarBanco(p.banco!.id, p.nome, p.banco!.saldo), `${p.banco!.nome} agora é ${p.nome}.`),
  },
  // ---- apagar: sempre pede confirmação, botão vermelho ----
  apagar_conta: {
    titulo: "Apagar conta", perigo: true,
    linhas: (p) => [["Conta", p.item?.nome], ["Valor", dinheiro(p.item?.valor)],
      ["Efeito", p.item?.continua ? "é de todo mês: escolha abaixo" : "some do app, com o histórico. Não dá pra desfazer."]],
    botoes: (p) => p.item?.continua && p.parar_em ? [
      [`Parar a partir de ${nomeMes(p.parar_em)}`, (p, c) => c.executar(() => api.pararConta(p.item!.id, p.parar_em!),
        `${p.item!.nome} não aparece mais a partir de ${mesCompleto(p.parar_em!)}.`)],
      ["Apagar de vez", (p, c) => c.executar(() => api.excluirConta(p.item!.id), `${p.item!.nome} apagada.`)],
    ] : null,
    executar: (p, c) => c.executar(() => api.excluirConta(p.item!.id), `${p.item!.nome} apagada.`),
  },
  apagar_ganho: {
    titulo: "Apagar ganho", perigo: true, varios: true,
    linhas: (p) => p.item ? [["Ganho", p.item.nome], ["Valor", dinheiro(p.item.valor)], ["Efeito", "sai de “Vai entrar”. Não dá pra desfazer."]] : [],
    executar: (p, c, x) => {
      const ids = p.item ? [p.item.id] : x.marcados;
      return c.executar(async () => { for (const id of ids) await api.excluirGanho(id); },
        ids.length > 1 ? `${ids.length} ganhos apagados.` : "Ganho apagado.");
    },
  },
  apagar_banco: {
    titulo: "Apagar banco", perigo: true,
    linhas: (p) => [["Banco", p.banco?.nome], ["Saldo", dinheiro(p.banco?.saldo)], ["Efeito", "sai de “Tenho nos bancos”. Não dá pra desfazer."]],
    executar: (p, c) => c.executar(() => api.excluirBanco(p.banco!.id), `${p.banco!.nome} apagado.`),
  },
};

/** Só as linhas que têm valor (no editar, o que não muda não aparece). */
function mudancas(linhas: [string, ReactNode][]): Linha[] {
  return linhas.filter(([, v]) => v !== null && v !== undefined && v !== "" && v !== false) as Linha[];
}

// Uma fase de cada vez: a tela mostra só o que é da fase atual.
type Fase =
  | { tipo: "fechado" }
  | { tipo: "ouvindo" }
  | { tipo: "entendendo" }
  | { tipo: "proposta"; p: PropostaVoz }
  | { tipo: "erro"; msg: string };

export function Voz() {
  const c = useCtx();
  const [fase, setFase] = useState<Fase>({ tipo: "fechado" });
  const [texto, setTexto] = useState("");
  const [extra, setExtra] = useState<Extra>({ banco: "", nome: "", marcados: [] });
  const [salvando, setSalvando] = useState(false);
  const rec = useRef<Reconhecedor | null>(null);
  const ultimo = useRef("");

  function mostrar(p: PropostaVoz) {
    setExtra({ banco: p.banco?.id ?? bancoPadrao(c), nome: p.nome, marcados: p.opcoes.map((o) => o.id) });
    setFase({ tipo: "proposta", p });
  }

  async function enviar(frase: string) {
    if (!frase.trim()) { setFase({ tipo: "erro", msg: ERROS["no-speech"] }); return; }
    setFase({ tipo: "entendendo" });
    try {
      mostrar(await api.entenderVoz(frase.trim(), c.mes));
    } catch (e) {
      setFase({ tipo: "erro", msg: e instanceof Error ? e.message : "Não deu pra entender agora." });
    }
  }

  function ouvir() {
    setTexto(""); ultimo.current = "";
    if (!Reconhecimento) { setFase({ tipo: "erro", msg: "Este navegador não transcreve fala. Use o Chrome, ou digite abaixo." }); return; }
    const r = new Reconhecimento();
    r.lang = "pt-BR"; r.interimResults = true; r.continuous = false;
    r.onresult = (e) => {
      let t = "";
      for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
      setTexto(t); ultimo.current = t;
    };
    let falhou = false;
    r.onerror = (e) => { falhou = true; setFase({ tipo: "erro", msg: ERROS[e.error] ?? `Deu erro no microfone (${e.error}).` }); };
    r.onend = () => { if (!falhou) enviar(ultimo.current); }; // parou de falar: manda pro backend
    rec.current = r; r.start(); setFase({ tipo: "ouvindo" });
  }

  function fechar() { rec.current?.stop(); rec.current = null; setFase({ tipo: "fechado" }); }
  useEffect(() => () => rec.current?.stop(), []);

  // escolheu uma das opções ("qual cartão?"): vira o item. Pagar/receber usam o valor dele;
  // no editar, o valor é o NOVO que a pessoa falou.
  function escolher(p: PropostaVoz, o: ItemVoz) {
    mostrar({ ...p, item: o, opcoes: [], valor: p.acao.startsWith("editar") ? p.valor : o.valor });
  }

  async function rodar(fn: () => Promise<boolean>) {
    setSalvando(true);
    const ok = await fn();
    setSalvando(false);
    if (ok) fechar();
  }
  const confirmar = (p: PropostaVoz, acao: Acao) => rodar(() => acao.executar(p, c, { ...extra, nome: extra.nome.trim() || p.nome }));
  const alternar = (id: string) => setExtra({ ...extra,
    marcados: extra.marcados.includes(id) ? extra.marcados.filter((m) => m !== id) : [...extra.marcados, id] });

  const p = fase.tipo === "proposta" ? fase.p : null;
  const tabela = p && p.acao !== "nao_entendi" ? ACOES[p.acao] : undefined;
  const marcar = !!(p && tabela?.varios && p.opcoes.length); // apagar vários: caixinhas
  const acao = p && tabela && (!p.opcoes.length || marcar) ? tabela : undefined;
  const botoes = p && acao?.botoes?.(p);
  const titulo = { fechado: "", ouvindo: "Tô ouvindo…", entendendo: "Entendendo…", erro: "Opa",
    proposta: marcar ? p!.mensagem || "Apagar estes?" : p?.opcoes.length ? "Qual destes?" : acao ? "Confere pra mim?" : "Olha só" }[fase.tipo];
  const podeDigitar = fase.tipo === "erro" || (!!p && !acao && !p.opcoes.length);

  return (
    <>
      <button className="voz-mic" type="button" onClick={ouvir} aria-label="Falar um comando">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
      </button>
      {fase.tipo !== "fechado" && (
        <>
          <div className="voz-veu" onClick={fechar} />
          <div className="voz-folha" role="dialog" aria-modal="true" aria-label="Comando de voz">
            <p className="voz-estado">{titulo}</p>
            {(fase.tipo === "ouvindo" || fase.tipo === "entendendo") && <div className="voz-ondas" aria-hidden="true"><i /><i /><i /><i /><i /></div>}
            <div className="voz-fala"><small>Você disse</small>{texto || (fase.tipo === "ouvindo" ? "fale agora…" : "—")}</div>

            {p && p.opcoes.length > 0 && !marcar && (
              <div className="voz-opcoes">
                {p.opcoes.map((o) => (
                  <button key={o.id} type="button" onClick={() => escolher(p, o)}><span>{o.nome}</span><b>{dinheiro(o.valor)}</b></button>
                ))}
              </div>
            )}

            {p && acao && (
              <div className="voz-cartao">
                <span className="voz-acao">{acao.titulo}</span>
                {marcar && (
                  <div className="voz-marcar">
                    {p.opcoes.map((o) => (
                      <label key={o.id}><input type="checkbox" checked={extra.marcados.includes(o.id)} onChange={() => alternar(o.id)} />
                        <span>{o.nome}</span><b>{dinheiro(o.valor)}</b></label>
                    ))}
                  </div>
                )}
                <dl>
                  {acao.usaNome && (
                    <div><dt>{acao.usaNome}</dt><dd><input value={extra.nome} maxLength={120} aria-label={acao.usaNome}
                      onChange={(e) => setExtra({ ...extra, nome: e.target.value })} /></dd></div>
                  )}
                  {acao.linhas(p).map(([rotulo, valor]) => <div key={rotulo}><dt>{rotulo}</dt><dd>{valor}</dd></div>)}
                  {acao.usaBanco && c.dados.bancos.length > 0 && (
                    <div><dt>{acao.usaBanco}</dt><dd>
                      <select value={extra.banco} onChange={(e) => setExtra({ ...extra, banco: e.target.value })} aria-label="Banco"><OpcoesBanco /></select>
                    </dd></div>
                  )}
                </dl>
              </div>
            )}

            {p && !acao && !p.opcoes.length && <p className="voz-msg">{p.mensagem || "Não entendi direito. Fala de novo ou digite abaixo."}</p>}
            {fase.tipo === "erro" && <p className="voz-erro">{fase.msg}</p>}

            {podeDigitar && (
              <form className="voz-digitar" onSubmit={(e) => { e.preventDefault(); const t = String(new FormData(e.currentTarget).get("frase") ?? ""); setTexto(t); enviar(t); }}>
                <input name="frase" placeholder="ou digite o comando" aria-label="Digitar comando" />
                <button className="btn">Enviar</button>
              </form>
            )}

            <div className="voz-botoes">
              <button className="btn" onClick={fechar}>{acao ? "Cancelar" : "Fechar"}</button>
              {p && acao && botoes
                ? botoes.map(([rotulo, fn], i) => (
                  <button key={rotulo} className={`btn ${i === botoes.length - 1 ? "perigo" : "pri"}`} disabled={salvando} onClick={() => rodar(() => fn(p, c))}>{rotulo}</button>
                ))
                : p && acao
                ? <button className={`btn ${acao.perigo ? "perigo" : "pri"}`} disabled={salvando || (marcar && !extra.marcados.length)} onClick={() => confirmar(p, acao)}>
                    {salvando ? "Salvando…" : acao.perigo ? (marcar ? `Apagar ${extra.marcados.length}` : "Apagar") : "Confirmar"}
                  </button>
                : <button className="btn pri" onClick={ouvir} disabled={fase.tipo === "ouvindo" || fase.tipo === "entendendo"}>Falar de novo</button>}
            </div>
          </div>
        </>
      )}
    </>
  );
}
