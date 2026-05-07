import { overridePendingTile } from "../api/api.js";
import { useGameState } from "../hooks/useGameState";
import { useState } from "react";

export default function DetectedTile({ pendingTile, validPlacements, pendingTileList, refresh }) {
  return <div className="card card-detect">
    <div className="card-header">
      <span>Detected Tile</span>
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

function CardBody({ pendingTile, validPlacements, pendingTileList, refresh }) {
    return <div className="card-body" style={{ textAlign: "center" }}>
        {pendingTile ? (
            <>
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
                <div className="tile-name">
                    <p>{pendingTile}</p>
                    </div>
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
                <TileCandidates pendingTileList={pendingTileList} refresh={refresh} />
            </>
        ) : (
            <>
                <div className="tile-preview">—</div>
                <div className="tile-name"><p>Waiting for CV...</p></div>
            </>
        )}
    </div>; 
}

function TileCandidates({ pendingTileList, refresh }) {
    const [manualInput, setManualInput] = useState("");
    const [error, setError] = useState("");

    function submitManual() {
        const raw = manualInput.trim().toUpperCase().replace("ID", "");
        const num = parseInt(raw, 10);
        if (isNaN(num) || num < 0 || num > 335) {
            setError("Enter a number 0–335");
            return;
        }
        setError("");
        setManualInput("");
        overridePendingTile(`ID${num}`);
        refresh();
    }

    return (
        <div style={{ marginTop: 16 }}>
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
            {error && <div style={{ fontSize: 11, color: "var(--red, #f88)", marginBottom: 6 }}>{error}</div>}
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
                        <img
                            src={`/tiles/ID${tileId}.jpg`}
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