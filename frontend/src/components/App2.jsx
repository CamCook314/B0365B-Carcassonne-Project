import { useState, useEffect } from "react";
import { getGameState, startGame, getHistory } from "../api/api";
import { POLLING_INTERVAL } from "../constants/config";
import { useGameState } from "../hooks/useGameState";
import { useSoundEffect } from "../hooks/useSoundEffect";
import "../css/App2.css";
import LandingPage from "./LandingPage";
import LoadingScreen from "./LoadingScreen";
import EndScreen from "./EndScreen";
import Grid from "./Grid";
import Header from "./Header";

export default function App2() {
  const { play } = useSoundEffect();
  const { gameState, loading, error, setError, retry: fetchState, immediateFetch, history } = useGameState(play);
  

  // start a new game
  const handleStart = async (numPlayers) => {
    try {
      await startGame(numPlayers);
      await fetchState();
      play('gameStart');
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
  const gameOver = gameState?.game_over || false;

  // Pending tile from CV (via API)
  const pendingTile = gameState?.pending_tile || null;
  const validPlacements = gameState?.pending_valid || [];
  const pendingTileList = gameState?.pending_candidates || [];

  // Pending placement awaiting a meeple decision
  const pendingPlacement = gameState?.pending_placement || null;

  // Active events (extra turn, volcano, unrest) for the events panel
  const activeEvents = gameState?.active_events || [];
  // Events stay locked until all 12 river tiles are placed.
  const eventsUnlocked = gameState?.events_unlocked || false;
  const riverTilesPlaced = gameState?.river_tiles_placed || 0;

  if (!loading && !gameState) {
    return <LandingPage error={error} handleStart={handleStart} />;
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
        meeples={meeples}
        validPlacements={validPlacements}
        remaining={remaining}
        currentTurn={currentTurn}
        pendingTile={pendingTile}
        pendingTileList={pendingTileList}
        pendingPlacement={pendingPlacement}
        activeEvents={activeEvents}
        eventsUnlocked={eventsUnlocked}
        riverTilesPlaced={riverTilesPlaced}
        history={history}
        refresh={async () => {
          await immediateFetch();
          console.log("Refreshed game state");
        }}
      />
    </div>
  );
}