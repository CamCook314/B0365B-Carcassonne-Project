import { getHistory } from "../api/api";

const COLOUR_EMOJI = {
  red: "🟥", blue: "🟦", green: "🟩", yellow: "🟨", black: "🟪",
};
const COLOUR_EMOJI_MEEPLE = {
  red: "🔴", blue: "🔵", green: "🟢", yellow: "🟡", black: "🟣",
};

let historyLength = 0;

export function ActivityLog( { history, players = [] }) {
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
                    <p>{`${colourEmoji(newTiles[index]?.current_player, players)} placed `}</p>
                    <img style={{width: 30, height: 30, display: "inline-block", verticalAlign: "middle"}} src={`/tiles/${newTiles[index]?.tile_id}.jpg`} alt={newTiles[index]?.tile_id} />
                    <p>{` at (${newTiles[index]?.position}) ${newTiles[index]?.meeple_attached ? colourEmojiMeeple(newTiles[index]?.current_player, players) : ''}`}</p>
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

function colourEmoji(playerIndex, players) {
    const colour = players[playerIndex]?.colour;
    return COLOUR_EMOJI[colour] ?? "⬜";
}

function colourEmojiMeeple(playerIndex, players) {
    const colour = players[playerIndex]?.colour;
    return COLOUR_EMOJI_MEEPLE[colour] ?? "⚪";
}
