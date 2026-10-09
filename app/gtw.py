import requests
import re
import base64
import struct
import logging
import argparse
from sys import exit
from os import getenv
from urllib.parse import urlparse, parse_qs, unquote, unquote_plus, quote
from flask import Flask, request, render_template_string, redirect

# (connect, read) timeout for every outgoing request
REQUEST_TIMEOUT = (3, 5)

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
    <title>Not a Google Maps Link!</title>
    <link rel="icon" href="https://cdnjs.cloudflare.com/ajax/libs/emojione/2.2.7/assets/png/1f30d.png" type="image/png">
    <!-- Include Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f4f4f9;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            color: #333;
        }
        .card {
            max-width: 600px;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .btn-outline-primary {
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="card bg-white text-center">
        <h1 class="text-danger">Not a Google Maps Link!</h1>
        <p class="lead">
            Looks like you gave me the wrong link. Right now, I can only handle Google Maps URLs. 
            Let’s keep it simple and straightforward.
        </p>
        <p>
            If you have ideas to improve this or want to help, feel free to contribute:
        </p>
        <a href="https://github.com/papko26/google-link-to-waze" target="_blank" class="btn btn-outline-primary">
            Visit the GitHub Repository
        </a>
        <a href="/" class="btn btn-outline-secondary">
            Return to Main Page
        </a>
    </div>

    <!-- Optional: Include Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
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
    <link rel="icon" href="https://cdnjs.cloudflare.com/ajax/libs/emojione/2.2.7/assets/png/1f30d.png" type="image/png">
    <!-- Include Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
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
        .card {
            max-width: 600px;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .btn-outline-primary {
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="card bg-white text-center">
        <h1 class="text-danger">Oops, Something Went Wrong!</h1>
        <p class="lead">
            We couldn't find a location in this link. Maybe Google has changed something again,
            or this kind of link is not supported yet.
        </p>
        <p>
            Please help us fix it: open an issue on GitHub and paste the link you used.
            If you don't know how to do that, just send the link to
            <a href="https://t.me/papko26" target="_blank">@papko26</a> on Telegram.
        </p>
        <a href="https://github.com/papko26/google-link-to-waze/issues/new" target="_blank" class="btn btn-outline-primary">
            Open an Issue on GitHub
        </a>
        <a href="https://t.me/papko26" target="_blank" class="btn btn-outline-primary">
            Message on Telegram
        </a>
        <a href="/" class="btn btn-outline-secondary">
            Return to Main Page
        </a>
    </div>

    <!-- Optional: Include Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

HTML_SHARE_GOOGLE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>share.google Links Are Not Supported</title>
    <link rel="icon" href="https://cdnjs.cloudflare.com/ajax/libs/emojione/2.2.7/assets/png/1f30d.png" type="image/png">
    <!-- Include Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f4f4f9;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            color: #333;
        }
        .card {
            max-width: 600px;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .btn-outline-primary {
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="card bg-white text-center">
        <h1 class="text-warning">Sorry, share.google Links Are Not Supported</h1>
        <p class="lead">
            Google does not let us handle share.google links properly: they hide the location
            behind a page that only works in a browser, so there is nothing we can send to Waze.
        </p>
        <p>
            Open the link in Google Maps, tap <strong>Share</strong> and copy the link from there
            (it starts with maps.app.goo.gl). That one will work.
        </p>
        <a href="/" class="btn btn-outline-primary">
            Return to Main Page
        </a>
    </div>

    <!-- Optional: Include Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

HTML_ROUTE_NO_DESTINATION = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>This Route Has No Destination</title>
    <link rel="icon" href="https://cdnjs.cloudflare.com/ajax/libs/emojione/2.2.7/assets/png/1f30d.png" type="image/png">
    <!-- Include Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f4f4f9;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            color: #333;
        }
        .card {
            max-width: 600px;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .btn-outline-primary {
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="card bg-white text-center">
        <h1 class="text-warning">This Route Has No Destination</h1>
        <p class="lead">
            You shared a route, but Google put only the starting point into the link,
            so there is nowhere to send Waze.
        </p>
        <p>
            Open the destination itself in Google Maps (the place or the dropped pin, not the route),
            tap <strong>Share</strong> and paste that link here.
        </p>
        <a href="/" class="btn btn-outline-primary">
            Return to Main Page
        </a>
    </div>

    <!-- Optional: Include Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
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
    <link rel="icon" href="https://cdnjs.cloudflare.com/ajax/libs/emojione/2.2.7/assets/png/1f30d.png" type="image/png">
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

    <!-- Contribution Section -->
    <div class="card shadow mt-4">
        <div class="card-body text-center"> <!-- Center align content -->
            <h5 class="card-title">Contribute</h5>
            <p class="card-text">
                Have ideas to make this better? Check out the project on GitHub and share your suggestions or improvements:
            </p>
            <a href="https://github.com/papko26/google-link-to-waze" target="_blank" class="btn btn-outline-primary">
                View Repo
            </a>
        </div>
    </div>
</div>

<!-- DigitalOcean Badge Section -->
<div class="container text-center mt-4">
    <a href="https://www.digitalocean.com/?refcode=6ca39966c289&utm_campaign=Referral_Invite&utm_medium=Referral_Program&utm_source=badge">
        <img src="https://web-platforms.sfo2.cdn.digitaloceanspaces.com/WWW/Badge%202.svg" alt="DigitalOcean Referral Badge" />
    </a>
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
        const spinner = document.querySelector('.spinner-overlay');
        spinner.style.display = 'flex';

        // Simulate a redirect check
        setTimeout(() => {
            // Redirect condition
            if (document.readyState === "complete") {
                stopSpinnerAndRedirect();
            }
        }, 3000);
    }

    // Function to stop spinner and redirect to root
    function stopSpinnerAndRedirect() {
        const spinner = document.querySelector('.spinner-overlay');
        spinner.style.display = 'none';
        window.location.href = '/'; // Redirect to root
    }
</script>

</body>
</html>
"""


def places_api_parse_cid(shitty_link):
    try:
        # Regex pattern to match latitude and longitude pairs
        logger.debug("places_api_parse_cid: Now will try resolve it as Google Place")
        logger.debug(shitty_link)
        # maps.google.com/?cid=<decimal>
        cid_param = parse_qs(urlparse(shitty_link).query).get("cid")
        if cid_param and cid_param[0].isdigit():
            logger.debug(f"cid is: {cid_param[0]}")
            return int(cid_param[0])
        patterns = [r"ftid.*:(\w+)",r"/data=.*0x(\w+)"]
        for pattern in patterns:
            match = re.search(pattern, shitty_link)
            if match:
                # Extract cid in hex
                cid_hex = match.groups()[0]
                logger.debug(f"cid hex is: {cid_hex}")
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
    1. Check if the URL length does not exceed 2048 characters.
    2. Add 'https://' if no scheme is provided.
    3. Validate the URL format.
    4. Check if the URL contains 'googl' (case-insensitive) or matches known Google domains.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if the URL is valid and matches the criteria, False otherwise.
    """
    if not url:
        logger.debug("No url")
        return False
    try: 
        # Step 0: Check length
        if len(url) > 2048:
            logger.debug(f"url is too long: {url}")
            return False

        # Step 1: Add 'https://' if no scheme is provided
        if not urlparse(url).scheme:
            url = f"https://{url}"

        parsed = urlparse(url)
        domain_pattern = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
        if not domain_pattern.match(parsed.netloc):
            logger.error(f"url did not mathed regex: {url}")
            return False

        # Step 2: Validate URL format
        parsed = urlparse(url)
        if not parsed.netloc or not parsed.scheme:
            logger.error(f"url did not mathed netloc/scheme: {url}")
            return False
        
    except Exception as e:
        logger.debug(f"{url}:{e}")
        return False

    # Step 3: Check domain against allowlist
    valid_google_domains = ["maps.app.goo.gl", "maps.google.com", "www.google.com", "google.com", "goo.gl"]
    netloc = parsed.netloc.lower()
    if not any(netloc == d or netloc.endswith("." + d) for d in valid_google_domains):
        logger.debug(f"url domain not in allowed list: {netloc}")
        return False

    return True

def normalize_user_input(text):
    """
    Users paste whatever their messenger copied: "Place name https://maps.app.goo.gl/xyz",
    links without scheme, etc. Pick the link out of it and make sure it has a scheme.
    """
    if not text:
        return text
    text = text.strip()
    match = re.search(r"https?://\S+", text)
    if match:
        return match.group(0)
    if " " not in text and not urlparse(text).scheme:
        return f"https://{text}"
    return text


def is_share_google_link(url):
    # share.google/<id> resolves to www.google.com/share.google?q=<id>, a JS-only page without coordinates
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    return netloc in ("share.google", "www.share.google") or parsed.path.startswith("/share.google")


def valid_coords(latitude, longitude):
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return False
    # 0,0 is what google puts into "@0,0,22z" when it has no idea
    return -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0, 0)


def parse_direct_coordinates(encoded_string):
    # Define the regex pattern for both latitude and longitude, e.g. 34°59'09.4"N 33°54'00.1"E
    pattern = r"(\d+)°(\d+)'(\d+(?:\.\d+)?)\"([NS])[\s+,]*(\d+)°(\d+)'(\d+(?:\.\d+)?)\"([EW])"

    # Search for matches
    match = re.search(pattern, unquote(encoded_string))
    if not match:
        logger.debug("parse_direct_coordinates: no coordinates found")
        return None

    # Extract groups from the match
    (lat_deg, lat_min, lat_sec, lat_dir,
     lon_deg, lon_min, lon_sec, lon_dir) = match.groups()

    # Convert latitude to decimal degrees
    latitude = float(lat_deg) + float(lat_min) / 60 + float(lat_sec) / 3600
    if lat_dir == 'S':  # South means negative latitude
        latitude = -latitude

    # Convert longitude to decimal degrees
    longitude = float(lon_deg) + float(lon_min) / 60 + float(lon_sec) / 3600
    if lon_dir == 'W':  # West means negative longitude
        longitude = -longitude

    # Return the parsed coordinates in the desired format
    return {"latitude": f"{latitude:.6f}", "longitude": f"{longitude:.6f}"}


def get_coordinates_from_place_id(place_id, api_key):
    """
    Convert a Google Places ID to coordinates using the Places Details API.

    Args:
        place_id (str): The Google Places ID.
        api_key (str): Your Google API key.

    Returns:
        dict: A dictionary containing latitude and longitude, or None if failed.
    """
    if not place_id:
        return None
    try:
        # API endpoint for Places Details
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {"cid": place_id, "key": api_key}

        # Make the API request
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
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


def extract_coordinates_with_regex(url, last_resort=False):
    try:
        # Sometimes /places link may contain coordinates of the location, which
        # user browsed after he chosed the destination.
        # Lets ensure we will not try to parse it.
        # Same for /dir/ locations - it is google maps directions (route).
        if not url:
            logger.error("extract_crds: no url passed")
            return None
        # %2C instead of comma, %C2%B0 instead of °, etc.
        url = unquote(url)
        if not last_resort:
            if "°" in url:
                logger.info("extract_crds: passed ° symbol. Will try another regex")
                crds = parse_direct_coordinates(url)
                if crds:
                    return crds
            if "/place/" in url:
                # The place itself is stored as !3d<lat>!4d<lon> in the data part
                match = re.search(r"!3d([-+]?\d+\.\d+)!4d([-+]?\d+\.\d+)", url)
                if match and valid_coords(*match.groups()):
                    latitude, longitude = match.groups()
                    logger.debug(f"extract_crds: place coords {latitude}/{longitude}")
                    return {"latitude": latitude, "longitude": longitude}
            if "/place/" in url or "/dir/" in url:
                logger.debug("extract_crds: it is a 'places' or 'dir' link, parsing skipped")
                return None
            if is_route_url(url):
                logger.debug("extract_crds: it is a route link, parsing skipped")
                return None
        if last_resort:
            logger.info("extract_crds_last_resort: lemme try to find any coords no matter what")

        # Regex pattern to match latitude and longitude pairs, "lat,lon", "lat, lon" or "lat,+lon"
        pattern = r"([-+]?\d+\.\d+),[\s+]*([-+]?\d+\.\d+)"
        for match in re.finditer(pattern, url):
            # Extract latitude and longitude from groups
            latitude, longitude = match.groups()
            latitude = latitude.lstrip('+')
            longitude = longitude.lstrip('+')
            if valid_coords(latitude, longitude):
                logger.debug(f"extract_crds: {latitude}/{longitude}")
                return {"latitude": latitude, "longitude": longitude}
        logger.debug("extract_crds: failed to parse cords")
    except Exception as e:
        logger.error(f"Error extracting coordinates: {e}")
    return None


def waze_link_from_coords(crds):
    if crds:
        latitude = crds.get("latitude")
        longitude = crds.get("longitude")
        logger.info(f"waze_from_coords: Latitude: {latitude}, Longitude: {longitude}")
        if latitude and longitude:
            return f"https://ul.waze.com/ul?ll={latitude}%2C{longitude}&navigate=yes"
    return None


def search_query_from_url(url):
    """
    Last resort when google gives us no coordinates (plus codes, plain addresses,
    places unknown to Places API): take the human readable name out of the link.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("q", "query"):
        if params.get(key):
            return params[key][0]
    match = re.search(r"/maps/(?:place|search)/([^/]+)", parsed.path)
    if match:
        return unquote_plus(match.group(1))
    return None


def waze_link_from_query(query):
    if not query:
        return None
    logger.info(f"waze_from_query: {query}")
    # No navigate=yes here: let the user pick the right search result in Waze
    return f"https://ul.waze.com/ul?q={quote(query)}"


class RouteWithoutDestination(Exception):
    pass


def is_route_url(url):
    params = parse_qs(urlparse(url).query)
    return "saddr" in params or "daddr" in params


def decode_geocode_point(point):
    """
    One point of the geocode= param of route links: base64 protobuf with
    field 2 = lat * 1e6 and field 3 = lon * 1e6 (fixed32), places also carry ftid (fixed64).
    """
    try:
        data = base64.urlsafe_b64decode(point + "=" * (-len(point) % 4))
        fields, i = {}, 0
        while i < len(data):
            field, wire_type = data[i] >> 3, data[i] & 7
            i += 1
            if wire_type == 5:
                fields[field] = struct.unpack("<i", data[i:i + 4])[0]
                i += 4
            elif wire_type == 1:
                i += 8
            else:
                break
        latitude, longitude = fields[2] / 1e6, fields[3] / 1e6
    except Exception as e:
        logger.debug(f"decode_geocode_point: {point}: {e}")
        return None
    if not valid_coords(latitude, longitude):
        return None
    return {"latitude": f"{latitude:.6f}", "longitude": f"{longitude:.6f}"}


def route_destination(url, api_key):
    """
    Routes shared from the app look like maps?saddr=<start>&daddr=<destination>&geocode=<start>;<destination>&ftid=...
    saddr is usually where the user is right now, so never navigate there: use the last stop of the route.
    """
    params = parse_qs(urlparse(url).query)
    daddr = params.get("daddr", [""])[0]
    if not daddr:
        logger.error("route_destination: route without destination")
        raise RouteWithoutDestination()
    # multi-stop routes: "A to:B to:C"
    daddr = daddr.split(" to:")[-1]
    crds = extract_coordinates_with_regex(daddr, last_resort=True)
    if not crds:
        # geocode has a point per stop, the start goes first
        points = params.get("geocode", [""])[0].split(";")
        if len(points) > 1:
            crds = decode_geocode_point(points[-1])
    if not crds:
        logger.debug("route_destination: Trying places API")
        crds = get_coordinates_from_place_id(places_api_parse_cid(url), api_key)
    if crds:
        return waze_link_from_coords(crds)
    logger.info("route_destination: no coordinates, falling back to Waze search")
    return waze_link_from_query(daddr)


def resolve_url(url, max_hops=5):
    """
    Follow redirects of shortened links manually, so we never leave google domains.
    """
    for _ in range(max_hops):
        response = requests.head(url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
        location = response.headers.get("Location")
        if not response.is_redirect or not location:
            return url
        url = requests.compat.urljoin(url, location)
        if not is_valid_google_url(url):
            logger.error(f"resolve_url: redirected outside of google: {url}")
            return None
    return url


def get_wise_link(google_link: str, api_key):
    # Resolve the shortened URL
    resolved_url = resolve_url(google_link)
    if not resolved_url:
        return None
    logger.debug(f"get_wise_link: Resolved URL: {resolved_url}")
    if is_route_url(resolved_url):
        return route_destination(resolved_url, api_key)
    crds = extract_coordinates_with_regex(resolved_url)
    if not crds:
        logger.debug("get_wise_link: Trying places API")
        cid = places_api_parse_cid(resolved_url)
        crds = get_coordinates_from_place_id(cid, api_key)
    if not crds:
        crds = extract_coordinates_with_regex(resolved_url, last_resort=True)
    if not crds:
        waze_search = waze_link_from_query(search_query_from_url(resolved_url))
        if waze_search:
            logger.info("get_wise_link: no coordinates, falling back to Waze search")
            return waze_search
        logger.error("get_wise_link: Every attempt to get coordinates failed")
        return None

    # Extract coordinates from the path
    return waze_link_from_coords(crds)


@app.route("/", methods=["GET", "POST"])
def index():
    url = None
    if request.method == "POST":
        url = request.form.get("url")
    elif request.method == "GET":
        url = request.args.get("url")

    if not url:
        return render_template_string(HTML_TEMPLATE)

    user_input = url
    url = normalize_user_input(url)
    if is_share_google_link(url):
        logger.info("index: share.google link passed, not supported")
        return render_template_string(HTML_SHARE_GOOGLE)

    if not is_valid_google_url(url):
        # Not a link, but maybe plain coordinates copied from google maps
        crds = None
        if "/" not in user_input:
            crds = parse_direct_coordinates(user_input) or extract_coordinates_with_regex(user_input, last_resort=True)
        if crds:
            logger.debug("index: plain coordinates passed")
            return redirect(waze_link_from_coords(crds))
        logger.error("index: invalid url passed from user")
        return render_template_string(HTML_WRONG)

    logger.debug("index: trying fastrack")
    fasttrack = extract_coordinates_with_regex(url)
    if fasttrack:
        logger.debug("index: fastrack succsess")
        waze_lnk = waze_link_from_coords(fasttrack)
        return redirect(waze_lnk)

    logger.debug("index: trying default flow")
    try:
        wlink = get_wise_link(url, args.gcp_maps_api_key)
    except RouteWithoutDestination:
        return render_template_string(HTML_ROUTE_NO_DESTINATION)
    if wlink:
        logger.debug("index: default flow succsess")
        return redirect(wlink)

    logger.error("index: failed to provide a wize link")
    return render_template_string(HTML_BROKEN)


if __name__ == "__main__":
    args = parse_arguments()
    args.gcp_maps_api_key = get_google_api_key()
    logger.debug("Arguments parsed successfully.")
    app.run(host=args.addr, port=args.port)
