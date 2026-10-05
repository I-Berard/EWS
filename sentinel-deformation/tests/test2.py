import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from oauthlib.oauth2 import BackendApplicationClient
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


# Very small test area around Kigali
BBOX = [
    30.05,   # min longitude
    -1.98,   # min latitude
    30.07,   # max longitude
    -1.96,   # max latitude
]

# Only one day for the first test
START_DATE = "2026-09-25"
END_DATE = "2026-09-26"

# Keep the output tiny
WIDTH = 256
HEIGHT = 256

OUTPUT_FILE = Path("sentinel2_test.png")


# ============================================================
# AUTHENTICATION
# ============================================================

def authenticate():
    print("1. Authenticating with Copernicus Data Space...")

    client = BackendApplicationClient(
        client_id=CLIENT_ID
    )

    oauth = OAuth2Session(
        client=client
    )

    started = time.perf_counter()

    token = oauth.fetch_token(
        token_url=TOKEN_URL,
        client_secret=CLIENT_SECRET,
        include_client_id=True,
    )

    elapsed = time.perf_counter() - started

    print(f"   Authentication successful ({elapsed:.2f}s)")
    print(f"   Token type: {token.get('token_type')}")
    print()

    return oauth


# ============================================================
# SENTINEL-2 TEST
# ============================================================

def test_sentinel2(oauth):

    print("2. Building tiny Sentinel-2 request...")

    evalscript = """
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

    request_body = {
        "input": {
            "bounds": {
                "bbox": BBOX,
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                }
            },

            "data": [
                {
                    "type": "sentinel-2-l2a",

                    "dataFilter": {
                        "timeRange": {
                            "from": f"{START_DATE}T00:00:00Z",
                            "to": f"{END_DATE}T23:59:59Z"
                        },

                        "mosaickingOrder": "leastCC"
                    }
                }
            ]
        },

        "output": {
            "width": WIDTH,
            "height": HEIGHT,

            "responses": [
                {
                    "identifier": "default",

                    "format": {
                        "type": "image/png"
                    }
                }
            ]
        },

        "evalscript": evalscript
    }

    print("   Endpoint:", PROCESS_URL)
    print("   BBOX:", BBOX)
    print("   Dates:", START_DATE, "->", END_DATE)
    print(f"   Size: {WIDTH} x {HEIGHT}")
    print()

    print("3. Sending request...")
    print("   Waiting for Process API response...")

    started = time.perf_counter()

    try:
        response = oauth.post(
            PROCESS_URL,
            json=request_body,

            # 20 seconds to establish connection,
            # 120 seconds maximum waiting for response.
            timeout=(20, 120)
        )

    except requests.exceptions.Timeout:
        elapsed = time.perf_counter() - started

        print()
        print(f"TIMEOUT after {elapsed:.1f} seconds.")
        print()
        print(
            "The request reached the network layer but "
            "did not complete within the timeout."
        )

        return False

    except requests.exceptions.RequestException as exc:
        elapsed = time.perf_counter() - started

        print()
        print(f"REQUEST ERROR after {elapsed:.1f} seconds:")
        print(exc)

        return False

    elapsed = time.perf_counter() - started

    print()
    print(f"4. Response received in {elapsed:.2f} seconds")
    print("   HTTP status:", response.status_code)
    print("   Content-Type:", response.headers.get("Content-Type"))
    print("   Response size:", f"{len(response.content):,}", "bytes")
    print()

    if not response.ok:

        print("SERVER RETURNED AN ERROR:")
        print()

        print(response.text[:5000])

        return False

    # ========================================================
    # SAVE IMAGE
    # ========================================================

    OUTPUT_FILE.write_bytes(response.content)

    print("SUCCESS!")
    print()
    print("Sentinel-2 image saved to:")
    print(OUTPUT_FILE.resolve())

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("COPERNICUS DATA SPACE - MINIMAL SENTINEL-2 TEST")
    print("=" * 60)
    print()

    oauth = authenticate()

    success = test_sentinel2(oauth)

    print()
    print("=" * 60)

    if success:
        print("TEST PASSED")
    else:
        print("TEST FAILED")

    print("=" * 60)


if __name__ == "__main__":
    main()
