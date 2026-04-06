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
  { id: 1, name: "Alice", color: "#BF616A", meeples: 5, score: 42 },
  { id: 2, name: "Bob", color: "#81A1C1", meeples: 4, score: 38 },
  { id: 3, name: "Clara", color: "#A3BE8C", meeples: 6, score: 27 },
  { id: 4, name: "David", color: "#EBCB8B", meeples: 3, score: 51 },
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

const generatePotentialPlacements = (bt) => {
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
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Source+Code+Pro:wght@400;500;600&display=swap');

  :root {
    --bg: #2E3440;
    --bg-card: rgba(46, 52, 64, 0.55);
    --bg-card-solid: #3B4252;
    --bg-input: rgba(216,222,233,0.06);
    --border: rgba(216,222,233,0.08);
    --border-hover: rgba(216,222,233,0.16);
    --text: #ECEFF4;
    --text-2: rgba(216,222,233,0.6);
    --text-3: rgba(216,222,233,0.3);
    --accent: #88C0D0;
    --accent-soft: rgba(136,192,208,0.1);
    --green: #A3BE8C;
    --green-soft: rgba(163,190,140,0.1);
    --gold: #EBCB8B;
    --gold-soft: rgba(235,203,139,0.1);
    --red: #BF616A;
    --red-soft: rgba(191,97,106,0.1);
    --blue: #81A1C1;
    --blue-soft: rgba(129,161,193,0.1);
    --frost: #88C0D0;
    --shadow: 0 2px 8px rgba(0,0,0,0.12);
    --shadow-md: 0 6px 20px rgba(0,0,0,0.16);
    --r: 8px;
    --r-sm: 5px;
    --heading: 'Outfit', sans-serif;
    --mono: 'Source Code Pro', monospace;
    --glass: blur(12px) saturate(1.2);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--heading);
    -webkit-font-smoothing: antialiased;
  }

  .app {
    min-height: 100vh;
    padding: 0 16px 40px;
    background:
      radial-gradient(ellipse at 20% 20%, rgba(136,192,208,0.04) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 80%, rgba(163,190,140,0.03) 0%, transparent 50%),
      var(--bg);
  }

  /* ═══ Header ═══ */
  .hdr {
    max-width: 1440px; margin: 0 auto;
    padding: 20px 8px 16px;
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 1px solid var(--border);
    margin-bottom: 14px;
  }

  .hdr-mark { display: flex; align-items: center; gap: 12px; }

  .hdr-logo {
    width: 34px; height: 34px; border-radius: 8px;
    background: linear-gradient(135deg, var(--accent), #5E81AC);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px; color: var(--bg);
    box-shadow: 0 3px 12px rgba(136,192,208,0.2);
  }

  .hdr h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.3px; line-height: 1.1; }
  .hdr h1 span { font-weight: 300; color: var(--text-3); margin-left: 4px; font-size: 18px; }
  .hdr-sub { font-size: 11px; color: var(--text-3); margin-top: 1px; letter-spacing: 0.2px; }

  .hdr-right { display: flex; align-items: center; gap: 18px; }
  .hdr-st { text-align: right; }
  .hdr-st-v { font-family: var(--mono); font-size: 15px; font-weight: 600; }
  .hdr-st-l { font-size: 9px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.8px; margin-top: 1px; }

  .live-chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px 4px 8px;
    background: var(--green-soft); border: 1px solid rgba(163,190,140,0.15);
    border-radius: 20px;
    font-size: 10px; font-weight: 600; color: var(--green); letter-spacing: 0.3px;
  }

  .live-pip { width: 6px; height: 6px; border-radius: 50%; background: var(--green); animation: pulse 2.5s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.35;transform:scale(0.8)} }

  /* ═══ Layout ═══ */
  .grid {
    max-width: 1440px; margin: 0 auto;
    display: grid;
    grid-template-columns: 270px 1fr 270px;
    gap: 12px;
    min-height: calc(100vh - 80px);
  }

  .col { display: flex; flex-direction: column; gap: 10px; }
  .col-scroll {
    display: flex; flex-direction: column; gap: 10px;
    max-height: calc(100vh - 90px);
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: rgba(216,222,233,0.08) transparent;
  }
  .col-scroll::-webkit-scrollbar { width: 4px; }
  .col-scroll::-webkit-scrollbar-thumb { background: rgba(216,222,233,0.1); border-radius: 2px; }

  /* ═══ Card ═══ */
  .card {
    background: var(--bg-card);
    backdrop-filter: var(--glass);
    border: 1px solid var(--border);
    border-radius: var(--r);
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  .card-h {
    padding: 12px 16px 10px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
  }

  .card-t { font-size: 12px; font-weight: 600; letter-spacing: 0.2px; color: white }

  .card-tag {
    font-family: var(--mono); font-size: 9px; font-weight: 500;
    padding: 2px 7px; border-radius: 4px; letter-spacing: 0.4px;
  }
  .tag-accent { background: var(--accent-soft); color: var(--accent); }
  .tag-green { background: var(--green-soft); color: var(--green); }
  .tag-gold { background: var(--gold-soft); color: var(--gold); }
  .tag-blue { background: var(--blue-soft); color: var(--blue); }

  .card-b { padding: 14px 16px; }

  /* ═══ Players ═══ */
  .player-row {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 0;
    transition: all 0.15s;
    cursor: pointer;
    border-radius: 4px;
  }
  .player-row:hover { background: rgba(216,222,233,0.03); }
  .player-row.active { background: rgba(136,192,208,0.06); }

  .player-av {
    width: 32px; height: 32px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 13px; color: white;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
  }

  .player-info { flex: 1; }
  .player-name { font-size: 13px; font-weight: 600; }
  .player-meeples { font-family: var(--mono); font-size: 10px; color: var(--text-3); margin-top: 1px; }
  .player-score { font-family: var(--mono); font-size: 22px; font-weight: 600; line-height: 1; }

  /* ═══ Score Sparklines ═══ */
  .spark-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .spark-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  .spark-val { font-family: var(--mono); font-size: 10px; color: var(--text-3); min-width: 18px; text-align: right; }

  /* ═══ Log ═══ */
  .log-scroll { max-height: 220px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: rgba(216,222,233,0.06) transparent; }
  .log-scroll::-webkit-scrollbar { width: 3px; }
  .log-scroll::-webkit-scrollbar-thumb { background: rgba(216,222,233,0.08); border-radius: 2px; }

  .log-entry { display: flex; align-items: flex-start; gap: 8px; padding: 7px 0; }
  .log-entry + .log-entry { border-top: 1px solid var(--border); }
  .log-turn { font-family: var(--mono); font-size: 10px; color: var(--text-3); min-width: 24px; padding-top: 1px; }
  .log-pip { width: 7px; height: 7px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; }
  .log-text { font-size: 12px; color: var(--text-2); line-height: 1.45; }
  .log-text strong { color: var(--text); font-weight: 600; }
  .log-pts { font-family: var(--mono); font-size: 10px; color: var(--green); font-weight: 600; }

  /* ═══ Board ═══ */
  .board-wrap {
    flex: 1;
    position: relative; cursor: grab; overflow: hidden;
    min-height: 400px;
    background: radial-gradient(circle at 50% 50%, rgba(136,192,208,0.02) 0%, transparent 60%);
  }
  .board-wrap:active { cursor: grabbing; }

  .board-canvas { position: absolute; inset: 0; }

  .board-grid {
    position: absolute; inset: -200%;
    background-image:
      linear-gradient(rgba(216,222,233,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(216,222,233,0.03) 1px, transparent 1px);
    background-size: 50px 50px;
  }

  .b-tile {
    position: absolute; width: 46px; height: 46px;
    border: 1px solid var(--border);
    background: var(--bg-card-solid);
    border-radius: var(--r-sm);
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; cursor: pointer;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  }
  .b-tile:hover {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent), var(--shadow-md);
    z-index: 10; transform: scale(1.08);
  }

  .b-tile-in { width: 100%; height: 100%; position: relative; display: flex; align-items: center; justify-content: center; }
  .b-tile-icon { font-size: 18px; opacity: 0.75; }
  .b-tile-own { position: absolute; top: 3px; right: 3px; width: 7px; height: 7px; border-radius: 50%; border: 1.5px solid var(--bg-card-solid); }

  .b-pot {
    position: absolute; width: 46px; height: 46px;
    border: 1.5px dashed; border-radius: var(--r-sm);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; transition: all 0.2s;
    font-family: var(--mono); font-size: 11px; font-weight: 600;
  }
  .b-pot.good { border-color: rgba(163,190,140,0.45); background: rgba(163,190,140,0.06); color: var(--green); }
  .b-pot.possible { border-color: rgba(235,203,139,0.35); background: rgba(235,203,139,0.04); color: var(--gold); }
  .b-pot:hover { transform: scale(1.1); box-shadow: var(--shadow); }

  .board-info {
    position: absolute; bottom: 10px; left: 10px;
    font-family: var(--mono); font-size: 10px; color: var(--text-3);
    background: rgba(46,52,64,0.85); backdrop-filter: var(--glass);
    padding: 4px 9px; border-radius: var(--r-sm); border: 1px solid var(--border);
  }

  .board-ctrls {
    position: absolute; top: 10px; right: 10px;
    display: flex; flex-direction: column; gap: 3px;
  }

  .board-btn {
    width: 30px; height: 30px;
    background: rgba(46,52,64,0.85); backdrop-filter: var(--glass);
    border: 1px solid var(--border); border-radius: var(--r-sm);
    color: var(--text-2); font-size: 14px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; font-family: var(--heading);
  }
  .board-btn:hover { border-color: var(--accent); color: var(--accent); }

  /* ═══ Metrics Strip ═══ */
  .metrics-strip {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    padding: 0;
  }

  .metric-block {
    text-align: center;
    padding: 12px 8px;
    background: var(--bg-card);
    backdrop-filter: var(--glass);
    border: 1px solid var(--border);
    border-radius: var(--r);
    transition: all 0.15s;
  }
  .metric-block:hover { border-color: var(--border-hover); }

  .metric-val { font-family: var(--mono); font-size: 20px; font-weight: 600; line-height: 1; }
  .metric-lbl { font-size: 9px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.7px; margin-top: 4px; }

  /* ═══ Tile Detection ═══ */
  .td { text-align: center; }

  .td-preview {
    width: 80px; height: 80px;
    margin: 0 auto 12px;
    border: 2px solid var(--border);
    border-radius: var(--r);
    display: flex; align-items: center; justify-content: center;
    background: var(--bg-input);
    position: relative;
  }
  .td-preview::before {
    content: ''; position: absolute; inset: -5px;
    border: 1px solid var(--border); border-radius: 11px; opacity: 0.4;
  }
  .td-icon { font-size: 32px; transition: transform 0.3s; }
  .td-name { font-size: 14px; font-weight: 600; margin-bottom: 6px; }

  .conf-row { display: flex; align-items: center; justify-content: center; gap: 7px; margin-bottom: 12px; }
  .conf-track { width: 56px; height: 4px; background: var(--bg-input); border-radius: 2px; overflow: hidden; }
  .conf-fill { height: 100%; border-radius: 2px; transition: width 0.4s; }
  .conf-txt { font-family: var(--mono); font-size: 11px; font-weight: 500; }

  .td-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin-bottom: 12px; }
  .td-s { background: var(--bg-input); border-radius: var(--r-sm); padding: 8px 3px; transition: border-color 0.15s; border: 1px solid transparent; }
  .td-s:hover { border-color: var(--border); }
  .td-s-v { font-family: var(--mono); font-size: 16px; font-weight: 600; text-align: center; }
  .td-s-l { font-size: 8px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.7px; text-align: center; margin-top: 1px; }

  .rot-row { display: flex; align-items: center; justify-content: center; gap: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
  .rot-btn {
    width: 32px; height: 32px;
    background: var(--bg-input); border: 1px solid var(--border);
    border-radius: var(--r-sm); cursor: pointer; font-size: 14px;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; color: var(--text-2);
  }
  .rot-btn:hover { border-color: var(--accent); color: var(--accent); }
  .rot-val { font-family: var(--mono); font-size: 14px; font-weight: 600; min-width: 36px; text-align: center; }

  /* ═══ Placements ═══ */
  .pl-row { display: flex; align-items: center; gap: 7px; margin-bottom: 6px; }
  .pl-rank { font-family: var(--mono); font-size: 10px; color: var(--text-3); min-width: 16px; }
  .pl-coord { font-family: var(--mono); font-size: 10px; color: var(--text-3); min-width: 48px; }
  .pl-bar { flex: 1; height: 6px; background: var(--bg-input); border-radius: 3px; overflow: hidden; }
  .pl-bar-f { height: 100%; border-radius: 3px; transition: width 0.5s; }
  .pl-sc { font-family: var(--mono); font-size: 11px; font-weight: 600; min-width: 26px; text-align: right; }
  .pl-tag {
    font-size: 8px; font-weight: 600; padding: 2px 5px; border-radius: 3px;
    text-transform: uppercase; letter-spacing: 0.3px;
  }
  .pl-tag.good { background: var(--green-soft); color: var(--green); }
  .pl-tag.possible { background: var(--gold-soft); color: var(--gold); }

  /* ═══ Toggles ═══ */
  .tog { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; }
  .tog+.tog { border-top: 1px solid var(--border); }
  .tog-lbl { font-size: 12px; color: var(--text-2); }

  .sw {
    width: 34px; height: 18px;
    background: rgba(216,222,233,0.1);
    border: 1px solid var(--border); border-radius: 9px;
    cursor: pointer; position: relative; transition: all 0.2s; padding: 0;
  }
  .sw.on { background: var(--accent); border-color: var(--accent); }
  .sw-k {
    position: absolute; top: 1.5px; left: 1.5px;
    width: 13px; height: 13px;
    background: white; border-radius: 50%;
    transition: transform 0.2s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  }
  .sw.on .sw-k { transform: translateX(16px); }

  /* ═══ Animations ═══ */
  @keyframes fadeUp { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
  .ani { animation: fadeUp 0.35s ease forwards; }
  .d1 { animation-delay: 0.04s; opacity: 0; }
  .d2 { animation-delay: 0.08s; opacity: 0; }
  .d3 { animation-delay: 0.12s; opacity: 0; }
  .d4 { animation-delay: 0.16s; opacity: 0; }
  .d5 { animation-delay: 0.2s; opacity: 0; }

  @media (max-width: 1100px) {
    .grid { grid-template-columns: 1fr; }
    .col-scroll { max-height: none; }
    .board-wrap { min-height: 350px; }
  }
`;

// ═══ Score Sparkline ═══
const Sparkline = ({ history, color, width = "100%", height = 28 }) => {
  const max = Math.max(...history, 1);
  const pts = history.map((v, i) => {
    const x = (i / (history.length - 1)) * 100;
    const y = 95 - (v / max) * 85;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg width={width} height={height} viewBox="0 0 100 100" preserveAspectRatio="none" style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" opacity="0.65" />
    </svg>
  );
};

// ═══ App ═══
export default function App() {
  const [boardTiles] = useState(generateBoardTiles);
  const [potentials] = useState(() => generatePotentialPlacements(boardTiles));
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

  const cx = 340, cy = 280, ts = 50;

  const onDown = (e) => { if (e.target.closest('.board-btn')) return; setIsDragging(true); setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y }); };
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

        {/* 3-Column Grid */}
        <div className="grid">
          {/* ═══ LEFT ═══ */}
          <div className="col-scroll">
            {/* Players */}
            <div className="card ani d1">
              <div className="card-h"><span className="card-t">Players</span><span className="card-tag tag-accent">TURN: P{activePlayer + 1}</span></div>
              <div className="card-b" style={{ padding: "6px 14px" }}>
                {PLAYERS.map((p, i) => (
                  <div key={p.id} className={`player-row ${i === activePlayer ? 'active' : ''}`} onClick={() => setActivePlayer(i)} style={{ padding: "8px 6px" }}>
                    <div className="player-av" style={{ background: p.color }}>{p.name[0]}</div>
                    <div className="player-info">
                      <div className="player-name">{p.name}</div>
                      <div className="player-meeples">{p.meeples}/7 meeples</div>
                    </div>
                    <div className="player-score" style={{ color: p.color }}>{p.score}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Score Trends */}
            <div className="card ani d2">
              <div className="card-h"><span className="card-t">Score Trend</span><span className="card-tag tag-blue">{METRICS.tilesPlaced} TURNS</span></div>
              <div className="card-b">
                {scoreHistory.map(p => (
                  <div key={p.id} className="spark-row">
                    <span className="spark-dot" style={{ background: p.color }} />
                    <div style={{ flex: 1 }}><Sparkline history={p.history} color={p.color} /></div>
                    <span className="spark-val">{p.history[p.history.length - 1]}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Activity Log */}
            <div className="card ani d3" style={{ flex: 1 }}>
              <div className="card-h"><span className="card-t">Activity Log</span><span className="card-tag tag-gold">RECENT</span></div>
              <div className="card-b" style={{ padding: "8px 14px" }}>
                <div className="log-scroll">
                  {gameLog.map((e, i) => (
                    <div key={i} className="log-entry">
                      <span className="log-turn">T{e.turn}</span>
                      <span className="log-pip" style={{ background: e.player.color }} />
                      <span className="log-text">
                        <strong>{e.player.name}</strong> {e.text}
                        {e.scored && <>{" "}<span className="log-pts">+{e.scored}</span></>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* ═══ CENTRE ═══ */}
          <div className="col">
            <div className="card ani d2" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
              <div className="card-h">
                <span className="card-t">Board State</span>
                <div style={{ display: "flex", gap: 4 }}>
                  <span className="card-tag tag-green">{boardTiles.length} TILES</span>
                </div>
              </div>
              <div className="board-wrap" onMouseDown={onDown}>
                <div className="board-canvas" style={{ transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`, transformOrigin: "center center" }}>
                  <div className="board-grid" />
                  {boardTiles.map((t, i) => (
                    <div key={i} className="b-tile" style={{ left: cx + t.col * ts, top: cy + t.row * ts }}>
                      <div className="b-tile-in" style={{ transform: `rotate(${t.rotation}deg)` }}>
                        <span className="b-tile-icon">{t.type.icon}</span>
                        {showMeeples && t.owner && <div className="b-tile-own" style={{ background: t.owner.color }} />}
                      </div>
                    </div>
                  ))}
                  {showPotentials && potentials.map((p, i) => (
                    <div key={i} className={`b-pot ${p.fit}`} style={{ left: cx + p.col * ts, top: cy + p.row * ts }}>+{p.score}</div>
                  ))}
                </div>
                <div className="board-ctrls">
                  <button className="board-btn" onClick={() => setZoom(z => Math.min(z + 0.15, 2.5))}>+</button>
                  <button className="board-btn" onClick={() => setZoom(z => Math.max(z - 0.15, 0.4))}>−</button>
                  <button className="board-btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>⌂</button>
                </div>
                <div className="board-info">{(zoom * 100).toFixed(0)}% · {boardTiles.length} tiles</div>
              </div>
            </div>

            {/* Metrics Strip */}
            <div className="metrics-strip ani d3">
              <div className="metric-block"><div className="metric-val">{METRICS.tilesPlaced}</div><div className="metric-lbl">Placed</div></div>
              <div className="metric-block"><div className="metric-val">{METRICS.tilesRemaining}</div><div className="metric-lbl">Remaining</div></div>
              <div className="metric-block"><div className="metric-val" style={{ color: "var(--red)" }}>{METRICS.completedCities}</div><div className="metric-lbl">Cities</div></div>
              <div className="metric-block"><div className="metric-val" style={{ color: "var(--green)" }}>{METRICS.longestRoad}</div><div className="metric-lbl">Longest Rd</div></div>
            </div>
          </div>

          {/* ═══ RIGHT ═══ */}
          <div className="col-scroll">
            {/* Tile Detection */}
            <div className="card ani d3">
              <div className="card-h"><span className="card-t">Detected Tile</span><span className="card-tag tag-accent">CV OUTPUT</span></div>
              <div className="card-b td">
                <div className="td-preview"><span className="td-icon" style={{ transform: `rotate(${tileRotation}deg)` }}>{currentTile.icon}</span></div>
                <div className="td-name">{currentTile.name}</div>
                <div className="conf-row">
                  <span className="conf-txt" style={{ color: "var(--text-3)", fontSize: 10 }}>CONF</span>
                  <div className="conf-track"><div className="conf-fill" style={{ width: `${confidence}%`, background: confidence > 80 ? "var(--green)" : "var(--gold)" }} /></div>
                  <span className="conf-txt" style={{ color: confidence > 80 ? "var(--green)" : "var(--gold)" }}>{confidence}%</span>
                </div>
                <div className="td-stats">
                  {[["Roads", currentTile.roads], ["City", currentTile.city], ["Fields", currentTile.fields]].map(([l, v]) => (
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

            {/* Best Placements */}
            <div className="card ani d4">
              <div className="card-h"><span className="card-t">Best Placements</span><span className="card-tag tag-green">ENGINE</span></div>
              <div className="card-b">
                {topP.map((p, i) => (
                  <div key={i} className="pl-row">
                    <span className="pl-rank">{i + 1}.</span>
                    <span className="pl-coord">({p.col},{p.row})</span>
                    <div className="pl-bar"><div className="pl-bar-f" style={{ width: `${(p.score / maxPS) * 100}%`, background: p.fit === "good" ? "var(--green)" : "var(--gold)", opacity: 0.6 }} /></div>
                    <span className="pl-sc" style={{ color: p.fit === "good" ? "var(--green)" : "var(--gold)" }}>+{p.score}</span>
                    <span className={`pl-tag ${p.fit}`}>{p.fit}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Overlays */}
            <div className="card ani d5">
              <div className="card-h"><span className="card-t">AR Overlays</span></div>
              <div className="card-b">
                <div className="tog"><span className="tog-lbl">Potential placements</span><button className={`sw ${showPotentials ? 'on' : ''}`} onClick={() => setShowPotentials(!showPotentials)}><span className="sw-k" /></button></div>
                <div className="tog"><span className="tog-lbl">Meeple ownership</span><button className={`sw ${showMeeples ? 'on' : ''}`} onClick={() => setShowMeeples(!showMeeples)}><span className="sw-k" /></button></div>
              </div>
            </div>

            {/* Extra Metrics */}
            <div className="card ani d5">
              <div className="card-h"><span className="card-t">Game Stats</span></div>
              <div className="card-b" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                {[
                  [METRICS.completedRoads, "Roads Done", "var(--blue)"],
                  [METRICS.activeMonasteries, "Monasteries", "var(--gold)"],
                  [METRICS.largestCity, "Largest City", "var(--red)"],
                  [METRICS.avgTurnTime, "Avg Turn", "var(--text-2)"],
                ].map(([v, l, c]) => (
                  <div key={l} style={{ background: "var(--bg-input)", borderRadius: "var(--r-sm)", padding: "10px 6px", textAlign: "center" }}>
                    <div style={{ fontFamily: "var(--mono)", fontSize: 18, fontWeight: 600, color: c }}>{v}</div>
                    <div style={{ fontSize: 8, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.6px", marginTop: 2 }}>{l}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}