import { createContext, useContext } from "react";
import type { Banco, Categoria, Conta, Corridas, Ganho, Renda, Resumo, Usuario } from "./api";

export interface Dados {
  usuario: Usuario;
  contas: Conta[];
  bancos: Banco[];
  ganhos: Ganho[];
  rendas: Renda[];
  corridas: Corridas;
  resumo: Resumo;
  categorias: Categoria[];
}

export interface Ctx {
  dados: Dados;
  mes: string;
  setMes: (m: string) => void;
  /** Roda uma ação na API, recarrega os dados e mostra a mensagem (ou o erro). */
  executar: (acao: () => Promise<unknown>, mensagem?: string) => Promise<boolean>;
  toast: (t: string) => void;
  /** Qual caixinha inline está aberta (pagar, editar, excluir…). Só uma por vez, como no protótipo. */
  aberto: string | null;
  abrir: (chave: string | null) => void;
  ultimoBanco: string;
  setUltimoBanco: (id: string) => void;
}

export const Contexto = createContext<Ctx | null>(null);
export const useCtx = () => useContext(Contexto)!;

export function bancoPadrao(c: Ctx): string {
  return c.dados.bancos.some((b) => b.id === c.ultimoBanco) ? c.ultimoBanco : c.dados.bancos[0]?.id ?? "";
}
