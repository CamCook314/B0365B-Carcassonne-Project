"""
grid_tracker.py — Grid coordinate tracking for the Carcassonne board.

GridTracker owns everything to do with the coordinate system:
  - origin pixel position, tile spacing, and board rotation angle
  - which cells are occupied
  - converting between grid coords and pixel positions
  - scoring candidate placement slots by blob coverage
  - snapshotting / restoring state for invalid-placement rollback

The grid model accounts for board rotation.  If the board is rotated θ degrees
clockwise from horizontal, a tile at grid position (gx, gy) sits at pixel:

    px = origin_x + gx·a + gy·b
    py = origin_y + gx·b − gy·a

where  a = tile_size·cos(θ)  and  b = tile_size·sin(θ).

Both a and b are fitted jointly from all observed tile centroids via least
squares, so rotation is recovered automatically without any explicit angle input.
"""

import cv2 as cv
import numpy as np


class GridTracker:

    def __init__(self, origin_px):
        self.origin_px      = origin_px   # (px, py) — pixel centre of grid (0, 0)
        self.a              = None        # tile_size * cos(θ) — horizontal grid step
        self.b              = None        # tile_size * sin(θ) — rotation component
        self.placed_tiles   = {(0, 0)}    # (gx, gy) for every confirmed placement
        self.tile_centroids = {(0, 0): origin_px}  # grid coord → observed pixel centroid
        self._snapshot      = None        # Saved state for rollback

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def tile_size_px(self):
        """Pixel distance between adjacent tile centres (derived from a and b)."""
        return None if self.a is None else float(np.hypot(self.a, self.b))

    # ── Coordinate conversion ─────────────────────────────────────────────────

    def grid_to_px(self, gx, gy):
        """Grid cell (gx, gy) → pixel centre (x, y), accounting for board rotation."""
        return (
            int(round(self.origin_px[0] + gx * self.a + gy * self.b)),
            int(round(self.origin_px[1] + gx * self.b - gy * self.a)),
        )

    # ── Slot queries ──────────────────────────────────────────────────────────

    def open_slots(self):
        """Grid cells adjacent to any placed tile that are not yet occupied."""
        candidates = set()
        for (gx, gy) in self.placed_tiles:
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nb = (gx + dx, gy + dy)
                if nb not in self.placed_tiles:
                    candidates.add(nb)
        return candidates

    def enclosed_slots(self):
        """Open slots where all 4 neighbours are already placed.

        Used as a last-resort fallback for centre-tile detection, where the
        diff mask is near-empty because morph-close already filled the ring hole.
        """
        return [
            s for s in self.open_slots()
            if all((s[0] + dx, s[1] + dy) in self.placed_tiles
                   for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)])
        ]

    # ── Coverage scoring ──────────────────────────────────────────────────────

    def cell_coverage(self, blob_mask, gx, gy):
        """Count blob pixels inside the expected bounding box of cell (gx, gy)."""
        cx   = int(self.origin_px[0] + gx * self.a + gy * self.b)
        cy   = int(self.origin_px[1] + gx * self.b - gy * self.a)
        half = int(self.tile_size_px * 0.5)
        x1 = max(cx - half, 0)
        y1 = max(cy - half, 0)
        x2 = min(cx + half, blob_mask.shape[1])
        y2 = min(cy + half, blob_mask.shape[0])
        if x2 <= x1 or y2 <= y1:
            return 0
        return cv.countNonZero(blob_mask[y1:y2, x1:x2])

    def best_coverage_slot(self, diff_mask):
        """Return (slot, coverage) for the open slot with the highest diff-pixel coverage.

        Scores every open slot by how many diff pixels fall within its expected
        bounding box.  More robust than centroid detection: a displacement of up
        to ±half-tile still picks the correct slot, and per-slot counting is not
        skewed by MORPH_CLOSE halos elsewhere in the diff.

        Call with sat_in_diff (= cv.bitwise_and(sat_blobs, diff_mask)) rather
        than raw diff_mask: MORPH_CLOSE halos are empty table with zero saturation,
        so they score exactly 0, while real tile pixels score high.

        Returns (None, 0) if no open slots are found or all have zero coverage.
        """
        if self.a is None:
            return None, 0
        best_slot, best_cov = None, 0
        for slot in self.open_slots():
            cov = self.cell_coverage(diff_mask, *slot)
            if cov > best_cov:
                best_cov, best_slot = cov, slot
        return best_slot, best_cov

    def closest_slot(self, diff_cx, diff_cy):
        """Return the open slot whose predicted pixel centre is closest to the
        diff centroid, or None if no slot is within one tile-width.

        Used as a diagnostic cross-check against best_coverage_slot.  The raw
        diff centroid is biased outward by MORPH_CLOSE halos and is unreliable
        when a hand is in frame, so it should NOT be the primary detection method.
        """
        if self.a is None or diff_cx is None or diff_cy is None:
            return None
        best_slot, best_dist = None, float('inf')
        for slot in self.open_slots():
            px = self.origin_px[0] + slot[0] * self.a + slot[1] * self.b
            py = self.origin_px[1] + slot[0] * self.b - slot[1] * self.a
            dist = float(np.hypot(px - diff_cx, py - diff_cy))
            if dist < best_dist:
                best_dist, best_slot = dist, slot
        if best_slot is None or best_dist > self.tile_size_px:
            return None
        return best_slot

    def slot_centroid(self, diff_mask, gx, gy):
        """Centroid of diff pixels within the expected bounding box of (gx, gy).

        More reliable than the full diff-mask centroid when morph-close fills
        interior gaps as the board grows — that fill-in area gets excluded
        because it lies outside the target slot's bounding box.

        Returns (cx, cy) or (None, None) if there are too few pixels in the box.
        """
        cx   = int(self.origin_px[0] + gx * self.a + gy * self.b)
        cy   = int(self.origin_px[1] + gx * self.b - gy * self.a)
        half = int(self.tile_size_px * 0.5)
        x1 = max(cx - half, 0)
        y1 = max(cy - half, 0)
        x2 = min(cx + half, diff_mask.shape[1])
        y2 = min(cy + half, diff_mask.shape[0])
        if x2 <= x1 or y2 <= y1:
            return None, None
        roi = diff_mask[y1:y2, x1:x2]
        M = cv.moments(roi)
        if M['m00'] < 100:
            return None, None
        return (x1 + M['m10'] / M['m00'], y1 + M['m01'] / M['m00'])

    # ── Calibration & grid fitting ────────────────────────────────────────────

    def calibrate(self, diff_cx, diff_cy):
        """Initial calibration from the first placement's diff-mask centroid.

        Sets tile_size from centroid distance and assumes zero rotation (b=0).
        This is only used to bootstrap best_coverage_slot for the first tile —
        refit_grid corrects the rotation immediately after confirm_placement.
        """
        if self.a is not None:
            return
        self.a = float(np.hypot(diff_cx - self.origin_px[0],
                                diff_cy - self.origin_px[1]))
        self.b = 0.0
        print(f"Tile size calibrated: {self.a:.0f}px  (rotation fitted after first placement)")

    def refit_grid(self):
        """Refit origin, tile_size, and rotation from all observed tile centroids.

        Builds a joint linear system over every known centroid using the model:
            px = origin_x + gx·a + gy·b
            py = origin_y + gx·b − gy·a
        Solves for (origin_x, origin_y, a, b) via least squares.  With N tiles
        this gives 2N equations and 4 unknowns, so the fit improves with each
        placement and corrects both drift and rotation simultaneously.
        """
        if len(self.tile_centroids) < 3:
            return
        rows_A, rhs = [], []
        for (gx, gy), (px, py) in self.tile_centroids.items():
            rows_A.append([1, 0,  gx,  gy])
            rhs.append(px)
            rows_A.append([0, 1, -gy,  gx])
            rhs.append(py)
        A     = np.array(rows_A, dtype=float)
        b_vec = np.array(rhs,    dtype=float)
        result, _, _, _ = np.linalg.lstsq(A, b_vec, rcond=None)
        origin_x, origin_y, a, b = result
        tile_size = np.hypot(a, b)
        if tile_size > 0:
            self.origin_px = (origin_x, origin_y)
            self.a         = float(a)
            self.b         = float(b)
            angle_deg      = np.degrees(np.arctan2(b, a))
            print(f"Grid refit: origin=({origin_x:.0f},{origin_y:.0f})  "
                  f"tile_size={tile_size:.1f}px  angle={angle_deg:.1f}°  "
                  f"n={len(self.tile_centroids)}")

    # ── Tile placement ────────────────────────────────────────────────────────

    def confirm_placement(self, coord, diff_cx=None, diff_cy=None):
        """Record a confirmed placement and refit the grid from all known centroids."""
        self.placed_tiles.add(coord)
        if diff_cx is not None and diff_cy is not None:
            self.tile_centroids[coord] = (diff_cx, diff_cy)
            if self.a is not None:
                self.refit_grid()

    # ── Rollback ──────────────────────────────────────────────────────────────

    def snapshot(self):
        """Save current state so it can be restored if the engine rejects a placement."""
        self._snapshot = {
            'origin_px':      self.origin_px,
            'a':              self.a,
            'b':              self.b,
            'placed_tiles':   set(self.placed_tiles),
            'tile_centroids': dict(self.tile_centroids),
        }

    def restore(self):
        """Restore to the last snapshot."""
        if self._snapshot is None:
            return
        self.origin_px      = self._snapshot['origin_px']
        self.a              = self._snapshot['a']
        self.b              = self._snapshot['b']
        self.placed_tiles   = set(self._snapshot['placed_tiles'])
        self.tile_centroids = dict(self._snapshot['tile_centroids'])
