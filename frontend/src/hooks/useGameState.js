import { useState, useCallback, useEffect, useRef } from 'react';
import Swal from 'sweetalert2';
import { getGameState, getHistory, clearNotification } from '../api/api.js';
import { POLLING_INTERVAL } from '../constants/config.js';

export function useGameState(playSound = null) {
  const [gameState, setGameState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const previousGameStateRef = useRef(null);

  const pollingRef = useRef(null);

  const fetchState = useCallback(async () => {
    try {
      const data = await getGameState();
      const historyData = await getHistory();

      if (playSound && previousGameStateRef.current && data) {
        // check if turn has changed
        if (previousGameStateRef.current.current_player !== data.current_player) {
          playSound('placeMeeple');
        }
      }

      if (data.notification) {
        clearNotification().catch(() => {});
        Swal.fire(data.notification);
      }

      setGameState(data);
      setHistory(historyData);
      setError(null);
      previousGameStateRef.current = data;
    } catch (err) {
      setError(err.message);
      setGameState(null);
    } finally {
      setLoading(false);
    }
  }, [playSound]);


  const immediateFetch = useCallback(async () => {
    clearInterval(pollingRef.current);
    await fetchState();
    pollingRef.current = setInterval(fetchState, POLLING_INTERVAL);
  }, [fetchState]);

  useEffect(() => {
    fetchState();
    pollingRef.current = setInterval(fetchState, POLLING_INTERVAL);
    return () => clearInterval(pollingRef.current);
  }, [fetchState]);



  return { gameState, loading, error, setError, retry: fetchState, immediateFetch, history };
}

