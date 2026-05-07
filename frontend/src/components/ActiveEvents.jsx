export default function ActiveEvents({ events, players }) {
  const list = events || [];

  return (
    <div className="card card-events">
      <div className="card-header">
        <span>Active Events</span>
        <span className="card-tag">{list.length}</span>
      </div>
      <div className="card-body">
        {list.length === 0 ? (
          <p style={{ fontSize: 12, color: "var(--dim)" }}>
            No active events.
          </p>
        ) : (
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
