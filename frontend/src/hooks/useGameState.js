import { useState, useCallback, useEffect } from 'react';
import { getGameState } from '../api/api.js';

export function useGameState() {
  const [gameData, setGameData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchState = useCallback(async () => {
    try {
      const data = await getGameState();
      setGameData(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      setGameData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, POLLING_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchState]);

  return { gameData, loading, error, retry: fetchState };
}