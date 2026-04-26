import { resetGame } from "../api/api";

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
          Winner: <span style={{ color: winners[0].colour }}>{winners[0].colour}</span> — {topScore} points
        </h2>
      ) : (
        <h2>
          Tie between {winners.map((w) => w.colour).join(", ")} — {topScore} points
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
              <td style={{ color: p.colour }}>{p.colour}</td>
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
