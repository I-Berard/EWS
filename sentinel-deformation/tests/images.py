import io
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import requests
from dotenv import load_dotenv
from oauthlib.oauth2 import BackendApplicationClient
from PIL import Image
from requests_oauthlib import OAuth2Session


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

CLIENT_ID = os.getenv("CDSE_CLIENT_ID")
CLIENT_SECRET = os.getenv("CDSE_CLIENT_SECRET")

if not CLIENT_ID:
    raise RuntimeError("CDSE_CLIENT_ID is missing from .env")

if not CLIENT_SECRET:
    raise RuntimeError("CDSE_CLIENT_SECRET is missing from .env")


TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)

PROCESS_URL = "https://sh.dataspace.copernicus.eu/process/v1"


# Kigali bounding box:
# [min_lon, min_lat, max_lon, max_lat]
KIGALI_BBOX = [
    29.95,
    -2.10,
    30.20,
    -1.80,
]


# Start small while testing the API.
#
# Once this works, you can expand the area/time period.
START_DATE = "2026-09-25"
END_DATE = "2026-10-01"


# Keep the first request modest.
WIDTH = 1200
HEIGHT = 1200


OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# AUTHENTICATION
# ============================================================

def authenticate():
    """
    Authenticate against the Copernicus Data Space OAuth2 server.
    """

    print("Authenticating with Copernicus Data Space...")

    client = BackendApplicationClient(
        client_id=CLIENT_ID
    )

    oauth = OAuth2Session(
        client=client
    )

    token = oauth.fetch_token(
        token_url=TOKEN_URL,
        client_secret=CLIENT_SECRET,
        include_client_id=True,
    )

    print("Authentication successful.")
    print(f"Token type: {token.get('token_type')}")
    print()

    return oauth


# ============================================================
# SENTINEL-2
# ============================================================

SENTINEL2_EVALSCRIPT = """
//VERSION=3

function setup() {
    return {
        input: [{
            bands: ["B02", "B03", "B04"]
        }],
        output: {
            bands: 3,
            sampleType: "AUTO"
        }
    };
}

function evaluatePixel(sample) {
    return [
        2.5 * sample.B04,
        2.5 * sample.B03,
        2.5 * sample.B02
    ];
}
"""


def download_sentinel2(oauth):
    """
    Download a Sentinel-2 L2A true-color image of Kigali.
    """

    print("Requesting Sentinel-2 L2A...")
    print(f"Endpoint: {PROCESS_URL}")
    print(f"BBOX: {KIGALI_BBOX}")
    print(f"Dates: {START_DATE} -> {END_DATE}")
    print(f"Size: {WIDTH} x {HEIGHT}")
    print()

    request_body = {
        "input": {
            "bounds": {
                "bbox": KIGALI_BBOX,
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                },
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{START_DATE}T00:00:00Z",
                            "to": f"{END_DATE}T23:59:59Z",
                        },
                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },
        "output": {
            "width": WIDTH,
            "height": HEIGHT,
            "responses": [
                {
                    "identifier": "default",
                    "format": {
                        "type": "image/png",
                    },
                }
            ],
        },
        "evalscript": SENTINEL2_EVALSCRIPT,
    }

    response = oauth.post(
        PROCESS_URL,
        json=request_body,
        timeout=300,
    )

    print(f"HTTP status: {response.status_code}")

    if not response.ok:
        print("Server response:")
        print(response.text)
        response.raise_for_status()

    image = Image.open(io.BytesIO(response.content)).convert("RGB")

    output_path = OUTPUT_DIR / "kigali_sentinel2.png"
    image.save(output_path)

    print(f"Sentinel-2 saved to: {output_path}")

    return np.asarray(image)


# ============================================================
# SENTINEL-1
# ============================================================

SENTINEL1_EVALSCRIPT = """
//VERSION=3

function setup() {
    return {
        input: [{
            bands: ["VV", "VH"],
            units: "LINEAR_POWER"
        }],
        output: {
            bands: 2,
            sampleType: "FLOAT32"
        }
    };
}

function evaluatePixel(sample) {
    return [
        sample.VV,
        sample.VH
    ];
}
"""


def download_sentinel1(oauth):
    """
    Download Sentinel-1 GRD VV/VH data for Kigali.

    The server returns linear power.
    We convert it to dB after downloading.
    """

    print()
    print("Requesting Sentinel-1 GRD...")
    print(f"Endpoint: {PROCESS_URL}")
    print(f"BBOX: {KIGALI_BBOX}")
    print(f"Dates: {START_DATE} -> {END_DATE}")
    print(f"Size: {WIDTH} x {HEIGHT}")
    print()

    request_body = {
        "input": {
            "bounds": {
                "bbox": KIGALI_BBOX,
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                },
            },
            "data": [
                {
                    "type": "sentinel-1-grd",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{START_DATE}T00:00:00Z",
                            "to": f"{END_DATE}T23:59:59Z",
                        }
                    },
                }
            ],
        },
        "output": {
            "width": WIDTH,
            "height": HEIGHT,
            "responses": [
                {
                    "identifier": "default",
                    "format": {
                        "type": "image/tiff",
                    },
                }
            ],
        },
        "evalscript": SENTINEL1_EVALSCRIPT,
    }

    response = oauth.post(
        PROCESS_URL,
        json=request_body,
        timeout=300,
    )

    print(f"HTTP status: {response.status_code}")

    if not response.ok:
        print("Server response:")
        print(response.text)
        response.raise_for_status()

    # --------------------------------------------------------
    # Read TIFF returned by Process API
    # --------------------------------------------------------

    try:
        import tifffile
    except ImportError:
        raise RuntimeError(
            "Missing tifffile. Install it with:\n"
            "pip install tifffile"
        )

    tiff_path = OUTPUT_DIR / "kigali_sentinel1_linear.tiff"

    with open(tiff_path, "wb") as f:
        f.write(response.content)

    data = tifffile.imread(tiff_path)

    print(f"Sentinel-1 raw shape: {data.shape}")
    print(f"Sentinel-1 saved to: {tiff_path}")

    # --------------------------------------------------------
    # Convert linear power -> decibels
    # --------------------------------------------------------

    data = np.asarray(data, dtype=np.float32)

    data_db = 10.0 * np.log10(
        np.maximum(data, 1e-10)
    )

    # Expected:
    # data_db[..., 0] = VV
    # data_db[..., 1] = VH

    vv_db = data_db[..., 0]
    vh_db = data_db[..., 1]

    np.save(
        OUTPUT_DIR / "kigali_sentinel1_vv_db.npy",
        vv_db,
    )

    np.save(
        OUTPUT_DIR / "kigali_sentinel1_vh_db.npy",
        vh_db,
    )

    return vv_db, vh_db


# ============================================================
# VISUALIZATION
# ============================================================

def show_results(sentinel2, vv_db, vh_db):
    """
    Display Sentinel-2 and Sentinel-1 side-by-side.
    """

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(18, 6),
    )

    # --------------------------------------------------------
    # Sentinel-2
    # --------------------------------------------------------

    axes[0].imshow(sentinel2)

    axes[0].set_title(
        "Sentinel-2 L2A\nTrue Color"
    )

    axes[0].axis("off")

    # --------------------------------------------------------
    # Sentinel-1 VV
    # --------------------------------------------------------

    im1 = axes[1].imshow(
        vv_db,
        cmap="gray",
        vmin=-25,
        vmax=5,
    )

    axes[1].set_title(
        "Sentinel-1 VV\nBackscatter (dB)"
    )

    axes[1].axis("off")

    fig.colorbar(
        im1,
        ax=axes[1],
        fraction=0.046,
        pad=0.04,
    )

    # --------------------------------------------------------
    # Sentinel-1 VH
    # --------------------------------------------------------

    im2 = axes[2].imshow(
        vh_db,
        cmap="gray",
        vmin=-30,
        vmax=-5,
    )

    axes[2].set_title(
        "Sentinel-1 VH\nBackscatter (dB)"
    )

    axes[2].axis("off")

    fig.colorbar(
        im2,
        ax=axes[2],
        fraction=0.046,
        pad=0.04,
    )

    plt.tight_layout()

    output_path = OUTPUT_DIR / "kigali_comparison.png"

    plt.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
    )

    print()
    print(f"Comparison saved to: {output_path}")

    plt.show()


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("COPERNICUS DATA SPACE - KIGALI SATELLITE DOWNLOAD")
    print("=" * 60)
    print()

    print(f"Client ID: {CLIENT_ID[:12]}...")
    print(f"Process API: {PROCESS_URL}")
    print()

    oauth = authenticate()

    # --------------------------------------------------------
    # Sentinel-2
    # --------------------------------------------------------

    sentinel2 = download_sentinel2(oauth)

    # --------------------------------------------------------
    # Sentinel-1
    # --------------------------------------------------------

    vv_db, vh_db = download_sentinel1(oauth)

    # --------------------------------------------------------
    # Visualization
    # --------------------------------------------------------

    show_results(
        sentinel2,
        vv_db,
        vh_db,
    )

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
