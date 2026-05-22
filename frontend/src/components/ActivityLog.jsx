/**
 * ActivityLog — scrollable card showing recent tile placements.
 * Diffs consecutive game history snapshots to detect newly placed tiles,
 * then renders each as a row with the placing player's colour emoji, a tile
 * thumbnail, its board position, and a meeple indicator if one was placed.
 */
import { getHistory } from "../api/api";
import { PLAYER_COLOURS } from "../constants/config";

let historyLength = 0;

export function ActivityLog( { history }) {
    if (!history || history.length === 0) {
        return (
            <div className="card card-log">
                <div className="card-header">
                    <span>Activity Log</span>
                    <span className="card-tag card-tag-gold">RECENT</span>
                </div>
                <div className="card-body">
                    <p style={{ color: "var(--dim)" }}>Move history will appear here</p>
                </div>
            </div>
        );
    }
  // filter history to remove meeple placement states
  const completeTurns = history.filter(entry => entry.data.pending_placement === null);
  const newHistory = [...completeTurns].reverse();
  const newTiles = findNewTiles(history);
  newTiles.reverse().slice(0, 6);
  return <div className="card card-log">
    <div className="card-header">
      <span>Activity Log</span>
      <span className="card-tag card-tag-gold">RECENT</span>
    </div>
    <div className="card-body" style={{ maxHeight: "200px", overflowY: "auto" }}>
            {newTiles ? newTiles.map((entry, index) => (
                <div key={index} className="log-entry">
                    <p>{`${convertPlayerToColour(newTiles[index]?.current_player)} placed `}</p>
                    <img style={{width: 30, height: 30, display: "inline-block", verticalAlign: "middle"}} src={`/tiles/${newTiles[index]?.tile_id}.jpg`} alt={newTiles[index]?.tile_id} />
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
        const firstKey = Object.keys(board)[0];
        if (firstKey && board[firstKey]) {
            tiles.push({ position: firstKey, tile_id: board[firstKey].tile_id });
        }
        return tiles;
    }
    for (let i = 1; i < history.length; i++) {
        const oldTiles = history[i - 1].data.board || {};
        const newTiles = history[i].data.board || {};
        for (const key in newTiles) {
            if (!oldTiles[key]) {
              const current_player = history[i-1].data.current_player; // player who made the move is the current player in the previous state
                tiles.push({ position: key, tile_id: newTiles[key].tile_id, meeple_attached: newTiles[key].meeple_attached, current_player: current_player });
            }
        }
    }
    return tiles;
}

function convertPlayerToColour(playerIndex) {
    switch (playerIndex) {
        case 0:
            return "🟨"
        case 1:
            return "🟦"
        case 2:
            return "🟩"
        case 3:
            return "🟥"
        case 4:
            return "🟪"
    }
}

export function convertPlayerToColourMeeple(playerIndex) {
    switch (playerIndex) {
        case 0:
            return "🟡"
        case 1:
            return "🔵"
        case 2:
            return "🟢"
        case 3:
            return "🔴"
        case 4:
            return "🟣"
    }
}
