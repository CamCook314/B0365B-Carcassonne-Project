import { overridePendingTile } from "../api/api.js";
import { useGameState } from "../hooks/useGameState";

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
                    {validPlacements.length} valid placement
                    {validPlacements.length !== 1 ? "s" : ""}
                </div>
                <TileCandidates pendingTileList={pendingTileList} refresh={refresh} />
            </>
        ) : (
            <>
                <div className="tile-preview">—</div>
                <div className="tile-name">Waiting for CV...</div>
            </>
        )}
    </div>; 
}

function TileCandidates({ pendingTileList, refresh }) {
    return (
        <div style={{
            marginTop: 16,
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
                        src={`/tiles/${tileId}.jpg`}
                        alt={tileId}
                        style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: 3 }}
                        onError={(e) => { e.target.style.display = "none"; }}
                    />
                </button>
            ))}
        </div>
    );
}