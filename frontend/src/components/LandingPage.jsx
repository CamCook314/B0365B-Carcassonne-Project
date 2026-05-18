import { useState } from "react";
import "../css/LandingPage.css";

const PLAYER_COLOURS = [
  { name: "Red",    hex: "#BF616A" },
  { name: "Blue",   hex: "#81A1C1" },
  { name: "Green",  hex: "#A3BE8C" },
  { name: "Yellow", hex: "#EBCB8B" },
  { name: "Black",  hex: "#4C566A" },
];

const CITY_IDS      = [60, 61, 62, 80, 81, 82];
const ROAD_IDS      = [0, 1, 4, 8, 12, 13];
const MONASTERY_IDS = [17, 18, 19];
const FIELD_IDS     = [22, 30, 40, 50];
const MOSAIC_IDS    = [0,1,4,8,12,17,22,30,40,52,60,72,80,90,100,110,120,130];

const PILLS = [
  { id: "about",    label: "About the Project" },
  { id: "rules",    label: "How to Play" },
  { id: "terrain",  label: "Terrain Types" },
  { id: "scoring",  label: "Scoring" },
  { id: "events",   label: "Special Events" },
];

function TileImg({ id, className = "rule-tile" }) {
  return (
    <img
      src={`/tiles/ID${id}.jpg`}
      alt={`Tile ${id}`}
      className={className}
      onError={e => { e.target.style.display = "none"; }}
    />
  );
}

/* ── Section panels ─────────────────────────────────────────────── */

function AboutPanel() {
  return (
    <div className="panel">
      <p className="panel-intro">
        Carcassonne AR bridges the physical and digital worlds. Players place real Carcassonne
        tiles on a table as normal, while an overhead camera feed runs computer vision to identify
        each tile and its position. The system tracks the game state, validates placements, and
        scores completed features automatically.
      </p>
      <div className="feature-grid">
        <div className="feature-card">
          <div className="feature-icon">📷</div>
          <h3>CV Tile Detection</h3>
          <p>An overhead camera identifies each tile as it is placed by matching it against
             a database of all 336 Carcassonne tiles.</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🗺️</div>
          <h3>Real-time Board Tracking</h3>
          <p>The digital board updates instantly as tiles are placed. Valid placement positions
             are highlighted and edge-matching is validated automatically.</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🏆</div>
          <h3>Automatic Scoring</h3>
          <p>Completed cities, roads, and monasteries are detected and scored immediately.
             Final scores are calculated when the game ends.</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">⚡</div>
          <h3>Special Events</h3>
          <p>A custom events system adds extra twists volcanoes, extra turns, unrest, and
             more that activate once all river tiles have been placed.</p>
        </div>
      </div>
    </div>
  );
}

function RulesPanel() {
  return (
    <div className="panel">
      <p className="panel-intro">
        Carcassonne is a tile-placement game for 2–5 players. Each turn a player draws a tile,
        places it on the growing board, and optionally places a meeple to claim a feature.
        Points are scored when cities, roads, and monasteries are completed.
      </p>
      <div className="rules-steps">

        <div className="rule-step">
          <div className="rule-step-num">1</div>
          <div className="rule-step-body">
            <h3>Place a Tile</h3>
            <p>
              The top tile from the draw pile is revealed (or detected by the camera).
              Place it adjacent to an existing tile so that all touching edges match
              city to city, road to road, field to field. The tile may be rotated into any of
              the four orientations. If no legal placement exists, the tile is removed from the game.
            </p>
          </div>
          <div className="rule-step-tiles">
            <TileImg id={0} /><TileImg id={4} /><TileImg id={12} />
          </div>
        </div>

        <div className="rule-step">
          <div className="rule-step-num">2</div>
          <div className="rule-step-body">
            <h3>Place a Meeple (optional)</h3>
            <p>
              After placing a tile you may place one of your meeples on a feature of that tile.
              You cannot place on a feature already occupied by any meeple (even your own).
              Each player has 7 meeples. A meeple on a road is a <strong>Highwayman</strong>,
              in a city a <strong>Knight</strong>, in a monastery a <strong>Monk</strong>, and
              in a field a <strong>Farmer</strong> (scores at end only).
            </p>
          </div>
          <div className="rule-step-tiles">
            <TileImg id={60} /><TileImg id={17} />
          </div>
        </div>

        <div className="rule-step">
          <div className="rule-step-num">3</div>
          <div className="rule-step-body">
            <h3>Score Completed Features</h3>
            <p>
              A feature is complete when fully enclosed with no open edges. All meeples on it
              are scored and returned to their owners. If multiple players share a feature, each
              scores the full amount. Completed city: 2 pts per tile + 2 pts per pennant.
              Completed road: 1 pt per tile. Completed monastery: 9 pts.
            </p>
          </div>
          <div className="rule-step-tiles">
            <TileImg id={80} /><TileImg id={8} />
          </div>
        </div>

        <div className="rule-step">
          <div className="rule-step-num">4</div>
          <div className="rule-step-body">
            <h3>End of Game</h3>
            <p>
              When the last tile is placed (or players choose to end), all incomplete features
              score at half value. Farmers score 3 pts per completed city adjacent to their field.
              Incomplete city: 1 pt per tile + 1 per pennant. Incomplete road: 1 pt per tile.
              Incomplete monastery: 1 pt per surrounding tile.
            </p>
          </div>
          <div className="rule-step-tiles">
            <TileImg id={22} /><TileImg id={30} />
          </div>
        </div>

      </div>
    </div>
  );
}

function TerrainPanel() {
  return (
    <div className="panel">
      <p className="panel-intro">
        Every tile is made up of terrain segments across its four edges and centre.
        Learning to read tile edges quickly is the key skill in Carcassonne.
      </p>
      <div className="terrain-grid">

        <div className="terrain-card">
          <div className="terrain-card-head">
            <span className="terrain-badge terrain-badge-city">City</span>
            <span className="terrain-pts">2 pts / tile (complete)</span>
          </div>
          <p>Blue-grey walled areas. A completed city scores 2 pts per tile, plus 2 pts per
             pennant shield inside it. Incomplete cities score 1 pt per tile at game end.</p>
          <div className="terrain-tiles">
            {CITY_IDS.map(id => <TileImg key={id} id={id} className="terrain-tile" />)}
          </div>
        </div>

        <div className="terrain-card">
          <div className="terrain-card-head">
            <span className="terrain-badge terrain-badge-road">Road</span>
            <span className="terrain-pts">1 pt / tile (complete)</span>
          </div>
          <p>Lines running between two edges. A road ends at a village, a city gate, or a
             monastery. Both complete and incomplete roads score 1 pt per tile.</p>
          <div className="terrain-tiles">
            {ROAD_IDS.map(id => <TileImg key={id} id={id} className="terrain-tile" />)}
          </div>
        </div>

        <div className="terrain-card">
          <div className="terrain-card-head">
            <span className="terrain-badge terrain-badge-monastery">Monastery</span>
            <span className="terrain-pts">Up to 9 pts</span>
          </div>
          <p>A building in the centre of a tile surrounded by field. Scores 1 pt for itself plus
             1 pt for each of the up to 8 surrounding tiles (9 pts when fully enclosed).</p>
          <div className="terrain-tiles">
            {MONASTERY_IDS.map(id => <TileImg key={id} id={id} className="terrain-tile" />)}
          </div>
        </div>

        <div className="terrain-card">
          <div className="terrain-card-head">
            <span className="terrain-badge terrain-badge-field">Field</span>
            <span className="terrain-pts">3 pts / city (end only)</span>
          </div>
          <p>Open grassland between features. Only Farmers (meeples on fields) score from fields,
             and only at the end of the game 3 pts per completed city their field touches.</p>
          <div className="terrain-tiles">
            {FIELD_IDS.map(id => <TileImg key={id} id={id} className="terrain-tile" />)}
          </div>
        </div>

      </div>
    </div>
  );
}

function ScoringPanel() {
  return (
    <div className="panel">
      <p className="panel-intro">
        Points are awarded during the game when features complete, and again at the end for
        everything unfinished. The player with the highest total wins. Ties are broken by most
        meeples remaining.
      </p>
      <div className="score-grid">
        <div className="score-card">
          <h3>During the Game</h3>
          <div className="score-row"><span>City tile (complete)</span><span className="score-pts">2 pts each</span></div>
          <div className="score-row"><span>Pennant shield (in complete city)</span><span className="score-pts">+2 pts each</span></div>
          <div className="score-row"><span>Road tile (complete)</span><span className="score-pts">1 pt each</span></div>
          <div className="score-row"><span>Monastery (all 8 neighbours placed)</span><span className="score-pts">9 pts</span></div>
        </div>
        <div className="score-card">
          <h3>End of Game</h3>
          <div className="score-row"><span>City tile (incomplete)</span><span className="score-pts">1 pt each</span></div>
          <div className="score-row"><span>Pennant shield (incomplete city)</span><span className="score-pts">+1 pt each</span></div>
          <div className="score-row"><span>Road tile (incomplete)</span><span className="score-pts">1 pt each</span></div>
          <div className="score-row"><span>Monastery per surrounding tile</span><span className="score-pts">1 pt each</span></div>
          <div className="score-row"><span>Farmer per completed city touched</span><span className="score-pts">3 pts each</span></div>
        </div>
      </div>

      <div className="score-note">
        <strong>Shared features:</strong> if multiple players have a meeple on the same completed
        feature (via merging), each player scores the full amount nobody is penalised.
      </div>

      <div className="meeple-colours">
        {PLAYER_COLOURS.map(p => (
          <div key={p.name} className="meeple-colour-chip">
            <div className="meeple-dot" style={{ background: p.hex }} />
            {p.name}
          </div>
        ))}
      </div>
    </div>
  );
}

function EventsPanel() {
  return (
    <div className="panel">
      <p className="panel-intro">
        This version of Carcassonne includes a custom events system. Events are locked until
        all 12 river tiles have been placed. Once unlocked, events trigger randomly during the
        game and can swing scores dramatically.
      </p>
      <div className="events-explainer">

        <div className="event-explain-card">
          <h3>Extra Turn</h3>
          <p>A player gets to place a second tile this turn. Draw and place an additional tile
             immediately before passing control to the next player.</p>
        </div>

        <div className="event-explain-card">
          <h3>Volcano</h3>
          <p>A random placed tile is removed from the board. Any meeple on that tile is returned
             to its owner without scoring. Features touching the gap become incomplete.</p>
        </div>

        <div className="event-explain-card">
          <h3>Unrest</h3>
          <p>A meeple belonging to the targeted player is forcibly removed from the board without
             scoring, disrupting their control of a feature.</p>
        </div>

        <div className="event-explain-card">
          <h3>Plague</h3>
          <p>The targeted player loses a set number of points from their current score, simulating
             a catastrophe hitting their civilization.</p>
        </div>

      </div>

      <div className="score-note" style={{ marginTop: 28 }}>
        <strong>River phase:</strong> the game always begins with the 12 river tiles, which must
        all be placed before normal tiles (and events) begin. The river tiles form a winding
        starting layout that shapes early strategy.
      </div>
    </div>
  );
}

/* ── Main component ─────────────────────────────────────────────── */

const PANEL_MAP = {
  about:   <AboutPanel />,
  rules:   <RulesPanel />,
  terrain: <TerrainPanel />,
  scoring: <ScoringPanel />,
  events:  <EventsPanel />,
};

export default function LandingPage({ error, handleStart }) {
  const [active, setActive] = useState(null);

  return (
    <div className="landing">

      {/* Nav */}
      <nav className="landing-nav">
        <div className="landing-nav-logo">Carcassonne<span> AR</span></div>
      </nav>

      {/* Hero */}
      <section className="landing-hero">
        <h1>Carcassonne <span>AR</span></h1>
        <p className="landing-hero-sub">
          A computer-vision powered digital companion for the classic tile-placement board game.
          Place real tiles the system detects and scores them automatically.
        </p>

        {error && error !== "Game not started" && (
          <p className="landing-error">
            Backend not reachable: {error}. Make sure the game engine is running.
          </p>
        )}

        <p className="landing-start-label">Choose number of players to start</p>
        <div className="landing-start-btns">
          {[2, 3, 4, 5].map(n => (
            <button key={n} className="landing-start-btn" onClick={() => handleStart(n)}>
              {n} Players
            </button>
          ))}
        </div>
      </section>

      {/* Tile mosaic strip FRIGGIN FIRE DESIGN YEAHHHHH*/}
      <div className="tile-strip">
        {MOSAIC_IDS.map(id => (
          <img key={id} src={`/tiles/ID${id}.jpg`} alt="" className="tile-strip-img"
            onError={e => { e.target.style.display = "none"; }} />
        ))}
      </div>

      {/* Pill nav */}
      <div className="pill-nav-wrap">
        <div className="pill-nav">
          {PILLS.map(pill => (
            <button
              key={pill.id}
              className={`pill${active === pill.id ? " pill-active" : ""}`}
              onClick={() => setActive(prev => prev === pill.id ? null : pill.id)}
            >
              {pill.label}
            </button>
          ))}
        </div>
      </div>

      {/* Panel content */}
      {active && (
        <div className="panel-wrap">
          {PANEL_MAP[active]}
        </div>
      )}

      {/* Footer */}
      <footer className="landing-footer">
        Carcassonne AR University Year 4 Project &nbsp;|&nbsp; B0365B
      </footer>

    </div>
  );
}
