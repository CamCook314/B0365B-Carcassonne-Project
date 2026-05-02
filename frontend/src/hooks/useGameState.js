import { useState, useCallback, useEffect, useRef } from 'react';
import { getGameState } from '../api/api.js';
import { POLLING_INTERVAL } from '../constants/config.js';



export function useGameState() {
  const [gameState, setGameState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const pollingRef = useRef(null);

  const fetchState = useCallback(async () => {
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
  }, []);


  const immediateFetch = useCallback(async () => {
    clearInterval(pollingRef.current);
    pollingRef.current = null;
    await fetchState();
  }, [fetchState]);

  useEffect(() => {
    fetchState();
    pollingRef.current = setInterval(fetchState, POLLING_INTERVAL);
    return () => clearInterval(pollingRef.current);
  }, [fetchState]);

  return { gameState, loading, error, retry: fetchState, immediateFetch };
}

