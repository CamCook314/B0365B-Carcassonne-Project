export default function DetectedTile({ pendingTile, validPlacements }) {
  return <div className="card card-detect">
    <div className="card-header">
      <span>Detected Tile</span>
      <span
        className={`card-tag ${pendingTile ? "card-tag-green" : ""}`}
      >
        {pendingTile ? "DETECTED" : "WAITING"}
      </span>
    </div>
    <div className="card-body" style={{ textAlign: "center" }}>
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
        </>
      ) : (
        <>
          <div className="tile-preview">—</div>
          <div className="tile-name">Waiting for CV...</div>
        </>
      )}
    </div>
  </div>;
}