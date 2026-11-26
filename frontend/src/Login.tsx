import { useEffect, useRef, useState, type FormEvent } from "react";
import { ErroApi, api, token, type Usuario } from "./api";
import { LogoCompleto } from "./componentes/Logo";

type Modo = "entrar" | "cadastrar" | "esqueci" | "redefinir" | "aguardando" | "confirmando";

/** Links que chegam por e-mail: ?redefinir=TOKEN ou ?confirmar=TOKEN */
const parametro = (nome: string) => new URLSearchParams(window.location.search).get(nome);
const limparLink = () => window.history.replaceState(null, "", window.location.pathname);

const TITULOS: Record<Modo, string> = {
  entrar: "Entre para ver suas contas.",
  cadastrar: "Crie sua conta. Vamos mandar um link para confirmar seu e-mail.",
  esqueci: "Digite seu e-mail. Vamos mandar um link para você criar uma senha nova.",
  redefinir: "Escolha sua senha nova.",
  aguardando: "Falta só ativar sua conta.",
  confirmando: "Ativando sua conta…",
};

function Moldura({ children }: { children: React.ReactNode }) {
  return (
    <main className="auth">
      <div className="lado">
        <LogoCompleto />
        <p>Quanto tenho, quanto entra, quanto falta. O mês inteiro numa conta só.</p>
      </div>
      <div className="form-lado">{children}</div>
    </main>
  );
}

const MarcaMini = () => <LogoCompleto className="marca-mini" />;

export function Login({ aoEntrar }: { aoEntrar: (u: Usuario) => void }) {
  const [linkRedefinir] = useState(() => parametro("redefinir"));
  const [linkConfirmar] = useState(() => parametro("confirmar"));
  const [modo, setModo] = useState<Modo>(linkConfirmar ? "confirmando" : linkRedefinir ? "redefinir" : "entrar");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [podeReenviar, setPodeReenviar] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const confirmou = useRef(false);

  function entrarCom(r: { token: string; usuario: Usuario }) {
    limparLink();
    token.gravar(r.token);
    aoEntrar(r.usuario);
  }

  // Link de ativação do e-mail: confirma e já entra.
  useEffect(() => {
    if (!linkConfirmar || confirmou.current) return;
    confirmou.current = true; // StrictMode roda o efeito duas vezes em dev
    api.confirmarEmail(linkConfirmar).then(entrarCom).catch((e) => {
      limparLink();
      setModo("entrar");
      setErro((e as Error).message + " Entre com seu e-mail e senha para receber outro link.");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const trocar = (m: Modo) => {
    setModo(m); setErro(""); setAviso(""); setPodeReenviar(false);
    if (m !== "redefinir") limparLink();
  };

  async function reenviar() {
    setErro("");
    try {
      setAviso((await api.reenviarConfirmacao(email)).detail + " Confira também a caixa de spam.");
      setPodeReenviar(false);
    } catch (e) { setErro((e as Error).message); }
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(""); setAviso(""); setPodeReenviar(false);
    setEnviando(true);
    try {
      if (modo === "esqueci") {
        setAviso((await api.esqueciSenha(email)).detail + " Confira também a caixa de spam.");
      } else if (modo === "cadastrar") {
        await api.cadastrar(nome, email, senha);
        setSenha("");
        setModo("aguardando");
      } else if (modo === "redefinir") {
        entrarCom(await api.redefinirSenha(linkRedefinir!, senha));
      } else {
        entrarCom(await api.entrar(email, senha));
      }
    } catch (err) {
      setErro((err as Error).message);
      if (err instanceof ErroApi && err.status === 403) setPodeReenviar(true);
    } finally {
      setEnviando(false);
    }
  }

  if (modo === "confirmando") return <Moldura><div className="card"><MarcaMini /><p className="hint">{TITULOS.confirmando}</p></div></Moldura>;

  if (modo === "aguardando") {
    return (
      <Moldura>
        <div className="card">
          <MarcaMini />
          <p className="hint">{TITULOS.aguardando}</p>
          <p>Enviamos um link para <b>{email}</b>. Abra o e-mail e clique em <b>Ativar minha conta</b>. Se não achar, veja a caixa de spam.</p>
          {erro && <p className="erro" role="alert">{erro}</p>}
          {aviso && <p className="hint" role="status" style={{ color: "var(--green)" }}>{aviso}</p>}
          <button className="btn" onClick={reenviar}>Reenviar e-mail</button>
          <button type="button" className="lnk" style={{ justifySelf: "start" }} onClick={() => trocar("entrar")}>Já ativei, quero entrar</button>
        </div>
      </Moldura>
    );
  }

  const senhaNova = modo === "cadastrar" || modo === "redefinir";

  return (
    <Moldura>
      <form className="card" onSubmit={enviar}>
        <MarcaMini />
        {(modo === "entrar" || modo === "cadastrar") && (
          <div className="tabs" role="tablist" style={{ margin: 0 }}>
            <button type="button" role="tab" aria-selected={modo === "entrar"} className={`tab ${modo === "entrar" ? "on" : ""}`} onClick={() => trocar("entrar")}>Entrar</button>
            <button type="button" role="tab" aria-selected={modo === "cadastrar"} className={`tab ${modo === "cadastrar" ? "on" : ""}`} onClick={() => trocar("cadastrar")}>Criar conta</button>
          </div>
        )}
        <p className="hint">{TITULOS[modo]}</p>
        {modo === "cadastrar" && (
          <label className="f">Nome<input value={nome} onChange={(e) => setNome(e.target.value)} required autoComplete="name" /></label>
        )}
        {modo !== "redefinir" && (
          <label className="f">E-mail<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></label>
        )}
        {modo !== "esqueci" && (
          <label className="f">
            {modo === "redefinir" ? "Senha nova" : "Senha"}{senhaNova ? " (mínimo 8 caracteres)" : ""}
            <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required
              minLength={senhaNova ? 8 : undefined} autoComplete={senhaNova ? "new-password" : "current-password"} />
          </label>
        )}
        {erro && <p className="erro" role="alert">{erro}</p>}
        {podeReenviar && <button type="button" className="btn" onClick={reenviar}>Reenviar e-mail de confirmação</button>}
        {aviso && <p className="hint" role="status" style={{ color: "var(--green)" }}>{aviso}</p>}
        <button className="btn pri" disabled={enviando}>
          {{ entrar: "Entrar", cadastrar: "Criar conta", esqueci: "Mandar link", redefinir: "Salvar senha e entrar" }[modo]}
        </button>
        {modo === "entrar" && (
          <button type="button" className="lnk" style={{ justifySelf: "start" }} onClick={() => trocar("esqueci")}>Esqueci minha senha</button>
        )}
        {(modo === "esqueci" || modo === "redefinir") && (
          <p className="troca">Lembrou a senha? <button type="button" className="lnk" onClick={() => trocar("entrar")}>Entrar</button></p>
        )}
      </form>
    </Moldura>
  );
}
