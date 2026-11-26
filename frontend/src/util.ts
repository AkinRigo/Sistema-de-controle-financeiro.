// Só formatação e navegação de tela. Regras de negócio ficam no backend.

const agora = new Date();
export const HOJE = new Date(agora.getTime() - agora.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
export const MES_ATUAL = HOJE.slice(0, 7);

/** Navegar entre meses na tela (‹ ›). */
export const somarMes = (m: string, n: number): string => {
  let [a, mes] = m.split("-").map(Number);
  mes += n;
  a += Math.floor((mes - 1) / 12);
  mes = (((mes - 1) % 12) + 12) % 12 + 1;
  return `${a}-${String(mes).padStart(2, "0")}`;
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

/** Lê o que a pessoa digitou ("1.234,56", "R$ 10"…) e manda "1234.56" para a API; null se não for número. */
export function lerDinheiro(v: string): string | null {
  let t = String(v ?? "").trim().replace(/R\$/gi, "").replace(/\s/g, "").replace(/[^0-9,.-]/g, "");
  if (!t) return null;
  const c = t.lastIndexOf(","), d = t.lastIndexOf(".");
  if (c >= 0 && d >= 0) t = c > d ? t.replace(/\./g, "").replace(",", ".") : t.replace(/,/g, "");
  else if (c >= 0) t = t.replace(/\./g, "").replace(",", ".");
  else if (d >= 0 && t.length - d - 1 === 3) t = t.replace(/\./g, "");
  return Number.isFinite(Number(t)) ? t : null;
}
