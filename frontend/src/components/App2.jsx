import { useState, useEffect } from "react";
import { getGameState, startGame } from "../api/api";
import { POLLING_INTERVAL } from "../constants/config";
import { useGameState } from "../hooks/useGameState";
import "../css/App2.css";
import EntryScreen from "./EntryScreen";
import LoadingScreen from "./LoadingScreen";
import Grid from "./Grid";
import Header from "./Header";

export default function App2() {
  const [gameState, setGameState] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch game state from API
  const fetchState = async () => {
    try {
      const data = await getGameState();
      setGameState(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      setGameState(null);
    } finally {
      setLoading(false);
    }
  };

  // start a new game
  const handleStart = async (numPlayers) => {
    try {
      await startGame(numPlayers);
      await fetchState();
    } catch (err) {
      setError(err.message);
    }
  };

  // start fetching on mount
  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, POLLING_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  // convert API board data to array for GameBoard
  const boardTiles = gameState
    ? Object.entries(gameState.board).map(([key, tile]) => {
        const [col, row] = key.split(",").map(Number);
        return {
          col,
          row,
          tileId: tile.tile_id,
          attribute: tile.attribute,
          meeple_attached: tile.meeple_attached,
        };
      })
    : [];

  const players = gameState?.players || [];
  const currentTurn = gameState?.current_turn || 0;
  const currentPlayer = gameState?.current_player || 0;
  const remaining = gameState?.remaining_pieces || 0;

  // Pending tile from CV (via API)
  const pendingTile = gameState?.pending_tile || null;
  const validPlacements = gameState?.pending_valid || [];

  // entry screens for picking player numbers for api
  if (!loading && !gameState) {
    return <EntryScreen error={error} handleStart={handleStart} />;
  }

  // loading
  if (loading) {
    return <LoadingScreen/>;
  }

  // Game running
  return (
    <div className="app">
      {/* Header */}
      <Header currentTurn={currentTurn} boardTiles={boardTiles} remaining={remaining} />

      <Grid
        currentPlayer={currentPlayer}
        players={players}
        boardTiles={boardTiles}
        validPlacements={validPlacements}
        remaining={remaining}
        currentTurn={currentTurn}
        pendingTile={pendingTile}
      />
    </div>
  );
}