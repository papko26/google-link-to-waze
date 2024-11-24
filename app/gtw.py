import requests
import re
import logging
import argparse
from sys import exit
from os import getenv
from urllib.parse import urlparse
from flask import Flask, request, render_template_string, redirect

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def get_google_api_key():
    """
    Check if the GOOGLE_API_KEY environment variable is set.
    If set, return the key. If not, terminate the program.

    Returns:
        str: The value of the GOOGLE_API_KEY environment variable.
    """
    api_key = getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("Error: GOOGLE_API_KEY is not set.")
        exit(1)  # Exit the program with a non-zero status
    return api_key


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Script to translate Google Maps link to Waze"
    )
    parser.add_argument(
        "--addr",
        required=False,
        default="0.0.0.0",
        help="The address to host the web server",
    )
    parser.add_argument(
        "--port", required=False, default="5000", help="The port to host the web server"
    )
    return parser.parse_args()


app = Flask(__name__)

HTML_WRONG = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>It does not looks like a google link!</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f9;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            text-align: center;
            color: #333;
        }
        .container {
            max-width: 600px;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        h1 {
            font-size: 2em;
            color: #e63946;
        }
        p {
            font-size: 1.2em;
            margin: 10px 0;
        }
        a {
            color: #1d3557;
            text-decoration: none;
            font-weight: bold;
        }
        a:hover {
            text-decoration: underline;
        }
        .footer {
            margin-top: 20px;
            font-size: 0.9em;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>It does not looks like a google maps link!</h1>
        <p>
            Look like you gave me the wrong link. At the moment, I can only handle Google Maps.
            <br>
            <br>
            I’m not a frontend guru at all, so I’ll just send you this message to keep things moving.
        </p>
            <br>
        <p>BUT. If you have any ideas to improve this, you're welcome to contribute:</p>
        <p>
            <a href="https://github.com/papko26/google-link-to-waze" target="_blank">
                Visit the GitHub Repository
            </a>
        </p>
    </div>
</body>
</html>
"""

HTML_BROKEN = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oops, Something Went Wrong!</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f9;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            text-align: center;
            color: #333;
        }
        .container {
            max-width: 600px;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        h1 {
            font-size: 2em;
            color: #e63946;
        }
        p {
            font-size: 1.2em;
            margin: 10px 0;
        }
        a {
            color: #1d3557;
            text-decoration: none;
            font-weight: bold;
        }
        a:hover {
            text-decoration: underline;
        }
        .footer {
            margin-top: 20px;
            font-size: 0.9em;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Oops, Something Went Wrong!</h1>
        <p>
            It seems Google has changed something again, and things are broken. 
            Don’t worry, <strong>I'll let the team know</strong> to fix it as soon as possible.
        </p>
        <p>If you have any ideas to improve this, you're welcome to contribute:</p>
        <p>
            <a href="https://github.com/papko26/google-link-to-waze" target="_blank">
                Visit the GitHub Repository
            </a>
        </p>
    </div>
</body>
</html>
"""

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Open in Waze</title>
    <!-- Include Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        /* Center the spinner overlay */
        .spinner-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            display: none; /* Hidden by default */
        }
    </style>
</head>
<body class="bg-light">

<div class="container mt-5">
    <div class="card shadow">
        <div class="card-body">
            <h1 class="card-title text-center mb-4">Google Maps URL to Waze</h1>
            <form method="post" class="text-center" onsubmit="showSpinner()">
                <div class="mb-3">
                    <label for="url" class="form-label">Enter Google Maps URL:</label>
                    <input type="text" id="url" name="url" class="form-control" placeholder="Paste your Google Maps link here" required>
                </div>
                <button type="submit" class="btn btn-primary">Open In Waze</button>
            </form>
        </div>
    </div>
</div>

<!-- Spinner Overlay -->
<div class="spinner-overlay">
    <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Loading...</span>
    </div>
</div>

<!-- Optional: Include Bootstrap JS -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>

<script>
    // Function to show the spinner
    function showSpinner() {
        document.querySelector('.spinner-overlay').style.display = 'flex';
    }
</script>

    <div class="container">
        <p>If you have any ideas to improve this, you're welcome to contribute:</p>
        <p>
            <a href="https://github.com/papko26/google-link-to-waze" target="_blank">
                Visit the GitHub Repository
            </a>
    </div>

</body>
</html>
"""


def places_api_parse_cid(shitty_link):
    try:
        # Regex pattern to match latitude and longitude pairs
        logger.debug("places_api_parse_cid: Now will try resolve it as Google Place")
        logger.debug(shitty_link)
        pattern = r"ftid.*:(\w+)"
        match = re.search(pattern, shitty_link)
        if match:
            # Extract cid in hex
            cid_hex = match.groups()[0]
            logger.debug(f"cid hex is: {cid_hex}")
            if cid_hex:
                cid = hex_to_decimal(cid_hex)
                logger.debug(f"cid is: {cid}")
            return cid
    except Exception as e:
        logger.error(f"Error extracting cid: {e}")
    logger.error("places_api_parse_cid: failed to parse cid")
    return None


def hex_to_decimal(hex_string):
    # Convert using Python's int function with base 16
    try:
        return int(hex_string, 16)
    except ValueError:
        logger.error("Invalid hexadecimal string")
        return None
    
def is_valid_google_url(url: str) -> bool:
    """
    Validates the given URL based on the following criteria:
    1. Check if the URL length does not exceed 512 characters.
    2. Add 'https://' if no scheme is provided.
    3. Validate the URL format.
    4. Check if the URL contains 'googl' (case-insensitive) or matches known Google domains.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if the URL is valid and matches the criteria, False otherwise.
    """
    # Step 0: Check length
    if len(url) > 512:
        print(url)
        return False

    # Step 1: Add 'https://' if no scheme is provided
    if not urlparse(url).scheme:
        url = f"https://{url}"

    # Step 2: Validate URL format
    try:
        parsed = urlparse(url)
        if not parsed.netloc or not parsed.scheme:
            print(url)
            return False
    except Exception:
        print(url)
        return False

    # Step 3: Check for 'googl' or valid Google domains
    if "googl" not in url.lower():
        valid_google_domains = ["maps.app.goo.gl", "google.com", "goo.gl"]
        if not any(domain in parsed.netloc for domain in valid_google_domains):
            print(url)
            return False

    return True


def get_coordinates_from_place_id(place_id, api_key):
    """
    Convert a Google Places ID to coordinates using the Places Details API.

    Args:
        place_id (str): The Google Places ID.
        api_key (str): Your Google API key.

    Returns:
        dict: A dictionary containing latitude and longitude, or None if failed.
    """
    try:
        # API endpoint for Places Details
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {"cid": place_id, "key": api_key}

        # Make the API request
        response = requests.get(url, params=params)
        response_data = response.json()

        # Check the response status
        if response_data["status"] == "OK":
            # Extract geometry location
            location = response_data["result"]["geometry"]["location"]
            return {"latitude": location["lat"], "longitude": location["lng"]}
        else:
            raise ValueError(f"Places API Error: {response_data['status']}")

    except Exception as e:
        logger.error(f"Error resolving coordinates from Place ID: {e}")
        return None


def extract_coordinates_with_regex(url):
    try:
        # Regex pattern to match latitude and longitude pairs
        pattern = r".*?(\d\d\.\d\d\d+).*?(\d\d\.\d\d\d+)"
        match = re.search(pattern, url)
        if match:
            # Extract latitude and longitude from groups
            latitude, longitude = match.groups()
            return {"latitude": latitude, "longitude": longitude}
    except Exception as e:
        logger.error(f"Error extracting coordinates: {e}")
    return None


def waze_link_from_coords(crds):
    if crds:
        latitude = crds.get("latitude")
        longitude = crds.get("longitude")
        logger.info(f"Latitude: {latitude}, Longitude: {longitude}")
        if latitude and longitude:
            return f"https://ul.waze.com/ul?ll={latitude}%2C{longitude}&navigate=yes"
    else:
        return None


def get_wise_link(google_link: str, api_key):
    # Resolve the shortened URL

    response = requests.head(google_link, allow_redirects=True)
    resolved_url = response.url
    logger.debug(f"Resolved URL: {resolved_url}")
    crds = extract_coordinates_with_regex(resolved_url)
    if not crds:
        logger.debug("get_wise_link: Trying places API")
        cid = places_api_parse_cid(resolved_url)
        crds = get_coordinates_from_place_id(cid, api_key)
    if not crds:
        logger.error("get_wise_link: Every attempt to get coordinates failed")
        return None

    # Extract coordinates from the path
    return waze_link_from_coords(crds)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        if not is_valid_google_url(url):
            logger.error("index: invalid url passed from user")
            return render_template_string(HTML_WRONG)
        if url:
            logger.debug("index: trying fastrack")
            fasttrack = extract_coordinates_with_regex(url)
            if fasttrack:
                logger.debug("index: fastrack succsess")
                return waze_link_from_coords(fasttrack)

            logger.debug("index: trying default flow")
            wlink = get_wise_link(url, args.gcp_maps_api_key)
            if wlink:
                # Redirect the user to the generated Google Maps link
                logger.debug("index: default flow succsess")
                return redirect(wlink)
            else:
                logger.error("index: failed to provide a wize link")
                return render_template_string(HTML_BROKEN)
    # Render the form if no POST data
    return render_template_string(HTML_TEMPLATE)


if __name__ == "__main__":
    args = parse_arguments()
    args.gcp_maps_api_key = get_google_api_key()
    logger.debug("Arguments parsed successfully.")
    app.run(host=args.addr, port=args.port)