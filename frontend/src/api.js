// frontend/src/api.js
// Drop this file into frontend/src/ next to your App.jsx

const BASE_URL = "http://127.0.0.1:1234";

// GET /gamestate - fetches current board, players, turn info
export async function getGameState() {
  const res = await fetch(`${BASE_URL}/gamestate`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to fetch game state");
  }
  return res.json();
}

// POST /start - starts a new game with n players
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

// POST /place - places a tile (you'll need to add this endpoint to api.py)
export async function placeTile(tileId, x, y) {
  const res = await fetch(`${BASE_URL}/place`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tile_id: tileId, x, y }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to place tile");
  }
  return res.json();
}

// GET /valid-placements?tile_id=ID0 - gets valid spots for a tile
export async function getValidPlacements(tileId) {
  const res = await fetch(`${BASE_URL}/valid-placements?tile_id=${tileId}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to get valid placements");
  }
  return res.json();
}