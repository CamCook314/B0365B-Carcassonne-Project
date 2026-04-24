import GameBoard from "./GameBoard";
import Players from "./Players";
import DetectedTile from "./DetectedTile";

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
      <DetectedTile pendingTile={pendingTile} validPlacements={validPlacements} />

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
