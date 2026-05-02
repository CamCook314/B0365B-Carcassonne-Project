import { useState, useEffect } from "react";
import { getGameState, startGame } from "../api/api";
import { POLLING_INTERVAL } from "../constants/config";
import { useGameState } from "../hooks/useGameState";
import "../css/App2.css";
import EntryScreen from "./EntryScreen";
import LoadingScreen from "./LoadingScreen";
import EndScreen from "./EndScreen";
import Grid from "./Grid";
import Header from "./Header";

export default function App2() {
  const { gameState, loading, error, retry: fetchState, immediateFetch } = useGameState();

  // start a new game
  const handleStart = async (numPlayers) => {
    try {
      await startGame(numPlayers);
      await fetchState();
    } catch (err) {
      setError(err.message);
    }
  };

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
  const gameOver = gameState?.game_over || false;

  // Pending tile from CV (via API)
  const pendingTile = gameState?.pending_tile || null;
  const validPlacements = gameState?.pending_valid || [];
  const pendingTileList = gameState?.pending_candidates || [];

  // entry screens for picking player numbers for api
  if (!loading && !gameState) {
    return <EntryScreen error={error} handleStart={handleStart} />;
  }

  // loading
  if (loading) {
    return <LoadingScreen/>;
  }

  // Game finished — show final scores
  if (gameOver) {
    return <EndScreen players={players} onReset={fetchState} />;
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
        pendingTileList={pendingTileList}
        refresh={async () => {
          await immediateFetch();
          console.log("Refreshed game state");
        }}
      />
    </div>
  );
}