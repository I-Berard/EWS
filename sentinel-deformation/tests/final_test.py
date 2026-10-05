import io
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
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


# ============================================================
# SMALL TEST AREA
# ============================================================

# [min_lon, min_lat, max_lon, max_lat]

TEST_BBOX = [
    30.05,
    -1.98,
    30.07,
    -1.96,
]


# ============================================================
# TEST DATE RANGE
# ============================================================

START_DATE = "2026-09-25"
END_DATE = "2026-10-01"


# ============================================================
# OUTPUT RESOLUTION
# ============================================================

WIDTH = 1024
HEIGHT = 1024


# ============================================================
# OUTPUT DIRECTORY
# ============================================================

OUTPUT_DIR = Path("output") / "satellite_test"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# AUTHENTICATION
# ============================================================

def authenticate():

    print("=" * 60)
    print("COPERNICUS DATA SPACE AUTHENTICATION")
    print("=" * 60)

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
    print(
        f"Token type: {token.get('token_type')}"
    )
    print()

    return oauth


# ============================================================
# SENTINEL-2 EVALSCRIPT
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


# ============================================================
# SENTINEL-2 DOWNLOAD
# ============================================================

def download_sentinel2(oauth):

    print("=" * 60)
    print("SENTINEL-2")
    print("=" * 60)

    print(f"BBOX:       {TEST_BBOX}")
    print(f"Dates:      {START_DATE} -> {END_DATE}")
    print(f"Resolution: {WIDTH} x {HEIGHT}")
    print()

    request_body = {

        "input": {

            "bounds": {

                "bbox": TEST_BBOX,

                "properties": {
                    "crs": (
                        "http://www.opengis.net/def/crs/"
                        "OGC/1.3/CRS84"
                    )
                },
            },

            "data": [

                {
                    "type": "sentinel-2-l2a",

                    "dataFilter": {

                        "timeRange": {

                            "from": (
                                f"{START_DATE}T00:00:00Z"
                            ),

                            "to": (
                                f"{END_DATE}T23:59:59Z"
                            ),
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
                        "type": "image/png"
                    },
                }
            ],
        },

        "evalscript": SENTINEL2_EVALSCRIPT,
    }

    print("Requesting Sentinel-2...")

    response = oauth.post(
        PROCESS_URL,
        json=request_body,
        timeout=300,
    )

    print(
        f"Sentinel-2 HTTP status: "
        f"{response.status_code}"
    )

    if not response.ok:

        print()
        print("Sentinel-2 server response:")
        print(response.text)

        response.raise_for_status()

    # --------------------------------------------------------
    # Read image
    # --------------------------------------------------------

    image = Image.open(
        io.BytesIO(response.content)
    ).convert("RGB")

    image_array = np.asarray(
        image
    )

    # --------------------------------------------------------
    # Save image
    # --------------------------------------------------------

    output_path = (
        OUTPUT_DIR /
        "sentinel2_true_color.png"
    )

    image.save(
        output_path
    )

    print(
        f"Sentinel-2 saved to:\n"
        f"  {output_path}"
    )

    print(
        f"Sentinel-2 shape:\n"
        f"  {image_array.shape}"
    )

    print()

    return image_array


# ============================================================
# SENTINEL-1 EVALSCRIPT
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


# ============================================================
# SENTINEL-1 DOWNLOAD
# ============================================================

def download_sentinel1(oauth):

    print("=" * 60)
    print("SENTINEL-1")
    print("=" * 60)

    print(f"BBOX:       {TEST_BBOX}")
    print(f"Dates:      {START_DATE} -> {END_DATE}")
    print(f"Resolution: {WIDTH} x {HEIGHT}")
    print()

    request_body = {

        "input": {

            "bounds": {

                "bbox": TEST_BBOX,

                "properties": {

                    "crs": (
                        "http://www.opengis.net/def/crs/"
                        "OGC/1.3/CRS84"
                    )

                },

            },

            "data": [

                {

                    "type": "sentinel-1-grd",

                    "dataFilter": {

                        "timeRange": {

                            "from": (
                                f"{START_DATE}T00:00:00Z"
                            ),

                            "to": (
                                f"{END_DATE}T23:59:59Z"
                            ),

                        },

                        "acquisitionMode": "IW",

                        "mosaickingOrder": "mostRecent",

                    },

                    "processing": {

                        "orthorectify": True

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

                        "type": "image/tiff"

                    },

                }

            ],

        },

        "evalscript": SENTINEL1_EVALSCRIPT,

    }

    print("Requesting Sentinel-1...")

    response = oauth.post(

        PROCESS_URL,

        json=request_body,

        timeout=300,

    )

    print(

        f"Sentinel-1 HTTP status: "
        f"{response.status_code}"

    )

    if not response.ok:

        print()
        print("Sentinel-1 server response:")
        print(response.text)

        response.raise_for_status()

    # --------------------------------------------------------
    # TIFF reader
    # --------------------------------------------------------

    try:

        import tifffile

    except ImportError:

        raise RuntimeError(

            "The tifffile package is required.\n\n"

            "Install it with:\n"

            "pip install tifffile"

        )

    # --------------------------------------------------------
    # Read TIFF directly from response
    # --------------------------------------------------------

    data = tifffile.imread(

        io.BytesIO(
            response.content
        )

    )

    data = np.asarray(

        data,

        dtype=np.float32

    )

    print(
        f"Returned Sentinel-1 shape: "
        f"{data.shape}"
    )

    print(
        f"Returned Sentinel-1 dtype: "
        f"{data.dtype}"
    )

    print()

    # --------------------------------------------------------
    # Extract polarizations
    # --------------------------------------------------------

    vv_linear = data[..., 0]

    vh_linear = data[..., 1]

    # --------------------------------------------------------
    # Linear power -> dB
    # --------------------------------------------------------

    vv_db = (

        10.0 *

        np.log10(

            np.maximum(
                vv_linear,
                1e-10
            )

        )

    )

    vh_db = (

        10.0 *

        np.log10(

            np.maximum(
                vh_linear,
                1e-10
            )

        )

    )

    # --------------------------------------------------------
    # VV - VH
    #
    # Since both layers are already in dB:
    #
    # VV - VH = polarization difference in dB
    # --------------------------------------------------------

    vv_minus_vh = (

        vv_db -

        vh_db

    )

    # --------------------------------------------------------
    # Clean invalid values
    # --------------------------------------------------------

    vv_db = np.where(

        np.isfinite(vv_db),

        vv_db,

        np.nan

    )

    vh_db = np.where(

        np.isfinite(vh_db),

        vh_db,

        np.nan

    )

    vv_minus_vh = np.where(

        np.isfinite(vv_minus_vh),

        vv_minus_vh,

        np.nan

    )

    # ========================================================
    # SAVE NUMERICAL ARRAYS
    # ========================================================

    np.save(

        OUTPUT_DIR /
        "sentinel1_vv_db.npy",

        vv_db

    )

    np.save(

        OUTPUT_DIR /
        "sentinel1_vh_db.npy",

        vh_db

    )

    np.save(

        OUTPUT_DIR /
        "sentinel1_vv_minus_vh.npy",

        vv_minus_vh

    )

    # ========================================================
    # SAVE FLOAT32 TIFF PRODUCTS
    # ========================================================

    tifffile.imwrite(

        OUTPUT_DIR /
        "sentinel1_vv_db.tiff",

        vv_db.astype(
            np.float32
        )

    )

    tifffile.imwrite(

        OUTPUT_DIR /
        "sentinel1_vh_db.tiff",

        vh_db.astype(
            np.float32
        )

    )

    tifffile.imwrite(

        OUTPUT_DIR /
        "sentinel1_vv_minus_vh.tiff",

        vv_minus_vh.astype(
            np.float32
        )

    )

    # ========================================================
    # PRINT STATISTICS
    # ========================================================

    print("Sentinel-1 statistics:")

    print(

        f"  VV dB   : "
        f"min={np.nanmin(vv_db):.2f}, "
        f"max={np.nanmax(vv_db):.2f}, "
        f"mean={np.nanmean(vv_db):.2f}"

    )

    print(

        f"  VH dB   : "
        f"min={np.nanmin(vh_db):.2f}, "
        f"max={np.nanmax(vh_db):.2f}, "
        f"mean={np.nanmean(vh_db):.2f}"

    )

    print(

        f"  VV - VH : "
        f"min={np.nanmin(vv_minus_vh):.2f}, "
        f"max={np.nanmax(vv_minus_vh):.2f}, "
        f"mean={np.nanmean(vv_minus_vh):.2f}"

    )

    print()

    return (

        vv_db,

        vh_db,

        vv_minus_vh

    )


# ============================================================
# VISUALIZATION
# ============================================================

def save_visualizations(

    sentinel2,

    vv_db,

    vh_db,

    vv_minus_vh

):

    print("=" * 60)
    print("CREATING VISUALIZATIONS")
    print("=" * 60)

    # ========================================================
    # SENTINEL-2
    # ========================================================

    plt.figure(
        figsize=(8, 8)
    )

    plt.imshow(
        sentinel2
    )

    plt.title(
        "Sentinel-2 L2A True Color"
    )

    plt.axis(
        "off"
    )

    plt.tight_layout()

    s2_path = (

        OUTPUT_DIR /
        "sentinel2_true_color_preview.png"

    )

    plt.savefig(

        s2_path,

        dpi=150,

        bbox_inches="tight"

    )

    plt.close()

    # ========================================================
    # SENTINEL-1 VV
    # ========================================================

    plt.figure(
        figsize=(8, 8)
    )

    plt.imshow(

        vv_db,

        cmap="gray",

        vmin=-25,

        vmax=5

    )

    plt.title(

        "Sentinel-1 VV Backscatter (dB)"

    )

    plt.axis(
        "off"
    )

    plt.colorbar(

        fraction=0.046,

        pad=0.04,

        label="dB"

    )

    plt.tight_layout()

    vv_path = (

        OUTPUT_DIR /
        "sentinel1_vv_db.png"

    )

    plt.savefig(

        vv_path,

        dpi=150,

        bbox_inches="tight"

    )

    plt.close()

    # ========================================================
    # SENTINEL-1 VH
    # ========================================================

    plt.figure(
        figsize=(8, 8)
    )

    plt.imshow(

        vh_db,

        cmap="gray",

        vmin=-30,

        vmax=-5

    )

    plt.title(

        "Sentinel-1 VH Backscatter (dB)"

    )

    plt.axis(
        "off"
    )

    plt.colorbar(

        fraction=0.046,

        pad=0.04,

        label="dB"

    )

    plt.tight_layout()

    vh_path = (

        OUTPUT_DIR /
        "sentinel1_vh_db.png"

    )

    plt.savefig(

        vh_path,

        dpi=150,

        bbox_inches="tight"

    )

    plt.close()

    # ========================================================
    # VV - VH
    # ========================================================

    plt.figure(
        figsize=(8, 8)
    )

    plt.imshow(

        vv_minus_vh,

        cmap="gray",

        vmin=0,

        vmax=15

    )

    plt.title(

        "Sentinel-1 VV - VH (dB)"

    )

    plt.axis(
        "off"
    )

    plt.colorbar(

        fraction=0.046,

        pad=0.04,

        label="VV - VH (dB)"

    )

    plt.tight_layout()

    difference_path = (

        OUTPUT_DIR /
        "sentinel1_vv_minus_vh.png"

    )

    plt.savefig(

        difference_path,

        dpi=150,

        bbox_inches="tight"

    )

    plt.close()

    # ========================================================
    # COMBINED OVERVIEW
    # ========================================================

    fig, axes = plt.subplots(

        2,

        2,

        figsize=(14, 12)

    )

    # --------------------------------------------------------
    # Sentinel-2
    # --------------------------------------------------------

    axes[0, 0].imshow(
        sentinel2
    )

    axes[0, 0].set_title(

        "Sentinel-2 L2A\n"
        "True Color"

    )

    axes[0, 0].axis(
        "off"
    )

    # --------------------------------------------------------
    # VV
    # --------------------------------------------------------

    im_vv = axes[0, 1].imshow(

        vv_db,

        cmap="gray",

        vmin=-25,

        vmax=5

    )

    axes[0, 1].set_title(

        "Sentinel-1 VV\n"
        "Backscatter (dB)"

    )

    axes[0, 1].axis(
        "off"
    )

    fig.colorbar(

        im_vv,

        ax=axes[0, 1],

        fraction=0.046,

        pad=0.04

    )

    # --------------------------------------------------------
    # VH
    # --------------------------------------------------------

    im_vh = axes[1, 0].imshow(

        vh_db,

        cmap="gray",

        vmin=-30,

        vmax=-5

    )

    axes[1, 0].set_title(

        "Sentinel-1 VH\n"
        "Backscatter (dB)"

    )

    axes[1, 0].axis(
        "off"
    )

    fig.colorbar(

        im_vh,

        ax=axes[1, 0],

        fraction=0.046,

        pad=0.04

    )

    # --------------------------------------------------------
    # VV - VH
    # --------------------------------------------------------

    im_difference = axes[1, 1].imshow(

        vv_minus_vh,

        cmap="gray",

        vmin=0,

        vmax=15

    )

    axes[1, 1].set_title(

        "Sentinel-1 VV - VH\n"
        "Polarization Difference (dB)"

    )

    axes[1, 1].axis(
        "off"
    )

    fig.colorbar(

        im_difference,

        ax=axes[1, 1],

        fraction=0.046,

        pad=0.04

    )

    plt.tight_layout()

    overview_path = (

        OUTPUT_DIR /
        "satellite_test_overview.png"

    )

    plt.savefig(

        overview_path,

        dpi=150,

        bbox_inches="tight"

    )

    plt.close()

    print("Visualization files saved:")

    print(
        f"  {s2_path}"
    )

    print(
        f"  {vv_path}"
    )

    print(
        f"  {vh_path}"
    )

    print(
        f"  {difference_path}"
    )

    print(
        f"  {overview_path}"
    )

    print()


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("COPERNICUS DATA SPACE")
    print("SENTINEL-1 + SENTINEL-2 TEST")
    print("=" * 60)
    print()

    print(
        f"Process API: {PROCESS_URL}"
    )

    print(
        f"Test BBOX:   {TEST_BBOX}"
    )

    print(
        f"Dates:       {START_DATE} -> {END_DATE}"
    )

    print(
        f"Resolution:  {WIDTH} x {HEIGHT}"
    )

    print(
        f"Output:      {OUTPUT_DIR.resolve()}"
    )

    print()

    # ========================================================
    # AUTHENTICATE
    # ========================================================

    oauth = authenticate()

    # ========================================================
    # SENTINEL-2
    # ========================================================

    sentinel2 = download_sentinel2(
        oauth
    )

    # ========================================================
    # SENTINEL-1
    # ========================================================

    (

        vv_db,

        vh_db,

        vv_minus_vh

    ) = download_sentinel1(
        oauth
    )

    # ========================================================
    # VISUALIZATIONS
    # ========================================================

    save_visualizations(

        sentinel2,

        vv_db,

        vh_db,

        vv_minus_vh

    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print()

    print(
        "All outputs are in:"
    )

    print(
        f"  {OUTPUT_DIR.resolve()}"
    )

    print()

    print("Visual products:")

    print(
        "  sentinel2_true_color.png"
    )

    print(
        "  sentinel1_vv_db.png"
    )

    print(
        "  sentinel1_vh_db.png"
    )

    print(
        "  sentinel1_vv_minus_vh.png"
    )

    print(
        "  satellite_test_overview.png"
    )

    print()

    print("Numerical products:")

    print(
        "  sentinel1_vv_db.npy"
    )

    print(
        "  sentinel1_vh_db.npy"
    )

    print(
        "  sentinel1_vv_minus_vh.npy"
    )

    print()

    print("Analysis TIFFs:")

    print(
        "  sentinel1_vv_db.tiff"
    )

    print(
        "  sentinel1_vh_db.tiff"
    )

    print(
        "  sentinel1_vv_minus_vh.tiff"
    )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()