// Tela "Gráficos": só desenha o que a API manda. O saldo de cada dia vem pronto de /saldo-diario.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type Categoria, type DiaDeSaldo, type SaldoDiario } from "../api";
import { useCtx } from "../contexto";
import { dinheiro, mesCompleto, num } from "../util";
import type { Vista } from "./ResumoTopo";

type Dica = { html: ReactNode; x: number; y: number } | null;

function useDica() {
  const [dica, setDica] = useState<Dica>(null);
  const mostrar = (html: ReactNode) => (e: React.MouseEvent) => setDica({ html, x: e.clientX, y: e.clientY });
  const caixa = dica && (
    <div className="gr-dica" style={{ left: dica.x + 260 > window.innerWidth ? dica.x - 254 : dica.x + 14, top: dica.y + 14 }}>
      {dica.html}
    </div>
  );
  return { mostrar, esconder: () => setDica(null), caixa };
}

function Bloqueado({ titulo, texto, botao, acao }: { titulo: string; texto: string; botao: string; acao: () => void }) {
  return (
    <div className="gr-bloqueado">
      <div><b>{titulo}</b><br />{texto}</div>
      <button type="button" onClick={acao}>{botao}</button>
    </div>
  );
}

function Painel({ titulo, sub, largo, children }: { titulo: string; sub: string; largo?: boolean; children: ReactNode }) {
  return (
    <section className={`gr-painel${largo ? " largo" : ""}`}>
      <h2>{titulo}</h2>
      <p className="gr-sub">{sub}</p>
      {children}
    </section>
  );
}

const Legenda = ({ itens }: { itens: [string, string][] }) => (
  <div className="gr-legenda">{itens.map(([cls, txt]) => <span key={txt}><i className={cls} />{txt}</span>)}</div>
);

/* ---------- saldo dia a dia (barras) ---------- */
function SaldoDiaADia({ s, mostrar, esconder }: { s: SaldoDiario; mostrar: ReturnType<typeof useDica>["mostrar"]; esconder: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(800);
  const [foco, setFoco] = useState<number | null>(null);
  const [tabela, setTabela] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth || 800));
    ro.observe(el); return () => ro.disconnect();
  }, []);

  const H = 240, m = { t: 16, r: 8, b: 26, l: 64 };
  const vals = s.dias.map((d) => num(d.saldo));
  const passo = escala(Math.max(...vals, 0) - Math.min(...vals, 0));
  const y0 = Math.floor(Math.min(0, ...vals) / passo) * passo, y1 = Math.max(passo, Math.ceil(Math.max(0, ...vals) / passo) * passo);
  const n = s.dias.length, larg = (W - m.l - m.r) / n, bw = Math.max(3, larg - 3);
  const X = (dia: number) => m.l + (dia - 0.5) * larg;
  const Y = (v: number) => m.t + ((y1 - v) / (y1 - y0)) * (H - m.t - m.b);
  const marcas: number[] = []; for (let v = y0; v <= y1 + 0.01; v += passo) marcas.push(v);
  const fim = s.dias[n - 1];
  const cor = (d: DiaDeSaldo) => (num(d.saldo) < 0 ? "var(--red)" : d.previsao ? "var(--gr-claro)" : "var(--gr-forte)");
  const dica = (d: DiaDeSaldo) => (
    <>
      <b>Dia {d.dia}{d.dia === s.hoje ? " · hoje" : d.previsao ? " · previsão" : ""}</b><br />
      Saldo: <b>{dinheiro(d.saldo)}</b>
      {d.movimentos.map((mv, i) => <div key={i}>{mv.nome}: {num(mv.valor) > 0 ? "+" : "−"}{dinheiro(Math.abs(num(mv.valor)))}</div>)}
    </>
  );

  return (
    <>
      <p className="gr-destaque">
        Fecha o mês com <b className={num(fim.saldo) < 0 ? "neg" : "pos"}>{dinheiro(fim.saldo)}</b>.
        {s.menor && <> Menor saldo daqui pra frente: <b className={num(s.menor.saldo) < 0 ? "neg" : ""}>{dinheiro(s.menor.saldo)}</b> no dia {s.menor.dia}.</>}
      </p>
      <Legenda itens={[["gr-forte", "Até hoje"], ["gr-claro", "Previsão"], ["gr-neg", "Saldo negativo"]]} />
      <div ref={ref} className="gr-grafico">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={`Saldo dia a dia em ${mesCompleto(s.mes)}`}
          onMouseLeave={() => { setFoco(null); esconder(); }}>
          {marcas.map((v) => (
            <g key={v}>
              <line x1={m.l} x2={W - m.r} y1={Y(v)} y2={Y(v)} stroke={v === 0 ? "var(--muted)" : "var(--dash)"} strokeWidth={v === 0 ? 1.5 : 1} />
              <text x={m.l - 8} y={Y(v) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">{rotuloEixo(v)}</text>
            </g>
          ))}
          {[1, 5, 10, 15, 20, 25, n].map((d) => (
            <text key={d} x={X(d)} y={H - 6} textAnchor="middle" fontSize="11" fill="var(--muted)">dia {d}</text>
          ))}
          {s.hoje && <text x={X(s.hoje)} y={m.t - 4} textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--ink)">hoje</text>}
          {s.dias.map((d) => {
            const v = num(d.saldo), top = Math.min(Y(v), Y(0)), h = Math.max(1, Math.abs(Y(v) - Y(0)));
            return (
              <g key={d.dia} onMouseMove={(e) => { setFoco(d.dia); mostrar(dica(d))(e); }}>
                <rect x={X(d.dia) - larg / 2} y={m.t} width={larg} height={H - m.t - m.b} fill="transparent" />
                <rect x={X(d.dia) - bw / 2} y={top} width={bw} height={h} rx={3} fill={cor(d)} opacity={foco && foco !== d.dia ? 0.45 : 1} />
              </g>
            );
          })}
        </svg>
      </div>
      <button type="button" className="gr-link" onClick={() => setTabela(!tabela)}>{tabela ? "Esconder tabela" : "Ver em tabela"}</button>
      {tabela && (
        <div className="gr-tabela">
          <table>
            <thead><tr><th>Dia</th><th>Movimento</th><th className="n">Saldo</th></tr></thead>
            <tbody>
              {s.dias.filter((d) => d.movimentos.length || d.dia === 1).map((d) => (
                <tr key={d.dia}><td>{d.dia}</td><td>{d.movimentos.map((mv) => mv.nome).join(", ") || "início do mês"}</td><td className="n">{dinheiro(d.saldo)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function escala(amplitude: number) {
  const bruto = Math.max(amplitude, 1) / 4, pot = 10 ** Math.floor(Math.log10(bruto));
  return [1, 2, 5, 10].map((k) => k * pot).find((p) => p >= bruto) ?? 10 * pot;
}
const rotuloEixo = (v: number) =>
  Math.abs(v) >= 1000 ? `${(v / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil` : v.toLocaleString("pt-BR");

/* ---------- barras horizontais ---------- */
function Trilho({ partes, largura }: { partes: [string, number][]; largura: number }) {
  return (
    <span className="gr-trilho" style={{ width: `${largura}%` }}>
      {partes.filter(([, v]) => v > 0).map(([cls, v]) => <span key={cls} className={cls} style={{ flex: v }} />)}
    </span>
  );
}

export function Graficos({ irPara }: { irPara: (v: Vista, chave?: string) => void }) {
  const { dados, mes } = useCtx();
  const r = dados.resumo;
  const [saldo, setSaldo] = useState<SaldoDiario | null>(null);
  const [cats, setCats] = useState<Categoria[]>([]);
  const [catAberta, setCatAberta] = useState<string | null>(null);
  const { mostrar, esconder, caixa } = useDica();

  useEffect(() => {
    let vivo = true;
    Promise.all([api.saldoDiario(mes), api.categorias(mes)]).then(([s, c]) => { if (vivo) { setSaldo(s); setCats(c); } });
    return () => { vivo = false; };
  }, [mes, dados]);

  const temMovimento = dados.contas.length > 0 || dados.ganhos.length > 0;
  const comValor = cats.filter((c) => num(c.ja_pago) + num(c.falta_pagar) > 0)
    .sort((a, b) => num(b.ja_pago) + num(b.falta_pagar) - (num(a.ja_pago) + num(a.falta_pagar)));
  const maxCat = Math.max(1, ...comValor.map((c) => num(c.ja_pago) + num(c.falta_pagar)));
  const maxBanco = Math.max(1, ...dados.bancos.map((b) => Math.max(0, num(b.saldo))));
  const tenho = num(r.tenho);
  const aberta = comValor.find((c) => c.chave === catAberta);

  return (
    <div className="gr">
      <header>
        <h2 className="gr-titulo">Seu mês em gráficos</h2>
        <p className="gr-sub">{mesCompleto(mes)}. Passe o mouse nos gráficos pra ver os valores.</p>
      </header>

      <div className="gr-grade">
        <Painel titulo="Saldo dia a dia" largo sub="Cada barra é o saldo no fim do dia. Depois de hoje, é a previsão com ganhos e contas nas datas.">
          {!temMovimento
            ? <Bloqueado titulo="Falta pouco pra ver seu mês dia a dia" texto="Cadastre as contas do mês e o que vai entrar." botao="+ Adicionar contas" acao={() => irPara("bills")} />
            : saldo ? <SaldoDiaADia s={saldo} mostrar={mostrar} esconder={esconder} /> : <p className="gr-sub">Carregando…</p>}
        </Painel>

        <Painel titulo="Pra onde vão as notas" sub="Contas do mês por categoria">
          {!comValor.length
            ? <Bloqueado titulo="Ainda sem contas" texto="Quando cadastrar, aparece aqui pra onde vai cada nota." botao="+ Adicionar conta" acao={() => irPara("bills")} />
            : <>
                <Legenda itens={[["gr-forte", "Pago"], ["gr-claro", "Falta pagar"]]} />
                <div className="gr-barras">
                  {comValor.map((c) => {
                    const pago = num(c.ja_pago), falta = num(c.falta_pagar);
                    return (
                      <button type="button" key={c.chave} className={`gr-barra${catAberta === c.chave ? " on" : ""}`}
                        onClick={() => setCatAberta(catAberta === c.chave ? null : c.chave)}
                        onMouseMove={mostrar(<><b>{c.nome}</b><br />Pago: <b>{dinheiro(pago)}</b><br />Falta: <b>{dinheiro(falta)}</b></>)} onMouseLeave={esconder}>
                        <span className="rot">{c.nome}</span>
                        <Trilho partes={[["gr-forte", pago], ["gr-claro", falta]]} largura={((pago + falta) / maxCat) * 100} />
                        <span className="vl">{dinheiro(pago + falta)}</span>
                      </button>
                    );
                  })}
                </div>
                <div className="gr-cat">
                  {aberta
                    ? <><b>{aberta.nome}</b><ul>{aberta.itens.map((i) => <li key={i.conta_id}><span>{i.nome}</span><span>{dinheiro(i.valor_parcela)}</span></li>)}</ul></>
                    : <small>Clique numa categoria pra ver as contas.</small>}
                </div>
              </>}
        </Painel>

        <Painel titulo="Como está o mês" sub="O que já foi e o que ainda falta">
          {!temMovimento
            ? <Bloqueado titulo="Nada pra comparar ainda" texto="Registre ganhos e contas pra ver o que já foi e o que falta." botao="+ Adicionar ganho" acao={() => irPara("incomes", "novoGanho")} />
            : <>
                {([["Ganhos", r.recebido, "Recebido", r.vai_entrar, "Vai entrar"], ["Contas", r.ja_pago, "Pago", r.falta_pagar, "Falta pagar"]] as const).map(([tit, a, ra, b, rb]) => (
                  <div className="gr-progresso" key={tit}>
                    <div className="linha"><span>{tit}</span><span><b>{dinheiro(a)}</b> de {dinheiro(num(a) + num(b))}</span></div>
                    <div onMouseMove={mostrar(<>{ra}: <b>{dinheiro(a)}</b><br />{rb}: <b>{dinheiro(b)}</b></>)} onMouseLeave={esconder}>
                      <Trilho partes={[["gr-forte", num(a)], ["gr-claro", num(b)]]} largura={100} />
                    </div>
                    <Legenda itens={[["gr-forte", ra], ["gr-claro", `${rb} · ${dinheiro(b)}`]]} />
                  </div>
                ))}
              </>}
        </Painel>

        <Painel titulo="Onde está o dinheiro" largo sub="Saldo de hoje em cada banco">
          {!dados.bancos.length
            ? <Bloqueado titulo="Nenhum banco ainda" texto="Cadastre seus bancos ou importe seus dados." botao="+ Adicionar banco" acao={() => irPara("accounts")} />
            : <div className="gr-barras">
                {dados.bancos.map((b) => (
                  <div key={b.id} className="gr-barra"
                    onMouseMove={mostrar(<><b>{b.nome}</b><br />{dinheiro(b.saldo)}{tenho > 0 ? ` · ${Math.round((num(b.saldo) / tenho) * 100)}% do total` : ""}</>)} onMouseLeave={esconder}>
                    <span className="rot">{b.nome}</span>
                    <Trilho partes={[["gr-forte", Math.max(0, num(b.saldo))]]} largura={(Math.max(0, num(b.saldo)) / maxBanco) * 100} />
                    <span className="vl">{dinheiro(b.saldo)}</span>
                  </div>
                ))}
              </div>}
        </Painel>
      </div>
      {caixa}
    </div>
  );
}
