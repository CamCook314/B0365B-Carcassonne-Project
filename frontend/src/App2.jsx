// App2.jsx
import { useState, useEffect } from "react";
import { getGameState, startGame } from "./api";
import GameBoard from "./Gameboard";
import "./App2.css";

// Player colors — matches the engine's player indices
const PLAYER_COLORS = ["#BF616A", "#81A1C1", "#A3BE8C", "#EBCB8B", "#B48EAD"];

export default function App2() {
  const [gameState, setGameState] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch game state from API
  const fetchState = async () => {
    try {
      const data = await getGameState();
      setGameState(data);
      setError(null);
    } catch (err) {
      // Game not started yet — that's fine
      setError(err.message);
      setGameState(null);
    } finally {
      setLoading(false);
    }
  };

  // Start a new game
  const handleStart = async (numPlayers) => {
    try {
      await startGame(numPlayers);
      await fetchState();
    } catch (err) {
      setError(err.message);
    }
  };

  // Fetch on mount, then poll every 2 seconds
  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 2000);
    return () => clearInterval(interval);
  }, []);

  // Convert API board data to array for GameBoard
  const boardTiles = gameState
    ? Object.entries(gameState.board).map(([key, tile]) => {
        const [col, row] = key.split(",").map(Number);
        return {
          col,
          row,
          tileId: tile.tile_id,
        };
      })
    : [];

  const players = gameState?.players || [];
  const currentTurn = gameState?.current_turn || 0;
  const currentPlayer = gameState?.current_player || 0;
  const remaining = gameState?.remaining_pieces || 0;

  // --- Not started screen ---
  if (!loading && !gameState) {
    return (
      <div className="app">
        <header className="header">
          <h1>Carcassonne<span> AR</span></h1>
        </header>
        <div style={{ textAlign: "center", marginTop: 80 }}>
          <h2 style={{ marginBottom: 16, color: "var(--text)" }}>No Game Running</h2>
          <p style={{ color: "var(--dim)", marginBottom: 24 }}>
            {error === "Game not started"
              ? "Start a new game to begin."
              : `API error: ${error}. Is the backend running?`}
          </p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            {[2, 3, 4, 5].map((n) => (
              <button
                key={n}
                onClick={() => handleStart(n)}
                style={{
                  padding: "10px 24px",
                  background: "var(--accent)",
                  color: "var(--bg)",
                  border: "none",
                  borderRadius: 6,
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {n} Players
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // --- Loading ---
  if (loading) {
    return (
      <div className="app">
        <p style={{ textAlign: "center", marginTop: 80, color: "var(--dim)" }}>
          Connecting to game engine...
        </p>
      </div>
    );
  }

  // --- Game running ---
  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div>
          <h1>Carcassonne<span> AR</span></h1>
        </div>
        <div className="header-right">
          <div>
            <div>{currentTurn}</div>
            <div className="header-stat-label">Turn</div>
          </div>
          <div>
            <div>{boardTiles.length}/{boardTiles.length + remaining}</div>
            <div className="header-stat-label">Tiles</div>
          </div>
          <div>
            <span className="live-dot" />
            <span style={{ color: "var(--green)", fontSize: 11, fontWeight: 600 }}>CV Live</span>
          </div>
        </div>
      </header>

      {/* 3-Column Layout */}
      <div className="grid">
        {/* LEFT */}
        <div className="col">
          {/* Players */}
          <div className="card card-players">
            <div className="card-header">
              <span>Players</span>
              <span className="card-tag card-tag-blue">
                TURN: P{currentPlayer + 1}
              </span>
            </div>
            <div className="card-body">
              {players.map((p, i) => (
                <div
                  key={i}
                  className={`player-row ${i === currentPlayer ? "active" : ""}`}
                >
                  <div
                    className="player-avatar"
                    style={{ background: PLAYER_COLORS[i] || "#888" }}
                  >
                    {p.colour?.[0]?.toUpperCase() || i + 1}
                  </div>
                  <div>
                    <div className="player-name">{p.colour || `Player ${i + 1}`}</div>
                    <div className="player-detail">{p.meeples}/7 meeples</div>
                  </div>
                  <div
                    className="player-score"
                    style={{ color: PLAYER_COLORS[i] || "#888" }}
                  >
                    {p.score}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Activity Log — placeholder until you track moves */}
          <div className="card card-log">
            <div className="card-header">
              <span>Activity Log</span>
              <span className="card-tag card-tag-gold">RECENT</span>
            </div>
            <div className="card-body">
              <p style={{ fontSize: 12, color: "var(--dim)" }}>
                Move history will appear here.
              </p>
            </div>
          </div>
        </div>

        {/* CENTRE */}
        <div className="col">
          <GameBoard tiles={boardTiles} />

          <div className="metrics">
            <div className="metric">
              <div className="metric-val">{boardTiles.length}</div>
              <div className="metric-label">Placed</div>
            </div>
            <div className="metric">
              <div className="metric-val">{remaining}</div>
              <div className="metric-label">Remaining</div>
            </div>
            <div className="metric">
              <div className="metric-val">{currentTurn}</div>
              <div className="metric-label">Turn</div>
            </div>
            <div className="metric">
              <div className="metric-val">{players.length}</div>
              <div className="metric-label">Players</div>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="col">
          {/* Detected Tile */}
          <div className="card card-detect">
            <div className="card-header">
              <span>Detected Tile</span>
              <span className="card-tag card-tag-green">CV OUTPUT</span>
            </div>
            <div className="card-body" style={{ textAlign: "center" }}>
              <div className="tile-preview">—</div>
              <div className="tile-name">Waiting for CV...</div>
            </div>
          </div>

          {/* Game Stats */}
          <div className="card card-stats">
            <div className="card-header">
              <span>Game Stats</span>
              <span className="card-tag card-tag-red">LIVE</span>
            </div>
            <div className="card-body">
              <p style={{ fontSize: 12, color: "var(--dim)" }}>
                Stats will populate as the game progresses.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}