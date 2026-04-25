import { useState } from "react";
import { setPendingTile } from "../api/api.js";


export default function DetectedTile({ pendingTile, validPlacements, pendingTileList }) {
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
        pendingTileList={pendingTileList} />
  </div>;
}

function CardBody({ pendingTile, validPlacements, pendingTileList }) {
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
                <div className="tile-name">{pendingTile}</div>
                <div
                    style={{
                        fontSize: 11,
                        color: "var(--green)",
                        marginTop: 4,
                    }}
                >
                    {validPlacements.length} valid placement
                    {validPlacements.length !== 1 ? "s" : ""}
                </div>
                <TileCandidates pendingTileList={pendingTileList} />
            </>
        ) : (
            <>
                <div className="tile-preview">—</div>
                <div className="tile-name">Waiting for CV...</div>
            </>
        )}
    </div>; 
}

function TileCandidates({ pendingTileList }) {
    // unused?
    const [pendingInput, setPendingInput] = useState(0);
    
    return (
        <div style={{ marginTop: 16, display: "flex", gap: 8, justifyContent: "center" }}>
            { /* iterate through ids for each button */ }
            {pendingTileList.map((tileId, index) => (
                <button
                key={index}
                onClick={() => setPendingTile(Number(tileId))}
                style={{
                padding: "1px 1px",
                background: "none",
                color: "var(--bg)",
                width: 50,
                height: 50
                }}>
                <img
                    src={`/tiles/ID${tileId*4}.jpg`}
                    alt={`ID${tileId*4}.jpg`}
                    style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                    }}
                />
        </button> 
      ))}
    </div>
)}