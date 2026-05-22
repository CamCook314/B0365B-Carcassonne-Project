/**
 * Players — roster card showing each player's colour avatar, meeple icons,
 * and live score. Highlights the active player's row and includes an End Game
 * button that prompts for confirmation via SweetAlert2 before calling endGame().
 */
import { useState } from 'react';
import Swal from 'sweetalert2';
import { PLAYER_COLOUR_MAP } from "../constants/config";
import { endGame } from '../api/api.js';
import { convertPlayerToColourMeeple } from './ActivityLog.jsx'

export default function Players({ currentPlayer, players, refresh }) {
  const [ending, setEnding] = useState(false);

  const handleEndGame = async () => {
    const confirm = await Swal.fire({
      title: 'End Game?',
      text: 'Are you sure you want to end the game? This cannot be undone.',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'End Game',
      cancelButtonText: 'Cancel',
      confirmButtonColor: '#BF616A',
      cancelButtonColor: '#888'
    });

    if (!confirm.isConfirmed) return;

    try {
      setEnding(true);
      const result = await endGame();
      // TODO: calculate scores from leftover structures
      // Find winner based on highest score
      const scores = result.scores;
      const winner = scores.reduce((max, current) => 
        current.score > max.score ? current : max
      );

      // Refresh game state to show end screen
      if (refresh) {
        await refresh();
      }
    } catch (err) {
      Swal.fire({
        title: 'Error',
        text: err.message,
        icon: 'error'
      });
    } finally {
      setEnding(false);
    }
  };

  return <div className="card card-players">
    <div className="card-header">
      <span>Players</span>
      {/* show which player number has the current turn, offset by 1 since index starts at 0 */}
      <span className="card-tag card-tag-blue">
        TURN: P{currentPlayer + 1}
      </span>
    </div>
    <div className="card-body">
      {/* render a row for each player in the game */}
      {players.map((p, i) => (
        <div
          key={i}
          className={`player-row ${i === currentPlayer ? "active" : ""}`}
        >
          <div
            className="player-avatar"
            style={{ background: PLAYER_COLOUR_MAP[p.colour] || "#888" }}
          >
            {p.colour?.[0]?.toUpperCase() || i + 1}
          </div>
          <div>
            <div className="player-name">
              {/* show colour as the player name, fall back to generic Player N */}
              <p style={{ padding: 0, margin: 0 }}>{p.colour || `Player ${i + 1}`}</p>
            </div>
            {/* show how many of the 7 meeples are still available */}
            <Meeples meeples={p.meeples} currentPlayer={i} />
          </div>
          <div
            className="player-score"
            // colour the score text to match the player so its easy to scan
            style={{ color: PLAYER_COLOUR_MAP[p.colour] || "#888" }}
          >
            {p.score}
          </div>
        </div>
      ))}
      <button 
        onClick={handleEndGame}
        disabled={ending}
        style={{
          marginTop: '15px',
          padding: '8px 12px',
          width: '100%',
          backgroundColor: '#BF616A',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          fontSize: '14px',
          fontWeight: 'bold'
        }}
      >
        End Game
      </button>
    </div>
  </div>;
}

function Meeples({ meeples, currentPlayer }) {
  // show number of meeple icons based on remaining meeples
  const meepleIcons = [];
  const meepleIcon = convertPlayerToColourMeeple(currentPlayer);
  for (let i = 0; i < meeples; i++) {
    meepleIcons.push(meepleIcon);
  }

  return <div className="meeple-icons" style={{ fontSize: "10px" }}>
    {meepleIcons.join(" ")}
  </div>;
}
