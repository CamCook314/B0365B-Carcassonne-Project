const PLAYER_COLOURS = ["#BF616A", "#81A1C1", "#A3BE8C", "#EBCB8B", "#B48EAD"];

export default function Players({ currentPlayer, players }) {
  return <div className="card card-players">
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
            style={{ background: PLAYER_COLOURS[i] || "#888" }}
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
            style={{ color: PLAYER_COLOURS[i] || "#888" }}
          >
            {p.score}
          </div>
        </div>
      ))}
    </div>
  </div>;
}