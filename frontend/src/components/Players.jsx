import { PLAYER_COLOURS } from "../constants/config";

export default function Players({ currentPlayer, players }) {
  return <div className="card card-players">
    <div className="card-header">
      <span>Players</span>
      {/* show which player number has the current turn, offset by 1 since index starts at 0 */}
      <span className="card-tag card-tag-blue">
        TURN: P{currentPlayer + 1}
      </span>
    </div>
    <div className="card-body">
      {/* render a row for each player in the game */}
      {players.map((p, i) => (
        <div
          key={i}
          className={`player-row ${i === currentPlayer ? "active" : ""}`}
        >
          <div
            className="player-avatar"
            style={{ background: PLAYER_COLOURS[i] || "#888" }}
          >
            {p.colour?.[0]?.toUpperCase() || i + 1}
          </div>
          <div>
            <div className="player-name">
              {/* show colour as the player name, fall back to generic Player N */}
              <p style={{ padding: 0, margin: 0 }}>{p.colour || `Player ${i + 1}`}</p>
            </div>
            {/* show how many of the 7 meeples are still available */}
            <div className="player-detail">{p.meeples}/7 meeples</div>
          </div>
          <div
            className="player-score"
            // colour the score text to match the player so its easy to scan
            style={{ color: PLAYER_COLOURS[i] || "#888" }}
          >
            {p.score}
          </div>
        </div>
      ))}
    </div>
  </div>;
}