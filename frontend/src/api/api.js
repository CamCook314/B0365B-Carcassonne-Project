const BASE_URL = "http://127.0.0.1:1234";

let history = ["starting history..."];
let lastState = null;

function addToHistory(endpoint, data) {
  if (endpoint === "/gamestate" && JSON.stringify(data) === JSON.stringify(lastState)) {
    return; // skip identical gamestate entries
  }
  history.push({ endpoint, data });
  lastState = data;
}

export function getHistory() {
  return history;
}

export function setHistory(newHistory) {
  history = newHistory;
}

export async function getGameState() {
  const res = await fetch(`${BASE_URL}/gamestate`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to fetch game state");
  }
  const data = await res.json();
  addToHistory("/gamestate", data);
  
  return data;
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
  const data = await res.json();
  addToHistory("/start", data);
  return data;
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
  const data = await res.json();
  addToHistory("/pending/change", data);
  return data;
}

export async function overridePendingTile(tileId) {
  const res = await fetch(`${BASE_URL}/pending/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tile_id: tileId }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to override pending tile");
  }
  const data = await res.json();
  addToHistory("/pending/override", data);
  return data;
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
  const data = await res.json();
  addToHistory("/pending/list", data);
  return data;
}

export async function setMeeple(row, col, side) {
  const res = await fetch(`${BASE_URL}/meeple`, {method: "POST"});
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to set meeple");
  }
  const data = await res.json();
  addToHistory("/meeple", data);
  return data;
}


export async function resetGame() {
  const res = await fetch(`${BASE_URL}/reset`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to reset game");
  }
  const data = await res.json();
  setHistory([]); // clear history on reset
  return data;
}

