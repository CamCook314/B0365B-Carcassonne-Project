/**
 * EndScreen — full-screen end-of-game results view. Ranks players by score,
 * declares the winner (or tie), shows a scoreboard table, and provides a
 * Play Again button that resets the game and returns to the entry screen.
 */
import { resetGame } from "../api/api";

// Map server-side colour names to the readable hex from PLAYER_COLOURS in
// constants/config.js. CSS named colours like "blue" and "black" are too
// dark against the navy background.
const COLOUR_HEX = {
  red:    "#BF616A",
  blue:   "#81A1C1",
  green:  "#A3BE8C",
  yellow: "#EBCB8B",
  black:  "#4C566A",
};

function colourFor(name) {
  return COLOUR_HEX[name] || "var(--text)";
}

export default function EndScreen({ players, onReset }) {
  const ranked = [...players].sort((a, b) => b.score - a.score);
  const topScore = ranked[0]?.score ?? 0;
  const winners = ranked.filter((p) => p.score === topScore);

  const handlePlayAgain = async () => {
    try {
      await resetGame();
      if (onReset) await onReset();
    } catch (err) {
      console.error("Failed to reset:", err);
    }
  };

  return (
    <div className="end-screen">
      <h1>Game Over</h1>

      {winners.length === 1 ? (
        <h2>
          Winner: <span style={{ color: colourFor(winners[0].colour) }}>{winners[0].colour}</span>, {topScore} points
        </h2>
      ) : (
        <h2>
          Tie between {winners.map((w) => w.colour).join(", ")}, {topScore} points
        </h2>
      )}

      <table className="scoreboard">
        <thead>
          <tr>
            <th>Place</th>
            <th>Player</th>
            <th>Score</th>
            <th>Meeples Left</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((p, i) => (
            <tr key={p.colour}>
              <td>{i + 1}</td>
              <td style={{ color: colourFor(p.colour) }}>{p.colour}</td>
              <td>{p.score}</td>
              <td>{p.meeples}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <button onClick={handlePlayAgain}>Play Again</button>
    </div>
  );
}
