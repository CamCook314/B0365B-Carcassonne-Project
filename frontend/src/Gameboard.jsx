// GameBoard.jsx
import { useState, useEffect, useCallback } from "react";

export default function GameBoard({ tiles }) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Tile size in pixels
  const ts = 50;

  // Center the board: offset so (0,0) appears roughly in the middle
  // These shift the whole board so tiles aren't jammed in the top-left
  const offsetX = 400;
  const offsetY = 200;

  // --- Pan handlers ---
  const onDown = (e) => {
    if (e.target.closest(".board-btn")) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const onMove = useCallback(
    (e) => {
      if (isDragging) setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    },
    [isDragging, dragStart]
  );

  const onUp = useCallback(() => setIsDragging(false), []);

  useEffect(() => {
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [onMove, onUp]);

  return (
    <div className="card card-board" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
      <div className="card-header">
        <span>Board State</span>
        <span className="card-tag">{tiles.length} TILES</span>
      </div>

      <div className="board-wrap" onMouseDown={onDown}>
        <div
          className="board-canvas"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
          }}
        >
          <div className="board-grid" />

          {tiles.map((t, i) => (
            <div
              key={i}
              className="tile"
              style={{
                left: offsetX + t.col * ts,
                top: offsetY - t.row * ts, // flip Y: game uses y-up, screen uses y-down
              }}
              title={`${t.tileId} (${t.col}, ${t.row})`}
            >
              {t.tileId ? (
                <img
                  src={`/tiles/${t.tileId}.jpg`}
                  alt={t.tileId}
                  style={{
                    width: "100%",
                    height: "100%",
                    borderRadius: 3,
                    objectFit: "cover",
                  }}
                  onError={(e) => {
                    // Fallback if image missing
                    e.target.style.display = "none";
                    e.target.parentElement.textContent = t.tileId;
                  }}
                />
              ) : (
                <span>?</span>
              )}
            </div>
          ))}
        </div>

        {/* Controls */}
        <div className="board-controls">
          <button className="board-btn" onClick={() => setZoom((z) => Math.min(z + 0.15, 2.5))}>+</button>
          <button className="board-btn" onClick={() => setZoom((z) => Math.max(z - 0.15, 0.4))}>−</button>
          <button className="board-btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>⌂</button>
        </div>

        <div className="board-info">
          {(zoom * 100).toFixed(0)}% · {tiles.length} tiles
        </div>
      </div>
    </div>
  );
}