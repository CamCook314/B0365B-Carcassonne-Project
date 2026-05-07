export default function Header({ currentTurn, boardTiles, remaining }) {
  return <header className="header">
    <div>
      <h1>
        Carcassonne<span> AR</span>
      </h1>
    </div>
    <div className="header-right">
      <div>
        <div style={{ color: "var(--green)", fontWeight: 600 }}>{currentTurn}</div>
        <div className="header-stat-label">Turn</div>
      </div>
      <div>
        <div style={{ color: "var(--green)", fontWeight: 600 }}>
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
  </header>;
}
