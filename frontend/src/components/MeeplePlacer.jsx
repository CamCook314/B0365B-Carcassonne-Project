import { placeMeeple, skipMeeple } from "../api/api.js";
import { PLAYER_COLOUR_MAP } from "../constants/config";

// labels for each side
const SIDE_LABEL = {
  up:     "↑ Up",
  down:   "↓ Down",
  left:   "← Left",
  right:  "→ Right",
  centre: "● Centre",
};

export default function MeeplePlacer({ pendingPlacement, currentPlayer, players }) {
  // Idle state there is no tile awaiting a meeple decision
  if (!pendingPlacement) {
    return (
      <div className="card card-meeple">
        <div className="card-header">
          <span>Meeple</span>
          <span className="card-tag">IDLE</span>
        </div>
        <div className="card-body">
          <p style={{ fontSize: 12, color: "var(--dim)" }}>
            Place a tile to choose a meeple position.
          </p>
        </div>
      </div>
    );
  }

  const { tile_id, x, y, valid_sides = [] } = pendingPlacement;
  const player = players?.[currentPlayer];
  const playerColour = PLAYER_COLOUR_MAP[player?.colour] || "#888";
  const meeplesLeft = player?.meeples ?? 0;

  const handlePlace = async (direction) => {
    try {
      await placeMeeple(direction);
    } catch (err) {
      console.error("placeMeeple failed:", err);
    }
  };

  const handleSkip = async () => {
    try {
      await skipMeeple();
    } catch (err) {
      console.error("skipMeeple failed:", err);
    }
  };

  return (
    <div className="card card-meeple">
      <div className="card-header">
        <span>Meeple</span>
        <span className="card-tag card-tag-green">PLACE</span>
      </div>
      <div className="card-body">

        {/* Outlines where Tile Placed */}
        <div style={{ fontSize: 12, color: "var(--dim)", marginBottom: 6 }}>
          Tile placed: <strong style={{ color: "var(--text)" }}>{tile_id}</strong> at ({x}, {y})
        </div>

        {/* Current player turn and how many meeples left for them */}
        <div style={{ fontSize: 12, marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              background: playerColour,
              display: "inline-block",
              border: "1px solid var(--border, #444)",
            }}
          />
          <span style={{ color: "var(--text)" }}>
            {player?.colour || `Player ${currentPlayer + 1}`}
          </span>
          <span style={{ color: "var(--dim)", marginLeft: "auto" }}>
            {meeplesLeft}/7 meeples left
          </span>
        </div>

        {/* show a message if no meeple spots exist otherwise render bttons for valid side */}
        {valid_sides.length === 0 ? (
          <div style={{ fontSize: 12, color: "var(--dim)", marginBottom: 10 }}>
            No road, city or monastery on this tile — only Skip is available.
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 8 }}>
            {valid_sides.map((side) => (
              <button
                key={side}
                onClick={() => handlePlace(side)}
                disabled={meeplesLeft <= 0}
                style={{
                  padding: "8px 10px",
                  background: meeplesLeft > 0 ? playerColour : "var(--dim)",
                  color: "var(--bg)",
                  border: "none",
                  borderRadius: 4,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: meeplesLeft > 0 ? "pointer" : "not-allowed",
                  opacity: meeplesLeft > 0 ? 1 : 0.5,
                }}
              >
                {SIDE_LABEL[side] || side}
              </button>
            ))}
          </div>
        )}

        <button
          onClick={handleSkip}
          style={{
            width: "100%",
            padding: "8px 10px",
            background: "transparent",
            color: "var(--text)",
            border: "1px solid var(--border, #444)",
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Skip (no meeple)
        </button>

        {/* No meeple left fallback */}
        {meeplesLeft <= 0 && (
          <div style={{ fontSize: 11, color: "var(--red, #BF616A)", marginTop: 8 }}>
            No meeples remaining — you must skip.
          </div>
        )}
      </div>
    </div>
  );
}