// Converte arquivos de backup para o formato versão 2 aceito por POST /backup.
// Aceita: backup do próprio painel (version 2) ou do painel antigo (com "debts").
/* eslint-disable @typescript-eslint/no-explicit-any */
import { HOJE, MES_ATUAL, sugerirCategoria } from "./util";

export function converterBackup(o: any): any {
  if (o && o.version === 2) return o;
  if (o && Array.isArray(o.debts)) return doPainelAntigo(o);
  throw new Error("formato");
}

const novoId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

function doPainelAntigo(o: any): any {
  const S = MES_ATUAL, months: Record<string, any> = o.months || {};
  const st: any = { version: 2, since: S, accounts: [], incomes: [], bills: [], payments: {}, sim: {} };
  const ids = (k: string, f: string): string[] => (((months[k] || {})[f]) || []).map(String);
  const pagoEm = (id: string) => Object.keys(months).filter((k) => ids(k, "paidIds").includes(id)).sort();
  const tem = (k: string, f: string, id: string) => ids(k, f).includes(id);
  const valorEm = (k: string, id: string): number | null => {
    const a = (months[k] || {}).amounts || {};
    return Number.isFinite(Number(a[id])) ? Number(a[id]) : null;
  };

  (o.debts || []).forEach((d: any) => {
    const id = String(d.id), corte = (Number(d.discount) || 0) + (Number(d.abated) || 0);
    const pago = pagoEm(id);
    let inicio: string = d.createdMonth && d.createdMonth > S ? d.createdMonth : S;
    // conta que foi "mudada de mês" no painel antigo
    if (tem(inicio, "excludedIds", id)) {
      const para = Object.keys(months).filter((k) => k > inicio && tem(k, "includedIds", id)).sort()[0];
      if (para) inicio = para;
    }
    // o painel antigo guardava o valor certo por mês; usa o mais recente a partir de agora
    const ks = Object.keys(months).filter((k) => k >= S && valorEm(k, id) !== null).sort();
    const base = ks.length ? valorEm(ks.includes(inicio) ? inicio : ks[ks.length - 1], id)! : Number(d.value) || 0;
    const efetivo = Math.max(0, base - corte);
    const b: any = {
      id, name: d.name || "Conta", creditor: d.category || "Outros", value: efetivo,
      dueDay: Number(d.dueDay) || 0,
      type: d.type === "fixed" ? "fixed" : d.type === "installment" ? "installment" : "single",
      startMonth: inicio, endMonth: null, startNumber: 1, total: 1,
      highInterest: !!d.highInterest, uncertain: !!d.uncertain,
    };
    if (b.type === "installment") {
      const antes = pago.filter((k) => k < inicio).length;
      const restam = Math.max(0, (Number(d.startingRemaining) || 0) - antes);
      if (restam <= 0) return;
      b.total = Math.max(1, Number(d.totalInstallments) || restam);
      b.startNumber = Math.max(1, b.total - restam + 1);
    }
    if (b.type === "single") {
      if (pago.some((k) => k < inicio)) return;
      const movida = Object.keys(months).filter((k) => k >= S && tem(k, "includedIds", id)).sort();
      if (movida.length) b.startMonth = movida[0];
    }
    b.group = sugerirCategoria(b.name, b.creditor);
    st.bills.push(b);
    pago.filter((k) => k >= S).forEach((k) => {
      const chave = b.type === "single" ? b.startMonth : k;
      if ((st.payments[chave] || {})[id]) return;
      const a = valorEm(k, id);
      (st.payments[chave] = st.payments[chave] || {})[id] = {
        amount: Math.max(0, (a === null ? base : a) - corte), accountId: null,
        date: k === MES_ATUAL ? HOJE : k + "-01",
      };
    });
  });

  st.incomes = (o.incomes || []).map((x: any) => ({
    id: String(x.id), name: x.name || "Ganho", value: Number(x.value) || 0, date: x.date || HOJE,
    received: !x.pending, accountId: null,
  }));
  st.accounts = (o.cashAccounts || []).map((a: any) => {
    const k = Object.keys(a.balances || {}).sort();
    return {
      id: String(a.id || novoId()), name: a.name || "Banco",
      balance: k.length ? Number(a.balances[k[k.length - 1]]) || 0 : Number(a.balance) || 0,
    };
  });
  const sm = (months[S] && months[S].sim) || o.globalSim || {};
  st.sim = { weekday: Number(sm.weekday) || 0, weekend: Number(sm.weekend) || 0, on: false };
  return st;
}
