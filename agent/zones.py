"""3x3 zone grid helpers. Zones are named by row (T, M, B) and column (L, C, R).
The center cell is called "C"."""
ZONES = ["TL", "TC", "TR", "ML", "C", "MR", "BL", "BC", "BR"]
_POS = {z: (i // 3, i % 3) for i, z in enumerate(ZONES)}


def pos(zone):
    return _POS.get(zone)


def relation(a, b):
    """same | adjacent (shares an edge) | far"""
    if a == b:
        return "same"
    pa, pb = pos(a), pos(b)
    if pa is None or pb is None:
        return "far"
    return "adjacent" if abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) == 1 else "far"


def zone_of_box(cx, cy, width, height):
    """Zone for a bbox centroid (pixels or normalized, as long as width/height match)."""
    col = min(2, int(3 * cx / width))
    row = min(2, int(3 * cy / height))
    return ZONES[row * 3 + col]
