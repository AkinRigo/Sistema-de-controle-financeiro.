// Central de emergência do admin. Só exibe e envia: números, status, filtros e
// séries vêm prontos da API (/admin/*).
import { useCallback, useEffect, useState } from "react";
import { api, type AdminUsuario, type AdminUsuarios, type Evento, type Indicadores, type Logs } from "../api";

type Aba = "geral" | "usuarios" | "convite" | "logs";
type Metrica = "logins" | "cadastros" | "erros";

const NOMES_ABA: Record<Aba, string> = { geral: "Visão geral", usuarios: "Usuários", convite: "Convidar", logs: "Logs" };
const TAG_STATUS: Record<string, [string, string]> = {
  master: ["Admin master", ""], ativo: ["Ativo", "green"], nao_ativou: ["Não ativou o e-mail", "amber"],
  convidado: ["Convite enviado", ""], desativado: ["Desativado", "off"],
};
const TAG_NIVEL: Record<string, [string, string]> = { erro: ["Erro", "red"], aviso: ["Aviso", "amber"], info: ["Info", ""] };

export function Admin({ toast }: { toast: (t: string) => void }) {
  const [aba, setAba] = useState<Aba>("geral");
  const [filtroUsuarios, setFiltroUsuarios] = useState("todos");
  const [buscaUsuarios, setBuscaUsuarios] = useState("");
  const [nivel, setNivel] = useState("todos");
  const irPara = (a: Aba, extra?: () => void) => { extra?.(); setAba(a); };

  return (
    <section className="admin">
      <div>
        <h2 className="titulo-admin">Central de emergência</h2>
        <p className="hint">Só você vê. Quem se cadastra entra direto; aqui você resolve problemas, convida pessoas e acompanha o sistema.</p>
      </div>
      <div className="tabs" role="tablist">
        {(Object.keys(NOMES_ABA) as Aba[]).map((a) => (
          <button key={a} role="tab" aria-selected={aba === a} className={`tab aba-admin ${aba === a ? "on" : ""}`} onClick={() => setAba(a)}>{NOMES_ABA[a]}</button>
        ))}
      </div>
      {aba === "geral" && (
        <VisaoGeral
          irUsuarios={(f, b) => irPara("usuarios", () => { setFiltroUsuarios(f); setBuscaUsuarios(b ?? ""); })}
          irLogs={(n) => irPara("logs", () => setNivel(n))}
        />
      )}
      {aba === "usuarios" && (
        <Usuarios toast={toast} filtro={filtroUsuarios} setFiltro={setFiltroUsuarios} busca={buscaUsuarios} setBusca={setBuscaUsuarios} />
      )}
      {aba === "convite" && <Convite toast={toast} />}
      {aba === "logs" && <ListaLogs nivel={nivel} setNivel={setNivel} />}
    </section>
  );
}

// ---------------- visão geral ----------------

function VisaoGeral({ irUsuarios, irLogs }: { irUsuarios: (f: string, busca?: string) => void; irLogs: (nivel: string) => void }) {
  const [dias, setDias] = useState(14);
  const [metrica, setMetrica] = useState<Metrica>("logins");
  const [dados, setDados] = useState<Indicadores | null>(null);
  const [erro, setErro] = useState("");
  const [foco, setFoco] = useState<number | null>(null);

  useEffect(() => {
    api.admin.indicadores(dias).then((d) => { setDados(d); setErro(""); }).catch((e) => setErro((e as Error).message));
  }, [dias]);

  if (erro) return <p className="erro-admin">{erro}</p>;
  if (!dados) return <p className="empty">Carregando indicadores…</p>;

  const serie = dados[metrica];
  const topo = Math.max(4, Math.ceil(Math.max(...serie) / 2) * 2);
  const rotuloDia = (i: number) => { const atras = serie.length - 1 - i; return atras === 0 ? "hoje" : atras === 1 ? "ontem" : `há ${atras} dias`; };
  const unidade = { logins: "login", cadastros: "cadastro", erros: "erro" }[metrica];
  const dica = foco === null
    ? `Total no período: ${serie.reduce((a, b) => a + b, 0)} · passe o mouse nas barras`
    : `${rotuloDia(foco)}: ${serie[foco]} ${unidade}${serie[foco] === 1 ? "" : "s"}`;
  const variacao = dados.logins_7d_variacao;

  return (
    <>
      <div className="kpis">
        <button className="kpi" onClick={() => irUsuarios("ativo")}>
          <span>Usuários ativos</span><b>{dados.usuarios_ativos}</b><small>ver usuários →</small>
        </button>
        <button className="kpi" onClick={() => setMetrica("logins")}>
          <span>Logins nos últimos 7 dias</span><b>{dados.logins_7d}</b>
          <small className={variacao !== null && variacao >= 0 ? "pos" : variacao !== null ? "neg" : ""}>
            {variacao === null ? "sem semana anterior para comparar" : `${variacao >= 0 ? "↑" : "↓"} ${Math.abs(variacao)}% que a semana anterior`}
          </small>
        </button>
        <button className={`kpi ${dados.erros_24h ? "alerta" : ""}`} onClick={() => irLogs("erro")}>
          <span>Erros nas últimas 24 h</span><b>{dados.erros_24h}</b><small>ver logs de erro →</small>
        </button>
        <button className="kpi" onClick={() => irUsuarios("nao_ativou")}>
          <span>Não ativaram o e-mail</span><b>{dados.nao_ativaram}</b><small>ativar na mão →</small>
        </button>
      </div>

      <div className="card grafico">
        <div className="grafico-topo">
          <h2>{{ logins: "Logins por dia", cadastros: "Cadastros por dia", erros: "Erros por dia" }[metrica]}</h2>
          <div className="tabs" style={{ margin: 0 }}>
            {(["logins", "cadastros", "erros"] as Metrica[]).map((m) => (
              <button key={m} className={`tab ${metrica === m ? "on" : ""}`} onClick={() => { setMetrica(m); setFoco(null); }}>
                {{ logins: "Logins", cadastros: "Cadastros", erros: "Erros" }[m]}
              </button>
            ))}
            {[7, 14, 30].map((d) => (
              <button key={d} className={`tab ${dias === d ? "on" : ""}`} onClick={() => { setDias(d); setFoco(null); }}>{d} dias</button>
            ))}
          </div>
        </div>
        <p className="grafico-dica" aria-live="polite">{dica}</p>
        <div className="grafico-area">
          <div className="grafico-eixo"><span>{topo}</span><span>{topo / 2}</span><span>0</span></div>
          <div className="grafico-barras" onMouseLeave={() => setFoco(null)}>
            {serie.map((v, i) => (
              <button key={dados.dias[i]} aria-label={`${rotuloDia(i)}: ${v}`} onMouseEnter={() => setFoco(i)} onFocus={() => setFoco(i)}>
                <i className={metrica === "erros" ? "erro" : ""} style={{ height: `${v ? Math.max(3, (v / topo) * 100) : 0}%`, opacity: foco === null || foco === i ? 1 : 0.45 }} />
              </button>
            ))}
          </div>
        </div>
        <div className="grafico-rodape"><span>há {serie.length - 1} dias</span><span>hoje</span></div>
      </div>

      <div className="duas-colunas">
        <div className="card">
          <h2>Últimos erros</h2>
          {dados.ultimos_erros.length
            ? dados.ultimos_erros.map((e) => <LinhaEventoCurta key={e.id} e={e} />)
            : <p className="empty">Nenhum erro registrado.</p>}
          <button className="btn" onClick={() => irLogs("todos")}>Ver todos os logs</button>
        </div>
        <div className="card">
          <h2>Precisam de você</h2>
          {dados.pendencias.length
            ? dados.pendencias.map((p) => (
                <div key={p.usuario_id} className="linha-curta">
                  <span><b>{p.nome}</b> · {p.motivo}</span>
                  <button className="btn pri" onClick={() => irUsuarios("todos", p.email)}>Resolver</button>
                </div>
              ))
            : <p className="empty">Nada pendente. 🎉</p>}
        </div>
      </div>
    </>
  );
}

function Tag({ par }: { par: [string, string] }) {
  return <span className={`tag ${par[1]}`}>{par[0]}</span>;
}

function LinhaEventoCurta({ e }: { e: Evento }) {
  return (
    <div className="linha-curta">
      <span className="num" style={{ color: "var(--muted)", whiteSpace: "nowrap" }}>{e.quando}</span>
      <Tag par={TAG_NIVEL[e.nivel]} />
      <span style={{ flex: "1 1 auto" }}>{e.mensagem}</span>
    </div>
  );
}

// ---------------- usuários ----------------

function Usuarios({ toast, filtro, setFiltro, busca, setBusca }: {
  toast: (t: string) => void; filtro: string; setFiltro: (f: string) => void; busca: string; setBusca: (b: string) => void;
}) {
  const [dados, setDados] = useState<AdminUsuarios | null>(null);
  const [aviso, setAviso] = useState("");
  const carregar = useCallback(() => {
    api.admin.usuarios(filtro, busca).then(setDados).catch((e) => toast((e as Error).message));
  }, [filtro, busca, toast]);
  useEffect(() => { const t = setTimeout(carregar, 250); return () => clearTimeout(t); }, [carregar]);

  async function agir(fazer: () => Promise<{ detail: string }>) {
    try { setAviso((await fazer()).detail); carregar(); } catch (e) { toast((e as Error).message); }
  }

  const acoes = (u: AdminUsuario): [string, string, () => Promise<{ detail: string }>][] => {
    const a = api.admin;
    switch (u.status) {
      case "nao_ativou": return [["Ativar agora", "pri", () => a.acaoUsuario(u.id, "ativar")], ["Reenviar e-mail de ativação", "", () => a.acaoUsuario(u.id, "reenviar-ativacao")]];
      case "ativo": return [["Mandar link de nova senha", "", () => a.acaoUsuario(u.id, "nova-senha")], ["Desativar", "danger", () => a.acaoUsuario(u.id, "desativar")]];
      case "convidado": return [["Reenviar convite", "", () => a.reenviarConvite(u.id)], ["Cancelar convite", "danger", () => a.cancelarConvite(u.id)]];
      case "desativado": return [["Reativar", "pri", () => a.acaoUsuario(u.id, "reativar")]];
      case "master": return [["Mandar link de nova senha", "", () => a.acaoUsuario(u.id, "nova-senha")]];
      default: return [];
    }
  };
  const filtros: [string, string][] = [["todos", "Todos"], ["ativo", "Ativos"], ["nao_ativou", "Não ativaram"], ["convidado", "Convites"], ["desativado", "Desativados"]];

  return (
    <div className="card">
      <div className="grafico-topo">
        <h2>Usuários</h2>
        <input className="busca" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar por nome ou e-mail" aria-label="Buscar usuário" />
      </div>
      <div className="tabs">
        {filtros.map(([k, l]) => (
          <button key={k} className={`tab ${filtro === k ? "on" : ""}`} onClick={() => setFiltro(k)}>{l} · {dados?.contagem[k] ?? 0}</button>
        ))}
      </div>
      {aviso && <p className="aviso-admin" role="status">{aviso}</p>}
      {!dados ? <p className="empty">Carregando…</p> : dados.usuarios.length === 0 ? <p className="empty">Ninguém encontrado.</p> : (
        dados.usuarios.map((u) => (
          <div key={u.tipo + u.id} className="linha-usuario">
            <span className={`avatar ${u.status === "master" ? "master" : ""}`} aria-hidden="true">{u.nome.slice(0, 1).toUpperCase()}</span>
            <div className="quem">
              <div className="nm">{u.nome}<Tag par={TAG_STATUS[u.status]} /></div>
              <div className="meta">{u.email} · {u.detalhe}</div>
            </div>
            <div className="acoes-usuario">
              {acoes(u).map(([rotulo, tipo, fazer]) => (
                <button key={rotulo} className={`btn ${tipo}`} onClick={() => agir(fazer)}>{rotulo}</button>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ---------------- convite ----------------

function Convite({ toast }: { toast: (t: string) => void }) {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [aviso, setAviso] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function convidar() {
    setEnviando(true);
    try {
      setAviso((await api.admin.convidar(nome, email)).detail + " Ele aparece em Usuários → Convites.");
      setNome(""); setEmail("");
    } catch (e) { toast((e as Error).message); } finally { setEnviando(false); }
  }

  return (
    <div className="duas-colunas">
      <div className="card convite-form">
        <h2>Convidar pessoa</h2>
        <label className="f">Nome<input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Bia" /></label>
        <label className="f">E-mail<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="bia@email.com" /></label>
        <button className="btn pri" disabled={enviando} onClick={convidar}>Enviar convite</button>
        {aviso && <p className="aviso-admin" role="status">{aviso}</p>}
        <p className="hint" style={{ margin: 0 }}>O link vale por 7 dias. Quem aceita cria a própria senha e já entra.</p>
      </div>
      <div>
        <p className="rotulo-previa">Prévia do e-mail</p>
        <div className="email-previa">
          <div className="email-cabecalho">
            <span><b>De:</b> No Corre das Notas</span>
            <span><b>Para:</b> {email.trim() || "[e-mail]"}</span>
            <span><b>Assunto:</b> Você recebeu um convite especial para o No Corre das Notas</span>
          </div>
          <div className="email-corpo">
            <span className="email-marca">No Corre das Notas</span>
            <b>Seja bem-vindo(a) ao No Corre das Notas, {nome.trim() || "[nome]"}!</b>
            <span>Pra gente, o que importa é como você lida com o seu dinheiro, e queremos estar junto nisso.</span>
            <span>Por isso te enviamos este <b>convite especial</b> para criar sua conta no nosso site e no aplicativo e organizar sua vida financeira, <b>sem custo nenhum</b>.</span>
            <span className="email-botao">Aceitar convite e criar minha senha</span>
            <small>O link vale por 7 dias. Se não esperava este e-mail, é só ignorar.</small>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------- logs ----------------

function ListaLogs({ nivel, setNivel }: { nivel: string; setNivel: (n: string) => void }) {
  const [tipo, setTipo] = useState("todos");
  const [busca, setBusca] = useState("");
  const [dados, setDados] = useState<Logs | null>(null);
  const [aberto, setAberto] = useState<number | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      api.admin.logs(nivel, tipo, busca).then((d) => { setDados(d); setErro(""); }).catch((e) => setErro((e as Error).message));
    }, 250);
    return () => clearTimeout(t);
  }, [nivel, tipo, busca]);

  const niveis: [string, string][] = [["todos", "Todos"], ["erro", "Erros"], ["aviso", "Avisos"], ["info", "Info"]];
  const tipos: [string, string][] = [["todos", "Tudo"], ["acesso", "Acesso"], ["sistema", "Sistema"], ["email", "E-mail"]];

  return (
    <div className="card">
      <div className="grafico-topo">
        <h2>Logs</h2>
        <input className="busca" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar (e-mail, rota, mensagem)" aria-label="Buscar nos logs" />
      </div>
      <div className="tabs">
        {niveis.map(([k, l]) => <button key={k} className={`tab ${nivel === k ? "on" : ""}`} onClick={() => setNivel(k)}>{l} · {dados?.contagem[k] ?? 0}</button>)}
        <span className="separador" />
        {tipos.map(([k, l]) => <button key={k} className={`tab ${tipo === k ? "on" : ""}`} onClick={() => setTipo(k)}>{l}</button>)}
      </div>
      {erro && <p className="erro-admin">{erro}</p>}
      {!dados ? <p className="empty">Carregando…</p> : dados.logs.length === 0 ? <p className="empty">Nenhum log com esses filtros.</p> : (
        dados.logs.map((l) => (
          <div key={l.id} className="linha-log">
            <button onClick={() => setAberto(aberto === l.id ? null : l.id)} aria-expanded={aberto === l.id}>
              <span className="num quando">{l.quando}</span>
              <Tag par={TAG_NIVEL[l.nivel]} />
              <span className="tipo-log">{{ acesso: "acesso", sistema: "sistema", email: "e-mail" }[l.tipo]}</span>
              <span className="msg">{l.mensagem}</span>
              <span className="meta">{l.email ?? ""}</span>
            </button>
            {aberto === l.id && (
              <dl className="detalhe-log">
                <dt>rota</dt><dd>{l.rota ?? "—"}</dd>
                <dt>código</dt><dd>{l.codigo ?? "—"}</dd>
                <dt>id da requisição</dt><dd>{l.requisicao ?? "—"}</dd>
                <dt>ação</dt><dd>{l.acao}</dd>
                <dt>detalhe</dt><dd>{l.detalhe ?? "—"}</dd>
              </dl>
            )}
          </div>
        ))
      )}
    </div>
  );
}
