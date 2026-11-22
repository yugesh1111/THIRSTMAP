"""Real-terrain mode: real elevation + real land cover for an Indian data-centre region.

Sources (free, open):
  Elevation  : Copernicus DEM GLO-30 (AWS open data bucket copernicus-dem-30m)
  Land cover : ESA WorldCover 10 m 2021 v200 (CC BY 4.0, bucket esa-worldcover), read by HTTP range requests
The data centre, villages, wetland sites etc. are HYPOTHETICAL placements on real terrain:
nothing here claims that a real facility affects a real village.
"""
import os
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

from .terrain import CELL_M, N

LOCATIONS = {
    # name: (lat, lon of the window centre, description)
    "navi_mumbai": (19.12, 73.04, "Navi Mumbai (Mahape / Parsik hills), Maharashtra"),
    "hyderabad": (17.44, 78.36, "Hyderabad (Gachibowli / Nanakramguda), Telangana"),
}
CREDIT = "Real terrain: Copernicus DEM GLO-30 (modified) · ESA WorldCover 2021 (CC BY 4.0)"
CACHE = Path(__file__).resolve().parent.parent / "data" / "real"
CA = "/root/.ccr/ca-bundle.crt"


def _dem_tile(lat, lon):
    t = f"N{int(lat):02d}_00_E{int(lon):03d}_00"
    name = f"Copernicus_DSM_COG_10_{t}_DEM.tif"
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = f"https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{t}_DEM/{name}"
        urllib.request.urlretrieve(url, path)
    return path


def _window(src, lat, lon, half_m, resample):
    import rasterio
    from rasterio.windows import from_bounds
    dlat = half_m / 111_320
    dlon = half_m / (111_320 * np.cos(np.radians(lat)))
    with rasterio.open(src) as d:
        w = from_bounds(lon - dlon, lat - dlat, lon + dlon, lat + dlat, d.transform)
        a = d.read(1, window=w).astype(np.float32)
    return np.asarray(Image.fromarray(a, mode="F").resize((N, N), resample))


def load(name):
    """Return dict(z, landcover, name, credit) on the standard 160 x 160 grid (25 m cells)."""
    lat, lon, desc = LOCATIONS[name]
    half = N * CELL_M / 2
    z = _window(str(_dem_tile(lat, lon)), lat, lon, half, Image.BILINEAR)
    # the DSM includes buildings and tree tops; light smoothing approximates the ground surface
    for _ in range(2):
        z = (z + np.roll(z, 1, 0) + np.roll(z, -1, 0) + np.roll(z, 1, 1) + np.roll(z, -1, 1)) / 5
    lc_cache = CACHE / f"worldcover_{name}.npy"
    if lc_cache.exists():
        lc = np.load(lc_cache)
    else:
        os.environ.setdefault("CURL_CA_BUNDLE", CA) if Path(CA).exists() else None
        tile = f"N{int(lat) // 3 * 3:02d}E{int(lon) // 3 * 3:03d}"
        url = ("/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
               f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")
        lc = _window(url, lat, lon, half, Image.NEAREST).astype(np.uint8)
        np.save(lc_cache, lc)
    return dict(z=z, landcover=lc, name=name, desc=desc, credit=CREDIT)
