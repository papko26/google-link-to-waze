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
    # issue #5 and other failures from production logs
    ("https://www.google.com/maps/search/?api=1&query=-22.795714194709404%2C-46.33673284202814", "ll:-22.7957,-46.3367"),
    ("https://www.google.com/maps/search/-16.604401,+-49.214156?entry=tts", "ll:-16.6044,-49.2141"),
    ("https://www.google.com/maps/search/34%C2%B0N", "q"),
    ("34°59'09.4\"N 33°54'00.1\"E", "ll:34.9859,33.9000"),
    ("34.98, 33.95", "ll:34.98,33.95"),
    ("google.com/maps?q=34.98,33.95&entry=gps", "ll:34.98,33.95"),
    ("Lietuva · Saulius https://maps.app.goo.gl/Crj1o13NznuE5fZn8?g_st=iw", "ll:60.347,5.29"),
    ("https://maps.google.com/maps?q=4VFV+586+Archagas+House,+C.+Piedra+Ancha&ftid=0x8f6fa564b2b9b215:0x3847536924ebaa87", "q"),
    ("https://www.google.com/maps/place//@0,0,22z?utm_campaign=ml-ardl", "broken"),
    # Places API
    ("https://www.google.com/maps/place/Eiffel+Tower/data=!4m2!3m1!1s0x47e66e2964e34e2d:0x8ddca9ee380ef7e0", "ll:48.858,2.294"),
    ("https://maps.google.com/?cid=10222232094831998944", "ll:48.858,2.294"),
    ("https://maps.app.goo.gl/91jma2zHp9mWgG6M6", "ll:45.54,11.57"),
    ("https://maps.app.goo.gl/5A5xc4qnSdL8DcVp6", "ll:41.90,12.45"),
    # regular links
    ("https://maps.app.goo.gl/5a2iNmeLGDpY9gc36", "ll:-6.6398,106.774"),
    ("maps.app.goo.gl/Crj1o13NznuE5fZn8", "ll:60.347,5.29"),
    ("https://www.google.com/maps/@34.9876,33.9001,15z", "ll:34.9876,33.9001"),
    # share.google
    ("https://share.google/6qgJzt7fxpp8bzbNZ", "share"),
    ("share.google/6qgJzt7fxpp8bzbNZ", "share"),
    ("Cafe https://share.google/6qgJzt7fxpp8bzbNZ", "share"),
    # rejects
    ("https://evil.com/maps/@34.1,33.1", "wrong"),
    ("http://localhost:5000/", "wrong"),
    ("http://169.254.169.254/latest/meta-data", "wrong"),
    ("Kai Garden Residences by DMCI Homes, Mandaluyong City", "wrong"),
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
