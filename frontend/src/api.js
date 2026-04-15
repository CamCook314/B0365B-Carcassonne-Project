const BASE_URL = "http://127.0.0.1:1234";

export async function getGameState() {
  const res = await fetch(`${BASE_URL}/gamestate`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to fetch game state");
  }
  return res.json();
}

export async function startGame(numPlayers) {
  const res = await fetch(`${BASE_URL}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ players: numPlayers }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to start game");
  }
  return res.json();
}

