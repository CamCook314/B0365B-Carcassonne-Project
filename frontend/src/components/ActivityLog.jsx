import { getHistory } from "../api/api";
import { PLAYER_COLOURS } from "../constants/config";

let historyLength = 0;

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
                    <p>{`${convertPlayerToColour(newTiles[index]?.current_player)} placed `}</p>
                    <img style={{width: 15, height: 15, display: "inline-block"}} src={`/tiles/${newTiles[index]?.tile_id}.jpg`} alt={newTiles[index]?.tile_id} />
                    <p>{` at (${newTiles[index]?.position}) ${newTiles[index]?.meeple_attached ? convertPlayerToColourMeeple(newTiles[index]?.current_player) : ''}`}</p>
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
                tiles.push({ position: key, tile_id: newTiles[key].tile_id, meeple_attached: newTiles[key].meeple_attached, current_player: history[i].data.current_player });
            }
        }
    }
    return tiles;
}

function convertPlayerToColour(playerIndex) {
    switch (playerIndex) {
        case 0:
            return "🟥"
        case 1:
            return "🟦"
        case 2:
            return "🟩"
        case 3:
            return "🟨"
        case 4:
            return "🟪"
    }
}

function convertPlayerToColourMeeple(playerIndex) {
    switch (playerIndex) {
        case 0:
            return "🔴"
        case 1:
            return "🔵"
        case 2:
            return "🟢"
        case 3:
            return "🟡"
        case 4:
            return "🟣"
    }
}
