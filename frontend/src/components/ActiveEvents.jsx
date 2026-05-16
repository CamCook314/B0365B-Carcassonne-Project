export default function ActiveEvents({
  events,
  players,
  eventsUnlocked = true,
  riverTilesPlaced = 0,
}) {
  const list = events || [];
  const showLockMessage = !eventsUnlocked && list.length === 0;
  const showEmptyMessage = eventsUnlocked && list.length === 0;

  return (
    <div className="card card-events">
      <div className="card-header">
        <span>Active Events</span>
        <span className="card-tag">{eventsUnlocked ? list.length : "locked"}</span>
      </div>
      <div className="card-body">
        {showLockMessage && (
          <p style={{ fontSize: 12, color: "var(--dim)" }}>
            Events locked: {riverTilesPlaced}/12 river tiles placed. Events activate once the river is complete.
          </p>
        )}
        {showEmptyMessage && (
          <p style={{ fontSize: 12, color: "var(--dim)" }}>
            No active events.
          </p>
        )}
        {list.length > 0 && (
          <ul className="events-list">
            {list.map((ev, i) => {
              let appliedTo = null;
              if (ev.player_index !== undefined && ev.player_index !== null) {
                const p = players[ev.player_index];
                if (p) {
                  appliedTo = p.colour;
                }
              }

              return (
                <li key={i} className="event-item">
                  <div className="event-name">{ev.name}</div>
                  <div className="event-desc">{ev.description}</div>
                  {appliedTo && (
                    <div className="event-applied">
                      Applied to:{" "}
                      <span style={{ color: appliedTo, fontWeight: 600 }}>
                        {appliedTo}
                      </span>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
