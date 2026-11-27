// Cliente da API do backend. Dinheiro chega e sai como texto ("150.50").

const BASE = import.meta.env.DEV ? "http://localhost:8000" : "";
const CHAVE_TOKEN = "painel_token";

export type Tipo = "fixa" | "unica" | "parcelada";

export interface Usuario { id: string; nome: string; email: string; desde: string; admin?: boolean }
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
  /** Mês aberto na tela: o backend converte "parcela N neste mês" e "virou fixa" no início certo. */
  mes_referencia?: string | null; parcela_no_mes?: number | null;
}
export interface Pagamento {
  id: string; conta_id: string; mes_conta: string; valor_pago: string;
  data_pagamento: string; banco_id: string | null; numero_parcela: number | null;
}
export interface GanhoDados {
  nome: string; valor: string; data: string; recebido: boolean; banco_id: string | null;
}
export interface Ganho extends GanhoDados {
  id: string;
  /** Preenchido quando o ganho veio de uma renda fixa (um por mês). */
  renda_id: string | null;
}
export interface GanhoDoMes extends Ganho { atrasado: boolean }
export interface RendaDados { nome: string; valor: string; dia: number; banco_id: string | null }
export interface Renda extends RendaDados { id: string; mes_inicio: string }
export interface Corridas {
  por_semana: string; por_fim_de_semana: string; contar_na_previsao: boolean; estimativa_mes: string | null;
}
export type CorridasDados = Omit<Corridas, "estimativa_mes">;
export interface Aberta {
  conta_id: string; nome: string; valor: string; categoria: string; mes_origem: string;
  atrasada: boolean; numero_parcela: number | null; total_parcelas: number | null;
  dia_vencimento: number; juros_altos: boolean; vence_em_dias: number | null;
  situacao_vencimento: "venceu" | "hoje" | "em_breve" | "no_prazo" | null;
}
export interface Resumo {
  mes: string; tenho: string; vai_entrar: string; recebido: string; corridas: string;
  falta_pagar: string; ja_pago: string; sobra: string; abertas: Aberta[]; pagas: Pagamento[];
  cobertura: number; divida_total: string;
}
export interface ItemCategoria {
  conta_id: string; nome: string; credor: string | null; tipo: Tipo; valor: string; valor_parcela: string;
  parcelas_restantes: number | null; total_parcelas: number | null;
  mes_referencia: string; parcela_no_mes: number | null;
}
export interface Categoria {
  chave: string; nome: string; falta_pagar: string; ja_pago: string; fixas_por_mes: string; ainda_devo: string;
  itens: ItemCategoria[];
}
// ---------- gráficos ----------
export interface Movimento { nome: string; valor: string; previsto: boolean }
export interface DiaDeSaldo { dia: number; saldo: string; previsao: boolean; movimentos: Movimento[] }
export interface SaldoDiario { mes: string; hoje: number | null; dias: DiaDeSaldo[]; menor: DiaDeSaldo | null }
// ---------- voz ----------
export interface ItemVoz { id: string; nome: string; valor: string; conta_id: string | null; mes_conta: string | null }
export interface BancoVoz { id: string; nome: string; saldo: string }
export interface PropostaVoz {
  acao: "pagar_conta" | "desfazer_pagamento" | "receber_ganho" | "novo_ganho" | "nova_conta" | "novo_banco"
    | "somar_banco" | "ajustar_saldo" | "transferir" | "consultar_sobra" | "consultar_falta" | "consultar_banco" | "nao_entendi";
  mensagem: string;
  item: ItemVoz | null;
  opcoes: ItemVoz[];
  valor: string | null;
  banco: BancoVoz | null;
  banco_destino: BancoVoz | null;
  saldo_novo: string | null;
  nome: string;
  data: string | null;
  tipo_conta: "" | Tipo;
  parcelas: number | null;
  dia: number;
  mes_inicio: string | null;
}
// ---------- admin ----------
export type StatusUsuario = "master" | "ativo" | "nao_ativou" | "convidado" | "desativado";
export interface AdminUsuario { id: string; tipo: "usuario" | "convite"; nome: string; email: string; status: StatusUsuario; detalhe: string }
export interface AdminUsuarios { usuarios: AdminUsuario[]; contagem: Record<string, number> }
export interface Evento {
  id: number; quando: string; nivel: "erro" | "aviso" | "info"; tipo: "acesso" | "sistema" | "email";
  acao: string; mensagem: string; email: string | null; rota: string | null; codigo: number | null;
  requisicao: string | null; detalhe: string | null;
}
export interface Logs { logs: Evento[]; contagem: Record<string, number> }
export interface Indicadores {
  usuarios_ativos: number; logins_7d: number; logins_7d_variacao: number | null; erros_24h: number; nao_ativaram: number;
  dias: string[]; logins: number[]; cadastros: number[]; erros: number[];
  ultimos_erros: Evento[]; pendencias: { usuario_id: string; nome: string; email: string; motivo: string }[];
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
  verConvite: (tokenLink: string) => pedir<{ nome: string; email: string }>("GET", `/auth/convite/${encodeURIComponent(tokenLink)}`),
  aceitarConvite: (tokenLink: string, senha: string) =>
    pedir<TokenSaida>("POST", "/auth/aceitar-convite", { token: tokenLink, senha }),
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
  transferir: (de: string, para: string, valor: string) => pedir<Banco[]>("POST", "/bancos/transferir", { de, para, valor }),

  contas: () => pedir<Conta[]>("GET", "/contas"),
  criarConta: (c: ContaEntrada) => pedir<Conta>("POST", "/contas", c),
  editarConta: (id: string, c: ContaEntrada) => pedir<Conta>("PUT", `/contas/${id}`, c),
  excluirConta: (id: string) => pedir<void>("DELETE", `/contas/${id}`),
  pararConta: (id: string, aPartirDe: string) => pedir<Conta>("POST", `/contas/${id}/parar`, { a_partir_de: aPartirDe }),

  pagar: (p: { conta_id: string; mes_conta: string; valor_pago: string; banco_id: string | null }) =>
    pedir<Pagamento>("POST", "/pagamentos", p),
  desfazerPagamento: (id: string) => pedir<void>("DELETE", `/pagamentos/${id}`),

  ganhosDoMes: (mes: string) => pedir<GanhoDoMes[]>("GET", `/ganhos/mes/${mes}`),
  receberGanho: (id: string, valor: string, bancoId: string | null, mesAberto: string) =>
    pedir<Ganho>("POST", `/ganhos/${id}/receber`, { valor, banco_id: bancoId, mes_aberto: mesAberto }),
  desfazerRecebimento: (id: string) => pedir<Ganho>("POST", `/ganhos/${id}/desfazer`),
  criarGanho: (g: GanhoDados) => pedir<Ganho>("POST", "/ganhos", g),
  editarGanho: (id: string, g: GanhoDados) => pedir<Ganho>("PUT", `/ganhos/${id}`, g),
  excluirGanho: (id: string) => pedir<void>("DELETE", `/ganhos/${id}`),

  rendas: () => pedir<Renda[]>("GET", "/rendas"),
  criarRenda: (r: RendaDados) => pedir<Renda>("POST", "/rendas", r),
  editarRenda: (id: string, r: RendaDados) => pedir<Renda>("PUT", `/rendas/${id}`, r),
  excluirRenda: (id: string) => pedir<void>("DELETE", `/rendas/${id}`),

  corridas: (mes: string) => pedir<Corridas>("GET", `/configuracoes/corridas?mes=${mes}`),
  salvarCorridas: (c: CorridasDados) => pedir<Corridas>("PUT", "/configuracoes/corridas", c),

  resumo: (mes: string) => pedir<Resumo>("GET", `/resumo/${mes}`),
  categorias: (mes: string) => pedir<Categoria[]>("GET", `/categorias/${mes}`),
  saldoDiario: (mes: string) => pedir<SaldoDiario>("GET", `/saldo-diario/${mes}`),
  entenderVoz: (texto: string, mes: string) => pedir<PropostaVoz>("POST", "/voz/entender", { texto, mes }),

  exportar: () => pedir<unknown>("GET", "/backup"),
  admin: {
    indicadores: (dias: number) => pedir<Indicadores>("GET", `/admin/indicadores?dias=${dias}`),
    usuarios: (status: string, busca: string) =>
      pedir<AdminUsuarios>("GET", `/admin/usuarios?status=${status}&busca=${encodeURIComponent(busca)}`),
    acaoUsuario: (id: string, acao: "ativar" | "desativar" | "reativar" | "nova-senha" | "reenviar-ativacao") =>
      pedir<{ detail: string }>("POST", `/admin/usuarios/${id}/${acao}`),
    convidar: (nome: string, email: string) => pedir<{ detail: string }>("POST", "/admin/convites", { nome, email }),
    reenviarConvite: (id: string) => pedir<{ detail: string }>("POST", `/admin/convites/${id}/reenviar`),
    cancelarConvite: (id: string) => pedir<{ detail: string }>("DELETE", `/admin/convites/${id}`),
    logs: (nivel: string, tipo: string, busca: string) =>
      pedir<Logs>("GET", `/admin/logs?nivel=${nivel}&tipo=${tipo}&busca=${encodeURIComponent(busca)}`),
  },

  importar: (dados: unknown) => pedir<ResultadoImportacao>("POST", "/backup", dados),
};
