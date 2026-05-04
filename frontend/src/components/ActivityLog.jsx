import { getHistory } from "../api/api";


export function ActivityLog( { history }) {
    if (!history || history.length === 0) {
        return (
            <div className="card card-log">
                <div className="card-header">
                    <span>Activity Log</span>
                    <span className="card-tag card-tag-gold">RECENT 10</span>
                </div>
                <div className="card-body">
                    <p style={{ color: "var(--dim)" }}>Move history will appear here</p>
                </div>
            </div>
        );
    }
  const newHistory = [...history].reverse().slice(0, 5);
  const newTiles = findNewTiles(history);
  newTiles.reverse().slice(0, 6);
  return <div className="card card-log">
    <div className="card-header">
      <span>Activity Log</span>
      <span className="card-tag card-tag-gold">RECENT 10</span>
    </div>
    <div className="card-body">
            {newTiles ? newHistory.map((entry, index) => (
                <div key={index} className="log-entry">
                    <p>Placed </p> 
                    <img style={{width: 15, height: 15, display: "inline-block"}} src={`/tiles/${newTiles[index]?.tile_id}.jpg`} alt={newTiles[index]?.tile_id} />
                    <p>{` at (${newTiles[index]?.position}) ${newTiles[index]?.meeple_attached ? '⚪' : ''}`}</p>
                </div>
        )) : <p style={{ color: "var(--dim)" }}>Move history will appear here</p>}
    </div>
  </div>;
}

function findNewTiles(history) {
    const tiles = [];
    if (history.length < 2) {
        const board = history[0].data.board;
        tiles.push({position: Object.keys(board)[0], tile_id: board[Object.keys(board)[0]].tile_id});
        return tiles;
    }
    for (let i = 1; i < history.length; i++) {
        const oldTiles = history[i - 1].data.board || {};
        const newTiles = history[i].data.board || {};
        for (const key in newTiles) {
            if (!oldTiles[key]) {
                tiles.push({ position: key, tile_id: newTiles[key].tile_id, meeple_attached: newTiles[key].meeple_attached });
            }
        }
    }
    return tiles;
}

