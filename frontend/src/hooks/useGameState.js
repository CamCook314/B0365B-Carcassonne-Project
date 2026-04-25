import { useState, useCallback, useEffect } from 'react';
import { getGameState } from '../api/api.js';
import { POLLING_INTERVAL } from '../constants/config.js';

export function useGameState() {
  const [gameState, setGameState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  


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

  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, POLLING_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchState]);

  return { gameState, loading, error, retry: fetchState };
}