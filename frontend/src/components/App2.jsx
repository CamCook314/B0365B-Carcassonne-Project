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
  const { gameState, loading, error, retry: fetchState } = useGameState();

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
          meeple: tile.meeple,
        };
      })
    : [];

  // Build a flat meeples list for the GameBoard
  const meeples = boardTiles
    .filter((t) => t.meeple)
    .map((t) => ({
      col: t.col,
      row: t.row,
      side: t.meeple.side,
      playerIndex: t.meeple.player_index,
    }));

  const players = gameState?.players || [];
  const currentTurn = gameState?.current_turn || 0;
  const currentPlayer = gameState?.current_player || 0;
  const remaining = gameState?.remaining_pieces || 0;

  // Pending tile from CV (via API)
  const pendingTile = gameState?.pending_tile || null;
  const validPlacements = gameState?.pending_valid || [];
  const pendingTileList = gameState?.pending_candidates || [];

  // Pending placement awaiting a meeple decision
  const pendingPlacement = gameState?.pending_placement || null;

  if (!loading && !gameState) {
    return <EntryScreen error={error} handleStart={handleStart} />;
  }

  // loading
  if (loading) {
    return <LoadingScreen/>;
  }

  return (
    <div className="app">
      {/* Header */}
      <Header currentTurn={currentTurn} boardTiles={boardTiles} remaining={remaining} />

      <Grid
        currentPlayer={currentPlayer}
        players={players}
        boardTiles={boardTiles}
        meeples={meeples}
        validPlacements={validPlacements}
        remaining={remaining}
        currentTurn={currentTurn}
        pendingTile={pendingTile}
        pendingTileList={pendingTileList}
        pendingPlacement={pendingPlacement}
      />
    </div>
  );
}