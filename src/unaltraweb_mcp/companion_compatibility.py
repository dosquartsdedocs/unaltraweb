"""Exact static-receipt compatibility points, not renderer/version intervals.

0.4.0 receipts were accepted in the published 0.5/0.6 coordinator deliveries.
Keeping their integrity checks usable must not force regeneration of authored
figures when a newer, explicitly accepted companion is selected for new work.
"""

LEGACY_RECEIPT_POINTS = {
    "diavisuals": {("0.4.0", "v0.4.0")},
    "vegavisuals": {("0.4.0", "v0.4.0")},
}


def accepts_receipt(owner, version, release, selected):
    if not isinstance(version, str) or not isinstance(release, str):
        return False
    point = (version, release)
    return point == (selected["version"], selected["release"]) or point in LEGACY_RECEIPT_POINTS.get(owner, set())
