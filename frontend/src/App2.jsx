import { useState, useEffect } from "react";
import { getGameState, startGame, setPendingTile, setPendingTileList} from "./api";
import GameBoard from "./Gameboard";
import "./App2.css";

const PLAYER_COLORS = ["#BF616A", "#81A1C1", "#A3BE8C", "#EBCB8B", "#B48EAD"];

export default function App2() {
  const [gameState, setGameState] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pendingInput, setPendingInput] = useState(0);

  // Pending tile from CV (via API)
  const pendingTile = gameState?.pending_tile || null;
  const pendingTileList = gameState?.tile_ids || [];
  const validPlacements = gameState?.pending_valid || [];

  // Fetch game state from API
  const fetchState = async () => {
    try {
      const data = await getGameState();
      setGameState(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      setGameState(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchTileList = async (tileIds) => {
    try {
      const tiles = await setPendingTileList(tileIds);
      console.log("Fetched tile list:", tiles);

      await fetchState(); // Refresh game state after fetching tiles
      return tiles;
    } catch (err) {
      console.error("Error fetching tile list:", err);
    }
  }

  const handleSetPending = async () => {
    try {
      await setPendingTile(Number(pendingInput));
      await fetchState();
    } catch (err) {
      setError(err.message);
    }
  };

  // start a new game
  const handleStart = async (numPlayers) => {
    try {
      await startGame(numPlayers);
      await fetchState();
    } catch (err) {
      setError(err.message);
    }
  };

  // start fetching on mount
  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 2000);
    return () => clearInterval(interval);
  }, []);

  // check if the tile has changed
  useEffect(() => {
    if (pendingTile != null) {
      console.log("Pending tile changed:", pendingTile);
    }
  }, [pendingTile]);

  // convert API board data to array for GameBoard
  const boardTiles = gameState
    ? Object.entries(gameState.board).map(([key, tile]) => {
        const [col, row] = key.split(",").map(Number);
        return {
          col,
          row,
          tileId: tile.tile_id,
          attribute: tile.attribute,
          meeple_attached: tile.meeple_attached,
        };
      })
    : [];

  const players = gameState?.players || [];
  const currentTurn = gameState?.current_turn || 0;
  const currentPlayer = gameState?.current_player || 0;
  const remaining = gameState?.remaining_pieces || 0;

  // entry screens for picking player numbers for api
  if (!loading && !gameState) {
    return (
      <div className="app">
        <header className="header">
          <h1>
            Carcassonne<span> AR</span>
          </h1>
        </header>
        <div style={{ textAlign: "center", marginTop: 80 }}>
          <h2 style={{ marginBottom: 16, color: "var(--text)" }}>
            No Game Running
          </h2>
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

  // loading
  if (loading) {
    return (
      <div className="app">
        <p
          style={{ textAlign: "center", marginTop: 80, color: "var(--dim)" }}
        >
          Connecting to game engine...
        </p>
      </div>
    );
  }

  // Game running
  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div>
          <h1>
            Carcassonne<span> AR</span>
          </h1>
        </div>
        <div className="header-right">
          <div>
            <div>{currentTurn}</div>
            <div className="header-stat-label">Turn</div>
          </div>
          <div>
            <div>
              {boardTiles.length}/{boardTiles.length + remaining}
            </div>
            <div className="header-stat-label">Tiles</div>
          </div>
          <div>
            <span className="live-dot" />
            <span
              style={{
                color: "var(--green)",
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              CV Live
            </span>
          </div>
        </div>
      </header>

      <div className="grid">
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
                  className={`player-row ${
                    i === currentPlayer ? "active" : ""
                  }`}
                >
                  <div
                    className="player-avatar"
                    style={{ background: PLAYER_COLORS[i] || "#888" }}
                  >
                    {p.colour?.[0]?.toUpperCase() || i + 1}
                  </div>
                  <div>
                    <div className="player-name">
                      {p.colour || `Player ${i + 1}`}
                    </div>
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

          {/* Activity Log */}
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

        {/* gameboard */}
        <div className="col">
          <GameBoard
            tiles={boardTiles}
            meeples={[]}
            validPlacements={validPlacements}
            onTileClick={(tile) => console.log("Clicked:", tile)}
          />

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

        <div className="col">
          {/* Detected Tile */}
          <div className="card card-detect">
            <div className="card-header">
              <span>Detected Tile</span>
              <span
                className={`card-tag ${
                  pendingTile ? "card-tag-green" : ""
                }`}
              >
                {pendingTile ? "DETECTED" : "WAITING"}
              </span>
            </div>
            <div className="card-body" style={{ textAlign: "center" }}>
              {pendingTile ? (
                <>
                  <div className="tile-preview">
                    <img
                      src={`/tiles/${pendingTile}.jpg`}
                      alt={pendingTile}
                      style={{
                        width: "100%",
                        height: "100%",
                        borderRadius: 4,
                        objectFit: "cover",
                      }}
                      onError={(e) => {
                        e.target.style.display = "none";
                      }}
                    />
                  </div>
                  <div className="tile-name">{pendingTile}</div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--green)",
                      marginTop: 4,
                    }}
                  >
                    {validPlacements.length} valid placement
                    {validPlacements.length !== 1 ? "s" : ""}
                  </div>
                  <div style={{ marginTop: 16, display: "flex", gap: 8, justifyContent: "center" }}>
                    <input
                      type="number"
                      min="0"
                      value={pendingInput}
                      onChange={(e) => setPendingInput(e.target.value)}
                      style={{ width: 80, padding: "8px 10px", borderRadius: 6, border: "1px solid #ccc" }}
                    />
                    <button
                      onClick={() => setPendingTile(Number(pendingInput))}
                      style={{
                        padding: "8px 8px",
                        background: "var(--accent)",
                        color: "var(--bg)",
                      }}
                    >
                      {pendingTileList[0]}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="tile-preview">—</div>
                  <div className="tile-name">Waiting for CV...</div>
                </>
              )}
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