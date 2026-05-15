import { overridePendingTile } from "../api/api.js";
import { useGameState } from "../hooks/useGameState";
import { useState } from "react";

/**
 * DetectedTile displays the tile currently detected by computer vision,
 * along with its valid board placements and a list of candidate tiles
 * the user can manually select as an override.
 *
 * @param {string|null} pendingTile - ID of the currently detected tile, or null if none detected.
 * @param {Array<[number, number]>} validPlacements - Array of [x, y] coordinates where the tile can legally be placed.
 * @param {string[]} pendingTileList - Ordered list of candidate tile IDs suggested by CV.
 * @param {function} refresh - Callback to re-fetch game state after an override is applied.
 */
export default function DetectedTile({ pendingTile, validPlacements, pendingTileList, refresh }) {
  return <div className="card card-detect">
    <div className="card-header">
      <span>Detected Tile</span>
      {/* green tag when CV has detected a tile plain tag while still waiting */}
      <span
        className={`card-tag ${pendingTile ? "card-tag-green" : ""}`}
      >
        {pendingTile ? "DETECTED" : "WAITING"}
      </span>
    </div>
    <CardBody
        pendingTile={pendingTile}
        validPlacements={validPlacements}
        pendingTileList={pendingTileList}
        refresh={refresh} />
  </div>;
}

/**
 * CardBody renders the main content area of the DetectedTile card.
 * Shows the tile image and placement count when a tile is detected;
 * otherwise shows a placeholder waiting state.
 *
 * @param {string|null} pendingTile - ID of the currently detected tile.
 * @param {Array<[number, number]>} validPlacements - Legal [x, y] placements for the tile.
 * @param {string[]} pendingTileList - Candidate tile IDs for manual override.
 * @param {function} refresh - Callback to refresh state after an override.
 */
function CardBody({ pendingTile, validPlacements, pendingTileList, refresh }) {
    return <div className="card-body" style={{ textAlign: "center" }}>
        {pendingTile ? (
            <>
                {/* use image for tile preview */}
                <div className="tile-preview">
                    <img
                        src={`/tiles/${pendingTile}.jpg`}
                        alt={pendingTile}
                        style={{
                            width: "100%",
                            height: "100%",
                            borderRadius: 4,
                            objectFit: "cover",
                        }}
                        onError={(e) => {
                            e.target.style.display = "none";
                        } } />
                </div>

                {/* Human-readable tile ID label */}
                <div className="tile-name">
                    <p>{pendingTile}</p>
                </div>

                {/* Deduplicated placement count — multiple rotations can share the same (x, y) */}
                <div
                    style={{
                        fontSize: 11,
                        color: "var(--green)",
                        marginTop: 4,
                    }}
                >
                    {new Set(validPlacements.map(([x, y]) => `${x},${y}`)).size} valid placement
                    {new Set(validPlacements.map(([x, y]) => `${x},${y}`)).size !== 1 ? "s" : ""}
                </div>

                {/* Manual override controls and CV candidate list */}
                <TileCandidates pendingTileList={pendingTileList} refresh={refresh} />
            </>
        ) : (
            // fallback view shown before the CV has detected anything
            <>
                <div className="tile-preview">—</div>
                <div className="tile-name"><p>Waiting for CV...</p></div>
            </>
        )}
    </div>;
}

/**
 * TileCandidates lets the user manually override the detected tile, either
 * by typing a tile ID/number or clicking a thumbnail from the CV candidate list.
 * Overrides are sent to the server immediately and trigger a state refresh.
 *
 * @param {string[]} pendingTileList - Ordered list of candidate tile IDs from CV.
 * @param {function} refresh - Callback to refresh game state after an override.
 */
function TileCandidates({ pendingTileList, refresh }) {
    // local state for the manual override input and any validation error message
    const [manualInput, setManualInput] = useState("");
    // Validation error message shown beneath the input when entry is invalid
    const [error, setError] = useState("");

    /**
     * Parses and submits a manually entered tile ID or numeric index.
     * Accepts bare numbers (e.g. "42") or prefixed IDs (e.g. "ID42").
     * Valid range is 0–335 inclusive.
     */
    function submitManual() {
        const raw = manualInput.trim().toUpperCase().replace("ID", "");
        const num = parseInt(raw, 10);
        if (isNaN(num) || num < 0 || num > 335) {
            setError("Enter a number 0–335");
            return;
        }
        setError("");
        setManualInput("");
        overridePendingTile(`${num}`);
        refresh();
    }

    return (
        <div style={{ marginTop: 16 }}>
            {/* Manual override input row — also submits on Enter key */}
            <div style={{
                display: "flex",
                gap: 4,
                marginBottom: 8,
                justifyContent: "center",
                alignItems: "center",
            }}>
                <input
                    type="text"
                    placeholder="ID or number"
                    value={manualInput}
                    onChange={e => { setManualInput(e.target.value); setError(""); }}
                    onKeyDown={e => e.key === "Enter" && submitManual()}
                    style={{
                        width: 110,
                        padding: "3px 6px",
                        fontSize: 12,
                        borderRadius: 4,
                        border: "1px solid var(--border, #555)",
                        background: "var(--bg2, #222)",
                        color: "inherit",
                    }}
                />
                <button
                    onClick={submitManual}
                    style={{
                        padding: "3px 8px",
                        fontSize: 12,
                        borderRadius: 4,
                        cursor: "pointer",
                    }}
                >Override</button>
            </div>

            {/* Inline validation error */}
            {error && <div style={{ fontSize: 11, color: "var(--red, #f88)", marginBottom: 6 }}>{error}</div>}

            {/* Scrollable thumbnail grid of CV tile candidates.
                Clicking any thumbnail immediately overrides the pending tile. */}
            <div style={{
                maxHeight: 220,
                overflowY: "auto",
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                justifyContent: "center",
            }}>
                {pendingTileList.map((tileId, index) => (
                    <button
                        key={index}
                        title={tileId}
                        onClick={() => {
                            overridePendingTile(tileId);
                            refresh();
                        }}
                        style={{
                            padding: 0,
                            background: "none",
                            width: 50,
                            height: 50,
                            border: "none",
                            cursor: "pointer",
                            flexShrink: 0,
                        }}
                    >
                        {/* Tile thumbnail — hidden silently if the asset doesn't exist */}
                        <img
                            src={`/tiles/${tileId}.jpg`}
                            alt={tileId}
                            style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: 3 }}
                            onError={(e) => { e.target.style.display = "none"; }}
                        />
                    </button>
                ))}
            </div>
        </div>
    );
}
