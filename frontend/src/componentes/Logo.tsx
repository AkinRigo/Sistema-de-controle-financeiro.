import { useId } from "react";

/** "NO CORRE das notas" em tinta roxa com contorno preto e borda branca de adesivo. */
export function LogoCompleto({ className }: { className?: string }) {
  const g = useId().replace(/:/g, "");
  const fonte = "'Rubik Wet Paint', cursive";
  const camadas = (props: React.SVGProps<SVGGElement>) => (
    <g fontFamily={fonte} {...props}>
      <text x="46" y="205" fontSize="104" textLength="190" lengthAdjust="spacingAndGlyphs">NO</text>
      <text x="30" y="335" fontSize="132" textLength="460" lengthAdjust="spacingAndGlyphs">CORRE</text>
    </g>
  );
  return (
    <svg viewBox="0 0 520 420" className={className} role="img" aria-label="No Corre das Notas">
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e3d4ff" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <g transform="rotate(-16 360 130)">
        <rect x="226" y="64" width="270" height="140" rx="14" fill="#fff" stroke="#141414" strokeWidth="3" />
        <rect x="238" y="76" width="246" height="116" rx="8" fill="#141414" />
      </g>
      <g transform="rotate(12 360 140)">
        <rect x="220" y="66" width="280" height="148" rx="14" fill="#fff" stroke="#141414" strokeWidth="3" />
        <rect x="232" y="78" width="256" height="124" rx="8" fill="#fff" stroke="#141414" strokeWidth="9" />
        <rect x="246" y="92" width="228" height="96" rx="4" fill="none" stroke="#141414" strokeWidth="3" />
        <text x="360" y="168" textAnchor="middle" fontFamily="Bangers, sans-serif" fontSize="78" fill="#141414">R$</text>
        <text x="262" y="122" textAnchor="middle" fontFamily="Bangers, sans-serif" fontSize="26" fill="#141414">100</text>
        <text x="458" y="178" textAnchor="middle" fontFamily="Bangers, sans-serif" fontSize="26" fill="#141414">100</text>
      </g>
      <g transform="rotate(-5 250 250)">
        {camadas({ fill: "#fff", stroke: "#fff", strokeWidth: 26, strokeLinejoin: "round" })}
        {camadas({ fill: "#141414", stroke: "#141414", strokeWidth: 12, strokeLinejoin: "round" })}
        {camadas({ fill: `url(#${g})` })}
        <g fill="#fff" opacity="0.85">
          <ellipse cx="78" cy="238" rx="12" ry="6" transform="rotate(-25 78 238)" />
          <ellipse cx="82" cy="122" rx="9" ry="5" transform="rotate(-25 82 122)" />
        </g>
        <g transform="translate(300 360) rotate(-4)">
          <rect x="0" y="0" width="190" height="44" rx="10" fill="#141414" stroke="#fff" strokeWidth="5" />
          <text x="95" y="33" textAnchor="middle" fontFamily="Bangers, sans-serif" fontSize="30" letterSpacing="2" fill="#fff">DAS NOTAS</text>
        </g>
      </g>
    </svg>
  );
}

/** Miniatura horizontal do logo da tela de entrada, para o cabeçalho:
 *  as notas de R$ atrás, "NO CORRE" e a etiqueta "DAS NOTAS". */
export function LogoLinha({ className }: { className?: string }) {
  const g = useId().replace(/:/g, "");
  const texto = (props: React.SVGProps<SVGTextElement>) => (
    <text x="14" y="74" fontSize="62" textLength="300" lengthAdjust="spacingAndGlyphs"
      fontFamily="'Rubik Wet Paint', cursive" {...props}>NO CORRE</text>
  );
  return (
    <svg viewBox="0 0 440 124" className={className} role="img" aria-label="No Corre das Notas">
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e3d4ff" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      {/* notas atrás, à direita */}
      <g transform="rotate(-14 362 52)">
        <rect x="296" y="18" width="134" height="70" rx="8" fill="#fff" stroke="#141414" strokeWidth="2" />
        <rect x="302" y="24" width="122" height="58" rx="5" fill="#141414" />
      </g>
      <g transform="rotate(10 360 56)">
        <rect x="292" y="20" width="138" height="74" rx="8" fill="#fff" stroke="#141414" strokeWidth="2" />
        <rect x="298" y="26" width="126" height="62" rx="5" fill="#fff" stroke="#141414" strokeWidth="5" />
        <text x="361" y="73" textAnchor="middle" fontFamily="Bangers, sans-serif" fontSize="40" fill="#141414">R$</text>
      </g>
      <g transform="rotate(-3 200 60)">
        {texto({ fill: "#fff", stroke: "#fff", strokeWidth: 16, strokeLinejoin: "round" })}
        {texto({ fill: "#141414", stroke: "#141414", strokeWidth: 8, strokeLinejoin: "round" })}
        {texto({ fill: `url(#${g})` })}
        <g transform="translate(196 84) rotate(-3)">
          <rect x="0" y="0" width="128" height="30" rx="7" fill="#141414" stroke="#fff" strokeWidth="3" />
          <text x="64" y="23" textAnchor="middle" fontFamily="Bangers, sans-serif" fontSize="21" letterSpacing="1.5" fill="#fff">DAS NOTAS</text>
        </g>
      </g>
    </svg>
  );
}
