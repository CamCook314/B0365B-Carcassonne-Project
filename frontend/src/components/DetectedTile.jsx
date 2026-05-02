import { overridePendingTile } from "../api/api.js";


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
    return (
        <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center" }}>
            {pendingTileList.map((tileId, index) => (
                <button
                    key={index}
                    onClick={() => overridePendingTile(tileId)}
                    style={{
                        padding: "1px 1px",
                        background: "none",
                        color: "var(--bg)",
                        width: 50,
                        height: 50,
                        border: "none",
                        cursor: "pointer",
                    }}
                >
                    <img
                        src={`/tiles/ID${tileId*4}.jpg`}
                        alt={tileId}
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                        //onError={(e) => { e.target.style.display = "none"; }}
                        onError={(e) => { console.error(`Error loading tile: ${tileId}`); e.target.style.display = "none"; }}
                    />
                </button>
            ))}
        </div>
    );
}