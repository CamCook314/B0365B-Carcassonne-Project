"""
grid_tracker.py — Grid coordinate tracking for the Carcassonne board.

GridTracker owns everything to do with the coordinate system:
  - origin pixel position, tile spacing, and board rotation angle
  - which cells are occupied
  - converting between grid coords and pixel positions
  - scoring candidate placement slots by blob coverage
  - snapshotting / restoring state for invalid-placement rollback

The grid model uses a general affine transform to handle perspective:

    px = origin_x + gx·a + gy·c
    py = origin_y + gx·b + gy·d

where (a, b) is the x-step vector and (c, d) is the y-step vector in
camera pixel space.  For an isotropic (perfectly overhead) camera:
    a = tile_size·cos(θ),  b = tile_size·sin(θ)
    c = b,                 d = −a

For a tilted camera the vertical pixel spacing differs from horizontal,
so (c, d) is fit independently from (a, b) once vertical centroid data
is available.  Until then the isotropic defaults are used.

All four step components plus origin are jointly fitted via least squares
from all observed tile centroids, so perspective is recovered automatically.
"""

import cv2 as cv
import numpy as np


class GridTracker:

    def __init__(self, origin_px):
        self.origin_px         = origin_px   # (px, py) — pixel centre of grid (0, 0)
        self.a                 = None        # x-step x-component  (tile_size_x * cos θ)
        self.b                 = None        # x-step y-component  (tile_size_x * sin θ)
        self.c                 = None        # y-step x-component  (≈ b for isotropic)
        self.d                 = None        # y-step y-component  (≈ −a for isotropic)
        self.placed_tiles      = {(0, 0)}    # (gx, gy) for every confirmed placement
        self.tile_centroids    = {(0, 0): origin_px}  # grid coord → observed pixel centroid
        self.centroid_weights  = {(0, 0): 1.0}        # WLS weight per centroid; >1 = trusted
        self._snapshot         = None        # Saved state for rollback

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def tile_size_px(self):
        """Pixel distance between adjacent tile centres along the x-axis."""
        return None if self.a is None else float(np.hypot(self.a, self.b))

    @property
    def tile_size_y_px(self):
        """Pixel distance between adjacent tile centres along the y-axis.

        Differs from tile_size_px when the camera is tilted (perspective),
        making vertical pixel spacing smaller than horizontal.
        """
        if self.c is None or self.d is None:
            return self.tile_size_px
        return float(np.hypot(self.c, self.d))

    # ── Coordinate conversion ─────────────────────────────────────────────────

    def grid_to_px(self, gx, gy):
        """Grid cell (gx, gy) → pixel centre (x, y), accounting for board rotation
        and camera perspective (anisotropic pixel spacing)."""
        return (
            int(round(self.origin_px[0] + gx * self.a + gy * self.c)),
            int(round(self.origin_px[1] + gx * self.b + gy * self.d)),
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
        """Open slots where all 4 neighbours are already placed."""
        return [
            s for s in self.open_slots()
            if all((s[0] + dx, s[1] + dy) in self.placed_tiles
                   for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)])
        ]

    # ── Coverage scoring ──────────────────────────────────────────────────────

    def cell_coverage(self, blob_mask, gx, gy):
        """Count blob pixels inside the expected bounding box of cell (gx, gy)."""
        cx   = int(self.origin_px[0] + gx * self.a + gy * self.c)
        cy   = int(self.origin_px[1] + gx * self.b + gy * self.d)
        half = int(max(self.tile_size_px, self.tile_size_y_px) * 0.5)
        x1 = max(cx - half, 0)
        y1 = max(cy - half, 0)
        x2 = min(cx + half, blob_mask.shape[1])
        y2 = min(cy + half, blob_mask.shape[0])
        if x2 <= x1 or y2 <= y1:
            return 0
        return cv.countNonZero(blob_mask[y1:y2, x1:x2])

    def best_coverage_slot(self, diff_mask):
        """Return (slot, coverage) for the open slot with the highest diff-pixel coverage."""
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
        diff centroid, or None if no slot is within one tile-width."""
        if self.a is None or diff_cx is None or diff_cy is None:
            return None
        best_slot, best_dist = None, float('inf')
        for slot in self.open_slots():
            px = self.origin_px[0] + slot[0] * self.a + slot[1] * self.c
            py = self.origin_px[1] + slot[0] * self.b + slot[1] * self.d
            dist = float(np.hypot(px - diff_cx, py - diff_cy))
            if dist < best_dist:
                best_dist, best_slot = dist, slot
        if best_slot is None or best_dist > self.tile_size_px:
            return None
        return best_slot

    def slot_centroid(self, diff_mask, gx, gy):
        """Centroid of diff pixels within the expected bounding box of (gx, gy).

        Uses the larger of the x and y tile sizes as the half-extent so the
        bounding box captures the tile regardless of perspective distortion.
        """
        cx   = int(self.origin_px[0] + gx * self.a + gy * self.c)
        cy   = int(self.origin_px[1] + gx * self.b + gy * self.d)
        half = int(max(self.tile_size_px, self.tile_size_y_px) * 0.5)
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
        """Initial calibration from the first placement's diff-mask centroid."""
        if self.a is not None:
            return
        self.a = float(np.hypot(diff_cx - self.origin_px[0],
                                diff_cy - self.origin_px[1]))
        self.b = 0.0
        self.c = 0.0       # isotropic default: c = b = 0
        self.d = -self.a   # isotropic default: d = -a
        print(f"Tile size calibrated: {self.a:.0f}px  (rotation fitted after first placement)")

    def refit_grid(self):
        """Refit origin and step vectors from all observed tile centroids.

        Uses a 6-parameter affine model:
            px = origin_x + gx·a + gy·c
            py = origin_y + gx·b + gy·d

        When only horizontal data is available (all gy = 0) the system is
        underdetermined for c and d, so the 4-parameter isotropic model is
        used instead and c/d are derived from a/b.  Once vertical centroid
        observations are present the full 6-parameter fit runs, recovering
        the correct (typically smaller) vertical pixel step independently of
        the horizontal step.
        """
        if len(self.tile_centroids) < 3:
            return

        gx_vals = [gx for (gx, _) in self.tile_centroids]
        gy_vals = [gy for (_, gy) in self.tile_centroids]
        has_x_var = len(set(gx_vals)) > 1
        has_y_var = len(set(gy_vals)) > 1

        if has_y_var and has_x_var:
            # 6-parameter fit: px = ox + gx*a + gy*c,  py = oy + gx*b + gy*d
            rows_A, rhs = [], []
            for (gx, gy), (px, py) in self.tile_centroids.items():
                sw = self.centroid_weights.get((gx, gy), 1.0) ** 0.5
                rows_A.append([sw,  0, sw*gx,    0, sw*gy,    0])
                rhs.append(sw * px)
                rows_A.append([ 0, sw,    0, sw*gx,    0, sw*gy])
                rhs.append(sw * py)
            A_mat  = np.array(rows_A, dtype=float)
            b_vec  = np.array(rhs,    dtype=float)
            result, _, _, _ = np.linalg.lstsq(A_mat, b_vec, rcond=None)
            origin_x, origin_y, a, b, c, d = result
            tile_size_x = float(np.hypot(a, b))
            tile_size_y = float(np.hypot(c, d))

            if tile_size_x <= 0 or tile_size_y <= 0:
                return

            angle_deg = float(np.degrees(np.arctan2(b, a)))

            # Sanity checks (relaxed slightly vs isotropic since we now have
            # separate x/y sizes — tile_size_y should be plausible relative to x).
            if self.a is not None:
                n = len(self.tile_centroids)
                prev_size  = self.tile_size_px
                prev_angle = float(np.degrees(np.arctan2(self.b, self.a)))
                size_thresh  = 0.35 if n <= 5 else 0.25
                angle_thresh = 12.0 if n <= 5 else 8.0
                size_change  = abs(tile_size_x - prev_size) / prev_size
                angle_change = abs(angle_deg - prev_angle)
                if size_change > size_thresh:
                    print(f"Grid refit rejected: tile_size_x {prev_size:.1f}→{tile_size_x:.1f}px "
                          f"({size_change*100:.0f}% change, n={n})")
                    return
                if angle_change > angle_thresh:
                    print(f"Grid refit rejected: angle {prev_angle:.1f}°→{angle_deg:.1f}° "
                          f"({angle_change:.1f}° change, n={n})")
                    return
                # Reject implausible vertical scale (must be 40%–160% of horizontal)
                ratio = tile_size_y / tile_size_x
                if ratio < 0.40 or ratio > 1.60:
                    print(f"Grid refit rejected: tile_size_y/x ratio {ratio:.2f} out of range "
                          f"(x={tile_size_x:.1f}  y={tile_size_y:.1f}  n={n})")
                    return

            self.origin_px = (origin_x, origin_y)
            self.a = float(a)
            self.b = float(b)
            self.c = float(c)
            self.d = float(d)
            _heavy = [k for k, w in self.centroid_weights.items() if w > 1.0]
            _heavy_str = f"  heavy={_heavy}" if _heavy else ""
            print(f"Grid refit [6-param]: origin=({origin_x:.0f},{origin_y:.0f})  "
                  f"tile_x={tile_size_x:.1f}px  tile_y={tile_size_y:.1f}px  "
                  f"angle={angle_deg:.1f}°  n={len(self.tile_centroids)}{_heavy_str}")

        elif has_y_var and not has_x_var:
            # Column placement: all tiles share the same gx so a/b are underdetermined
            # in the full 6-param system.  Keep the existing a/b and fit only the
            # y-step (c, d) plus the origin offset from the observed centroids.
            # Model: px = ox + gy*c  (gx contribution subtracted using known a/b)
            #        py = oy + gy*d
            if self.a is None:
                return
            rows_A, rhs = [], []
            for (gx, gy), (px, py) in self.tile_centroids.items():
                sw = self.centroid_weights.get((gx, gy), 1.0) ** 0.5
                rows_A.append([sw,  0, sw*gy,    0])
                rhs.append(sw * (px - gx * self.a))
                rows_A.append([ 0, sw,    0, sw*gy])
                rhs.append(sw * (py - gx * self.b))
            A_mat  = np.array(rows_A, dtype=float)
            b_vec  = np.array(rhs,    dtype=float)
            result, _, _, _ = np.linalg.lstsq(A_mat, b_vec, rcond=None)
            origin_x, origin_y, c, d = result
            tile_size_x = self.tile_size_px
            tile_size_y = float(np.hypot(c, d))

            if tile_size_y <= 0:
                return

            n     = len(self.tile_centroids)
            ratio = tile_size_y / tile_size_x
            if ratio < 0.40 or ratio > 1.60:
                print(f"Grid refit rejected: tile_size_y/x ratio {ratio:.2f} out of range "
                      f"(x={tile_size_x:.1f}  y={tile_size_y:.1f}  n={n})")
                return

            self.origin_px = (origin_x, origin_y)
            self.c = float(c)
            self.d = float(d)
            angle_deg = float(np.degrees(np.arctan2(self.b, self.a)))
            _heavy = [k for k, w in self.centroid_weights.items() if w > 1.0]
            _heavy_str = f"  heavy={_heavy}" if _heavy else ""
            print(f"Grid refit [y-fit]: origin=({origin_x:.0f},{origin_y:.0f})  "
                  f"tile_x={tile_size_x:.1f}px  tile_y={tile_size_y:.1f}px  "
                  f"angle={angle_deg:.1f}°  n={n}{_heavy_str}")
        else:
            # 4-parameter isotropic fit (all tiles at same gy — no vertical data yet)
            rows_A, rhs = [], []
            for (gx, gy), (px, py) in self.tile_centroids.items():
                sw = self.centroid_weights.get((gx, gy), 1.0) ** 0.5
                rows_A.append([sw,  0,  sw*gx,  sw*gy])
                rhs.append(sw * px)
                rows_A.append([ 0, sw, -sw*gy,  sw*gx])
                rhs.append(sw * py)
            A_mat  = np.array(rows_A, dtype=float)
            b_vec  = np.array(rhs,    dtype=float)
            result, _, _, _ = np.linalg.lstsq(A_mat, b_vec, rcond=None)
            origin_x, origin_y, a, b = result
            tile_size = float(np.hypot(a, b))

            if tile_size <= 0:
                return

            angle_deg = float(np.degrees(np.arctan2(b, a)))
            if self.a is not None:
                n = len(self.tile_centroids)
                prev_size  = self.tile_size_px
                prev_angle = float(np.degrees(np.arctan2(self.b, self.a)))
                size_thresh  = 0.25 if n <= 4 else 0.20
                angle_thresh = 10.0 if n <= 4 else 8.0
                if abs(tile_size - prev_size) / prev_size > size_thresh:
                    print(f"Grid refit rejected: tile_size {prev_size:.1f}→{tile_size:.1f}px "
                          f"({abs(tile_size-prev_size)/prev_size*100:.0f}% change, n={n})")
                    return
                if abs(angle_deg - prev_angle) > angle_thresh:
                    print(f"Grid refit rejected: angle {prev_angle:.1f}°→{angle_deg:.1f}° "
                          f"({abs(angle_deg-prev_angle):.1f}° change, n={n})")
                    return

            self.origin_px = (origin_x, origin_y)
            self.a = float(a)
            self.b = float(b)
            self.c = float(b)    # isotropic: c = b
            self.d = float(-a)   # isotropic: d = -a
            _heavy = [k for k, w in self.centroid_weights.items() if w > 1.0]
            _heavy_str = f"  heavy={_heavy}" if _heavy else ""
            print(f"Grid refit [4-param]: origin=({origin_x:.0f},{origin_y:.0f})  "
                  f"tile_size={tile_size:.1f}px  angle={angle_deg:.1f}°  "
                  f"n={len(self.tile_centroids)}{_heavy_str}")

    def update_centroid(self, coord, cx, cy, weight=None):
        """Replace the stored centroid for a placed tile and refit the grid."""
        if coord not in self.placed_tiles:
            return
        self.tile_centroids[coord] = (float(cx), float(cy))
        if weight is not None:
            self.centroid_weights[coord] = float(weight)
        if len(self.tile_centroids) >= 3:
            self.refit_grid()

    # ── Tile placement ────────────────────────────────────────────────────────

    def confirm_placement(self, coord, diff_cx=None, diff_cy=None, weight=1.0):
        """Record a confirmed placement and refit the grid from all known centroids."""
        self.placed_tiles.add(coord)
        if diff_cx is not None and diff_cy is not None:
            self.tile_centroids[coord] = (diff_cx, diff_cy)
            self.centroid_weights[coord] = float(weight)
            if self.a is not None:
                self.refit_grid()

    # ── Rollback ──────────────────────────────────────────────────────────────

    def snapshot(self):
        """Save current state so it can be restored if the engine rejects a placement."""
        self._snapshot = {
            'origin_px':         self.origin_px,
            'a':                 self.a,
            'b':                 self.b,
            'c':                 self.c,
            'd':                 self.d,
            'placed_tiles':      set(self.placed_tiles),
            'tile_centroids':    dict(self.tile_centroids),
            'centroid_weights':  dict(self.centroid_weights),
        }

    def restore(self):
        """Restore to the last snapshot."""
        if self._snapshot is None:
            return
        self.origin_px        = self._snapshot['origin_px']
        self.a                = self._snapshot['a']
        self.b                = self._snapshot['b']
        self.c                = self._snapshot['c']
        self.d                = self._snapshot['d']
        self.placed_tiles     = set(self._snapshot['placed_tiles'])
        self.tile_centroids   = dict(self._snapshot['tile_centroids'])
        self.centroid_weights = dict(self._snapshot['centroid_weights'])
