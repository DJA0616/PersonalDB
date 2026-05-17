import { useState, useEffect, useRef, useCallback, createContext, useContext } from "react";

// ═══════════════════════════════════════════════════════════════
// BLOCK KIT — Composable content blocks for probsets & lectures
// ═══════════════════════════════════════════════════════════════

const DS = {
  colors: {
    bg: "#0a0a0a", surface: "#111111", elevated: "#181818",
    border: "#222222", muted: "#2a2a2a", dim: "#555555",
    subtle: "#888888", body: "#c8c8c8", heading: "#efefef",
    accent: "#7eb8d4", accentAlt: "#a0d4b0", err: "#d47e8a",
    glow: "rgba(126,184,212,0.18)", glowStr: "rgba(126,184,212,0.5)",
  },
  font: {
    serif: "'EB Garamond', Georgia, serif",
    mono: "'JetBrains Mono', monospace",
  },
  radius: "4px",
};

const { colors: C, font: F } = DS;

// ═══════════════════════════════════════════════════════════════
// GLOBAL CSS
// ═══════════════════════════════════════════════════════════════

const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=JetBrains+Mono:wght@300;400&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: ${C.bg}; color: ${C.body}; font-family: ${F.serif}; font-size: 16px; line-height: 1.7; -webkit-font-smoothing: antialiased; }
  ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: ${C.bg}; } ::-webkit-scrollbar-thumb { background: ${C.muted}; border-radius: 2px; }
  @keyframes fadeUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
  @keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
  @keyframes timerFadeIn { from { opacity:0; } to { opacity:1; } }
  .bk-fade { animation: fadeUp 0.45s ease both; }
  .bk-fade-fast { animation: fadeUp 0.3s ease both; }
  input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
  input[type=range] { -webkit-appearance: none; width: 100%; height: 2px; background: ${C.muted}; border-radius: 1px; outline: none; cursor: pointer; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 12px; height: 12px; border-radius: 50%; background: ${C.accent}; cursor: pointer; box-shadow: 0 0 6px ${C.glow}; }
  input:focus, select:focus { outline: none; }
`;

// ═══════════════════════════════════════════════════════════════
// GEO BACKGROUND
// ═══════════════════════════════════════════════════════════════

function Geo() {
  if (typeof window !== "undefined" && window.__geoBgInstance) return null;
  return (
    <svg className="geo-static" style={{ position: "fixed", inset: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 0 }} xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="bk-g1" cx="85%" cy="5%" r="35%">
          <stop offset="0%" stopColor="#7eb8d4" stopOpacity="0.05" />
          <stop offset="100%" stopColor="#7eb8d4" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="bk-g2" cx="5%" cy="95%" r="30%">
          <stop offset="0%" stopColor="#a0d4b0" stopOpacity="0.04" />
          <stop offset="100%" stopColor="#a0d4b0" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="100%" height="100%" fill="url(#bk-g1)" />
      <rect width="100%" height="100%" fill="url(#bk-g2)" />
      <g opacity="0.06" stroke="#7eb8d4" strokeWidth="0.6" fill="none">
        <polygon points="820,15 900,70 740,70" /><polygon points="900,70 960,15 960,125" />
        <line x1="820" y1="15" x2="820" y2="125" /><line x1="740" y1="70" x2="960" y2="70" />
      </g>
      <g opacity="0.045" stroke="#a0d4b0" strokeWidth="0.5" fill="none">
        {[80, 140, 200, 260].map((r, i) => <circle key={i} cx="50" cy="95%" r={r} />)}
      </g>
      <g opacity="0.02" stroke="#7eb8d4" strokeWidth="0.4">
        {Array.from({ length: 18 }).map((_, i) => <line key={`h${i}`} x1="0" y1={i * 60} x2="100%" y2={i * 60} />)}
        {Array.from({ length: 24 }).map((_, i) => <line key={`v${i}`} x1={i * 80} y1="0" x2={i * 80} y2="100%" />)}
      </g>
      {[[150, 180], [350, 420], [560, 160], [680, 360], [820, 280], [220, 560]].map(([cx, cy], i) => (
        <circle key={i} cx={cx} cy={cy} r="1.5" fill="#7eb8d4" opacity="0.16" />
      ))}
    </svg>
  );
}

// ═══════════════════════════════════════════════════════════════
// PRIMITIVES
// ═══════════════════════════════════════════════════════════════

function Card({ children, style = {} }) {
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: DS.radius, padding: "22px 26px", position: "relative", overflow: "hidden", ...style }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: `linear-gradient(90deg,transparent,${C.accent}44,transparent)` }} />
      {children}
    </div>
  );
}

function Label({ children, style = {} }) {
  return <span style={{ fontFamily: F.mono, fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: C.dim, ...style }}>{children}</span>;
}

function Mono({ children, style = {} }) {
  return <span style={{ fontFamily: F.mono, fontSize: 12, fontWeight: 300, color: C.subtle, ...style }}>{children}</span>;
}

function Dots({ filled = 1 }) {
  return (
    <span style={{ display: "inline-flex", gap: 3 }}>
      {[1, 2, 3].map(i => (
        <span key={i} style={{ width: 5, height: 5, borderRadius: "50%", background: i <= filled ? C.accent : C.muted, boxShadow: i <= filled ? `0 0 4px ${C.glowStr}` : "none" }} />
      ))}
    </span>
  );
}

function Tag({ children, accent = false, alt = false }) {
  return (
    <span style={{
      fontFamily: F.mono, fontSize: 9, letterSpacing: "0.1em", textTransform: "uppercase",
      padding: "2px 7px", borderRadius: DS.radius,
      border: `1px solid ${alt ? C.accentAlt + "44" : accent ? C.accent + "44" : C.border}`,
      color: alt ? C.accentAlt : accent ? C.accent : C.dim,
    }}>{children}</span>
  );
}

function Rule({ accent = false }) {
  return <div style={{ borderTop: `1px solid ${accent ? C.accent + "44" : C.border}`, margin: "18px 0" }} />;
}

function MathBlock({ children, style = {} }) {
  return (
    <div style={{
      fontFamily: F.mono, fontSize: 14, fontWeight: 300,
      background: C.bg, border: `1px solid ${C.border}`, borderLeft: `2px solid ${C.accent}88`,
      borderRadius: DS.radius, padding: "12px 16px",
      color: C.subtle, letterSpacing: "0.03em", lineHeight: 2, whiteSpace: "pre",
      ...style,
    }}>{children}</div>
  );
}

function InfoRow({ label, value, accent = false }) {
  return (
    <div style={{ display: "flex", gap: 16, padding: "9px 0", borderBottom: `1px solid ${C.border}`, alignItems: "baseline" }}>
      <Mono style={{ minWidth: 160, color: C.dim, flexShrink: 0, fontSize: 11 }}>{label}</Mono>
      <span style={{ fontFamily: F.serif, fontSize: 14, color: accent ? C.accent : C.body, lineHeight: 1.5 }}>{value}</span>
    </div>
  );
}

function QuoteBlock({ text, author }) {
  return (
    <div style={{ padding: "14px 18px", borderLeft: `2px solid ${C.accent}55`, margin: "4px 0" }}>
      <p style={{ fontFamily: F.serif, fontSize: 15, color: C.dim, fontStyle: "italic", lineHeight: 1.7, marginBottom: 6 }}>"{text}"</p>
      <Mono style={{ fontSize: 10 }}>— {author}</Mono>
    </div>
  );
}

function HintBox({ children, variant = "info" }) {
  const borderCol = variant === "comp" ? C.accentAlt + "77" : variant === "warn" ? C.err + "55" : C.accent + "55";
  const bg = variant === "comp" ? C.accentAlt + "08" : variant === "warn" ? C.err + "08" : C.accent + "06";
  const labelColor = variant === "comp" ? C.accentAlt : variant === "warn" ? C.err : C.accent;
  const labelText = variant === "comp" ? "Competition Insight" : variant === "warn" ? "Warning" : "Note";
  return (
    <div style={{ padding: "12px 16px", background: bg, border: `1px solid ${borderCol}22`, borderLeft: `2px solid ${borderCol}`, borderRadius: DS.radius }}>
      <Label style={{ color: labelColor, display: "block", marginBottom: 8 }}>{labelText}</Label>
      <div style={{ fontFamily: F.serif, fontSize: 13, color: C.dim, lineHeight: 1.7 }}>{children}</div>
    </div>
  );
}

function SummaryBox({ intro, points }) {
  return (
    <div style={{ padding: "16px 18px", background: C.elevated, border: `1px solid ${C.accent}33`, borderLeft: `2px solid ${C.accent}88`, borderRadius: DS.radius }}>
      <Label style={{ display: "block", marginBottom: 10, color: C.accent }}>Summary</Label>
      {intro && <p style={{ fontFamily: F.serif, fontSize: 14, color: C.body, lineHeight: 1.65, marginBottom: points ? 12 : 0 }}>{intro}</p>}
      {points && (
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {points.map((p, i) => (
            <div key={i} style={{ display: "flex", gap: 10 }}>
              <Mono style={{ color: C.accent, minWidth: 14, fontSize: 11, flexShrink: 0 }}>{i + 1}.</Mono>
              <span style={{ fontFamily: F.serif, fontSize: 13, color: C.dim, lineHeight: 1.55 }}>{p}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// CONTENT BLOCKS
// ═══════════════════════════════════════════════════════════════

// --- Paragraph ---
// animateIndex: stagger delay = index * 60ms
function Paragraph({ children, animateIndex = 0, style = {} }) {
  return (
    <p
      className="bk-fade"
      style={{
        fontFamily: F.serif, fontSize: 15, color: C.body, lineHeight: 1.75,
        animationDelay: `${animateIndex * 60}ms`,
        ...style,
      }}
    >
      {children}
    </p>
  );
}

// --- Section Header ---
function SectionHeader({ title, subtitle, animateIndex = 0 }) {
  return (
    <div className="bk-fade" style={{ animationDelay: `${animateIndex * 60}ms`, marginTop: 8, marginBottom: 12 }}>
      <Rule accent />
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: subtitle ? 6 : 0 }}>
        <h2 style={{ fontFamily: F.serif, fontSize: 22, fontWeight: 500, color: C.heading, letterSpacing: "-0.01em" }}>{title}</h2>
        <Tag accent>{title}</Tag>
      </div>
      {subtitle && <p style={{ fontFamily: F.serif, fontSize: 13, color: C.dim, fontStyle: "italic" }}>{subtitle}</p>}
    </div>
  );
}

// --- Diagram ---
// Renders custom SVG inside a Card with optional caption.
// render: (C, F, dims) => JSX  where dims = { width, height }
function Diagram({ render, caption, width = 780, height = 260, animateIndex = 0 }) {
  const svg = render(C, F, { width, height });
  return (
    <Card style={{ padding: "18px 22px" }}>
      <div className="bk-fade" style={{ animationDelay: `${animateIndex * 60}ms` }}>
        {caption && <Label style={{ display: "block", marginBottom: 12 }}>{caption}</Label>}
        <div style={{ display: "flex", justifyContent: "center" }}>
          {svg}
        </div>
      </div>
    </Card>
  );
}

// --- SliderGraph ---
// Interactive: slider controls a parameter, graph re-renders live.
// param: { key, label, min, max, step, defaultValue }
// render: (C, F, dims, value) => JSX
function SliderGraph({ param, render, width = 780, height = 260, animateIndex = 0 }) {
  const [value, setValue] = useState(param.defaultValue ?? param.min);
  const svg = render(C, F, { width, height }, value);
  return (
    <Card style={{ padding: "18px 22px" }}>
      <div className="bk-fade" style={{ animationDelay: `${animateIndex * 60}ms` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <Label>{param.label}</Label>
          <Mono style={{ fontSize: 10, color: C.accent }}>{param.key} = {typeof value === "number" ? value.toFixed(2) : value}</Mono>
        </div>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>
          {svg}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Mono style={{ fontSize: 9, color: C.dim }}>{param.min}</Mono>
          <input
            type="range"
            min={param.min} max={param.max} step={param.step ?? 0.01}
            value={value}
            onChange={e => setValue(parseFloat(e.target.value))}
          />
          <Mono style={{ fontSize: 9, color: C.dim }}>{param.max}</Mono>
        </div>
      </div>
    </Card>
  );
}

// --- Equation ---
// display: show the equation in mono math block
// inline: if true, render inline (smaller, no block border)
function Equation({ display, inline = false, animateIndex = 0 }) {
  if (inline) {
    return (
      <span className="bk-fade-fast" style={{
        animationDelay: `${animateIndex * 60}ms`,
        fontFamily: F.mono, fontSize: 13, color: C.accent,
        background: C.bg, padding: "2px 6px", borderRadius: 3,
        border: `1px solid ${C.border}`,
      }}>{display}</span>
    );
  }
  return (
    <MathBlock>
      <span className="bk-fade" style={{ animationDelay: `${animateIndex * 60}ms` }}>{display}</span>
    </MathBlock>
  );
}

// --- Hint ---
// Collapsed by default, expand on click.
function Hint({ children, revealLabel = "Show hint", animateIndex = 0 }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bk-fade" style={{ animationDelay: `${animateIndex * 60}ms` }}>
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          style={{
            fontFamily: F.serif, fontSize: 13, padding: "6px 14px",
            borderRadius: DS.radius, border: `1px dashed ${C.accent}44`,
            background: "transparent", color: C.dim, cursor: "pointer",
            transition: "all 0.2s",
          }}
        >
          {revealLabel} →
        </button>
      ) : (
        <div style={{ padding: "10px 14px", background: C.bg, border: `1px solid ${C.border}`, borderLeft: `2px solid ${C.accent}77`, borderRadius: DS.radius }}>
          <p style={{ fontFamily: F.serif, fontSize: 13, color: C.dim, lineHeight: 1.65 }}>{children}</p>
        </div>
      )}
    </div>
  );
}

// --- Example ---
// Labeled example box
function Example({ label = "Example", children, animateIndex = 0 }) {
  return (
    <div className="bk-fade" style={{
      animationDelay: `${animateIndex * 60}ms`,
      padding: "14px 18px", background: C.surface,
      border: `1px solid ${C.border}`, borderRadius: DS.radius,
    }}>
      <Label style={{ display: "block", marginBottom: 8, color: C.accentAlt }}>{label}</Label>
      <div style={{ fontFamily: F.serif, fontSize: 14, color: C.body, lineHeight: 1.7 }}>{children}</div>
    </div>
  );
}

// --- Spacer ---
function Spacer({ size = 16 }) {
  return <div style={{ height: size }} />;
}

// ═══════════════════════════════════════════════════════════════
// ANSWER FIELD COMPONENTS
// ═══════════════════════════════════════════════════════════════

function MCField({ question, choices, correct, pts = 3, diff = 1, explain, animateIndex = 0, onResult, suppressExplain }) {
  const [selected, setSelected] = useState(null);
  const [revealed, setRevealed] = useState(false);
  const [showExplain, setShowExplain] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const startRef = useRef(Date.now());

  return (
    <div className="bk-fade" style={{ animationDelay: `${animateIndex * 60}ms` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Tag>MC</Tag><Dots filled={diff} />
        </div>
        <Mono style={{ fontSize: 10 }}>{pts} pts</Mono>
      </div>
      <p style={{ fontFamily: F.serif, fontSize: 14, color: C.body, lineHeight: 1.65, marginBottom: 14 }}>{question}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        {choices.map((ch, i) => {
          const L = ["A", "B", "C", "D"][i];
          const on = selected === i;
          const ok = revealed && i === correct;
          const bad = revealed && on && i !== correct;
          return (
            <div
              key={i}
              onClick={() => !revealed && setSelected(i)}
              style={{
                display: "flex", alignItems: "center", gap: 12, padding: "10px 14px",
                border: `1px solid ${ok ? C.accentAlt + "aa" : bad ? C.err + "88" : on ? C.accent + "88" : C.border}`,
                borderRadius: DS.radius, cursor: revealed ? "default" : "pointer",
                background: ok ? C.accentAlt + "0e" : bad ? C.err + "0e" : on ? C.accent + "0e" : "transparent",
                boxShadow: on ? `0 0 12px ${C.glow}` : "none", transition: "all 0.18s ease",
              }}
            >
              <Mono style={{ fontSize: 10, color: on ? C.accent : C.dim, minWidth: 14 }}>{L}</Mono>
              <span style={{ fontFamily: F.serif, fontSize: 14, color: ok ? C.accentAlt : bad ? C.err : on ? C.accent : C.body, flex: 1, lineHeight: 1.5 }}>{ch}</span>
              {ok && <Mono style={{ fontSize: 9, color: C.accentAlt }}>✓</Mono>}
              {bad && <Mono style={{ fontSize: 9, color: C.err }}>✗</Mono>}
            </div>
          );
        })}
      </div>
      {selected !== null && (
        <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
          {!revealed && (
            <button onClick={() => {
              const att = attempts + 1;
              setAttempts(att);
              setRevealed(true);
              if (onResult) onResult({ correct: selected === correct, attempts: att, timeSpent: Math.round((Date.now() - startRef.current) / 1000) });
            }} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.accent}55`, background: "transparent", color: C.accent, cursor: "pointer" }}>
              Check
            </button>
          )}
          <button onClick={() => { setSelected(null); setRevealed(false); setShowExplain(false); setAttempts(0); }} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.border}`, background: "transparent", color: C.subtle, cursor: "pointer" }}>
            Clear
          </button>
          {revealed && explain && !suppressExplain && (
            <button onClick={() => setShowExplain(v => !v)} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.border}`, background: "transparent", color: C.subtle, cursor: "pointer" }}>
              {showExplain ? "Hide" : "Explain"}
            </button>
          )}
        </div>
      )}
      {showExplain && explain && (
        <div style={{ marginTop: 10, padding: "10px 14px", background: C.bg, border: `1px solid ${C.border}`, borderLeft: `2px solid ${C.accent}88`, borderRadius: DS.radius }}>
          <p style={{ fontFamily: F.serif, fontSize: 13, color: C.dim, lineHeight: 1.65 }}>{explain}</p>
        </div>
      )}
    </div>
  );
}

function TFField({ statement, correct = true, pts = 3, diff = 1, animateIndex = 0, onResult }) {
  const [selected, setSelected] = useState(null);
  const [revealed, setRevealed] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const startRef = useRef(Date.now());

  return (
    <div className="bk-fade" style={{ animationDelay: `${animateIndex * 60}ms` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Tag>T / F</Tag><Dots filled={diff} />
        </div>
        <Mono style={{ fontSize: 10 }}>{pts} pts</Mono>
      </div>
      <p style={{ fontFamily: F.serif, fontSize: 14, fontStyle: "italic", color: C.body, lineHeight: 1.65, marginBottom: 16, paddingLeft: 12, borderLeft: `2px solid ${C.accent}44` }}>
        "{statement}"
      </p>
      <div style={{ display: "flex", gap: 10 }}>
        {[true, false].map(val => {
          const label = val ? "True" : "False";
          const on = selected === val;
          const ok = revealed && val === correct;
          const bad = revealed && on && val !== correct;
          return (
            <div
              key={label}
              onClick={() => !revealed && setSelected(val)}
              style={{
                flex: 1, padding: "14px 0", textAlign: "center",
                border: `1px solid ${ok ? C.accentAlt + "aa" : bad ? C.err + "88" : on ? C.accent + "88" : C.border}`,
                borderRadius: DS.radius, cursor: revealed ? "default" : "pointer",
                background: ok ? C.accentAlt + "0e" : bad ? C.err + "0e" : on ? C.accent + "0e" : "transparent",
                boxShadow: on ? `0 0 14px ${C.glow}` : "none",
                fontFamily: F.serif, fontSize: 16,
                color: ok ? C.accentAlt : bad ? C.err : on ? C.accent : C.subtle,
                transition: "all 0.18s ease",
              }}
            >
              {label}{ok && " ✓"}{bad && " ✗"}
            </div>
          );
        })}
      </div>
      {selected !== null && (
        <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
          {!revealed && (
            <button onClick={() => {
              const att = attempts + 1;
              setAttempts(att);
              setRevealed(true);
              if (onResult) onResult({ correct: selected === correct, attempts: att, timeSpent: Math.round((Date.now() - startRef.current) / 1000) });
            }} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.accent}55`, background: "transparent", color: C.accent, cursor: "pointer" }}>
              Check
            </button>
          )}
          <button onClick={() => { setSelected(null); setRevealed(false); setAttempts(0); }} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.border}`, background: "transparent", color: C.subtle, cursor: "pointer" }}>
            Clear
          </button>
        </div>
      )}
    </div>
  );
}

function INTField({ question, answer, pts = 4, diff = 2, hint, animateIndex = 0, onResult, suppressHint }) {
  const [val, setVal] = useState("");
  const [checked, setChecked] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [focused, setFocused] = useState(false);
  const startRef = useRef(Date.now());
  const intVal = parseInt(val) || 0;
  const isCorrect = parseInt(val) === answer;

  const stepUp = () => { if (!checked) { setVal(String(Math.min(999, intVal + 1))); } };
  const stepDown = () => { if (!checked) { setVal(String(Math.max(0, intVal - 1))); } };

  const spinBtn = (char, onClick) => (
    <button
      onClick={onClick}
      disabled={checked}
      style={{
        width: 28, height: 22, display: "flex", alignItems: "center", justifyContent: "center",
        border: `1px solid ${checked ? C.muted : C.accent}55`,
        borderRadius: 3, background: "transparent",
        color: checked ? C.muted : C.accent,
        fontFamily: F.mono, fontSize: 10, lineHeight: 1, cursor: checked ? "default" : "pointer",
        padding: 0, transition: "all 0.15s",
        opacity: checked ? 0.35 : 1,
      }}
      onMouseEnter={e => { if (!checked) { e.target.style.background = C.accent + "15"; e.target.style.borderColor = C.accent + "88"; } }}
      onMouseLeave={e => { if (!checked) { e.target.style.background = "transparent"; e.target.style.borderColor = C.accent + "55"; } }}
    >{char}</button>
  );

  const borderCol = checked ? (isCorrect ? C.accentAlt + "99" : C.err + "88")
    : focused ? C.accent + "77"
    : C.border;

  return (
    <div className="bk-fade" style={{ animationDelay: `${animateIndex * 60}ms` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Tag>INT</Tag><Dots filled={diff} />
        </div>
        <Mono style={{ fontSize: 10 }}>{pts} pts</Mono>
      </div>
      <p style={{ fontFamily: F.serif, fontSize: 14, color: C.body, lineHeight: 1.65, marginBottom: 16 }}>{question}</p>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="text" inputMode="numeric" pattern="[0-9]*"
          value={val}
          onChange={e => { const v = e.target.value.replace(/[^0-9]/g, "").slice(0, 3); setVal(v); setChecked(false); }}
          placeholder="0"
          onFocus={() => { if (!checked) setFocused(true); }}
          onBlur={() => setFocused(false)}
          style={{
            width: 80, padding: "10px 12px",
            border: `1px solid ${borderCol}`,
            borderRadius: DS.radius,
            background: checked ? (isCorrect ? C.accentAlt + "0a" : C.err + "0a") : C.bg,
            color: checked ? (isCorrect ? C.accentAlt : C.err) : C.heading,
            fontFamily: F.mono, fontSize: 22, fontWeight: 300, textAlign: "center",
            boxShadow: val ? `0 0 10px ${C.glow}` : "none",
            transition: "all 0.2s", outline: "none", caretColor: C.accent,
          }}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {spinBtn("+", stepUp)}
          {spinBtn("−", stepDown)}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <Mono style={{ fontSize: 9, letterSpacing: "0.12em" }}>INTEGER · 0 – 999</Mono>
          {checked && <Mono style={{ fontSize: 9, color: isCorrect ? C.accentAlt : C.err }}>{isCorrect ? "✓ correct" : "✗ try again"}</Mono>}
        </div>
      </div>
      {val !== "" && (
        <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
          {!checked && (
            <button onClick={() => {
              const att = attempts + 1;
              setAttempts(att);
              setChecked(true);
              const ok = parseInt(val) === answer;
              if (onResult) onResult({ correct: ok, attempts: att, timeSpent: Math.round((Date.now() - startRef.current) / 1000) });
            }} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.accent}55`, background: "transparent", color: C.accent, cursor: "pointer" }}>
              Check
            </button>
          )}
          <button onClick={() => { setVal(""); setChecked(false); setShowHint(false); setAttempts(0); }} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.border}`, background: "transparent", color: C.subtle, cursor: "pointer" }}>
            Clear
          </button>
          {hint && !checked && !suppressHint && <button onClick={() => setShowHint(v => !v)} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.border}`, background: "transparent", color: C.subtle, cursor: "pointer" }}>{showHint ? "Hide hint" : "Hint"}</button>}
        </div>
      )}
      {showHint && hint && (
        <div style={{ marginTop: 10, padding: "10px 14px", background: C.bg, border: `1px solid ${C.border}`, borderLeft: `2px solid ${C.accent}88`, borderRadius: DS.radius }}>
          <p style={{ fontFamily: F.serif, fontSize: 13, color: C.dim, lineHeight: 1.65 }}>{hint}</p>
        </div>
      )}
    </div>
  );
}

function FIEField({ question, equation, cards, slotCount = 2, correct = () => false, correctDisplay, pts = 5, diff = 3, animateIndex = 0, onResult }) {
  const CARD_LABELS = {};
  const [attempts, setAttempts] = useState(0);
  const startRef = useRef(Date.now());
  cards.forEach(c => { CARD_LABELS[c] = c; });

  const initSlots = {};
  for (let i = 0; i < slotCount; i++) initSlots[i] = null;
  const initTexts = {};
  for (let i = 0; i < slotCount; i++) initTexts[i] = "";

  const [slots, setSlots] = useState(initSlots);
  const [texts, setTexts] = useState(initTexts);
  const [selected, setSelected] = useState(null);
  const [hovering, setHovering] = useState(null);
  const [checked, setChecked] = useState(false);

  const usedCards = new Set(Object.values(slots).filter(Boolean));

  const blankVal = id => slots[id] ? CARD_LABELS[slots[id]] : texts[id];
  const anyFilled = Object.keys(slots).some(id => slots[id] || texts[id]);
  const allFilled = Object.keys(slots).every(id => slots[id] || texts[id].trim());
  const isCorrect = correct(Object.keys(slots).map(id => blankVal(id)));

  const placeCard = (card, slotId) => {
    const next = { ...slots };
    Object.keys(next).forEach(k => { if (next[k] === card) next[k] = null; });
    next[slotId] = card;
    setSlots(next);
    setTexts(t => ({ ...t, [slotId]: "" }));
    setSelected(null);
    setChecked(false);
  };

  const removeCard = slotId => {
    setSlots({ ...slots, [slotId]: null });
    setChecked(false);
  };

  const handleCardClick = card => {
    if (usedCards.has(card)) return;
    setSelected(selected === card ? null : card);
  };

  const handleSlotClick = slotId => {
    if (selected !== null) { placeCard(selected, slotId); return; }
    if (slots[slotId]) { removeCard(slotId); }
  };

  const handleDrop = (e, slotId) => {
    e.preventDefault();
    const card = e.dataTransfer.getData("card");
    if (card) placeCard(card, slotId);
    setHovering(null);
  };

  const sanitize = v => v.replace(/[^a-zA-Z0-9]/g, "").slice(0, 8);

  const Blank = ({ slotId }) => {
    const card = slots[slotId];
    const text = texts[slotId];
    const hover = hovering === slotId;
    const val = blankVal(slotId);
    const slotOk = checked && isCorrect;
    const slotErr = checked && !isCorrect && val;

    const borderCol = slotOk ? C.accentAlt + "aa"
      : slotErr ? C.err + "88"
      : hover || (selected && !card) ? C.accent + "99"
      : card ? C.accent + "66"
      : text ? C.accent + "55"
      : C.accent + "40";

    const bgCol = slotOk ? C.accentAlt + "0e"
      : slotErr ? C.err + "0a"
      : hover ? C.accent + "12"
      : card ? C.accent + "09"
      : "transparent";

    if (card) {
      return (
        <div
          onDragOver={e => { e.preventDefault(); setHovering(slotId); }}
          onDragLeave={() => setHovering(null)}
          onDrop={e => handleDrop(e, slotId)}
          style={{
            display: "inline-flex", alignItems: "center", gap: 5,
            height: 30, padding: "0 8px 0 10px",
            border: `1px solid ${borderCol}`, borderRadius: DS.radius,
            background: bgCol, boxShadow: `0 0 10px ${C.glow}`,
            fontFamily: F.mono, fontSize: 13, color: slotOk ? C.accentAlt : slotErr ? C.err : C.accent,
            position: "relative", bottom: 1, userSelect: "none",
            transition: "all 0.15s",
          }}
        >
          {CARD_LABELS[card]}
          <span onClick={e => { e.stopPropagation(); removeCard(slotId); }}
            style={{ fontSize: 9, color: C.dim, cursor: "pointer", lineHeight: 1, paddingLeft: 2 }}>✕</span>
        </div>
      );
    }

    return (
      <div
        onDragOver={e => { e.preventDefault(); setHovering(slotId); }}
        onDragLeave={() => setHovering(null)}
        onDrop={e => handleDrop(e, slotId)}
        style={{ display: "inline-flex", alignItems: "center", position: "relative", bottom: 1 }}
      >
        {selected ? (
          <div
            onClick={() => handleSlotClick(slotId)}
            style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              minWidth: 44, height: 30, padding: "0 8px",
              border: `1px dashed ${borderCol}`, borderRadius: DS.radius,
              background: bgCol, boxShadow: hover ? `0 0 10px ${C.glow}` : "none",
              cursor: "pointer", fontFamily: F.mono, fontSize: 11, color: C.dim,
              transition: "all 0.15s",
            }}
          >
            <span style={{ fontSize: 9, letterSpacing: "0.04em" }}>drop here</span>
          </div>
        ) : (
          <input
            type="text" value={text} placeholder="type" maxLength={8}
            onChange={e => { setTexts(t => ({ ...t, [slotId]: sanitize(e.target.value) })); setChecked(false); }}
            style={{
              width: Math.max(52, text.length * 9 + 20), height: 30, padding: "0 8px",
              border: `1px dashed ${borderCol}`, borderRadius: DS.radius,
              background: text ? C.accent + "09" : "transparent",
              color: slotOk ? C.accentAlt : slotErr ? C.err : C.accent,
              fontFamily: F.mono, fontSize: 13, textAlign: "center", outline: "none",
              transition: "all 0.15s", caretColor: C.accent,
            }}
            onFocus={e => { e.target.style.borderColor = C.accent + "88"; e.target.style.borderStyle = "solid"; }}
            onBlur={e => { e.target.style.borderColor = text ? C.accent + "55" : C.accent + "40"; e.target.style.borderStyle = "dashed"; }}
          />
        )}
      </div>
    );
  };

  return (
    <div className="bk-fade" style={{ animationDelay: `${animateIndex * 60}ms` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Tag>FIE</Tag><Dots filled={diff} />
        </div>
        <Mono style={{ fontSize: 10 }}>{pts} pts</Mono>
      </div>

      <p style={{ fontFamily: F.serif, fontSize: 14, color: C.body, lineHeight: 1.65, marginBottom: 14 }}>{question}</p>

      <div style={{
        fontFamily: F.mono, fontSize: 15, fontWeight: 300,
        background: C.bg, border: `1px solid ${C.border}`, borderLeft: `2px solid ${C.accent}88`,
        borderRadius: DS.radius, padding: "14px 18px",
        color: C.subtle, letterSpacing: "0.03em",
        display: "flex", alignItems: "center", flexWrap: "wrap", gap: 5,
        lineHeight: 2.6, marginBottom: 18,
      }}>
        {equation.map((part, i) => {
          if (part === "__BLANK__") {
            const slotId = Object.keys(slots).find(k => slots[k] === null && texts[k] === "") ?? "0";
            return <Blank key={i} slotId={slotId} />;
          }
          return <span key={i}>{part}</span>;
        })}
      </div>

      <div style={{ marginBottom: 8 }}>
        <Label>{selected ? "tap a blank or drag to place — or type directly" : "card bank — tap to select · drag to place · or type in blank"}</Label>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
        {cards.map(card => {
          const inSlot = usedCards.has(card);
          const isSel = selected === card;
          return (
            <div
              key={card} draggable={!inSlot}
              onDragStart={e => { e.dataTransfer.setData("card", card); }}
              onDragEnd={() => {}}
              onClick={() => handleCardClick(card)}
              style={{
                padding: "7px 16px",
                border: `1px solid ${isSel ? C.accent + "aa" : inSlot ? C.border + "22" : C.border}`,
                borderRadius: DS.radius,
                background: isSel ? C.accent + "18" : "transparent",
                color: inSlot ? C.muted : isSel ? C.accent : C.body,
                fontFamily: F.mono, fontSize: 13, fontWeight: 300,
                cursor: inSlot ? "default" : "grab",
                opacity: inSlot ? 0.22 : 1,
                boxShadow: isSel ? `0 0 14px ${C.glow}` : "none",
                transition: "all 0.15s ease", userSelect: "none",
              }}
            >
              {CARD_LABELS[card]}
            </div>
          );
        })}
      </div>

      <div style={{ marginBottom: 12, padding: "8px 12px", border: `1px solid ${C.border}`, borderRadius: DS.radius, background: C.elevated }}>
        <Mono style={{ fontSize: 9, letterSpacing: "0.1em" }}>FREE TEXT — type directly in any blank · letters & digits only · max 8 chars</Mono>
      </div>

      {anyFilled && (
        <div style={{ display: "flex", gap: 8 }}>
          {!checked && allFilled && (
            <button onClick={() => {
              const att = attempts + 1;
              setAttempts(att);
              setChecked(true);
              const ok = correct(Object.keys(slots).map(id => blankVal(id)));
              if (onResult) onResult({ correct: ok, attempts: att, timeSpent: Math.round((Date.now() - startRef.current) / 1000) });
            }} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.accent}55`, background: "transparent", color: C.accent, cursor: "pointer" }}>
              Check
            </button>
          )}
          <button onClick={() => { setSlots(initSlots); setTexts(initTexts); setSelected(null); setChecked(false); setAttempts(0); }} style={{ fontFamily: F.serif, fontSize: 13, padding: "5px 14px", borderRadius: DS.radius, border: `1px solid ${C.border}`, background: "transparent", color: C.subtle, cursor: "pointer" }}>
            Clear all
          </button>
        </div>
      )}

      {checked && isCorrect && correctDisplay && <Mono style={{ display: "block", marginTop: 10, color: C.accentAlt, fontSize: 10, letterSpacing: "0.1em" }}>✓ {correctDisplay}</Mono>}
      {checked && !isCorrect && <Mono style={{ display: "block", marginTop: 10, color: C.err, fontSize: 10, letterSpacing: "0.1em" }}>✗ review your answer</Mono>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// PROGRESS STORAGE — localStorage persistence
// ═══════════════════════════════════════════════════════════════

const ProgStorage = (() => {
  const KEY = "smpt-progress";

  const _all = () => {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; }
    catch { return {}; }
  };
  const _write = (data) => { try { localStorage.setItem(KEY, JSON.stringify(data)); } catch(e) { console.error('ProgStorage _write FAIL', e); } };

  return {
    load(file) {
      return _all()[file] || null;
    },

    save(file, record) {
      const data = _all();
      data[file] = { ...(data[file] || {}), ...record };
      _write(data);
    },

    updateProblem(file, blockIndex, result) {
      const data = _all();
      const rec = data[file] || { problems: {} };
      const prev = rec.problems[blockIndex] || {};
      rec.problems[blockIndex] = {
        ...prev,
        answered: true,
        correct: result.correct,
        attempts: result.attempts,
        timeSpent: result.timeSpent,
      };
      const pts = prev.pointsAvailable ?? 0;
      if (result.correct && !prev.correct) {
        rec.pointsEarned = (rec.pointsEarned || 0) + pts;
      }
      if (!result.correct && prev.correct) {
        rec.pointsEarned = Math.max(0, (rec.pointsEarned || 0) - pts);
      }
      data[file] = rec;
      _write(data);
    },

    setProblemMeta(file, blockIndex, meta) {
      const data = _all();
      const rec = data[file] || { problems: {} };
      rec.problems[blockIndex] = { ...(rec.problems[blockIndex] || {}), ...meta };
      data[file] = rec;
      _write(data);
    },

    startSession(file, totalPoints) {
      const data = _all();
      data[file] = {
        ...(data[file] || {}),
        startedAt: new Date().toISOString(),
        totalPointsAvailable: totalPoints,
        pointsEarned: data[file]?.pointsEarned || 0,
        problems: data[file]?.problems || {},
      };
      _write(data);
    },

    endSession(file) {
      const data = _all();
      if (data[file]) {
        const rec = data[file];
        rec.completedAt = new Date().toISOString();
        const probs = Object.values(rec.problems || {});
        rec.totalTimeSeconds = probs.reduce((sum, p) => sum + (p.timeSpent || 0), 0);
        if (rec.startedAt) {
          rec.wallTimeSeconds = Math.round((new Date(rec.completedAt) - new Date(rec.startedAt)) / 1000);
        }
        _write(data);
      }
    },

    getHighscores() {
      const data = _all();
      return Object.entries(data)
        .filter(([, r]) => r.pointsEarned > 0)
        .map(([file, r]) => ({
          file,
          title: file.split("/").pop().replace(/\.jsx$/, "").replace(/_/g, " "),
          pointsEarned: r.pointsEarned || 0,
          totalPoints: r.totalPointsAvailable || 0,
          pct: r.totalPointsAvailable ? Math.round((r.pointsEarned / r.totalPointsAvailable) * 100) : 0,
          completedAt: r.completedAt || null,
          startedAt: r.startedAt || null,
          examMode: r.examMode || false,
          totalTimeSeconds: r.totalTimeSeconds || 0,
          wallTimeSeconds: r.wallTimeSeconds || 0,
        }))
        .sort((a, b) => b.pct - a.pct || b.pointsEarned - a.pointsEarned);
    },

    getHistory(limit = 10) {
      const data = _all();
      return Object.entries(data)
        .filter(([, r]) => r.startedAt)
        .map(([file, r]) => ({
          file,
          title: file.split("/").pop().replace(/\.jsx$/, "").replace(/_/g, " "),
          pointsEarned: r.pointsEarned || 0,
          totalPoints: r.totalPointsAvailable || 0,
          pct: r.totalPointsAvailable ? Math.round((r.pointsEarned / r.totalPointsAvailable) * 100) : 0,
          completedAt: r.completedAt || null,
          startedAt: r.startedAt || null,
          answered: r.problems ? Object.values(r.problems).filter(p => p.answered).length : 0,
          total: r.problems ? Object.keys(r.problems).length : 0,
          totalTimeSeconds: r.totalTimeSeconds || 0,
          wallTimeSeconds: r.wallTimeSeconds || 0,
        }))
        .sort((a, b) => (b.completedAt || b.startedAt || "").localeCompare(a.completedAt || a.startedAt || ""))
        .slice(0, limit);
    },

    clearAll() {
      try { localStorage.removeItem(KEY); } catch {}
    },
  };
})();

// ═══════════════════════════════════════════════════════════════
// TIMER CONTEXT
// ═══════════════════════════════════════════════════════════════

const TimerCtx = createContext({ frozen: false, timeLeft: 0, phase: "blue" });
const useTimer = () => useContext(TimerCtx);

// ═══════════════════════════════════════════════════════════════
// TIMER OVERLAY
// ═══════════════════════════════════════════════════════════════

const PHASES = {
  blue:  { c: "#7eb8d4", g: "rgba(126,184,212,0.55)", dim: "rgba(126,184,212,0.09)", label: "normal",       transition: 300, floatPhaseDiv: 2000, floatAmp: 6 },
  sage:  { c: "#a0d4b0", g: "rgba(160,212,176,0.55)", dim: "rgba(160,212,176,0.07)", label: "≤ 10s",        transition: 200, floatPhaseDiv: 1000, floatAmp: 5 },
  red:   { c: "#d47e8a", g: "rgba(212,126,138,0.65)", dim: "rgba(212,126,138,0.10)", label: "≤ 5s — urgent", transition: 100, floatPhaseDiv: 500,  floatAmp: 4 },
};

// 6-point polygon frames centered at (200,200) in 400x400 space
const pt = (deg, r) => [
  200 + r * Math.cos((deg - 90) * Math.PI / 180),
  200 + r * Math.sin((deg - 90) * Math.PI / 180),
];

const FRAMES = [
  [pt(0, 108), pt(60, 48), pt(120, 108), pt(180, 48), pt(240, 108), pt(300, 48)],
  [pt(0, 108), pt(90, 108), pt(180, 108), pt(270, 108), pt(45, 50), pt(225, 50)],
  [pt(0, 108), pt(72, 108), pt(144, 108), pt(216, 108), pt(288, 108), pt(180, 38)],
  [pt(0, 108), pt(60, 108), pt(120, 108), pt(180, 108), pt(240, 108), pt(300, 108)],
  [pt(5, 128), pt(75, 58), pt(148, 116), pt(212, 64), pt(278, 120), pt(335, 76)],
  [pt(0, 76), pt(58, 126), pt(122, 70), pt(178, 126), pt(238, 76), pt(300, 112)],
  [pt(22, 116), pt(84, 50), pt(158, 100), pt(222, 50), pt(288, 116), pt(196, 80)],
];

const sCurve = (a, b, t) => a + (b - a) * (10 * Math.pow(t, 3) - 15 * Math.pow(t, 4) + 6 * Math.pow(t, 5));
const sCurvePts = (p1, p2, t) => p1.map((p, i) => [sCurve(p[0], p2[i][0], t), sCurve(p[1], p2[i][1], t)]);
const str = pts => pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
const scale = (pts, s) => pts.map(([x, y]) => [200 + (x - 200) * s, 200 + (y - 200) * s]);

function TimerOverlay({ enabled, duration, onExpire, phaseThresholds, phaseConfig }) {
  const [timeLeft, setTimeLeft] = useState(duration);
  const [running, setRunning] = useState(false);
  const [frozen, setFrozen] = useState(false);
  const [pts, setPts] = useState(FRAMES[0]);
  const baseRef = useRef(FRAMES[0]);   // un-oscillated base shape
  const ptsRef = useRef(FRAMES[0]);    // display points (oscillated)
  const snapRafRef = useRef(null);
  const floatRafRef = useRef(null);
  const snapActiveRef = useRef(false);
  const tickRef = useRef(0);
  const phaseRef = useRef("blue");
  const startedRef = useRef(false);

  const thresholds = phaseThresholds ?? { sage: 10, red: 5 };
  const mergedPhases = { ...PHASES };
  if (phaseConfig) {
    for (const k of Object.keys(phaseConfig)) {
      mergedPhases[k] = { ...mergedPhases[k], ...phaseConfig[k] };
    }
  }

  const phase = timeLeft <= thresholds.red ? "red" : timeLeft <= thresholds.sage ? "sage" : "blue";
  const col = mergedPhases[phase];
  useEffect(() => { phaseRef.current = phase; }, [phase]);

  // Auto-start on mount
  useEffect(() => {
    if (enabled && !startedRef.current) {
      startedRef.current = true;
      setRunning(true);
    }
  }, [enabled]);

  // Continuous float oscillation — runs on every render, reads live phaseRef
  const floatLoop = useCallback(() => {
    if (floatRafRef.current) cancelAnimationFrame(floatRafRef.current);
    const step = now => {
      if (!snapActiveRef.current && floatRafRef.current) {
        const amp = mergedPhases[phaseRef.current].floatAmp;
        const phaseDiv = mergedPhases[phaseRef.current].floatPhaseDiv;
        const base = baseRef.current;
        const cur = base.map(([x, y], i) => [
          x + amp * Math.cos(now / phaseDiv * Math.PI + i),
          y + amp * Math.sin(now / phaseDiv * Math.PI + i),
        ]);
        ptsRef.current = cur;
        setPts(cur.map(p => [...p]));
      }
      floatRafRef.current = requestAnimationFrame(step);
    };
    floatRafRef.current = requestAnimationFrame(step);
  }, []);

  // Tick every second — snap morphs base then floatLoop oscillates it
  useEffect(() => {
    if (!running || timeLeft === 0 || !enabled) return;
    const id = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) {
          setRunning(false);
          setFrozen(true);
          if (onExpire) onExpire();
          return 0;
        }
        return t - 1;
      });
      tickRef.current++;
      const idx = tickRef.current;
      // Snap: morph base from previous frame to current frame
      if (snapRafRef.current) cancelAnimationFrame(snapRafRef.current);
      snapActiveRef.current = true;
      const from = baseRef.current;
      const to = FRAMES[idx % FRAMES.length];
      const amp = mergedPhases[phaseRef.current].floatAmp;
      const phaseDiv = mergedPhases[phaseRef.current].floatPhaseDiv;
      const dur = mergedPhases[phaseRef.current].transition;
      const t0 = performance.now();
      const step = now => {
        const t = Math.min((now - t0) / dur, 1);
        const morphed = sCurvePts(from, to, t);
        baseRef.current = morphed;
        const curFloated = morphed.map(([x, y], i) => [
          x + amp * Math.cos(now / phaseDiv * Math.PI + i),
          y + amp * Math.sin(now / phaseDiv * Math.PI + i),
        ]);
        ptsRef.current = curFloated;
        setPts(curFloated.map(p => [...p]));
        if (t < 1) snapRafRef.current = requestAnimationFrame(step);
        else snapActiveRef.current = false;
      };
      snapRafRef.current = requestAnimationFrame(step);
    }, 1000);
    return () => clearInterval(id);
  }, [running, timeLeft, enabled, onExpire]);

  // Float animation — restarts on phase change for fresh amp/speed
  useEffect(() => {
    if (!enabled || !running) return;
    floatLoop();
    return () => { if (floatRafRef.current) cancelAnimationFrame(floatRafRef.current); };
  }, [running, enabled, phase, floatLoop]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (snapRafRef.current) cancelAnimationFrame(snapRafRef.current);
      if (floatRafRef.current) cancelAnimationFrame(floatRafRef.current);
    };
  }, []);

  if (!enabled) return null;

  const mm = String(Math.floor(timeLeft / 60)).padStart(2, "0");
  const ss = String(timeLeft % 60).padStart(2, "0");
  const inner = scale(pts, 0.46);
  const outer = scale(pts, 1.18);

  const ctxVal = { frozen, timeLeft, phase };

  return (
    <TimerCtx.Provider value={ctxVal}>
      {/* Inline timer — positioned by parent */}
      <div style={{
        position: "relative", display: "inline-flex", flexDirection: "column",
        alignItems: "center", flexShrink: 0,
        pointerEvents: "none",
      }}>
        {/* Morphing polygon — behind timer text */}
        <svg
          width="140" height="140" viewBox="0 0 400 400"
          style={{
            position: "absolute", left: "50%", top: "50%",
            transform: "translate(-50%,-50%)", pointerEvents: "none",
            zIndex: 0, opacity: 0.35,
            animation: "timerFadeIn 1s ease",
          }}
        >
          <polygon points={str(pts)} fill="none" stroke={col.c} strokeWidth="3" strokeOpacity="0.08" style={{ filter: "blur(8px)", transition: "stroke 0.7s" }} />
          <polygon points={str(outer)} fill="none" stroke={col.c} strokeWidth="0.4" strokeOpacity="0.10" style={{ transition: "stroke 0.7s" }} />
          <polygon points={str(pts)} fill="none" stroke={col.c} strokeWidth="0.85" strokeOpacity="0.45" style={{ transition: "stroke 0.7s" }} />
          <polygon points={str(inner)} fill="none" stroke={col.c} strokeWidth="0.4" strokeOpacity="0.18" style={{ transition: "stroke 0.7s" }} />
          {pts.map(([x, y], i) => (
            <line key={i} x1="200" y1="200" x2={x} y2={y} stroke={col.c} strokeWidth="0.3" strokeOpacity="0.10" style={{ transition: "stroke 0.7s" }} />
          ))}
          {[32, 60, 92].map((r, i) => (
            <circle key={i} cx="200" cy="200" r={r} fill="none" stroke={col.c} strokeWidth="0.4" strokeOpacity={0.08 - i * 0.02} style={{ transition: "stroke 0.7s" }} />
          ))}
          {pts.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r="1.8" fill={col.c} opacity="0.30" style={{ transition: "fill 0.7s" }} />
          ))}
          <circle cx="200" cy="200" r="2.5" fill={col.c} opacity="0.50" style={{ transition: "fill 0.7s" }} />
        </svg>

        {/* Timer text — above the polygon */}
        <span style={{
          position: "relative", zIndex: 1,
          fontFamily: F.mono, fontSize: 9, letterSpacing: "0.22em", color: C.muted,
          textTransform: "uppercase", marginBottom: 2,
          animation: "timerFadeIn 0.6s ease",
        }}>Exam Timer</span>
        <span style={{
          position: "relative", zIndex: 1,
          fontFamily: F.mono, fontSize: "clamp(28px, 4vw, 44px)",
          fontWeight: 300, lineHeight: 1, letterSpacing: "-0.04em",
          color: col.c, textShadow: `0 0 30px ${col.g}, 0 0 60px ${col.dim}`,
          transition: "color 0.7s ease, text-shadow 0.7s ease",
          animation: "timerFadeIn 0.8s ease",
        }}>
          {mm}:{ss}
        </span>
        <span style={{
          position: "relative", zIndex: 1,
          fontFamily: F.mono, fontSize: 8, letterSpacing: "0.14em", textTransform: "uppercase",
          color: col.c, opacity: 0.5, marginTop: 2,
          transition: "color 0.7s ease",
          animation: "timerFadeIn 1s ease",
        }}>
          {col.label}
        </span>
      </div>

      {/* Frozen overlay */}
      {frozen && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 99,
          background: `${C.bg}cc`, display: "flex", alignItems: "center", justifyContent: "center",
          animation: "fadeIn 0.5s ease",
        }}>
          <div style={{ textAlign: "center" }}>
            <p style={{ fontFamily: F.serif, fontSize: 28, color: C.heading, marginBottom: 8 }}>Time's up</p>
            <p style={{ fontFamily: F.serif, fontSize: 15, color: C.dim }}>Answers submitted. Review your results below.</p>
          </div>
        </div>
      )}
    </TimerCtx.Provider>
  );
}

// ═══════════════════════════════════════════════════════════════
// HIGHSCORES PAGE — leaderboard from localStorage
// ═══════════════════════════════════════════════════════════════

function fmtTime(seconds) {
  if (!seconds || seconds <= 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function HighscoresPage({ navLinks }) {
  const [tab, setTab] = useState("scores");
  const [scores, setScores] = useState([]);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    setScores(ProgStorage.getHighscores());
    setHistory(ProgStorage.getHistory(20));
  }, []);

  const tabBtn = t => ({
    fontFamily: F.serif, fontSize: 13, padding: "5px 13px", borderRadius: DS.radius,
    border: `1px solid ${tab === t ? C.accent + "55" : "transparent"}`,
    background: tab === t ? C.accent + "11" : "transparent",
    color: tab === t ? C.accent : C.subtle, cursor: "pointer", transition: "all 0.2s",
  });

  const defaultNav = [
    { href: "../index.html", label: "← Index" },
    { href: "../highscores.html", label: "Highscores" },
  ];

  const links = navLinks || defaultNav;

  const thStyle = {
    fontFamily: F.mono, fontSize: 9, letterSpacing: "0.1em", textTransform: "uppercase",
    color: C.dim, textAlign: "left", padding: "8px 12px", borderBottom: `1px solid ${C.border}`,
  };

  const tdStyle = {
    fontFamily: F.serif, fontSize: 13, color: C.body, padding: "10px 12px",
    borderBottom: `1px solid ${C.border}`,
  };

  const monoStyle = {
    fontFamily: F.mono, fontSize: 10, color: C.subtle, padding: "10px 12px",
    borderBottom: `1px solid ${C.border}`,
  };

  const pctColor = pct => pct >= 90 ? C.accentAlt : pct >= 70 ? C.accent : pct >= 50 ? C.subtle : C.err;

  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <Geo />
      <div style={{ position: "relative", zIndex: 1, maxWidth: 820, margin: "0 auto", padding: "44px 20px 80px" }}>

        {/* Navbar */}
        <div className="bk-fade" style={{
          animationDelay: "0ms", marginBottom: 28,
          display: "flex", alignItems: "center", gap: 16,
          padding: "8px 0", borderBottom: `1px solid ${C.border}`,
        }}>
          {links.map((l, i) => (
            <span key={i}>
              {i > 0 && <span style={{ color: C.muted, fontSize: 10, marginRight: 16 }}>|</span>}
              <a href={l.href} style={{
                fontFamily: F.mono, fontSize: 10, letterSpacing: "0.1em",
                color: C.dim, textDecoration: "none",
                padding: "3px 0", borderBottom: `1px solid transparent`,
                transition: "all 0.2s",
              }}
                onMouseEnter={e => { e.target.style.color = C.accent; e.target.style.borderBottomColor = C.accent + "55"; }}
                onMouseLeave={e => { e.target.style.color = C.dim; e.target.style.borderBottomColor = "transparent"; }}
              >{l.label}</a>
            </span>
          ))}
        </div>

        {/* Header */}
        <div className="bk-fade" style={{ animationDelay: "0ms", marginBottom: 36 }}>
          <Label style={{ display: "block", marginBottom: 10 }}>Records</Label>
          <h1 style={{
            fontFamily: F.serif, fontSize: "clamp(26px,4vw,42px)", fontWeight: 500,
            color: C.heading, letterSpacing: "-0.02em", lineHeight: 1.2,
            marginBottom: 10, textShadow: `0 0 24px ${C.glowStr}`,
          }}>Highscores<br /><em>&amp; History</em></h1>
          <p style={{ fontFamily: F.serif, fontSize: 15, color: C.dim, fontStyle: "italic" }}>
            Best scores and completion times across all problem sets.
          </p>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
          {["scores", "history"].map(t => (
            <button key={t} onClick={() => setTab(t)} style={tabBtn(t)}>
              {t === "scores" ? "High Scores" : "Recent History"}
            </button>
          ))}
          <button onClick={() => {
            if (confirm("Clear all stored scores and history?")) {
              ProgStorage.clearAll();
              setScores([]);
              setHistory([]);
            }
          }} style={{
            fontFamily: F.mono, fontSize: 9, letterSpacing: "0.1em",
            marginLeft: "auto", padding: "4px 10px", borderRadius: DS.radius,
            border: `1px solid ${C.err}33`, background: "transparent",
            color: C.muted, cursor: "pointer", transition: "all 0.2s",
          }}
            onMouseEnter={e => { e.target.style.color = C.err; e.target.style.borderColor = C.err + "55"; }}
            onMouseLeave={e => { e.target.style.color = C.muted; e.target.style.borderColor = C.err + "33"; }}
          >Clear All</button>
        </div>
        <div style={{ borderTop: `1px solid ${C.accent}44`, marginBottom: 28 }} />

        {/* High Scores tab */}
        {tab === "scores" && (
          <div className="bk-fade">
            {scores.length === 0 ? (
              <Card>
                <p style={{ fontFamily: F.serif, fontSize: 14, color: C.dim, textAlign: "center", padding: "20px 0" }}>
                  No scores yet. Complete a problem set to see your results here.
                </p>
              </Card>
            ) : (
              <Card style={{ padding: 0, overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ ...thStyle, width: "5%", textAlign: "center" }}>#</th>
                      <th style={{ ...thStyle, width: "30%" }}>Problem Set</th>
                      <th style={{ ...thStyle, width: "15%", textAlign: "center" }}>Score</th>
                      <th style={{ ...thStyle, width: "12%", textAlign: "center" }}>%</th>
                      <th style={{ ...thStyle, width: "18%", textAlign: "center" }}>Best Time</th>
                      <th style={{ ...thStyle, width: "20%", textAlign: "right" }}>Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scores.map((s, i) => (
                      <tr key={s.file} style={{ transition: "background 0.2s" }}
                        onMouseEnter={e => { e.currentTarget.style.background = C.elevated; }}
                        onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
                      >
                        <td style={{ ...monoStyle, textAlign: "center", color: i === 0 ? C.accent : C.dim }}>{i + 1}</td>
                        <td style={tdStyle}>
                          <a href={s.file.replace(/\.jsx$/, ".html")} style={{
                            color: i === 0 ? C.accent : C.body, textDecoration: "none",
                            fontFamily: F.serif, fontSize: 13,
                          }}
                            onMouseEnter={e => { e.target.style.color = C.accent; }}
                            onMouseLeave={e => { e.target.style.color = i === 0 ? C.accent : C.body; }}
                          >{s.title.replace(/\b\w/g, c => c.toUpperCase())}</a>
                          {s.examMode && <Tag accent style={{ marginLeft: 8 }}>EXAM</Tag>}
                        </td>
                        <td style={{ ...monoStyle, textAlign: "center", color: C.heading }}>{s.pointsEarned}/{s.totalPoints}</td>
                        <td style={{ ...monoStyle, textAlign: "center", color: pctColor(s.pct), fontWeight: 400 }}>{s.pct}%</td>
                        <td style={{ ...monoStyle, textAlign: "center" }}>{fmtTime(s.totalTimeSeconds)}</td>
                        <td style={{ ...monoStyle, textAlign: "right", color: C.dim, fontSize: 9 }}>{fmtDate(s.completedAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </div>
        )}

        {/* History tab */}
        {tab === "history" && (
          <div className="bk-fade">
            {history.length === 0 ? (
              <Card>
                <p style={{ fontFamily: F.serif, fontSize: 14, color: C.dim, textAlign: "center", padding: "20px 0" }}>
                  No history yet. Start a problem set to begin tracking.
                </p>
              </Card>
            ) : (
              <Card style={{ padding: 0, overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ ...thStyle, width: "30%" }}>Problem Set</th>
                      <th style={{ ...thStyle, width: "12%", textAlign: "center" }}>Progress</th>
                      <th style={{ ...thStyle, width: "12%", textAlign: "center" }}>Score</th>
                      <th style={{ ...thStyle, width: "16%", textAlign: "center" }}>Time</th>
                      <th style={{ ...thStyle, width: "14%", textAlign: "center" }}>Status</th>
                      <th style={{ ...thStyle, width: "16%", textAlign: "right" }}>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(h => (
                      <tr key={h.file + h.startedAt} style={{ transition: "background 0.2s" }}
                        onMouseEnter={e => { e.currentTarget.style.background = C.elevated; }}
                        onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
                      >
                        <td style={tdStyle}>
                          <a href={h.file.replace(/\.jsx$/, ".html")} style={{
                            color: C.body, textDecoration: "none", fontFamily: F.serif, fontSize: 13,
                          }}
                            onMouseEnter={e => { e.target.style.color = C.accent; }}
                            onMouseLeave={e => { e.target.style.color = C.body; }}
                          >{h.title.replace(/\b\w/g, c => c.toUpperCase())}</a>
                        </td>
                        <td style={{ ...monoStyle, textAlign: "center" }}>{h.answered}/{h.total}</td>
                        <td style={{ ...monoStyle, textAlign: "center", color: pctColor(h.pct) }}>{h.pct}%</td>
                        <td style={{ ...monoStyle, textAlign: "center" }}>{fmtTime(h.totalTimeSeconds)}</td>
                        <td style={{ ...monoStyle, textAlign: "center" }}>
                          <span style={{
                            display: "inline-block", width: 8, height: 8, borderRadius: "50%",
                            background: h.completedAt ? C.accentAlt : C.accent,
                            marginRight: 6, verticalAlign: "middle",
                          }} />
                          {h.completedAt ? "Done" : "Active"}
                        </td>
                        <td style={{ ...monoStyle, textAlign: "right", color: C.dim, fontSize: 9 }}>{fmtDate(h.completedAt || h.startedAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </div>
        )}

        {/* Footer */}
        <div style={{ marginTop: 56, borderTop: `1px solid ${C.border}`, paddingTop: 18, display: "flex", justifyContent: "space-between" }}>
          <Mono style={{ fontSize: 9 }}>highscores · block-kit</Mono>
          <Mono style={{ fontSize: 9, color: C.dim }}>{scores.length} sets completed</Mono>
        </div>
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
// PROBSET COMPOSER — renders a content tree
// ═══════════════════════════════════════════════════════════════

const DIFFICULTY_ORDER = { "easy": 1, "medium": 2, "hard": 3 };
const DIFFICULTY_PTS = { "easy": 3, "medium": 4, "hard": 5 };

function ProbsetComposer({ config, storageKey }) {
  const { meta, blocks } = config;
  const [frozen, setFrozen] = useState(false);
  const [results, setResults] = useState({});
  const sessionStarted = useRef(false);

  const effectiveKey = storageKey ?? (typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('f') : null);

  const questionBlocks = blocks
    .map((b, i) => ({ ...b, _idx: i }))
    .filter(b => ["mc", "tf", "int", "fie"].includes(b.type));
  const questionCount = questionBlocks.length;
  const totalPoints = questionBlocks.reduce((sum, b) => sum + (b.pts ?? DIFFICULTY_PTS[b.diff] ?? 3), 0);

  const examMode = meta.examMode ?? questionCount >= 30;
  const quizMode = meta.quizMode ?? false;
  const timerDuration = meta.timerDuration ?? (questionCount >= 45 ? 90 * 60 : 60 * 60);
  const suppressExplain = quizMode && !frozen;
  const suppressHint = quizMode && !frozen;

  const answeredCount = Object.values(results).filter(r => r.answered).length;
  const earnedPoints = Object.values(results).reduce((sum, r) => sum + (r.correct ? r.pts : 0), 0);
  const allAnswered = answeredCount >= questionCount && questionCount > 0;

  useEffect(() => {
    if (effectiveKey && !sessionStarted.current) {
      sessionStarted.current = true;
      ProgStorage.startSession(effectiveKey, totalPoints);
      questionBlocks.forEach(b => {
        ProgStorage.setProblemMeta(effectiveKey, b._idx, { pointsAvailable: b.pts ?? DIFFICULTY_PTS[b.diff] ?? 3 });
      });
    }
  }, [effectiveKey, totalPoints]);

  useEffect(() => {
    if (allAnswered && effectiveKey) {
      ProgStorage.endSession(effectiveKey);
    }
  }, [allAnswered, effectiveKey]);

  const handleResult = (blockIdx, pts, result) => {
    setResults(prev => {
      const existing = prev[blockIdx];
      // Keep the first correct answer — don't downgrade
      if (existing?.correct) return prev;
      const next = { ...prev, [blockIdx]: { answered: true, correct: result.correct, attempts: result.attempts, pts, timeSpent: result.timeSpent } };
      if (effectiveKey) ProgStorage.updateProblem(effectiveKey, blockIdx, result);
      return next;
    });
  };

  const renderBlock = (block, i) => {
    const idx = block.animateIndex ?? i;
    const pts = block.pts ?? DIFFICULTY_PTS[block.diff] ?? 3;
    const onResult = ["mc", "tf", "int", "fie"].includes(block.type)
      ? (r) => handleResult(i, pts, r)
      : undefined;
    switch (block.type) {
      case "section-header":
        return <SectionHeader key={i} title={block.title} subtitle={block.subtitle} animateIndex={idx} />;
      case "paragraph":
        return <Paragraph key={i} animateIndex={idx} style={block.style}>{block.text}</Paragraph>;
      case "equation":
        return <Equation key={i} display={block.display} inline={block.inline} animateIndex={idx} />;
      case "diagram":
        return <Diagram key={i} render={block.render} caption={block.caption} width={block.width} height={block.height} animateIndex={idx} />;
      case "slider-graph":
        return <SliderGraph key={i} param={block.param} render={block.render} width={block.width} height={block.height} animateIndex={idx} />;
      case "hint":
        return <Hint key={i} revealLabel={block.revealLabel} animateIndex={idx}>{block.text}</Hint>;
      case "note":
        return <HintBox key={i} variant={block.variant}>{block.text}</HintBox>;
      case "summary":
        return <SummaryBox key={i} intro={block.intro} points={block.points} />;
      case "quote":
        return <QuoteBlock key={i} text={block.text} author={block.author} />;
      case "example":
        return <Example key={i} label={block.label} animateIndex={idx}>{block.text}</Example>;
      case "spacer":
        return <Spacer key={i} size={block.size} />;
      case "rule":
        return <Rule key={i} accent={block.accent} />;
      case "info-row":
        return <InfoRow key={i} label={block.label} value={block.value} accent={block.accent} />;
      case "mc":
        return <MCField key={i} question={block.question} choices={block.choices} correct={block.correct} pts={pts} diff={DIFFICULTY_ORDER[block.diff] ?? block.diff ?? 1} explain={block.explain} animateIndex={idx} onResult={onResult} suppressExplain={suppressExplain} />;
      case "tf":
        return <TFField key={i} statement={block.statement} correct={block.correct} pts={pts} diff={DIFFICULTY_ORDER[block.diff] ?? block.diff ?? 1} animateIndex={idx} onResult={onResult} />;
      case "int":
        return <INTField key={i} question={block.question} answer={block.answer} pts={pts} diff={DIFFICULTY_ORDER[block.diff] ?? block.diff ?? 2} hint={block.hint} animateIndex={idx} onResult={onResult} suppressHint={suppressHint} />;
      case "fie":
        return <FIEField key={i} question={block.question} equation={block.equation} cards={block.cards} slotCount={block.slotCount ?? 2} correct={block.correct} correctDisplay={block.correctDisplay} pts={pts} diff={block.diff ?? 3} animateIndex={idx} onResult={onResult} />;
      default:
        return null;
    }
  };

  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <Geo />
      <div style={{ position: "relative", zIndex: 1, maxWidth: 820, margin: "0 auto", padding: "44px 20px 80px" }}>

        {/* Navigation bar */}
        <div className="bk-fade" style={{
          animationDelay: "0ms", marginBottom: 28,
          display: "flex", alignItems: "center", gap: 16,
          padding: "8px 0", borderBottom: `1px solid ${C.border}`,
        }}>
          <a href="index.html" style={{
            fontFamily: F.mono, fontSize: 10, letterSpacing: "0.1em",
            color: C.dim, textDecoration: "none",
            padding: "3px 0", borderBottom: `1px solid transparent`,
            transition: "all 0.2s",
          }}
            onMouseEnter={e => { e.target.style.color = C.accent; e.target.style.borderBottomColor = C.accent + "55"; }}
            onMouseLeave={e => { e.target.style.color = C.dim; e.target.style.borderBottomColor = "transparent"; }}
          >&larr; Index</a>
          <span style={{ color: C.muted, fontSize: 10 }}>|</span>
          <a href="highscores.html" style={{
            fontFamily: F.mono, fontSize: 10, letterSpacing: "0.1em",
            color: C.dim, textDecoration: "none",
            padding: "3px 0", borderBottom: `1px solid transparent`,
            transition: "all 0.2s",
          }}
            onMouseEnter={e => { e.target.style.color = C.accent; e.target.style.borderBottomColor = C.accent + "55"; }}
            onMouseLeave={e => { e.target.style.color = C.dim; e.target.style.borderBottomColor = "transparent"; }}
          >Highscores</a>
          {(meta.navLinks || []).map((l, i) => (
            <span key={i}>
              <span style={{ color: C.muted, fontSize: 10 }}>|</span>
              <a href={l.href} style={{
                fontFamily: F.mono, fontSize: 10, letterSpacing: "0.1em",
                color: C.dim, textDecoration: "none", marginLeft: 16,
                padding: "3px 0", borderBottom: `1px solid transparent`,
                transition: "all 0.2s",
              }}
                onMouseEnter={e => { e.target.style.color = C.accent; e.target.style.borderBottomColor = C.accent + "55"; }}
                onMouseLeave={e => { e.target.style.color = C.dim; e.target.style.borderBottomColor = "transparent"; }}
              >{l.label}</a>
            </span>
          ))}
          <Mono style={{ fontSize: 9, color: C.dim, marginLeft: "auto" }}>
            {answeredCount}/{questionCount} answered
            {earnedPoints > 0 && <> &middot; {earnedPoints}/{totalPoints} pts</>}
          </Mono>
          {allAnswered && (
            <Mono style={{ fontSize: 9, color: C.accentAlt }}>
              Score: {earnedPoints}/{totalPoints} ({Math.round(earnedPoints / totalPoints * 100)}%)
            </Mono>
          )}
        </div>

        {/* Header */}
        <div className="bk-fade" style={{ animationDelay: "0ms", marginBottom: 40, display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 24 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <Label style={{ display: "block", marginBottom: 10 }}>{meta.topic ?? meta.title}</Label>
            <h1 style={{
              fontFamily: F.serif, fontSize: "clamp(26px,4vw,42px)", fontWeight: 500,
              color: C.heading, letterSpacing: "-0.02em", lineHeight: 1.2,
              marginBottom: 10, textShadow: `0 0 24px ${C.glowStr}, 0 0 48px ${C.glow}`,
            }}>
              {meta.title.includes("<em>") || meta.title.includes("<br") ? (
                <span dangerouslySetInnerHTML={{ __html: meta.title }} />
              ) : (
                meta.title
              )}
            </h1>
            {meta.subtitle && (
              <p style={{ fontFamily: F.serif, fontSize: 15, color: C.dim, fontStyle: "italic" }}>
                {meta.subtitle}
              </p>
            )}
          </div>
          <TimerOverlay enabled={examMode} duration={timerDuration} onExpire={() => setFrozen(true)} phaseThresholds={meta.timerPhaseThresholds} phaseConfig={meta.timerPhaseConfig} />
        </div>

        {/* Blocks */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {blocks.map((block, i) => renderBlock(block, i))}
        </div>

        {/* Footer */}
        <div style={{ marginTop: 56, borderTop: `1px solid ${C.border}`, paddingTop: 18, display: "flex", justifyContent: "space-between" }}>
          <Mono style={{ fontSize: 9 }}>{meta.topic ?? "probset"} · block-kit</Mono>
          <Mono style={{ fontSize: 9, color: C.dim }}>{questionCount} questions · {totalPoints} points total</Mono>
        </div>
        {allAnswered && (
          <div style={{ marginTop: 18, padding: "14px 18px", background: C.accentAlt + "08", border: `1px solid ${C.accentAlt}33`, borderLeft: `2px solid ${C.accentAlt}88`, borderRadius: DS.radius, textAlign: "center" }}>
            <p style={{ fontFamily: F.serif, fontSize: 15, color: C.accentAlt }}>All problems answered — {earnedPoints}/{totalPoints} points ({Math.round(earnedPoints / totalPoints * 100)}%)</p>
            <div style={{ display: "flex", gap: 20, justifyContent: "center", marginTop: 8 }}>
              <a href="index.html" style={{ fontFamily: F.mono, fontSize: 10, color: C.dim, textDecoration: "none" }}>&larr; Index</a>
              <a href="highscores.html" style={{ fontFamily: F.mono, fontSize: 10, color: C.dim, textDecoration: "none" }}>Highscores &rarr;</a>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
// EXPORT
// ═══════════════════════════════════════════════════════════════

export {
  DS, C, F,
  Geo, GLOBAL_CSS,
  Card, Label, Mono, Dots, Tag, Rule, MathBlock, InfoRow, QuoteBlock, HintBox, SummaryBox,
  Paragraph, SectionHeader, Diagram, SliderGraph, Equation, Hint, Example, Spacer,
  MCField, TFField, INTField, FIEField,
  TimerOverlay, useTimer,
  ProbsetComposer, ProgStorage,
  HighscoresPage,
};
