/**
 * EntryScreen — fallback screen shown when no game is running and the
 * LandingPage is not in use. Offers 2–5 player start buttons and surfaces
 * any API connection errors.
 */
export default function EntryScreen({ error, handleStart }) {
  return <div className="app">
    <header className="header">
      <h1>
        Carcassonne<span> AR</span>
      </h1>
    </header>
    <div style={{ textAlign: "center", marginTop: 80 }}>
      <h2 style={{ marginBottom: 16, color: "var(--text)" }}>
        No Game Running
      </h2>
      <p style={{ color: "var(--dim)", marginBottom: 24 }}>
        {error === "Game not started"
          ? "Start a new game to begin."
          : `API error: ${error}. Is the backend running?`}
      </p>
      <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
        {[2, 3, 4, 5].map((n) => (
          <button
            key={n}
            onClick={() => handleStart(n)}
            style={{
              padding: "10px 24px",
              background: "var(--accent)",
              color: "var(--bg)",
              border: "none",
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {n} Players
          </button>
        ))}
      </div>
    </div>
  </div>;
}