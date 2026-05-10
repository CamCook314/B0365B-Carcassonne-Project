"""
meeple_detector.py — Diff-based meeple detection on a placed tile.

Primary signal: absolute difference between a baseline frame (taken after a
settle period in WAIT_MEEPLE, with the arm fully cleared) and the current frame.
Only pixels that are NEW since the baseline contribute — tile artwork is
subtracted out entirely.

Contour-per-blob approach: each connected diff region is tested independently.
Arm/hand blobs (too large) are discarded without affecting meeple-sized blobs.
Noise blobs (too small) are also discarded.  Colour is matched only within the
surviving contour's own pixels, so tile art in the surrounding area cannot
pollute the result.

Returns (colour, direction, debug_dict) from detect_meeple().
debug_dict keys:
  base_crop : BGR crop of the baseline frame at the tile region (or None)
  diff_vis  : BGR crop with contours drawn (grey=noise, red=arm, orange=no-colour, green=match)
  stats     : human-readable string summarising what was found this frame
"""
import cv2 as cv
import numpy as np

# HSV colour ranges.  Red wraps 0°, so it needs two entries.
# Black: value < 70 (black plastic reflects some light).
COLOUR_RANGES = {
    "red":    [((0,   100, 60),  (10,  255, 255)),
               ((165, 100, 60),  (180, 255, 255))],
    "blue":   [((100, 80,  60),  (130, 255, 255))],
    "green":  [((55,  120, 60),  (80,  255, 255))],
    "yellow": [((20,  100, 60),  (35,  255, 255))],
    "black":  [((0,   0,   0),   (180, 80,  70))],
}

DIFF_THRESHOLD     = 20     # abs pixel change to count as "new"
MIN_BLOB_AREA      = 60     # px² — smallest diff blob that could be a meeple
MAX_BLOB_AREA_FRAC = 0.25   # fraction of tile area — blobs larger than this are arm/hand
COLOUR_MATCH_FRAC  = 0.22   # fraction of blob that must match a colour
CROP_HALF_FRAC     = 0.60   # half-width of crop as fraction of tile_size_px (was 0.45;
                             # increased to catch meeples placed near tile edges)
CIRC_MIN           = 0.30   # minimum circularity for Pass 1; meeple bodies pass, tile art fails


def _colour_mask(hsv_crop, colour):
    mask = None
    for lo, hi in COLOUR_RANGES[colour]:
        m = cv.inRange(hsv_crop,
                       np.array(lo, dtype=np.uint8),
                       np.array(hi, dtype=np.uint8))
        mask = m if mask is None else cv.bitwise_or(mask, m)
    return mask


def detect_meeple(proc_frame, slot_px, tile_size_px,
                  baseline_frame=None, centre_frac=0.25,
                  expected_colour=None):
    """Detect a meeple on the last-placed tile.

    proc_frame     : current 1920×1080 BGR frame.
    slot_px        : (cx, cy) grid-predicted tile centre, proc coords.
    tile_size_px   : side length of one tile in proc coords.
    baseline_frame : proc_frame captured after the baseline settle period
                     (arm fully cleared).  If None, falls back to pure-colour.
    centre_frac    : displacement fraction below which centroid → 'centre'.

    Returns (colour_name, direction, debug_dict) or (None, None, debug_dict).
    """
    cx, cy = int(slot_px[0]), int(slot_px[1])
    half   = int(tile_size_px * CROP_HALF_FRAC)

    x1 = max(cx - half, 0)
    y1 = max(cy - half, 0)
    x2 = min(cx + half, proc_frame.shape[1])
    y2 = min(cy + half, proc_frame.shape[0])

    crop = proc_frame[y1:y2, x1:x2]
    dbg  = {"base_crop": None, "diff_vis": crop.copy(), "stats": ""}

    if crop.size == 0:
        dbg["stats"] = "empty crop"
        return None, None, dbg

    tile_area    = tile_size_px ** 2
    max_blob_area = tile_area * MAX_BLOB_AREA_FRAC

    mcx = mcy = None
    best_colour = None

    # ── Diff-based detection ──────────────────────────────────────────────────
    if baseline_frame is not None:
        base_crop = baseline_frame[y1:y2, x1:x2]
        dbg["base_crop"] = base_crop.copy()

        if base_crop.shape != crop.shape:
            dbg["stats"] = "shape mismatch"
            return None, None, dbg

        diff      = cv.absdiff(crop, base_crop)
        diff_grey = cv.cvtColor(diff, cv.COLOR_BGR2GRAY)
        _, diff_mask = cv.threshold(diff_grey, DIFF_THRESHOLD, 255, cv.THRESH_BINARY)

        k = cv.getStructuringElement(cv.MORPH_ELLIPSE, (3, 3))
        diff_mask = cv.morphologyEx(diff_mask, cv.MORPH_OPEN, k)

        contours, _ = cv.findContours(diff_mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        hsv         = cv.cvtColor(crop, cv.COLOR_BGR2HSV)

        # Baseline-subtracted new-pixel masks: current colour AND NOT dilated baseline colour.
        # Dilation absorbs ~7px tile shifts so moved tile art disappears; the meeple survives.
        colours_to_check = [expected_colour] if expected_colour else list(COLOUR_RANGES.keys())
        baseline_hsv = cv.cvtColor(base_crop, cv.COLOR_BGR2HSV)
        dilate_k = cv.getStructuringElement(cv.MORPH_ELLIPSE, (15, 15))
        new_masks = {
            c: cv.bitwise_and(
                _colour_mask(hsv, c),
                cv.bitwise_not(cv.dilate(_colour_mask(baseline_hsv, c), dilate_k)),
            )
            for c in colours_to_check
        }

        diff_vis    = crop.copy()
        best_score  = 0.0
        stats_parts = []
        total_diff  = cv.countNonZero(diff_mask)

        for cnt in contours:
            area = cv.contourArea(cnt)

            if area < MIN_BLOB_AREA:
                cv.drawContours(diff_vis, [cnt], -1, (80, 80, 80), 1)   # grey: noise
                continue

            if area > max_blob_area:
                cv.drawContours(diff_vis, [cnt], -1, (0, 0, 255), 2)    # red: arm/hand
                stats_parts.append(f"arm({area:.0f}px)")
                continue

            # Valid-size blob — test colours using baseline-subtracted new pixels
            cnt_mask = np.zeros(diff_mask.shape, dtype=np.uint8)
            cv.drawContours(cnt_mask, [cnt], -1, 255, -1)

            blob_best_colour = None
            blob_best_score  = 0.0
            blob_best_frac   = 0.0

            for colour in colours_to_check:
                overlap = cv.countNonZero(cv.bitwise_and(new_masks[colour], cnt_mask))
                frac    = overlap / area
                if frac >= COLOUR_MATCH_FRAC:
                    perim = cv.arcLength(cnt, True)
                    circ  = (4 * np.pi * area / perim ** 2) if perim > 0 else 0.0
                    if circ < CIRC_MIN:
                        continue  # irregular tile-art fragment — reject
                    score = area * circ
                    if score > blob_best_score:
                        blob_best_score  = score
                        blob_best_colour = colour
                        blob_best_frac   = frac

            if blob_best_colour is not None:
                cv.drawContours(diff_vis, [cnt], -1, (0, 255, 0), 2)    # green: colour match
                stats_parts.append(f"{blob_best_colour}({blob_best_frac:.0%},{area:.0f}px)")
                if blob_best_score > best_score:
                    best_score  = blob_best_score
                    best_colour = blob_best_colour
                    M = cv.moments(cnt_mask)
                    if M["m00"] > 0:
                        mcx = M["m10"] / M["m00"]
                        mcy = M["m01"] / M["m00"]
            else:
                cv.drawContours(diff_vis, [cnt], -1, (0, 165, 255), 1)  # orange: no colour
                fracs = {c: cv.countNonZero(cv.bitwise_and(new_masks[c], cnt_mask)) / area
                         for c in colours_to_check}
                best_col_any  = max(fracs, key=fracs.get)
                best_frac_any = fracs[best_col_any]
                stats_parts.append(f"no-match({area:.0f}px,best={best_col_any}@{best_frac_any:.0%})")

        # ── Sub-contour fallback ─────────────────────────────────────────────
        # When the main pass fails (tile shifted after baseline → large mixed diff
        # blob with the meeple embedded inside), find the meeple via two layers:
        #
        #   1. Baseline subtraction: for each colour, compute pixels that are NEW
        #      since the baseline — i.e. current_colour AND NOT(dilated baseline).
        #      Dilating the baseline mask by ~15px absorbs small tile shifts so
        #      moved tile-art disappears from the candidate set entirely.
        #      The meeple, which was absent from the baseline, always survives.
        #
        #   2. Circularity weighting: score sub-contours by area × circularity so
        #      compact meeple shapes beat any irregular tile-art that survived (1).
        if best_colour is None:
            for cnt in contours:
                cnt_area_sub = cv.contourArea(cnt)
                if cnt_area_sub < MIN_BLOB_AREA or cnt_area_sub > max_blob_area:
                    continue  # skip noise and arm/hand blobs
                cnt_mask = np.zeros(diff_mask.shape, dtype=np.uint8)
                cv.drawContours(cnt_mask, [cnt], -1, 255, -1)
                parent_area = cnt_area_sub

                for colour in colours_to_check:
                    colour_pixels = cv.bitwise_and(new_masks[colour], cnt_mask)
                    sub_cnts, _ = cv.findContours(colour_pixels, cv.RETR_EXTERNAL,
                                                  cv.CHAIN_APPROX_SIMPLE)
                    for sc in sub_cnts:
                        sc_area = cv.contourArea(sc)
                        if sc_area < MIN_BLOB_AREA or sc_area > max_blob_area:
                            continue
                        sc_perim = cv.arcLength(sc, True)
                        sc_circ  = (4 * np.pi * sc_area / sc_perim ** 2
                                    if sc_perim > 0 else 0.0)
                        if sc_circ < CIRC_MIN:
                            continue  # irregular tile-art fragment
                        sc_mask = np.zeros(diff_mask.shape, dtype=np.uint8)
                        cv.drawContours(sc_mask, [sc], -1, 255, -1)
                        M = cv.moments(sc_mask)
                        if M["m00"] > 0:
                            sc_score = sc_area * sc_circ
                            if sc_score > best_score:
                                best_score  = sc_score
                                best_colour = colour
                                mcx = M["m10"] / M["m00"]
                                mcy = M["m01"] / M["m00"]
                                cv.drawContours(diff_vis, [cnt], -1, (255, 255, 0), 1)
                                cv.drawContours(diff_vis, [sc], -1, (0, 255, 255), 2)
                                stats_parts.append(
                                    f"sub:{colour}({sc_area:.0f}px"
                                    f",circ={sc_circ:.2f}"
                                    f" in {parent_area:.0f}px blob)")
                    if best_colour is not None:
                        break
                if best_colour is not None:
                    break

        dbg["diff_vis"] = diff_vis
        dbg["stats"]    = ("  ".join(stats_parts)
                           if stats_parts
                           else f"no blobs (total diff={total_diff}px)")

        if best_colour is None or mcx is None:
            return None, None, dbg

    # ── Fallback: pure colour detection (no baseline) ────────────────────────
    else:
        hsv    = cv.cvtColor(crop, cv.COLOR_BGR2HSV)
        kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (3, 3))

        best_area = MIN_BLOB_AREA - 1

        for colour in COLOUR_RANGES:
            mask = _colour_mask(hsv, colour)
            mask = cv.morphologyEx(mask, cv.MORPH_OPEN, kernel)
            M    = cv.moments(mask)
            area = M["m00"]
            if area < MIN_BLOB_AREA or area > max_blob_area or area <= best_area:
                continue
            best_colour = colour
            best_area   = area
            mcx         = M["m10"] / M["m00"]
            mcy         = M["m01"] / M["m00"]

        dbg["stats"] = (f"fallback: {best_colour}({best_area:.0f}px)"
                        if best_colour else "fallback: no match")
        if best_colour is None:
            return None, None, dbg

    # ── Direction ─────────────────────────────────────────────────────────────
    crop_cx   = (x2 - x1) / 2.0
    crop_cy   = (y2 - y1) / 2.0
    dx        = mcx - crop_cx
    dy        = mcy - crop_cy
    threshold = tile_size_px * centre_frac

    if abs(dx) < threshold and abs(dy) < threshold:
        direction = "centre"
    elif abs(dx) >= abs(dy):
        direction = "right" if dx > 0 else "left"
    else:
        direction = "down" if dy > 0 else "up"

    # Confidence: fraction of crop half-width the meeple is displaced from centre.
    # 0 = exactly at centre, 1 = at the crop edge.  < 0.75 triggers valid-side snapping.
    dbg["confidence"] = float(np.hypot(dx, dy)) / (tile_size_px * CROP_HALF_FRAC)
    dbg["dx"] = dx
    dbg["dy"] = dy

    return best_colour, direction, dbg
