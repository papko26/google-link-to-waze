"""
End-to-end checks against a running instance, real Google and real Places API.
    GTW_BASE_URL=https://waze.papko.org pytest -m smoke
nginx allows 1 request per second per IP, so requests are spaced out.
"""
import os
import time

import pytest
import requests

BASE_URL = os.getenv("GTW_BASE_URL")
DELAY = 1.3

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not BASE_URL, reason="GTW_BASE_URL is not set"),
]

TITLES = {
    "share": "share.google Links Are Not Supported",
    "wrong": "Not a Google Maps Link!",
    "broken": "Oops, Something Went Wrong!",
}

# (input, expected): "ll:<lat prefix>,<lon prefix>" | "q" | "share" | "wrong" | "broken"
CASES = [
    # link formats
    ("https://www.google.com/maps/search/?api=1&query=-12.345678912345678%2C-45.67891234567891", "ll:-12.3456,-45.6789"),
    ("https://www.google.com/maps/search/-11.111111,+-22.222222?entry=tts", "ll:-11.1111,-22.2222"),
    ("https://www.google.com/maps/search/34%C2%B0N", "q"),
    ("10°10'10.0\"N 20°20'20.0\"E", "ll:10.1694,20.3388"),
    ("10.12, 20.34", "ll:10.12,20.34"),
    ("google.com/maps?q=10.12,20.34&entry=gps", "ll:10.12,20.34"),
    ("Example Cafe · Someone https://maps.app.goo.gl/rh9XcEKq1bc5G3nS9?g_st=it", "ll:41.890,12.492"),
    ("https://maps.google.com/maps?q=9C3X+2W+Example+House,+Example+St&ftid=0x1111111111111111:0x2222222222222222", "q"),
    ("https://www.google.com/maps/place//@0,0,22z?utm_campaign=ml-ardl", "broken"),
    # Places API
    ("https://www.google.com/maps/place/Eiffel+Tower/data=!4m2!3m1!1s0x47e66e2964e34e2d:0x8ddca9ee380ef7e0", "ll:48.858,2.294"),
    ("https://maps.google.com/?cid=10222232094831998944", "ll:48.858,2.294"),
    ("https://maps.app.goo.gl/rh9XcEKq1bc5G3nS9?g_st=it", "ll:41.890,12.492"),
    # route, the destination is used; the redirect is longer than 512 characters
    ("https://maps.app.goo.gl/5EPDonpF1VgktnWx9?g_st=it", "ll:41.890,12.492"),
    # regular links
    ("https://maps.app.goo.gl/WfN845QbZ6LzPPv79?g_st=it", "ll:34.9799,33.9446"),
    ("maps.app.goo.gl/WfN845QbZ6LzPPv79", "ll:34.9799,33.9446"),
    ("https://www.google.com/maps/@10.1234,20.5678,15z", "ll:10.1234,20.5678"),
    # share.google
    ("https://share.google/XyZ12abCDef34GhIj", "share"),
    ("share.google/XyZ12abCDef34GhIj", "share"),
    ("Cafe https://share.google/XyZ12abCDef34GhIj", "share"),
    # rejects
    ("https://evil.com/maps/@34.1,33.1", "wrong"),
    ("http://localhost:5000/", "wrong"),
    ("http://169.254.169.254/latest/meta-data", "wrong"),
    ("Example Residences by Example Homes, Example City", "wrong"),
]


def call(method, url, retries=3):
    for attempt in range(retries):
        time.sleep(DELAY)
        kwargs = {"params": {"url": url}} if method == "GET" else {"data": {"url": url}}
        r = requests.request(method, BASE_URL, allow_redirects=False, timeout=20, **kwargs)
        # 503 is nginx rate limiting, 502 is the app still starting after deploy
        if r.status_code not in (502, 503):
            return r
        time.sleep(DELAY * (attempt + 2))
    return r


def test_main_page():
    r = call("GET", "")
    assert r.status_code == 200 and "Google Maps URL to Waze" in r.text


# Every case via GET, coordinate cases via the form (POST) as well
PARAMS = [
    pytest.param(method, url, expected, id=f"{method}-{i:02d}-{expected}")
    for i, (url, expected) in enumerate(CASES)
    for method in ("GET", "POST")
    if method == "GET" or expected.startswith("ll:")
]


@pytest.mark.parametrize("method, url, expected", PARAMS)
def test_link(method, url, expected):
    r = call(method, url)
    location = r.headers.get("Location", "")
    if expected.startswith("ll:"):
        lat, lon = expected[3:].split(",")
        assert r.status_code == 302, r.text[:200]
        assert location.startswith(f"https://ul.waze.com/ul?ll={lat}") and f"%2C{lon}" in location, location
    elif expected == "q":
        assert r.status_code == 302 and location.startswith("https://ul.waze.com/ul?q="), location
    else:
        assert r.status_code == 200
        assert f"<title>{TITLES[expected]}</title>" in r.text
