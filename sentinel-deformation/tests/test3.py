import os
import time
from pathlib import Path

import numpy as np
import tifffile

from dotenv import load_dotenv
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session


# ============================================================
# 1. CONFIGURATION
# ============================================================

load_dotenv()

CLIENT_ID = os.getenv("CDSE_CLIENT_ID")
CLIENT_SECRET = os.getenv("CDSE_CLIENT_SECRET")

if not CLIENT_ID:
    raise RuntimeError(
        "CDSE_CLIENT_ID is missing from your .env file"
    )

if not CLIENT_SECRET:
    raise RuntimeError(
        "CDSE_CLIENT_SECRET is missing from your .env file"
    )


TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)

PROCESS_URL = (
    "https://sh.dataspace.copernicus.eu/process/v1"
)


# ============================================================
# 2. SMALL TEST AREA
# ============================================================

# Small area around Kigali.
#
# [minimum longitude,
#  minimum latitude,
#  maximum longitude,
#  maximum latitude]

BBOX = [
    30.05,
    -1.98,
    30.07,
    -1.96,
]


# Keep the time range reasonably small for the diagnostic.
START_DATE = "2026-09-25"
END_DATE = "2026-10-01"


# Small output for the first test.
WIDTH = 1024
HEIGHT = 1024


OUTPUT_FILE = Path(
    "sentinel1_diagnostic.tiff"
)


# ============================================================
# 3. AUTHENTICATION
# ============================================================

def authenticate():

    print("=" * 60)
    print("AUTHENTICATING WITH COPERNICUS DATA SPACE")
    print("=" * 60)

    client = BackendApplicationClient(
        client_id=CLIENT_ID
    )

    oauth = OAuth2Session(
        client=client
    )

    started = time.perf_counter()

    try:

        token = oauth.fetch_token(
            token_url=TOKEN_URL,
            client_secret=CLIENT_SECRET,
            include_client_id=True,
        )

    except Exception as exc:

        elapsed = time.perf_counter() - started

        print(
            f"Authentication failed after "
            f"{elapsed:.2f} seconds."
        )

        print()
        print("Error:")
        print(exc)

        raise

    elapsed = time.perf_counter() - started

    print(
        f"Authentication successful "
        f"({elapsed:.2f} seconds)"
    )

    print(
        "Token type:",
        token.get("token_type")
    )

    print()

    return oauth


# ============================================================
# 4. SENTINEL-1 REQUEST
# ============================================================

def download_sentinel1(oauth):

    print("=" * 60)
    print("SENTINEL-1 DIAGNOSTIC REQUEST")
    print("=" * 60)

    print("Bounding box:")
    print(BBOX)

    print()
    print("Date range:")
    print(f"{START_DATE} -> {END_DATE}")

    print()
    print(f"Output size: {WIDTH} x {HEIGHT}")

    print()
    print("Preparing request...")


    # --------------------------------------------------------
    # Evalscript
    # --------------------------------------------------------
    #
    # We deliberately request the RAW linear-power VV/VH
    # values here.
    #
    # We do NOT convert to dB yet.
    #
    # That makes this a data diagnostic rather than a
    # visualization test.
    #

    evalscript = """
//VERSION=3

function setup() {

    return {

        input: [{
            bands: [
                "VV",
                "VH",
                "dataMask"
            ],

            units: "LINEAR_POWER"
        }],

        output: {

            bands: 3,

            sampleType: "FLOAT32"
        }
    };
}


function evaluatePixel(sample) {

    return [

        sample.VV,

        sample.VH,

        sample.dataMask

    ];
}
"""


    # --------------------------------------------------------
    # Process API request
    # --------------------------------------------------------

    request_body = {

        "input": {

            "bounds": {

                "bbox": BBOX,

                "properties": {

                    "crs":
                        "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                }
            },


            "data": [

                {

                    "type":
                        "sentinel-1-grd",


                    "dataFilter": {

                        "timeRange": {

                            "from":
                                f"{START_DATE}T00:00:00Z",

                            "to":
                                f"{END_DATE}T23:59:59Z"
                        },


                        "acquisitionMode":
                            "IW",


                        "mosaickingOrder":
                            "mostRecent"
                    },


                    "processing": {

                        "orthorectify":
                            "true"
                    }
                }

            ]
        },


        "output": {

            "width": WIDTH,

            "height": HEIGHT,


            "responses": [

                {

                    "identifier":
                        "default",


                    "format": {

                        "type":
                            "image/tiff"
                    }
                }

            ]
        },


        "evalscript":
            evalscript
    }


    # --------------------------------------------------------
    # Send request
    # --------------------------------------------------------

    print()
    print("Sending request to Process API...")
    print("Waiting for response...")

    started = time.perf_counter()


    try:

        response = oauth.post(

            PROCESS_URL,

            json=request_body,

            timeout=(20, 120)
        )


    except Exception as exc:

        elapsed = time.perf_counter() - started

        print()
        print(
            f"Request failed after "
            f"{elapsed:.2f} seconds."
        )

        print()
        print("Error:")
        print(exc)

        return False


    elapsed = time.perf_counter() - started


    # --------------------------------------------------------
    # Basic response information
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("API RESPONSE")
    print("=" * 60)

    print(
        f"HTTP status: {response.status_code}"
    )

    print(
        f"Response time: {elapsed:.2f} seconds"
    )

    print(
        "Content-Type:",
        response.headers.get("Content-Type")
    )

    print(
        "Response size:",
        f"{len(response.content):,}",
        "bytes"
    )


    # --------------------------------------------------------
    # Handle API errors
    # --------------------------------------------------------

    if not response.ok:

        print()
        print("THE API RETURNED AN ERROR")
        print("=" * 60)

        print(response.text[:5000])

        return False


    # --------------------------------------------------------
    # Save TIFF
    # --------------------------------------------------------

    OUTPUT_FILE.write_bytes(
        response.content
    )

    print()
    print("Request succeeded.")

    print(
        "Saved TIFF:",
        OUTPUT_FILE.resolve()
    )


    # ========================================================
    # 5. READ RETURNED DATA
    # ========================================================

    print()
    print("=" * 60)
    print("INSPECTING RETURNED PIXELS")
    print("=" * 60)


    try:

        data = tifffile.imread(
            OUTPUT_FILE
        )

    except Exception as exc:

        print()
        print("Could not read returned TIFF.")

        print("Error:")
        print(exc)

        return False


    print()
    print("Original array information:")

    print(
        "Shape:",
        data.shape
    )

    print(
        "Dtype:",
        data.dtype
    )


    # --------------------------------------------------------
    # Normalize array orientation
    # --------------------------------------------------------
    #
    # Depending on the TIFF representation, the array may be:
    #
    #     (3, height, width)
    #
    # or
    #
    #     (height, width, 3)
    #
    # We normalize it to:
    #
    #     (height, width, 3)
    #

    if (
        data.ndim == 3
        and data.shape[0] == 3
    ):

        data = np.moveaxis(
            data,
            0,
            -1
        )


    print()
    print(
        "Normalized shape:",
        data.shape
    )


    # --------------------------------------------------------
    # Check dimensions
    # --------------------------------------------------------

    if (
        data.ndim != 3
        or data.shape[-1] != 3
    ):

        print()
        print(
            "Unexpected TIFF layout."
        )

        print(
            "Expected three bands: "
            "VV, VH, dataMask"
        )

        return False


    # --------------------------------------------------------
    # Extract bands
    # --------------------------------------------------------

    vv = data[..., 0]

    vh = data[..., 1]

    data_mask = data[..., 2]


    # ========================================================
    # 6. VV STATISTICS
    # ========================================================

    print()
    print("-" * 60)
    print("VV STATISTICS")
    print("-" * 60)

    print(
        "Minimum:",
        np.nanmin(vv)
    )

    print(
        "Maximum:",
        np.nanmax(vv)
    )

    print(
        "Mean:",
        np.nanmean(vv)
    )

    print(
        "Non-zero pixels:",
        np.count_nonzero(vv)
    )

    print(
        "Total pixels:",
        vv.size
    )


    # ========================================================
    # 7. VH STATISTICS
    # ========================================================

    print()
    print("-" * 60)
    print("VH STATISTICS")
    print("-" * 60)

    print(
        "Minimum:",
        np.nanmin(vh)
    )

    print(
        "Maximum:",
        np.nanmax(vh)
    )

    print(
        "Mean:",
        np.nanmean(vh)
    )

    print(
        "Non-zero pixels:",
        np.count_nonzero(vh)
    )

    print(
        "Total pixels:",
        vh.size
    )


    # ========================================================
    # 8. DATA MASK
    # ========================================================

    print()
    print("-" * 60)
    print("DATA MASK")
    print("-" * 60)

    print(
        "Minimum:",
        np.nanmin(data_mask)
    )

    print(
        "Maximum:",
        np.nanmax(data_mask)
    )

    valid_pixels = np.count_nonzero(
        data_mask > 0
    )

    total_pixels = data_mask.size

    print(
        "Valid pixels:",
        valid_pixels
    )

    print(
        "Total pixels:",
        total_pixels
    )

    print(
        "Valid percentage:",
        f"{100 * valid_pixels / total_pixels:.2f}%"
    )


    # ========================================================
    # 9. CONVERT VV/VH TO dB FOR INFORMATION
    # ========================================================

    print()
    print("=" * 60)
    print("VV/VH IN DECIBELS")
    print("=" * 60)


    # Avoid log10(0).
    vv_safe = np.maximum(
        vv,
        1e-10
    )

    vh_safe = np.maximum(
        vh,
        1e-10
    )


    vv_db = (
        10.0 *
        np.log10(vv_safe)
    )

    vh_db = (
        10.0 *
        np.log10(vh_safe)
    )


    print()
    print("VV dB:")
    print(
        "  Minimum:",
        np.nanmin(vv_db)
    )

    print(
        "  Maximum:",
        np.nanmax(vv_db)
    )

    print(
        "  Mean:",
        np.nanmean(vv_db)
    )


    print()
    print("VH dB:")
    print(
        "  Minimum:",
        np.nanmin(vh_db)
    )

    print(
        "  Maximum:",
        np.nanmax(vh_db)
    )

    print(
        "  Mean:",
        np.nanmean(vh_db)
    )


    # ========================================================
    # 10. FINAL DIAGNOSTIC
    # ========================================================

    print()
    print("=" * 60)
    print("DIAGNOSTIC RESULT")
    print("=" * 60)


    if valid_pixels == 0:

        print(
            "NO VALID PIXELS WERE RETURNED."
        )

        print()
        print(
            "The API request succeeded, but there "
            "does not appear to be usable Sentinel-1 "
            "data for this request."
        )

        return False


    if (
        np.count_nonzero(vv) == 0
        or np.count_nonzero(vh) == 0
    ):

        print(
            "VV or VH contains only zero values."
        )

        return False


    print(
        "VALID SENTINEL-1 DATA RECEIVED."
    )

    print()
    print(
        "The API, authentication, area, and "
        "Sentinel-1 request are working."
    )

    print()
    print(
        "The next step is visualization/"
        "preprocessing rather than API debugging."
    )

    return True


# ============================================================
# 11. MAIN
# ============================================================

def main():

    print()
    print("#" * 60)
    print("# SENTINEL-1 MINIMAL DIAGNOSTIC")
    print("#" * 60)
    print()


    oauth = authenticate()


    success = download_sentinel1(
        oauth
    )


    print()
    print("#" * 60)

    if success:

        print(
            "SENTINEL-1 TEST PASSED"
        )

    else:

        print(
            "SENTINEL-1 TEST DID NOT PASS"
        )

    print("#" * 60)


if __name__ == "__main__":

    main()
