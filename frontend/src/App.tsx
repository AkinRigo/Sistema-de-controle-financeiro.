import { useEffect, useState } from "react";
import { api, definirAoDeslogar, token, type Usuario } from "./api";
import { Login } from "./Login";
import { Painel } from "./Painel";

export function App() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(!!token.ler());

  useEffect(() => {
    definirAoDeslogar(() => setUsuario(null));
    if (!token.ler()) return;
    api.eu().then(setUsuario).catch(() => token.apagar()).finally(() => setCarregando(false));
  }, []);

  if (carregando) return <div className="loading">Carregando…</div>;
  if (!usuario) return <Login aoEntrar={setUsuario} />;
  return (
    <Painel
      usuario={usuario}
      aoSair={() => { token.apagar(); setUsuario(null); }}
    />
  );
}
