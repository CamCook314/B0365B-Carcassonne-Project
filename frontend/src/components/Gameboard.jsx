/**
 * Gameboard — zoomable, pannable board rendering component.
 * Converts tile coordinate data into pixel positions, draws placed tiles as
 * images, overlays colour-coded meeple dots by side, and shows "+" ghost
 * markers at valid placement positions. Ghost markers are clickable when a
 * pending tile is detected, triggering a force-place. Right-click on any
 * placed tile rotates it via the API.
 */
import { useState, useMemo } from "react";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import { rotateTile, forcePlace } from "../api/api";
import "../css/Gameboard.css";

const PLAYER_COLORS = ["#BF616A", "#81A1C1", "#A3BE8C", "#EBCB8B", "#B48EAD"];
const CELL = 52; // tile size + gap

export default function GameBoard({ tiles = [], meeples = [], validPlacements = [], onTileClick, refresh, pendingTile = null }) {
  const [selectedTile, setSelectedTile] = useState(null);

  // work out the board bounds and convert tile and ghost grid coords into pixel positions
  const { placedTiles, ghostTiles, width, height } = useMemo(() => {
    const allCols = [...tiles.map(t => t.col), ...validPlacements.map(v => v[0])];
    const allRows = [...tiles.map(t => t.row), ...validPlacements.map(v => v[1])];

    if (!allCols.length) return { placedTiles: [], ghostTiles: [], width: 0, height: 0 };

    const minCol = Math.min(...allCols);
    const maxCol = Math.max(...allCols);
    const minRow = Math.min(...allRows);
    const maxRow = Math.max(...allRows);

    // flip the row axis so higher row values render upward like a normal grid
    const px = (col, row) => ({ left: (col - minCol) * CELL, top: (maxRow - row) * CELL });

    return {
      placedTiles: tiles.map(t => ({ ...t, ...px(t.col, t.row) })),
      ghostTiles: validPlacements.map(([x, y]) => ({ col: x, row: y, ...px(x, y) })),
      width: (maxCol - minCol + 1) * CELL,
      height: (maxRow - minRow + 1) * CELL,
    };
  }, [tiles, validPlacements]);

  // group meeples by tile position so each tile can look up its own meeples quickly
  const meepleLookup = useMemo(() => {
    const map = {};
    for (const m of meeples) {
      const key = `${m.col},${m.row}`;
      if (!map[key]) map[key] = [];
      map[key].push(m);
    }
    return map;
  }, [meeples]);

  // toggle selection clicking the same tile twice deselects it
  const handleClick = (tile) => {
    setSelectedTile(prev =>
      prev && prev.col === tile.col && prev.row === tile.row ? null : tile
    );
    onTileClick?.(tile);
    console.log("meeples: ", meeples);
  };

  const handleGhostClick = async (col, row) => {
    if (!pendingTile) return;
    try {
      await forcePlace(col, row);
      console.log(`Force placed at (${col}, ${row})`);
      refresh?.();
    } catch (err) {
      console.error("Force place failed:", err);
      alert("Could not force place: " + err.message);
    }
  };

  const handleContextMenu = (tile, event) => {
    event.preventDefault(); // prevent default right-click menu
    console.log("Right-clicked tile:", tile);
    const rotateLog = rotateTile(tile.col, tile.row)
      .then(updatedTile => {
        console.log("Tile rotated:", updatedTile);
      })
      .catch(err => {
        console.error("Failed to rotate tile:", err);
        alert("Failed to rotate tile: " + err.message);
      });
      refresh();
  }

  return (
    <div className="card card-board" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
      <div className="card-header">
        <span>Board State</span>
        <span className="card-tag">{tiles.length} TILES</span>
      </div>

      <div className="board-wrap">
        <TransformWrapper initialScale={1.5} minScale={1} maxScale={3} centerOnInit wheel={{ step: 0.01 }} panning={{ velocityDisabled: true }}>
          {({ zoomIn, zoomOut, resetTransform }) => (
            <>
              <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }} contentStyle={{ width, height, position: "relative" }}>

                {/* Ghost tiles to show valid placements */}
                {ghostTiles.map(g => (
                  <div
                    key={`g-${g.col},${g.row}`}
                    className={`tile tile-ghost${pendingTile ? " tile-ghost-clickable" : ""}`}
                    style={{ left: g.left, top: g.top, cursor: pendingTile ? "pointer" : "default" }}
                    title={pendingTile ? `Place here: (${g.col}, ${g.row})` : `Valid: (${g.col}, ${g.row})`}
                    onClick={pendingTile ? () => handleGhostClick(g.col, g.row) : undefined}
                  >
                    <span className="ghost-plus">+</span>
                  </div>
                ))}

                {/* Placed tiles */}
                {placedTiles.map(t => (
                  <div
                    key={`${t.col},${t.row}`}
                    className={`tile${selectedTile?.col === t.col && selectedTile?.row === t.row ? " tile-selected" : ""}`}
                    style={{ left: t.left, top: t.top }}
                    title={`${t.tileId} (${t.col}, ${t.row})`}
                    onClick={e => { e.stopPropagation(); handleClick(t); }}
                    onContextMenu={e => handleContextMenu(t, e)}
                  >
                    {t.tileId ? (
                      <img src={`/tiles/${t.tileId}.jpg`} alt={t.tileId} draggable={false}
                        style={{ width: "100%", height: "100%", borderRadius: 3, objectFit: "cover" }}

                        // if the tile image fails to load, fall back to showing the ID as text
                        onError={e => { e.target.style.display = "none"; e.target.parentElement.textContent = t.tileId; }}
                      />
                    ) : <span style={{ fontSize: 11, color: "var(--dim)" }}>?</span>}

                    {/* render each meeple on this tile, positioned by side */}
                    {(meepleLookup[`${t.col},${t.row}`] || []).map((m, i) => (
                      <div key={i} className={`meeple meeple-${m.side || "centre"}`} style={{ background: PLAYER_COLORS[m.playerIndex] || "#888" }} />
                    ))}
                  </div>
                ))}

              </TransformComponent>

              <div className="board-controls">
                <button className="board-btn" onClick={() => zoomIn()}>+</button>
                <button className="board-btn" onClick={() => zoomOut()}>−</button>
                <button className="board-btn" onClick={() => resetTransform()}>⌂</button>
              </div>
              <div className="board-info">{tiles.length} tiles</div>
            </>
          )}
        </TransformWrapper>

        {selectedTile && (
          <div className="tile-popup">
            <div className="tile-popup-header">
              <span>TILE INFO</span>
              <button className="tile-popup-close" onClick={() => setSelectedTile(null)}>×</button>
            </div>
            <div className="tile-popup-body">
              <div><strong>ID:</strong> {selectedTile.tileId}</div>
              <div><strong>Pos:</strong> ({selectedTile.col}, {selectedTile.row})</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}