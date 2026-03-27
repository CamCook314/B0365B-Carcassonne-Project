import { useState, useEffect, useCallback } from "react";

const TILE_TYPES = [
  { id: "monastery_road", name: "Monastery + Road", fields: 1, roads: 1, city: 0, monastery: 1, icon: "⛪" },
  { id: "city_edge", name: "City Edge", fields: 2, roads: 0, city: 1, monastery: 0, icon: "🏰" },
  { id: "road_bend", name: "Road Bend", fields: 2, roads: 1, city: 0, monastery: 0, icon: "↗" },
  { id: "crossroads", name: "Crossroads", fields: 4, roads: 4, city: 0, monastery: 0, icon: "✚" },
  { id: "city_cap", name: "City Cap", fields: 1, roads: 0, city: 1, monastery: 0, icon: "🏛" },
  { id: "city_tunnel", name: "City Tunnel", fields: 0, roads: 0, city: 2, monastery: 0, icon: "🏘" },
];

const PLAYERS = [
  { id: 1, name: "Alice", color: "#C06845", meeples: 5, score: 42 },
  { id: 2, name: "Bob", color: "#5C8BA5", meeples: 4, score: 38 },
  { id: 3, name: "Clara", color: "#6A9B6F", meeples: 6, score: 27 },
  { id: 4, name: "David", color: "#B89B3E", meeples: 3, score: 51 },
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

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Bitter:ital,wght@0,400;0,500;0,600;0,700;1,400&family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&display=swap');

  :root {
    --bg: #F5F0E8;
    --bg-card: #FFFDF9;
    --bg-input: #EDE8DE;
    --border: #DDD6C8;
    --border-hover: #C4BAA8;
    --text: #33302A;
    --text-2: #7D7568;
    --text-3: #AAA294;
    --accent: #C06845;
    --accent-soft: rgba(192,104,69,0.08);
    --accent-softer: rgba(192,104,69,0.04);
    --green: #6A9B6F;
    --green-soft: rgba(106,155,111,0.08);
    --gold: #B89B3E;
    --gold-soft: rgba(184,155,62,0.08);
    --blue: #5C8BA5;
    --blue-soft: rgba(92,139,165,0.08);
    --shadow: 0 1px 4px rgba(60,50,30,0.06), 0 1px 2px rgba(60,50,30,0.04);
    --shadow-md: 0 4px 16px rgba(60,50,30,0.08), 0 1px 3px rgba(60,50,30,0.04);
    --r: 8px;
    --r-sm: 5px;
    --heading: 'Bitter', Georgia, serif;
    --body: 'DM Sans', -apple-system, sans-serif;
    --mono: 'DM Mono', 'Menlo', monospace;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--body);
    -webkit-font-smoothing: antialiased;
  }

  .app {
    min-height: 100vh;
    max-width: 1300px;
    margin: 0 auto;
    padding: 0 28px 56px;
    background:
      radial-gradient(ellipse at 10% 90%, rgba(192,104,69,0.04) 0%, transparent 45%),
      radial-gradient(ellipse at 90% 10%, rgba(106,155,111,0.03) 0%, transparent 45%),
      transparent;
  }

  /* ═══════════ Header ═══════════ */
  .hdr {
    padding: 28px 0 20px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border-bottom: 1px solid var(--border);
  }

  .hdr-mark { display: flex; align-items: center; gap: 14px; }

  .hdr-logo {
    width: 38px; height: 38px;
    border-radius: 8px;
    background: linear-gradient(135deg, var(--accent), #A85A3A);
    display: flex; align-items: center; justify-content: center;
    font-family: var(--heading); font-weight: 700; font-size: 16px; color: white;
    box-shadow: 0 3px 10px rgba(192,104,69,0.2);
  }

  .hdr h1 {
    font-family: var(--heading);
    font-size: 24px; font-weight: 700;
    letter-spacing: -0.3px; line-height: 1.1;
    color: var(--text);
  }

  .hdr h1 span {
    font-weight: 400; color: var(--text-3);
    margin-left: 5px; font-size: 22px;
  }

  .hdr-sub {
    font-size: 12px; color: var(--text-3);
    margin-top: 2px; letter-spacing: 0.2px;
  }

  .hdr-stats { display: flex; gap: 22px; align-items: flex-end; }

  .hdr-st { text-align: right; }
  .hdr-st-v { font-family: var(--mono); font-size: 17px; font-weight: 500; color: var(--text); }
  .hdr-st-l { font-size: 10px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.8px; margin-top: 2px; }

  .live-chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px 4px 8px;
    background: var(--green-soft);
    border: 1px solid rgba(106,155,111,0.15);
    border-radius: 20px;
    font-size: 11px; font-weight: 600;
    color: var(--green); letter-spacing: 0.3px;
  }

  .live-pip {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--green);
    animation: pulse 2.5s ease-in-out infinite;
  }

  @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.35;transform:scale(0.8)} }

  /* ═══════════ Tabs ═══════════ */
  .tabs {
    display: flex; gap: 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
    position: sticky; top: 0;
    background: var(--bg);
    z-index: 100;
    padding-top: 10px;
  }

  .tab {
    font-family: var(--body);
    font-size: 13px; font-weight: 500;
    color: var(--text-3);
    background: none; border: none;
    padding: 10px 18px 12px;
    cursor: pointer;
    border-radius: 6px 6px 0 0;
    transition: all 0.2s;
    position: relative;
  }

  .tab:hover { color: var(--text-2); background: rgba(192,104,69,0.03); }

  .tab.on {
    color: var(--accent);
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-bottom-color: var(--bg-card);
    margin-bottom: -1px;
  }

  .tab.on::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent);
    border-radius: 2px 2px 0 0;
  }

  /* ═══════════ Card ═══════════ */
  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  .card-h {
    padding: 16px 20px 12px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center;
    justify-content: space-between;
  }

  .card-t {
    font-family: var(--heading);
    font-size: 15px; font-weight: 600;
    color: var(--text);
  }

  .card-badge {
    font-family: var(--mono);
    font-size: 10px; font-weight: 500;
    padding: 3px 8px;
    border-radius: 4px;
    letter-spacing: 0.5px;
  }

  .badge-accent { background: var(--accent-soft); color: var(--accent); }
  .badge-green { background: var(--green-soft); color: var(--green); }
  .badge-blue { background: var(--blue-soft); color: var(--blue); }

  .card-b { padding: 20px; }

  /* ═══════════ Board ═══════════ */
  .b-layout { display: grid; grid-template-columns: 1fr 290px; gap: 16px; }

  .b-view {
    min-height: 540px;
    position: relative; cursor: grab; overflow: hidden;
    background: radial-gradient(circle at 50% 50%, rgba(192,104,69,0.02) 0%, transparent 60%);
  }
  .b-view:active { cursor: grabbing; }

  .b-canvas { position: absolute; inset: 0; }

  .b-grid {
    position: absolute; inset: -200%;
    background-image:
      linear-gradient(var(--border) 1px, transparent 1px),
      linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 50px 50px;
    opacity: 0.35;
  }

  .b-tile {
    position: absolute; width: 46px; height: 46px;
    border: 1px solid var(--border);
    background: var(--bg-card);
    border-radius: var(--r-sm);
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; cursor: pointer;
    box-shadow: 0 1px 3px rgba(60,50,30,0.06);
  }

  .b-tile:hover {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent), var(--shadow-md);
    z-index: 10; transform: scale(1.08);
  }

  .b-tile-in {
    width: 100%; height: 100%;
    position: relative;
    display: flex; align-items: center; justify-content: center;
  }

  .b-tile-icon { font-size: 18px; opacity: 0.75; }

  .b-tile-own {
    position: absolute; top: 3px; right: 3px;
    width: 7px; height: 7px; border-radius: 50%;
    border: 1.5px solid var(--bg-card);
  }

  .b-pot {
    position: absolute; width: 46px; height: 46px;
    border: 1.5px dashed; border-radius: var(--r-sm);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; transition: all 0.2s;
    font-family: var(--mono); font-size: 11px; font-weight: 500;
  }

  .b-pot.good { border-color: rgba(106,155,111,0.5); background: rgba(106,155,111,0.06); color: var(--green); }
  .b-pot.possible { border-color: rgba(184,155,62,0.4); background: rgba(184,155,62,0.05); color: var(--gold); }
  .b-pot:hover { transform: scale(1.1); box-shadow: var(--shadow); }

  .b-info {
    position: absolute; bottom: 12px; left: 12px;
    font-family: var(--mono); font-size: 11px; color: var(--text-3);
    background: rgba(255,253,249,0.9);
    padding: 5px 10px; border-radius: var(--r-sm);
    border: 1px solid var(--border);
  }

  .b-ctrls {
    position: absolute; top: 12px; right: 12px;
    display: flex; flex-direction: column; gap: 4px;
  }

  .b-btn {
    width: 32px; height: 32px;
    background: rgba(255,253,249,0.92);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    color: var(--text-2); font-size: 15px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; font-family: var(--body);
  }

  .b-btn:hover { border-color: var(--accent); color: var(--accent); background: white; }

  /* ═══════════ Sidebar ═══════════ */
  .b-side { display: flex; flex-direction: column; gap: 12px; }

  /* ═══════════ Tile Detection ═══════════ */
  .td { text-align: center; }

  .td-preview {
    width: 96px; height: 96px;
    margin: 0 auto 16px;
    border: 2px solid var(--border);
    border-radius: var(--r);
    display: flex; align-items: center; justify-content: center;
    background: var(--bg-input);
    position: relative;
  }

  .td-preview::before {
    content: ''; position: absolute; inset: -6px;
    border: 1px solid var(--border);
    border-radius: 12px; opacity: 0.4;
  }

  .td-icon { font-size: 36px; transition: transform 0.3s; }
  .td-name { font-family: var(--heading); font-size: 15px; font-weight: 600; margin-bottom: 8px; }

  .conf-row { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 16px; }
  .conf-track { width: 64px; height: 4px; background: var(--bg-input); border-radius: 2px; overflow: hidden; }
  .conf-fill { height: 100%; border-radius: 2px; transition: width 0.4s; }
  .conf-txt { font-family: var(--mono); font-size: 12px; font-weight: 500; }

  .td-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 16px; }

  .td-s {
    background: var(--bg-input);
    border-radius: var(--r-sm);
    padding: 10px 4px;
    border: 1px solid transparent;
    transition: border-color 0.15s;
  }
  .td-s:hover { border-color: var(--border); }

  .td-s-v { font-family: var(--mono); font-size: 18px; font-weight: 500; text-align: center; color: var(--text); }
  .td-s-l { font-size: 9px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.8px; text-align: center; margin-top: 2px; }

  .rot-row { display: flex; align-items: center; justify-content: center; gap: 14px; padding-top: 14px; border-top: 1px solid var(--border); }

  .rot-btn {
    width: 34px; height: 34px;
    background: var(--bg-input); border: 1px solid var(--border);
    border-radius: var(--r-sm); cursor: pointer; font-size: 15px;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; color: var(--text-2);
  }
  .rot-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-softer); }

  .rot-val { font-family: var(--mono); font-size: 15px; font-weight: 500; min-width: 40px; text-align: center; color: var(--text); }

  /* ═══════════ Toggle ═══════════ */
  .tog { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; }
  .tog+.tog { border-top: 1px solid var(--border); }
  .tog-lbl { font-size: 13px; color: var(--text-2); }

  .sw {
    width: 36px; height: 20px;
    background: var(--border);
    border: none; border-radius: 10px;
    cursor: pointer; position: relative;
    transition: background 0.2s; padding: 0;
  }
  .sw.on { background: var(--accent); }

  .sw-k {
    position: absolute; top: 2px; left: 2px;
    width: 16px; height: 16px;
    background: white; border-radius: 50%;
    transition: transform 0.2s;
    box-shadow: 0 1px 4px rgba(60,50,30,0.15);
  }
  .sw.on .sw-k { transform: translateX(16px); }

  /* ═══════════ Players ═══════════ */
  .p-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 20px; }

  .p-card {
    border-left: 3px solid;
    transition: all 0.15s;
  }
  .p-card:hover { box-shadow: var(--shadow-md); }

  .p-inner { padding: 18px 20px; display: flex; align-items: center; gap: 16px; }

  .p-av {
    width: 42px; height: 42px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--heading); font-weight: 700; font-size: 17px; color: white;
    box-shadow: 0 3px 8px rgba(60,50,30,0.12);
  }

  .p-det { flex: 1; }
  .p-name { font-family: var(--heading); font-size: 16px; font-weight: 600; }
  .p-mee { font-size: 12px; color: var(--text-3); margin-top: 3px; font-family: var(--mono); }
  .p-score { font-family: var(--mono); font-size: 28px; font-weight: 500; line-height: 1; }
  .p-score-l { font-size: 10px; color: var(--text-3); text-align: right; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.5px; }

  /* ═══════════ Score Chart ═══════════ */
  .sc-wrap { position: relative; height: 200px; }
  .sc-svg { width: 100%; height: 100%; }
  .sc-grid { stroke: var(--border); stroke-width: 0.5; }
  .sc-lbl { font-family: var(--mono); font-size: 10px; fill: var(--text-3); }
  .sc-legend { display: flex; justify-content: center; gap: 20px; margin-top: 14px; }
  .sc-leg { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-2); }
  .sc-sw { width: 16px; height: 3px; border-radius: 2px; }

  /* ═══════════ Metrics ═══════════ */
  .m-section { margin-bottom: 20px; }

  .m-label {
    font-family: var(--heading);
    font-size: 12px; font-weight: 600;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 10px;
  }

  .m-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }

  .m-card {
    padding: 20px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    transition: all 0.15s;
    box-shadow: var(--shadow);
  }
  .m-card:hover { border-color: var(--border-hover); box-shadow: var(--shadow-md); }

  .m-val { font-family: var(--mono); font-size: 28px; font-weight: 500; line-height: 1; color: var(--text); }
  .m-lbl { font-size: 12px; color: var(--text-3); margin-top: 6px; }

  .m-bar { margin-top: 12px; height: 4px; background: var(--bg-input); border-radius: 2px; overflow: hidden; }
  .m-bar-f { height: 100%; border-radius: 2px; background: var(--accent); transition: width 0.6s ease; }

  /* ═══════════ Placements ═══════════ */
  .pl-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

  .pl-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
  .pl-row+.pl-row { border-top: 1px solid var(--border); }

  .pl-rank { font-family: var(--mono); font-size: 11px; color: var(--text-3); min-width: 20px; }
  .pl-coord { font-family: var(--mono); font-size: 12px; color: var(--text-2); min-width: 56px; }

  .pl-bar-w { flex: 1; height: 8px; background: var(--bg-input); border-radius: 4px; overflow: hidden; }
  .pl-bar { height: 100%; border-radius: 4px; transition: width 0.5s; }

  .pl-sc { font-family: var(--mono); font-size: 13px; font-weight: 500; min-width: 32px; text-align: right; }

  .pl-tag {
    font-size: 10px; padding: 3px 8px; border-radius: 4px;
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px;
  }
  .pl-tag.good { background: var(--green-soft); color: var(--green); }
  .pl-tag.possible { background: var(--gold-soft); color: var(--gold); }

  /* ═══════════ Log ═══════════ */
  .log-list { max-height: 440px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--border) transparent; }

  .log-i { display: flex; align-items: flex-start; gap: 12px; padding: 12px 0; }
  .log-i+.log-i { border-top: 1px solid var(--border); }

  .log-t { font-family: var(--mono); font-size: 11px; color: var(--text-3); min-width: 28px; padding-top: 2px; }
  .log-d { width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
  .log-c { font-size: 13px; color: var(--text-2); line-height: 1.5; }
  .log-c strong { color: var(--text); font-weight: 600; }
  .log-pts { font-family: var(--mono); font-size: 11px; color: var(--green); font-weight: 500; }

  /* ═══════════ Animations ═══════════ */
  @keyframes fadeUp { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
  .ani { animation: fadeUp 0.35s ease forwards; }
  .d1 { animation-delay: 0.05s; opacity: 0; }
  .d2 { animation-delay: 0.1s; opacity: 0; }
  .d3 { animation-delay: 0.15s; opacity: 0; }
  .d4 { animation-delay: 0.2s; opacity: 0; }

  @media (max-width: 960px) {
    .app { padding: 0 16px 40px; }
    .b-layout, .pl-layout { grid-template-columns: 1fr; }
    .p-grid { grid-template-columns: 1fr; }
    .hdr { flex-direction: column; align-items: flex-start; gap: 16px; }
    .hdr-stats { align-self: flex-start; }
  }
`;

const ScoreTimeline = ({ data }) => {
  const maxS = Math.max(...data.flatMap(p => p.history));
  const steps = data[0].history.length - 1;
  const w = 620, h = 180, pad = { t: 8, r: 8, b: 22, l: 34 };
  const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
  const toPath = (hist) => hist.map((v, i) => {
    const x = pad.l + (i / steps) * pw, y = pad.t + ph - (v / (maxS || 1)) * ph;
    return `${i === 0 ? 'M' : 'L'}${x},${y}`;
  }).join(' ');
  return (
    <div className="sc-wrap">
      <svg className="sc-svg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet">
        {[0,.25,.5,.75,1].map((p, i) => {
          const y = pad.t + ph * (1 - p);
          return <g key={i}><line className="sc-grid" x1={pad.l} y1={y} x2={w-pad.r} y2={y}/><text className="sc-lbl" x={pad.l-6} y={y+3} textAnchor="end">{Math.round(maxS*p)}</text></g>;
        })}
        {[0, Math.floor(steps/4), Math.floor(steps/2), Math.floor(steps*3/4), steps].map((s, i) => (
          <text key={i} className="sc-lbl" x={pad.l + (s/steps)*pw} y={h-4} textAnchor="middle">T{s}</text>
        ))}
        {data.map(p => <path key={p.id} d={toPath(p.history)} fill="none" stroke={p.color} strokeWidth="2.5" opacity="0.75" strokeLinejoin="round" strokeLinecap="round"/>)}
      </svg>
      <div className="sc-legend">{data.map(p => <div key={p.id} className="sc-leg"><span className="sc-sw" style={{background:p.color}}/>{p.name}</div>)}</div>
    </div>
  );
};

export default function App() {
  const [tab, setTab] = useState("board");
  const [boardTiles] = useState(generateBoardTiles);
  const [potentials] = useState(() => generatePotentialPlacements(boardTiles));
  const [scoreHistory] = useState(generateScoreHistory);
  const [currentTile] = useState(TILE_TYPES[0]);
  const [tileRotation, setTileRotation] = useState(0);
  const [confidence] = useState(87);
  const [showPotentials, setShowPotentials] = useState(true);
  const [showMeeples, setShowMeeples] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const cx = 340, cy = 270, ts = 50;

  const onDown = (e) => { if (e.target.closest('.b-btn')) return; setIsDragging(true); setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y }); };
  const onMove = useCallback((e) => { if (isDragging) setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y }); }, [isDragging, dragStart]);
  const onUp = useCallback(() => setIsDragging(false), []);

  useEffect(() => {
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [onMove, onUp]);

  const tabList = [
    { id: "board", label: "Board State" },
    { id: "players", label: "Players & Scores" },
    { id: "metrics", label: "Game Metrics" },
    { id: "placements", label: "Placements" },
    { id: "log", label: "Activity" },
  ];

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

  const topP = [...potentials].sort((a, b) => b.score - a.score).slice(0, 8);
  const maxPS = topP.length > 0 ? topP[0].score : 1;

  return (
    <>
      <style>{css}</style>
      <div className="app">
        <header className="hdr ani">
          <div className="hdr-mark">
            <div className="hdr-logo">C</div>
            <div>
              <h1>Carcassonne<span>AR</span></h1>
              <div className="hdr-sub">Augmented Reality Board Analysis</div>
            </div>
          </div>
          <div className="hdr-stats">
            <div className="hdr-st"><div className="hdr-st-v">{METRICS.turnNumber}</div><div className="hdr-st-l">Turn</div></div>
            <div className="hdr-st"><div className="hdr-st-v">{METRICS.tilesPlaced}/{METRICS.tilesPlaced+METRICS.tilesRemaining}</div><div className="hdr-st-l">Tiles</div></div>
            <div className="live-chip"><span className="live-pip"/>CV Feed Live</div>
          </div>
        </header>

        <nav className="tabs">
          {tabList.map(t => <button key={t.id} className={`tab ${tab===t.id?'on':''}`} onClick={()=>setTab(t.id)}>{t.label}</button>)}
        </nav>

        {tab === "board" && (
          <div className="b-layout ani">
            <div className="card b-view" onMouseDown={onDown}>
              <div className="b-canvas" style={{ transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`, transformOrigin: "center center" }}>
                <div className="b-grid"/>
                {boardTiles.map((t,i) => (
                  <div key={i} className="b-tile" style={{ left:cx+t.col*ts, top:cy+t.row*ts }}>
                    <div className="b-tile-in" style={{ transform:`rotate(${t.rotation}deg)` }}>
                      <span className="b-tile-icon">{t.type.icon}</span>
                      {showMeeples && t.owner && <div className="b-tile-own" style={{background:t.owner.color}}/>}
                    </div>
                  </div>
                ))}
                {showPotentials && potentials.map((p,i) => (
                  <div key={i} className={`b-pot ${p.fit}`} style={{ left:cx+p.col*ts, top:cy+p.row*ts }}>+{p.score}</div>
                ))}
              </div>
              <div className="b-ctrls">
                <button className="b-btn" onClick={()=>setZoom(z=>Math.min(z+0.15,2.5))}>+</button>
                <button className="b-btn" onClick={()=>setZoom(z=>Math.max(z-0.15,0.4))}>−</button>
                <button className="b-btn" onClick={()=>{setZoom(1);setPan({x:0,y:0})}}>⌂</button>
              </div>
              <div className="b-info">{(zoom*100).toFixed(0)}% · {boardTiles.length} tiles</div>
            </div>

            <div className="b-side">
              <div className="card ani d1">
                <div className="card-h"><span className="card-t">Current Tile</span><span className="card-badge badge-accent">CV OUTPUT</span></div>
                <div className="card-b td">
                  <div className="td-preview"><span className="td-icon" style={{transform:`rotate(${tileRotation}deg)`}}>{currentTile.icon}</span></div>
                  <div className="td-name">{currentTile.name}</div>
                  <div className="conf-row">
                    <span className="conf-txt" style={{color:"var(--text-3)",fontSize:11}}>Confidence</span>
                    <div className="conf-track"><div className="conf-fill" style={{width:`${confidence}%`,background:confidence>80?"var(--green)":"var(--gold)"}}/></div>
                    <span className="conf-txt" style={{color:confidence>80?"var(--green)":"var(--gold)"}}>{confidence}%</span>
                  </div>
                  <div className="td-stats">
                    {[["Roads",currentTile.roads],["City",currentTile.city],["Fields",currentTile.fields],["Abbey",currentTile.monastery]].map(([l,v])=>(
                      <div key={l} className="td-s"><div className="td-s-v">{v}</div><div className="td-s-l">{l}</div></div>
                    ))}
                  </div>
                  <div className="rot-row">
                    <button className="rot-btn" onClick={()=>setTileRotation(r=>(r-90+360)%360)}>↶</button>
                    <span className="rot-val">{tileRotation}°</span>
                    <button className="rot-btn" onClick={()=>setTileRotation(r=>(r+90)%360)}>↷</button>
                  </div>
                </div>
              </div>
              <div className="card ani d2">
                <div className="card-h"><span className="card-t">Overlays</span></div>
                <div className="card-b">
                  <div className="tog"><span className="tog-lbl">Potential placements</span><button className={`sw ${showPotentials?'on':''}`} onClick={()=>setShowPotentials(!showPotentials)}><span className="sw-k"/></button></div>
                  <div className="tog"><span className="tog-lbl">Meeple ownership</span><button className={`sw ${showMeeples?'on':''}`} onClick={()=>setShowMeeples(!showMeeples)}><span className="sw-k"/></button></div>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === "players" && (
          <div className="ani">
            <div className="p-grid">
              {PLAYERS.map((p,i) => (
                <div key={p.id} className={`card p-card ani d${i+1}`} style={{borderLeftColor:p.color}}>
                  <div className="p-inner">
                    <div className="p-av" style={{background:p.color}}>{p.name[0]}</div>
                    <div className="p-det"><div className="p-name">{p.name}</div><div className="p-mee">{p.meeples}/7 meeples</div></div>
                    <div><div className="p-score" style={{color:p.color}}>{p.score}</div><div className="p-score-l">points</div></div>
                  </div>
                </div>
              ))}
            </div>
            <div className="card ani d3">
              <div className="card-h"><span className="card-t">Score Progression</span><span className="card-badge badge-blue">{METRICS.tilesPlaced} TURNS</span></div>
              <div className="card-b"><ScoreTimeline data={scoreHistory}/></div>
            </div>
          </div>
        )}

        {tab === "metrics" && (
          <div className="ani">
            <div className="m-section">
              <div className="m-label">Progress</div>
              <div className="m-row">
                <div className="m-card ani d1"><div className="m-val">{METRICS.tilesPlaced}</div><div className="m-lbl">Tiles placed</div><div className="m-bar"><div className="m-bar-f" style={{width:`${(METRICS.tilesPlaced/72)*100}%`}}/></div></div>
                <div className="m-card ani d2"><div className="m-val">{METRICS.tilesRemaining}</div><div className="m-lbl">Tiles remaining</div><div className="m-bar"><div className="m-bar-f" style={{width:`${(METRICS.tilesRemaining/72)*100}%`}}/></div></div>
                <div className="m-card ani d3"><div className="m-val">{METRICS.avgTurnTime}</div><div className="m-lbl">Avg. turn time</div></div>
                <div className="m-card ani d4"><div className="m-val">{METRICS.turnNumber}</div><div className="m-lbl">Current turn</div></div>
              </div>
            </div>
            <div className="m-section">
              <div className="m-label">Completed Features</div>
              <div className="m-row">
                <div className="m-card ani d1"><div className="m-val" style={{color:"var(--accent)"}}>{METRICS.completedCities}</div><div className="m-lbl">Cities</div></div>
                <div className="m-card ani d2"><div className="m-val" style={{color:"var(--blue)"}}>{METRICS.completedRoads}</div><div className="m-lbl">Roads</div></div>
                <div className="m-card ani d3"><div className="m-val" style={{color:"var(--gold)"}}>{METRICS.activeMonasteries}</div><div className="m-lbl">Active monasteries</div></div>
              </div>
            </div>
            <div className="m-section">
              <div className="m-label">Records</div>
              <div className="m-row">
                <div className="m-card ani d1"><div className="m-val" style={{color:"var(--green)"}}>{METRICS.largestCity}</div><div className="m-lbl">Largest city (tiles)</div></div>
                <div className="m-card ani d2"><div className="m-val" style={{color:"var(--green)"}}>{METRICS.longestRoad}</div><div className="m-lbl">Longest road (tiles)</div></div>
              </div>
            </div>
          </div>
        )}

        {tab === "placements" && (
          <div className="pl-layout ani">
            <div className="card ani d1">
              <div className="card-h"><span className="card-t">Best Placements</span><span className="card-badge badge-green">ENGINE</span></div>
              <div className="card-b">
                {topP.map((p,i) => (
                  <div key={i} className="pl-row">
                    <span className="pl-rank">{i+1}.</span>
                    <span className="pl-coord">({p.col}, {p.row})</span>
                    <div className="pl-bar-w"><div className="pl-bar" style={{width:`${(p.score/maxPS)*100}%`,background:p.fit==="good"?"var(--green)":"var(--gold)",opacity:0.75}}/></div>
                    <span className="pl-sc" style={{color:p.fit==="good"?"var(--green)":"var(--gold)"}}>+{p.score}</span>
                    <span className={`pl-tag ${p.fit}`}>{p.fit}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="card ani d2">
              <div className="card-h"><span className="card-t">Summary</span></div>
              <div className="card-b">
                <div className="m-row" style={{gridTemplateColumns:"1fr 1fr",marginBottom:16}}>
                  <div className="m-card"><div className="m-val" style={{color:"var(--green)"}}>{potentials.filter(p=>p.fit==="good").length}</div><div className="m-lbl">Good fits</div></div>
                  <div className="m-card"><div className="m-val" style={{color:"var(--gold)"}}>{potentials.filter(p=>p.fit==="possible").length}</div><div className="m-lbl">Possible fits</div></div>
                </div>
                <div style={{padding:"16px 18px",background:"var(--bg-input)",borderRadius:"var(--r)",border:"1px solid var(--border)"}}>
                  <div style={{fontFamily:"var(--heading)",fontSize:14,fontWeight:600,marginBottom:8}}>Analysis</div>
                  <p style={{fontSize:13,color:"var(--text-2)",lineHeight:1.65}}>
                    The current tile ({currentTile.name}) has {potentials.length} valid placement positions identified by the game engine.
                    The highest-scoring position yields +{maxPS} points. Positions tagged "good" indicate strong feature alignment with adjacent tiles.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === "log" && (
          <div className="card ani" style={{maxWidth:660}}>
            <div className="card-h"><span className="card-t">Game Activity</span><span className="card-badge badge-accent">{gameLog.length} RECENT</span></div>
            <div className="card-b">
              <div className="log-list">
                {gameLog.map((e,i) => (
                  <div key={i} className={`log-i ani d${Math.min(i+1,4)}`}>
                    <span className="log-t">T{e.turn}</span>
                    <span className="log-d" style={{background:e.player.color}}/>
                    <span className="log-c"><strong>{e.player.name}</strong> {e.text}{e.scored&&<>{" "}<span className="log-pts">+{e.scored} pts</span></>}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}