/**
 * LoadingScreen — minimal full-screen loading state displayed while the
 * initial game state is being fetched from the backend.
 */
export default function LoadingScreen() {
  return <div className="app">
    <p
      style={{ textAlign: "center", marginTop: 80, color: "var(--dim)" }}
    >
      Connecting to game engine...
    </p>
  </div>;
}