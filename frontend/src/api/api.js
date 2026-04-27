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

export async function setPendingTile(tileId) {
  const res = await fetch(`${BASE_URL}/pending/change`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_tile: tileId }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to set pending tile");
  }
  return res.json();
}


export async function setPendingTileList(tileIds) {
  const res = await fetch(`${BASE_URL}/pending/list`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tile_ids: tileIds }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to fetch tile list");
  }
  return res.json();
}

export async function placeMeeple(direction) {
  const res = await fetch(`${BASE_URL}/meeple`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ direction }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `meeple failed (${res.status})`);
  }
  return res.json();
}

export async function skipMeeple() {
  const res = await fetch(`${BASE_URL}/meeple/skip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `meeple/skip failed (${res.status})`);
  }
  return res.json();
}

