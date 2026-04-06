import { useState, useEffect, useCallback } from "react";

// ═══ Data ═══
const TILE_TYPES = [
  { id: "monastery_road", name: "Monastery + Road", fields: 1, roads: 1, city: 0, monastery: 1, icon: "⛪" },
  { id: "city_edge", name: "City Edge", fields: 2, roads: 0, city: 1, monastery: 0, icon: "🏰" },
  { id: "road_bend", name: "Road Bend", fields: 2, roads: 1, city: 0, monastery: 0, icon: "↗" },
  { id: "crossroads", name: "Crossroads", fields: 4, roads: 4, city: 0, monastery: 0, icon: "✚" },
  { id: "city_cap", name: "City Cap", fields: 1, roads: 0, city: 1, monastery: 0, icon: "🏛" },
  { id: "city_tunnel", name: "City Tunnel", fields: 0, roads: 0, city: 2, monastery: 0, icon: "🏘" },
];

const PLAYERS = [
  { id: 1, name: "Alice", color: "#F87171", meeples: 5, score: 42 },
  { id: 2, name: "Bob", color: "#3B82F6", meeples: 4, score: 38 },
  { id: 3, name: "Clara", color: "#34D399", meeples: 6, score: 27 },
  { id: 4, name: "David", color: "#FBBF24", meeples: 3, score: 51 },
];

const METRICS = {
  tilesPlaced: 34, tilesRemaining: 38, completedCities: 5,
  completedRoads: 3, activeMonasteries: 2, turnNumber: 35,
  avgTurnTime: "18s", longestRoad: 7, largestCity: 12,
};

const generateBoardTiles = () => {
  const tiles = []; const placed = new Set();
  for (let i = 0; i < 34; i++) {
    let r, c;
    do { r = Math.floor(Math.random() * 12) - 6; c = Math.floor(Math.random() * 14) - 7; } while (placed.has(`${r},${c}`));
    placed.add(`${r},${c}`);
    tiles.push({ row: r, col: c, type: TILE_TYPES[Math.floor(Math.random() * TILE_TYPES.length)], rotation: Math.floor(Math.random() * 4) * 90, owner: Math.random() > 0.6 ? PLAYERS[Math.floor(Math.random() * 4)] : null });
  }
  return tiles;
};

const generatePotentials = (bt) => {
  const occ = new Set(bt.map(t => `${t.row},${t.col}`)); const pot = []; const chk = new Set();
  bt.forEach(t => { [[0,1],[0,-1],[1,0],[-1,0]].forEach(([dr,dc]) => { const k = `${t.row+dr},${t.col+dc}`; if (!occ.has(k) && !chk.has(k)) { chk.add(k); if (Math.random() > 0.4) pot.push({ row: t.row+dr, col: t.col+dc, score: Math.floor(Math.random()*15)+1, fit: Math.random() > 0.5 ? "good" : "possible" }); } }); });
  return pot;
};

const generateScoreHistory = () => PLAYERS.map(p => {
  let s = 0; const h = [0];
  for (let i = 1; i <= 34; i++) { s += Math.floor(Math.random() * 5); h.push(s); }
  return { ...p, history: h };
});

// ═══ Styles ═══
const css = `
  @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

  :root {
    --bg: #0A0A0C;
    --bg2: #101014;
    --bg-card: rgba(18,18,22,0.75);
    --bg-solid: #121216;
    --bg-in: rgba(255,255,255,0.03);
    --bdr: rgba(255,255,255,0.06);
    --bdr2: rgba(255,255,255,0.12);
    --tx: #EAEAEE;
    --tx2: rgba(234,234,238,0.5);
    --tx3: rgba(234,234,238,0.22);
    --acc: #3B82F6;
    --acc-s: rgba(59,130,246,0.1);
    --grn: #34D399;
    --grn-s: rgba(52,211,153,0.1);
    --gld: #FBBF24;
    --gld-s: rgba(251,191,36,0.1);
    --red: #F87171;
    --red-s: rgba(248,113,113,0.1);
    --sh: 0 2px 6px rgba(0,0,0,0.4);
    --sh2: 0 8px 24px rgba(0,0,0,0.35);
    --r: 8px;
    --rs: 5px;
    --font: 'Manrope', sans-serif;
    --mono: 'JetBrains Mono', monospace;
    --glass: blur(16px) saturate(1.4);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--tx); font-family: var(--font); -webkit-font-smoothing: antialiased; }

  .app {
    min-height: 100vh;
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 20px 48px;
    background:
      radial-gradient(ellipse at 40% 0%, rgba(59,130,246,0.05) 0%, transparent 45%),
      radial-gradient(ellipse at 60% 100%, rgba(52,211,153,0.03) 0%, transparent 40%),
      var(--bg);
  }

  /* ═══ Header ═══ */
  .hdr {
    padding: 20px 4px 16px;
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 1px solid var(--bdr);
    margin-bottom: 14px;
  }
  .hdr-mark { display: flex; align-items: center; gap: 12px; }
  .hdr-logo {
    width: 34px; height: 34px; border-radius: 8px;
    background: linear-gradient(135deg, var(--acc), #2563EB);
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 14px; color: white;
    box-shadow: 0 3px 14px rgba(59,130,246,0.25);
  }
  .hdr h1 { font-size: 20px; font-weight: 800; letter-spacing: -0.4px; line-height: 1.1; }
  .hdr h1 span { font-weight: 400; color: var(--tx3); margin-left: 4px; font-size: 18px; }
  .hdr-sub { font-size: 11px; color: var(--tx3); margin-top: 1px; letter-spacing: 0.2px; }
  .hdr-right { display: flex; align-items: center; gap: 18px; }
  .hdr-st { text-align: right; }
  .hdr-st-v { font-family: var(--mono); font-size: 15px; font-weight: 600; }
  .hdr-st-l { font-size: 9px; color: var(--tx3); text-transform: uppercase; letter-spacing: 0.8px; margin-top: 1px; }
  .live-chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px 4px 8px;
    background: var(--grn-s); border: 1px solid rgba(52,211,153,0.15);
    border-radius: 20px; font-size: 10px; font-weight: 600; color: var(--grn);
  }
  .live-pip { width: 6px; height: 6px; border-radius: 50%; background: var(--grn); animation: pulse 2.5s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.35;transform:scale(0.8)} }

  /* ═══ Card ═══ */
  .c { background: var(--bg-card); backdrop-filter: var(--glass); border: 1px solid var(--bdr); border-radius: var(--r); box-shadow: var(--sh); overflow: hidden; }
  .c-h { padding: 12px 16px 10px; border-bottom: 1px solid var(--bdr); display: flex; align-items: center; justify-content: space-between; }
  .c-t { font-size: 12px; font-weight: 700; letter-spacing: 0.2px; }
  .c-tag { font-family: var(--mono); font-size: 9px; font-weight: 500; padding: 2px 7px; border-radius: 4px; letter-spacing: 0.4px; }
  .tg-a { background: var(--acc-s); color: var(--acc); }
  .tg-g { background: var(--grn-s); color: var(--grn); }
  .tg-y { background: var(--gld-s); color: var(--gld); }
  .tg-r { background: var(--red-s); color: var(--red); }
  .c-b { padding: 14px 16px; }

  /* ═══ Top Section: Board + Tile + Placements ═══ */
  .top-grid { display: grid; grid-template-columns: 1fr 310px; gap: 12px; margin-bottom: 12px; }

  /* ═══ Board ═══ */
  .board-wrap {
    flex: 1; position: relative; cursor: grab; overflow: hidden; min-height: 380px;
    background: radial-gradient(circle at 50% 50%, rgba(59,130,246,0.015) 0%, transparent 60%);
  }
  .board-wrap:active { cursor: grabbing; }
  .board-canvas { position: absolute; inset: 0; }
  .board-grid {
    position: absolute; inset: -200%;
    background-image: linear-gradient(var(--bdr) 1px, transparent 1px), linear-gradient(90deg, var(--bdr) 1px, transparent 1px);
    background-size: 50px 50px; opacity: 0.5;
  }
  .bt {
    position: absolute; width: 46px; height: 46px;
    border: 1px solid var(--bdr); background: var(--bg-solid);
    border-radius: var(--rs); display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; cursor: pointer; box-shadow: 0 1px 4px rgba(0,0,0,0.15);
  }
  .bt:hover { border-color: var(--acc); box-shadow: 0 0 0 1px var(--acc), var(--sh2); z-index: 10; transform: scale(1.08); }
  .bt-in { width: 100%; height: 100%; position: relative; display: flex; align-items: center; justify-content: center; }
  .bt-icon { font-size: 18px; opacity: 0.75; }
  .bt-own { position: absolute; top: 3px; right: 3px; width: 7px; height: 7px; border-radius: 50%; border: 1.5px solid var(--bg-solid); }
  .bp {
    position: absolute; width: 46px; height: 46px;
    border: 1.5px dashed; border-radius: var(--rs);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; transition: all 0.2s;
    font-family: var(--mono); font-size: 11px; font-weight: 600;
  }
  .bp.good { border-color: rgba(52,211,153,0.45); background: rgba(52,211,153,0.05); color: var(--grn); }
  .bp.possible { border-color: rgba(251,191,36,0.35); background: rgba(251,191,36,0.04); color: var(--gld); }
  .bp:hover { transform: scale(1.1); box-shadow: var(--sh); }
  .b-info {
    position: absolute; bottom: 10px; left: 10px;
    font-family: var(--mono); font-size: 10px; color: var(--tx3);
    background: rgba(10,10,12,0.85); backdrop-filter: var(--glass);
    padding: 4px 9px; border-radius: var(--rs); border: 1px solid var(--bdr);
  }
  .b-ctrls { position: absolute; top: 10px; right: 10px; display: flex; flex-direction: column; gap: 3px; }
  .b-btn {
    width: 30px; height: 30px;
    background: rgba(10,10,12,0.85); backdrop-filter: var(--glass);
    border: 1px solid var(--bdr); border-radius: var(--rs);
    color: var(--tx2); font-size: 14px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; font-family: var(--font);
  }
  .b-btn:hover { border-color: var(--acc); color: var(--acc); }

  /* ═══ Right Side ═══ */
  .right-col { display: flex; flex-direction: column; gap: 10px; }

  /* ═══ Tile Detection ═══ */
  .td { text-align: center; }
  .td-preview {
    width: 76px; height: 76px; margin: 0 auto 10px;
    border: 2px solid var(--bdr); border-radius: var(--r);
    display: flex; align-items: center; justify-content: center;
    background: var(--bg-in); position: relative;
  }
  .td-preview::before { content: ''; position: absolute; inset: -5px; border: 1px solid var(--bdr); border-radius: 11px; opacity: 0.35; }
  .td-icon { font-size: 30px; transition: transform 0.3s; }
  .td-name { font-size: 13px; font-weight: 700; margin-bottom: 5px; }

  .conf-row { display: flex; align-items: center; justify-content: center; gap: 6px; margin-bottom: 10px; }
  .conf-track { width: 52px; height: 4px; background: var(--bg-in); border-radius: 2px; overflow: hidden; }
  .conf-fill { height: 100%; border-radius: 2px; transition: width 0.4s; }
  .conf-txt { font-family: var(--mono); font-size: 10px; font-weight: 500; }

  .td-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin-bottom: 10px; }
  .td-s { background: var(--bg-in); border-radius: var(--rs); padding: 7px 2px; border: 1px solid transparent; transition: border-color 0.15s; }
  .td-s:hover { border-color: var(--bdr); }
  .td-s-v { font-family: var(--mono); font-size: 15px; font-weight: 600; text-align: center; }
  .td-s-l { font-size: 7px; color: var(--tx3); text-transform: uppercase; letter-spacing: 0.6px; text-align: center; margin-top: 1px; }

  .rot-row { display: flex; align-items: center; justify-content: center; gap: 10px; padding-top: 10px; border-top: 1px solid var(--bdr); }
  .rot-btn {
    width: 30px; height: 30px;
    background: var(--bg-in); border: 1px solid var(--bdr);
    border-radius: var(--rs); cursor: pointer; font-size: 13px;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; color: var(--tx2);
  }
  .rot-btn:hover { border-color: var(--acc); color: var(--acc); }
  .rot-val { font-family: var(--mono); font-size: 13px; font-weight: 600; min-width: 34px; text-align: center; }

  /* ═══ Placements ═══ */
  .pl-row { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }
  .pl-rank { font-family: var(--mono); font-size: 9px; color: var(--tx3); min-width: 14px; }
  .pl-coord { font-family: var(--mono); font-size: 9px; color: var(--tx3); min-width: 44px; }
  .pl-bar { flex: 1; height: 5px; background: var(--bg-in); border-radius: 3px; overflow: hidden; }
  .pl-bar-f { height: 100%; border-radius: 3px; }
  .pl-sc { font-family: var(--mono); font-size: 10px; font-weight: 600; min-width: 24px; text-align: right; }
  .pl-tag { font-size: 7px; font-weight: 700; padding: 1px 5px; border-radius: 3px; text-transform: uppercase; letter-spacing: 0.3px; }
  .pl-tag.good { background: var(--grn-s); color: var(--grn); }
  .pl-tag.possible { background: var(--gld-s); color: var(--gld); }

  /* ═══ Toggles ═══ */
  .tog { display: flex; align-items: center; justify-content: space-between; padding: 7px 0; }
  .tog+.tog { border-top: 1px solid var(--bdr); }
  .tog-lbl { font-size: 11px; color: var(--tx2); }
  .sw {
    width: 32px; height: 17px; background: rgba(255,255,255,0.07);
    border: 1px solid var(--bdr); border-radius: 9px;
    cursor: pointer; position: relative; transition: all 0.2s; padding: 0;
  }
  .sw.on { background: var(--acc); border-color: var(--acc); }
  .sw-k {
    position: absolute; top: 1.5px; left: 1.5px;
    width: 12px; height: 12px; background: white; border-radius: 50%;
    transition: transform 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.25);
  }
  .sw.on .sw-k { transform: translateX(15px); }

  /* ═══ Bottom Section: Players + Metrics + Log ═══ */
  .bot-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

  /* ═══ Player Score Bars ═══ */
  .ps-row {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 4px;
    border-bottom: 1px solid var(--bdr);
    cursor: pointer; transition: background 0.15s;
  }
  .ps-row:last-child { border-bottom: none; }
  .ps-row:hover { background: rgba(255,255,255,0.015); }
  .ps-row.active { background: rgba(59,130,246,0.04); }

  .ps-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .ps-name { font-size: 13px; font-weight: 600; min-width: 52px; }
  .ps-bar-wrap {
    flex: 1; position: relative; height: 24px;
    background: var(--bg-in); border-radius: 5px; overflow: hidden;
  }
  .ps-bar-fill {
    position: absolute; top: 0; left: 0; height: 100%;
    border-radius: 5px; opacity: 0.15;
  }
  .ps-spark-wrap { position: absolute; top: 0; left: 8px; right: 8px; height: 100%; display: flex; align-items: center; }
  .ps-score { font-family: var(--mono); font-size: 20px; font-weight: 700; min-width: 36px; text-align: right; }
  .ps-mee { font-family: var(--mono); font-size: 9px; color: var(--tx3); min-width: 28px; text-align: right; }

  /* ═══ Metric Pill ═══ */
  .m-pill {
    text-align: center; padding: 14px 8px;
    background: var(--bg-card); backdrop-filter: var(--glass);
    border: 1px solid var(--bdr); border-radius: var(--r);
    transition: all 0.15s;
  }
  .m-pill:hover { border-color: var(--bdr2); }
  .m-val { font-family: var(--mono); font-size: 22px; font-weight: 600; line-height: 1; }
  .m-lbl { font-size: 8px; color: var(--tx3); text-transform: uppercase; letter-spacing: 0.7px; margin-top: 4px; }
  .m-bar { margin-top: 8px; height: 3px; background: var(--bg-in); border-radius: 2px; overflow: hidden; }
  .m-bar-f { height: 100%; border-radius: 2px; transition: width 0.6s; }

  /* ═══ Log ═══ */
  .log-scroll { max-height: 260px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.06) transparent; }
  .log-scroll::-webkit-scrollbar { width: 3px; }
  .log-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 2px; }
  .log-e { display: flex; align-items: flex-start; gap: 8px; padding: 7px 0; }
  .log-e+.log-e { border-top: 1px solid var(--bdr); }
  .log-t { font-family: var(--mono); font-size: 10px; color: var(--tx3); min-width: 24px; padding-top: 1px; }
  .log-pip { width: 7px; height: 7px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; }
  .log-c { font-size: 12px; color: var(--tx2); line-height: 1.45; }
  .log-c strong { color: var(--tx); font-weight: 600; }
  .log-pts { font-family: var(--mono); font-size: 10px; color: var(--grn); font-weight: 600; }

  /* ═══ Extra Stats ═══ */
  .xstats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }

  /* ═══ Animations ═══ */
  @keyframes fadeUp { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
  .ani { animation: fadeUp 0.35s ease forwards; }
  .d1 { animation-delay: 0.04s; opacity: 0; }
  .d2 { animation-delay: 0.08s; opacity: 0; }
  .d3 { animation-delay: 0.12s; opacity: 0; }
  .d4 { animation-delay: 0.16s; opacity: 0; }
  .d5 { animation-delay: 0.2s; opacity: 0; }

  @media (max-width: 1000px) {
    .top-grid, .bot-grid { grid-template-columns: 1fr; }
    .board-wrap { min-height: 300px; }
  }
`;

// ═══ Sparkline ═══
const Spark = ({ history, color, w = "100%", h = 22 }) => {
  const max = Math.max(...history, 1);
  const pts = history.map((v, i) => `${(i / (history.length - 1)) * 100},${95 - (v / max) * 85}`).join(" ");
  return (
    <svg width={w} height={h} viewBox="0 0 100 100" preserveAspectRatio="none" style={{ display: "block", width: "100%", height: "100%" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.6" />
    </svg>
  );
};

// ═══ App ═══
export default function App() {
  const [boardTiles] = useState(generateBoardTiles);
  const [potentials] = useState(() => generatePotentials(boardTiles));
  const [scoreHistory] = useState(generateScoreHistory);
  const [currentTile] = useState(TILE_TYPES[0]);
  const [tileRotation, setTileRotation] = useState(0);
  const [confidence] = useState(87);
  const [activePlayer, setActivePlayer] = useState(3);
  const [showPotentials, setShowPotentials] = useState(true);
  const [showMeeples, setShowMeeples] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const cx = 340, cy = 260, ts = 50;

  const onDown = (e) => { if (e.target.closest('.b-btn')) return; setIsDragging(true); setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y }); };
  const onMove = useCallback((e) => { if (isDragging) setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y }); }, [isDragging, dragStart]);
  const onUp = useCallback(() => setIsDragging(false), []);

  useEffect(() => {
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [onMove, onUp]);

  const gameLog = [
    { turn: 35, player: PLAYERS[3], text: "placed City Edge at (2, −1)", scored: 8 },
    { turn: 34, player: PLAYERS[2], text: "placed Road Bend at (0, 3)" },
    { turn: 33, player: PLAYERS[1], text: "placed Monastery at (−1, 2)", scored: 4 },
    { turn: 32, player: PLAYERS[0], text: "placed Crossroads at (1, 1)", scored: 12 },
    { turn: 31, player: PLAYERS[3], text: "placed City Cap at (−2, 0)" },
    { turn: 30, player: PLAYERS[2], text: "placed City Tunnel at (3, −2)", scored: 6 },
    { turn: 29, player: PLAYERS[1], text: "placed Road Bend at (2, 2)" },
    { turn: 28, player: PLAYERS[0], text: "placed Monastery at (−3, 1)", scored: 9 },
    { turn: 27, player: PLAYERS[3], text: "placed Crossroads at (0, −2)" },
    { turn: 26, player: PLAYERS[2], text: "placed City Edge at (1, −3)", scored: 5 },
  ];

  const topP = [...potentials].sort((a, b) => b.score - a.score).slice(0, 6);
  const maxPS = topP.length > 0 ? topP[0].score : 1;
  const maxScore = 55;

  return (
    <>
      <style>{css}</style>
      <div className="app">
        {/* Header */}
        <header className="hdr ani">
          <div className="hdr-mark">
            <div className="hdr-logo">C</div>
            <div>
              <h1>Carcassonne<span>AR</span></h1>
              <div className="hdr-sub">Augmented Reality Board Analysis</div>
            </div>
          </div>
          <div className="hdr-right">
            <div className="hdr-st"><div className="hdr-st-v">{METRICS.turnNumber}</div><div className="hdr-st-l">Turn</div></div>
            <div className="hdr-st"><div className="hdr-st-v">{METRICS.tilesPlaced}/{METRICS.tilesPlaced + METRICS.tilesRemaining}</div><div className="hdr-st-l">Tiles</div></div>
            <div className="live-chip"><span className="live-pip" />CV Feed Live</div>
          </div>
        </header>

        {/* ═══ TOP HALF: Board + CV ═══ */}
        <div className="top-grid">
          {/* Board */}
          <div className="c ani d1" style={{ display: "flex", flexDirection: "column" }}>
            <div className="c-h">
              <span className="c-t">Board State</span>
              <div style={{ display: "flex", gap: 4 }}>
                <span className="c-tag tg-g">{boardTiles.length} TILES</span>
                <span className="c-tag tg-y">{potentials.length} POTENTIAL</span>
              </div>
            </div>
            <div className="board-wrap" onMouseDown={onDown}>
              <div className="board-canvas" style={{ transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`, transformOrigin: "center center" }}>
                <div className="board-grid" />
                {boardTiles.map((t, i) => (
                  <div key={i} className="bt" style={{ left: cx + t.col * ts, top: cy + t.row * ts }}>
                    <div className="bt-in" style={{ transform: `rotate(${t.rotation}deg)` }}>
                      <span className="bt-icon">{t.type.icon}</span>
                      {showMeeples && t.owner && <div className="bt-own" style={{ background: t.owner.color }} />}
                    </div>
                  </div>
                ))}
                {showPotentials && potentials.map((p, i) => (
                  <div key={i} className={`bp ${p.fit}`} style={{ left: cx + p.col * ts, top: cy + p.row * ts }}>+{p.score}</div>
                ))}
              </div>
              <div className="b-ctrls">
                <button className="b-btn" onClick={() => setZoom(z => Math.min(z + 0.15, 2.5))}>+</button>
                <button className="b-btn" onClick={() => setZoom(z => Math.max(z - 0.15, 0.4))}>−</button>
                <button className="b-btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>⌂</button>
              </div>
              <div className="b-info">{(zoom * 100).toFixed(0)}% · {boardTiles.length} tiles</div>
            </div>
          </div>

          {/* Right: Tile + Placements + Overlays */}
          <div className="right-col">
            <div className="c ani d2">
              <div className="c-h"><span className="c-t">Detected Tile</span><span className="c-tag tg-a">CV OUTPUT</span></div>
              <div className="c-b td">
                <div className="td-preview"><span className="td-icon" style={{ transform: `rotate(${tileRotation}deg)` }}>{currentTile.icon}</span></div>
                <div className="td-name">{currentTile.name}</div>
                <div className="conf-row">
                  <span className="conf-txt" style={{ color: "var(--tx3)", fontSize: 9 }}>CONF</span>
                  <div className="conf-track"><div className="conf-fill" style={{ width: `${confidence}%`, background: confidence > 80 ? "var(--grn)" : "var(--gld)" }} /></div>
                  <span className="conf-txt" style={{ color: confidence > 80 ? "var(--grn)" : "var(--gld)" }}>{confidence}%</span>
                </div>
                <div className="td-stats">
                  {[["Roads", currentTile.roads], ["City", currentTile.city], ["Fields", currentTile.fields], ["Abbey", currentTile.monastery]].map(([l, v]) => (
                    <div key={l} className="td-s"><div className="td-s-v">{v}</div><div className="td-s-l">{l}</div></div>
                  ))}
                </div>
                <div className="rot-row">
                  <button className="rot-btn" onClick={() => setTileRotation(r => (r - 90 + 360) % 360)}>↶</button>
                  <span className="rot-val">{tileRotation}°</span>
                  <button className="rot-btn" onClick={() => setTileRotation(r => (r + 90) % 360)}>↷</button>
                </div>
              </div>
            </div>

            <div className="c ani d3" style={{ flex: 1 }}>
              <div className="c-h"><span className="c-t">Best Placements</span><span className="c-tag tg-g">ENGINE</span></div>
              <div className="c-b">
                {topP.map((p, i) => (
                  <div key={i} className="pl-row">
                    <span className="pl-rank">{i + 1}.</span>
                    <span className="pl-coord">({p.col},{p.row})</span>
                    <div className="pl-bar"><div className="pl-bar-f" style={{ width: `${(p.score / maxPS) * 100}%`, background: p.fit === "good" ? "var(--grn)" : "var(--gld)", opacity: 0.55 }} /></div>
                    <span className="pl-sc" style={{ color: p.fit === "good" ? "var(--grn)" : "var(--gld)" }}>+{p.score}</span>
                    <span className={`pl-tag ${p.fit}`}>{p.fit}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="c ani d4">
              <div className="c-h"><span className="c-t">AR Overlays</span></div>
              <div className="c-b" style={{ padding: "8px 14px" }}>
                <div className="tog"><span className="tog-lbl">Potential placements</span><button className={`sw ${showPotentials ? 'on' : ''}`} onClick={() => setShowPotentials(!showPotentials)}><span className="sw-k" /></button></div>
                <div className="tog"><span className="tog-lbl">Meeple ownership</span><button className={`sw ${showMeeples ? 'on' : ''}`} onClick={() => setShowMeeples(!showMeeples)}><span className="sw-k" /></button></div>
                <div className="tog"><span className="tog-lbl">Score heatmap</span><button className={`sw ${showHeatmap ? 'on' : ''}`} onClick={() => setShowHeatmap(!showHeatmap)}><span className="sw-k" /></button></div>
              </div>
            </div>
          </div>
        </div>

        {/* ═══ BOTTOM HALF: Players + Metrics + Log ═══ */}
        <div className="bot-grid">
          {/* Players with score bars + sparklines */}
          <div className="c ani d3">
            <div className="c-h"><span className="c-t">Players & Scores</span><span className="c-tag tg-a">TURN: P{activePlayer + 1}</span></div>
            <div className="c-b" style={{ padding: "6px 14px" }}>
              {PLAYERS.map((p, i) => {
                const hist = scoreHistory.find(s => s.id === p.id)?.history || [];
                return (
                  <div key={p.id} className={`ps-row ${i === activePlayer ? 'active' : ''}`} onClick={() => setActivePlayer(i)}>
                    <div className="ps-dot" style={{ background: p.color }} />
                    <span className="ps-name">{p.name}</span>
                    <div className="ps-bar-wrap">
                      <div className="ps-bar-fill" style={{ width: `${(p.score / maxScore) * 100}%`, background: p.color }} />
                      <div className="ps-spark-wrap"><Spark history={hist} color={p.color} /></div>
                    </div>
                    <span className="ps-score" style={{ color: p.color }}>{p.score}</span>
                    <span className="ps-mee">{p.meeples}/7</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right bottom: Metrics + Log */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {/* Metrics */}
            <div className="ani d4" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
              <div className="m-pill"><div className="m-val">{METRICS.tilesPlaced}</div><div className="m-lbl">Placed</div><div className="m-bar"><div className="m-bar-f" style={{ width: `${(METRICS.tilesPlaced / 72) * 100}%`, background: "var(--acc)" }} /></div></div>
              <div className="m-pill"><div className="m-val">{METRICS.tilesRemaining}</div><div className="m-lbl">Remaining</div><div className="m-bar"><div className="m-bar-f" style={{ width: `${(METRICS.tilesRemaining / 72) * 100}%`, background: "var(--acc)" }} /></div></div>
              <div className="m-pill"><div className="m-val" style={{ color: "var(--red)" }}>{METRICS.completedCities}</div><div className="m-lbl">Cities</div></div>
              <div className="m-pill"><div className="m-val" style={{ color: "var(--grn)" }}>{METRICS.longestRoad}</div><div className="m-lbl">Longest Rd</div></div>
            </div>

            {/* Extra stats */}
            <div className="xstats ani d4">
              {[
                [METRICS.completedRoads, "Roads", "var(--acc)"],
                [METRICS.activeMonasteries, "Monasteries", "var(--gld)"],
                [METRICS.avgTurnTime, "Avg Turn", "var(--tx2)"],
              ].map(([v, l, col]) => (
                <div key={l} className="m-pill">
                  <div className="m-val" style={{ fontSize: 18, color: col }}>{v}</div>
                  <div className="m-lbl">{l}</div>
                </div>
              ))}
            </div>

            {/* Log */}
            <div className="c ani d5" style={{ flex: 1 }}>
              <div className="c-h"><span className="c-t">Activity Log</span><span className="c-tag tg-y">RECENT</span></div>
              <div className="c-b" style={{ padding: "8px 14px" }}>
                <div className="log-scroll">
                  {gameLog.map((e, i) => (
                    <div key={i} className="log-e">
                      <span className="log-t">T{e.turn}</span>
                      <span className="log-pip" style={{ background: e.player.color }} />
                      <span className="log-c">
                        <strong>{e.player.name}</strong> {e.text}
                        {e.scored && <>{" "}<span className="log-pts">+{e.scored}</span></>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}