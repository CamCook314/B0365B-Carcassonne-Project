export default function Header({ currentTurn, boardTiles, remaining, isMuted, toggleMute }) {
  return <header className="header">
    <div>
      <h1>
        Carcassonne<span> AR</span>
      </h1>
    </div>
    <div className="header-right">
      {/* Cur Turn Display */}
      <div>
        <div style={{ color: "var(--green)", fontWeight: 600 }}>{currentTurn}</div>
        <div className="header-stat-label">Turn</div>
      </div>
      {/* Tiles Placed */}
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
      <MuteButton toggleMute={toggleMute} isMuted={isMuted} />
    </div>
  </header>;
}

function MuteButton({ toggleMute, isMuted }) {
  return <button
    onClick={toggleMute}
    title={isMuted ? "Unmute" : "Mute"}
    style={{
      background: "transparent",
      border: "none",
      padding: 3,
      fontSize: 18,
    }}
  >
    {isMuted ? "🔈" : "🔊"}
  </button>;
}

