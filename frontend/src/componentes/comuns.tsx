import { useCtx } from "../contexto";
import { CATEGORIAS, dinheiro } from "../util";

export function OpcoesBanco() {
  const { dados } = useCtx();
  return (
    <>
      {dados.bancos.map((b) => (
        <option key={b.id} value={b.id}>{b.nome} ({dinheiro(b.saldo)})</option>
      ))}
      <option value="">Não tirar/pôr de nenhum banco</option>
    </>
  );
}

export function OpcoesCategoria() {
  return <>{CATEGORIAS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</>;
}

export function Cancelar() {
  const { abrir } = useCtx();
  return <button className="btn" type="button" onClick={() => abrir(null)}>Cancelar</button>;
}

export const valorDe = (id: string) => (document.getElementById(id) as HTMLInputElement | null)?.value ?? "";
export const marcado = (id: string) => !!(document.getElementById(id) as HTMLInputElement | null)?.checked;
