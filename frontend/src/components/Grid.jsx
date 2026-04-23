import GameBoard from "./GameBoard";
import Players from "./Players";

export default function Grid({ currentPlayer, players, boardTiles, validPlacements, remaining, currentTurn, pendingTile }) {
  return <div className="grid">
    <div className="col">
      {/* Players */}
      <Players currentPlayer={currentPlayer} players={players} />

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
        onTileClick={(tile) => console.log("Clicked:", tile)} />

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
            className={`card-tag ${pendingTile ? "card-tag-green" : ""}`}
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
                  } } />
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
  </div>;
}