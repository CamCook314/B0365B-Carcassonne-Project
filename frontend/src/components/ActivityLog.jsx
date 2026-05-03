import { getHistory } from "../api/api";


export function ActivityLog( { history }) {
    //console.log("ActivityLog history:", history);
  return <div className="card card-log">
    <div className="card-header">
      <span>Activity Log</span>
      <span className="card-tag card-tag-gold">RECENT</span>
    </div>
    <div className="card-body">
      <p style={{ fontSize: 12, color: "var(--dim)" }}>
        Move history will appear here.
      </p>
        {history.map((entry, index) => (
            <div key={index} className="log-entry">
            <p>{findNewTile(history[index - 1]?.data, entry.data)}</p>
        </div>
        ))}
    </div>
  </div>;
}

function findNewTile(oldState, newState) {
  const oldTiles = oldState?.board || {};
  const newTiles = newState?.board || {};
    for (const key in newTiles) {
        if (!oldTiles[key]) {
            console.log("New tile placed at:", key, "with data:", newState.board[key]);
        }
    }
    return null;
}

