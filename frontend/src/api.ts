// Cliente da API do backend. Dinheiro chega e sai como texto ("150.50").

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";
const CHAVE_TOKEN = "painel_token";

export type Tipo = "fixa" | "unica" | "parcelada";

export interface Usuario { id: string; nome: string; email: string; desde: string }
export interface Banco { id: string; nome: string; saldo: string }
export interface Conta {
  id: string; nome: string; valor: string; tipo: Tipo; mes_inicio: string;
  categoria: string; categoria_efetiva: string; credor: string | null; dia_vencimento: number;
  mes_fim: string | null; parcela_inicial: number | null; total_parcelas: number | null;
  juros_altos: boolean; incerto: boolean; ainda_devo: string;
}
export interface ContaEntrada {
  nome: string; valor: string; tipo: Tipo; mes_inicio: string; categoria: string;
  credor: string | null; dia_vencimento: number; mes_fim: string | null;
  parcela_inicial: number | null; total_parcelas: number | null; juros_altos: boolean; incerto: boolean;
}
export interface Pagamento {
  id: string; conta_id: string; mes_conta: string; valor_pago: string;
  data_pagamento: string; banco_id: string | null;
}
export interface Ganho {
  id: string; nome: string; valor: string; data: string; recebido: boolean; banco_id: string | null;
}
export interface Corridas { por_semana: string; por_fim_de_semana: string; contar_na_previsao: boolean }
export interface Aberta {
  conta_id: string; nome: string; valor: string; categoria: string; mes_origem: string;
  atrasada: boolean; numero_parcela: number | null; total_parcelas: number | null;
  dia_vencimento: number; juros_altos: boolean;
}
export interface Resumo {
  mes: string; tenho: string; vai_entrar: string; recebido: string; corridas: string;
  falta_pagar: string; ja_pago: string; sobra: string; abertas: Aberta[]; pagas: Pagamento[];
}
export interface Categoria {
  chave: string; nome: string; falta_pagar: string; ja_pago: string; fixas_por_mes: string; ainda_devo: string;
}
export interface ResultadoImportacao { bancos: number; contas: number; ganhos: number; pagamentos: number; ignorados: number }

export class ErroApi extends Error {
  constructor(public status: number, mensagem: string) { super(mensagem); }
}

export const token = {
  ler: (): string | null => { try { return localStorage.getItem(CHAVE_TOKEN); } catch { return null; } },
  gravar: (t: string) => { try { localStorage.setItem(CHAVE_TOKEN, t); } catch { /* sem storage */ } },
  apagar: () => { try { localStorage.removeItem(CHAVE_TOKEN); } catch { /* sem storage */ } },
};

let aoDeslogar: () => void = () => {};
export const definirAoDeslogar = (f: () => void) => { aoDeslogar = f; };

function mensagemDeErro(corpo: unknown, status: number): string {
  const d = (corpo as { detail?: unknown } | null)?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) {
    const primeiro = d[0] as { msg?: string; loc?: unknown[] };
    const campo = primeiro.loc?.[primeiro.loc.length - 1];
    return `${campo ? campo + ": " : ""}${primeiro.msg ?? "dado inválido"}`;
  }
  return status === 0 ? "Sem conexão com o servidor." : `Erro ${status}.`;
}

async function pedir<T>(metodo: string, caminho: string, corpo?: unknown): Promise<T> {
  const cabecalhos: Record<string, string> = {};
  const t = token.ler();
  if (t) cabecalhos.Authorization = `Bearer ${t}`;
  if (corpo !== undefined) cabecalhos["Content-Type"] = "application/json";
  let resposta: Response;
  try {
    resposta = await fetch(BASE + caminho, {
      method: metodo, headers: cabecalhos, body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch {
    throw new ErroApi(0, "Sem conexão com o servidor.");
  }
  if (resposta.status === 204) return undefined as T;
  const json = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    if (resposta.status === 401 && t) { token.apagar(); aoDeslogar(); }
    throw new ErroApi(resposta.status, mensagemDeErro(json, resposta.status));
  }
  return json as T;
}

interface TokenSaida { token: string; usuario: Usuario }

export const api = {
  cadastrar: (nome: string, email: string, senha: string) =>
    pedir<{ detail: string }>("POST", "/auth/cadastro", { nome, email, senha }),
  confirmarEmail: (tokenLink: string) => pedir<TokenSaida>("POST", "/auth/confirmar-email", { token: tokenLink }),
  reenviarConfirmacao: (email: string) =>
    pedir<{ detail: string }>("POST", "/auth/reenviar-confirmacao", { email }),
  entrar: (email: string, senha: string) => pedir<TokenSaida>("POST", "/auth/login", { email, senha }),
  eu: () => pedir<Usuario>("GET", "/auth/eu"),
  esqueciSenha: (email: string) => pedir<{ detail: string }>("POST", "/auth/esqueci-senha", { email }),
  redefinirSenha: (tokenLink: string, senha: string) =>
    pedir<TokenSaida>("POST", "/auth/redefinir-senha", { token: tokenLink, senha }),

  bancos: () => pedir<Banco[]>("GET", "/bancos"),
  criarBanco: (nome: string, saldo: string) => pedir<Banco>("POST", "/bancos", { nome, saldo }),
  editarBanco: (id: string, nome: string, saldo: string) => pedir<Banco>("PUT", `/bancos/${id}`, { nome, saldo }),
  excluirBanco: (id: string) => pedir<void>("DELETE", `/bancos/${id}`),

  contas: () => pedir<Conta[]>("GET", "/contas"),
  criarConta: (c: ContaEntrada) => pedir<Conta>("POST", "/contas", c),
  editarConta: (id: string, c: ContaEntrada) => pedir<Conta>("PUT", `/contas/${id}`, c),
  excluirConta: (id: string) => pedir<void>("DELETE", `/contas/${id}`),

  pagar: (p: { conta_id: string; mes_conta: string; valor_pago: string; banco_id: string | null }) =>
    pedir<Pagamento>("POST", "/pagamentos", p),
  desfazerPagamento: (id: string) => pedir<void>("DELETE", `/pagamentos/${id}`),

  ganhos: () => pedir<Ganho[]>("GET", "/ganhos"),
  criarGanho: (g: Omit<Ganho, "id">) => pedir<Ganho>("POST", "/ganhos", g),
  editarGanho: (id: string, g: Omit<Ganho, "id">) => pedir<Ganho>("PUT", `/ganhos/${id}`, g),
  excluirGanho: (id: string) => pedir<void>("DELETE", `/ganhos/${id}`),

  corridas: () => pedir<Corridas>("GET", "/configuracoes/corridas"),
  salvarCorridas: (c: Corridas) => pedir<Corridas>("PUT", "/configuracoes/corridas", c),

  resumo: (mes: string) => pedir<Resumo>("GET", `/resumo/${mes}`),
  categorias: (mes: string) => pedir<Categoria[]>("GET", `/categorias/${mes}`),

  exportar: () => pedir<unknown>("GET", "/backup"),
  importar: (dados: unknown) => pedir<ResultadoImportacao>("POST", "/backup", dados),
};
