// Datas, meses e dinheiro — mesmas regras de exibição do protótipo.

const agora = new Date();
export const HOJE = new Date(agora.getTime() - agora.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
export const MES_ATUAL = HOJE.slice(0, 7);
export const DIA_HOJE = agora.getDate();

export const somarMes = (m: string, n: number): string => {
  let [a, mes] = m.split("-").map(Number);
  mes += n;
  a += Math.floor((mes - 1) / 12);
  mes = (((mes - 1) % 12) + 12) % 12 + 1;
  return `${a}-${String(mes).padStart(2, "0")}`;
};
export const difMes = (de: string, ate: string): number => {
  const [ya, ma] = de.split("-").map(Number);
  const [yb, mb] = ate.split("-").map(Number);
  return (yb - ya) * 12 + (mb - ma);
};
export const nomeMes = (m: string) =>
  new Date(m + "-01T12:00:00").toLocaleDateString("pt-BR", { month: "long" });
export const mesCompleto = (m: string) =>
  new Date(m + "-01T12:00:00").toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
export const maiuscula = (t: string) => t.replace(/^./, (c) => c.toUpperCase());
export const dataCurta = (d: string) => (d ? d.split("-").reverse().slice(0, 2).join("/") : "");

export const num = (v: string | number | null | undefined): number => Number(v ?? 0) || 0;
export const dinheiro = (v: string | number | null | undefined) =>
  "R$ " + num(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
/** Valor para pôr num campo de texto: "150.5" → "150,50". */
export const paraCampo = (v: string | number) => num(v).toFixed(2).replace(".", ",");

/** Lê "1.234,56", "1234.56", "R$ 10" etc. Devolve texto "1234.56" para a API, ou null. */
export function lerDinheiro(v: string): string | null {
  let t = String(v ?? "").trim().replace(/R\$/gi, "").replace(/\s/g, "").replace(/[^0-9,.-]/g, "");
  if (!t) return null;
  const c = t.lastIndexOf(","), d = t.lastIndexOf(".");
  if (c >= 0 && d >= 0) t = c > d ? t.replace(/\./g, "").replace(",", ".") : t.replace(/,/g, "");
  else if (c >= 0) t = t.replace(/\./g, "").replace(",", ".");
  else if (d >= 0 && t.length - d - 1 === 3) t = t.replace(/\./g, "");
  const n = Number(t);
  return Number.isFinite(n) ? (Math.round(n * 100) / 100).toFixed(2) : null;
}

export const CATEGORIAS: [string, string][] = [
  ["casa", "Casa"], ["pessoas", "Devo a pessoas"], ["moto", "Moto"],
  ["cartoes", "Cartões e banco"], ["alimentacao", "Alimentação"], ["outros", "Outros"],
];
export const NOME_CATEGORIA: Record<string, string> = Object.fromEntries(CATEGORIAS);

const dobrar = (t: string) => t.toLocaleLowerCase("pt-BR").normalize("NFD").replace(/[̀-ͯ]/g, "");
/** Sugestão instantânea no formulário; o backend tem a regra oficial. */
export function sugerirCategoria(nome: string, credor: string): string {
  const t = dobrar(credor + " " + nome);
  if (/\b(moto|gasolina|combustivel|mobilidade|ipva|licenciamento|oficina|pneu|multa)/.test(t)) return "moto";
  if (/(cart(ao|oes)|nubank|neon|inter\b|banco|cheque|emprestimo|fatura|picpay|mercado pago)/.test(t)) return "cartoes";
  if (/\b(casa|aluguel|condominio|luz|energia|agua|internet|gas|iptu)\b/.test(t)) return "casa";
  if (/(mercado|aliment|comida|ifood|feira|padaria|acougue|lanche|restaurante)/.test(t)) return "alimentacao";
  if (/\b(pai|mae|irma|irmao|amigo|amiga|tio|tia|primo|prima|avo|vo|namorad|sogr)/.test(t)) return "pessoas";
  return "outros";
}

/** Estimativa de corridas igual à do backend, para a nota da seção de corridas. */
export function estimarCorridas(mes: string, porSemana: number, porFds: number): number {
  if (mes < MES_ATUAL) return 0;
  const [a, m] = mes.split("-").map(Number);
  const dias = new Date(a, m, 0).getDate();
  const de = mes === MES_ATUAL ? DIA_HOJE : 1;
  let restam = 0, sabados = 0;
  for (let d = de; d <= dias; d++) { restam++; if (new Date(a, m - 1, d).getDay() === 6) sabados++; }
  return porSemana * (restam / 7) + porFds * sabados;
}

export function numeroParcela(c: { tipo: string; mes_inicio: string; parcela_inicial: number | null }, mes: string) {
  return c.tipo === "parcelada" && c.parcela_inicial ? c.parcela_inicial + difMes(c.mes_inicio, mes) : null;
}
