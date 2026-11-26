import { useCtx } from "../contexto";
import { dinheiro } from "../util";

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

/** Categorias vindas da API. "Automática" deixa o backend escolher pelo nome e "para quem". */
export function OpcoesCategoria() {
  const { dados } = useCtx();
  return (
    <>
      <option value="">Automática (pelo nome)</option>
      {dados.categorias.map((c) => <option key={c.chave} value={c.chave}>{c.nome}</option>)}
    </>
  );
}

/** Nome da categoria pela chave, como a API devolve. */
export function useNomeCategoria() {
  const { dados } = useCtx();
  return (chave: string) => dados.categorias.find((c) => c.chave === chave)?.nome ?? chave;
}

export function Cancelar() {
  const { abrir } = useCtx();
  return <button className="btn" type="button" onClick={() => abrir(null)}>Cancelar</button>;
}

export const valorDe = (id: string) => (document.getElementById(id) as HTMLInputElement | null)?.value ?? "";
export const marcado = (id: string) => !!(document.getElementById(id) as HTMLInputElement | null)?.checked;
