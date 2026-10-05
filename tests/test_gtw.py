"""
Offline tests: no network, requests.head/get are faked.
Most inputs are real links that failed in production logs.
"""
import pytest

import gtw


class FakeHead:
    def __init__(self, location=None):
        self.headers = {"Location": location} if location else {}
        self.is_redirect = location is not None


class FakeGet:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


@pytest.fixture
def fake_net(monkeypatch):
    """
    redirects: {url: location} served by requests.head, anything else is a final page.
    places: {cid: (lat, lon)} served by Places API, anything else is NOT_FOUND.
    """
    redirects, places, calls = {}, {}, {"head": [], "places": []}

    def head(url, **kwargs):
        calls["head"].append(url)
        assert kwargs.get("timeout"), "requests.head without timeout"
        assert kwargs.get("allow_redirects") is False
        return FakeHead(redirects.get(url))

    def get(url, params=None, **kwargs):
        calls["places"].append(params["cid"])
        assert kwargs.get("timeout"), "requests.get without timeout"
        if params["cid"] in places:
            lat, lon = places[params["cid"]]
            return FakeGet({"status": "OK", "result": {"geometry": {"location": {"lat": lat, "lng": lon}}}})
        return FakeGet({"status": "NOT_FOUND"})

    monkeypatch.setattr(gtw.requests, "head", head)
    monkeypatch.setattr(gtw.requests, "get", get)
    return redirects, places, calls


def waze_ll(lat, lon):
    return f"https://ul.waze.com/ul?ll={lat}%2C{lon}&navigate=yes"


# --- coordinates parsing ---

@pytest.mark.parametrize("url, expected", [
    # issue #5: url-encoded comma
    ("https://www.google.com/maps/search/?api=1&query=-12.345678912345678%2C-45.67891234567891",
     ("-12.345678912345678", "-45.67891234567891")),
    # "+-" before negative longitude
    ("https://www.google.com/maps/search/-11.111111,+-22.222222?entry=tts", ("-11.111111", "-22.222222")),
    ("https://www.google.com/maps/@10.1234,20.5678,15z", ("10.1234", "20.5678")),
    ("https://www.google.com/maps?q=10.12, 20.34", ("10.12", "20.34")),
    # place: real coordinates from !3d!4d, not the "@" viewport
    ("https://www.google.com/maps/place/X/@50.1234567,8.1234567,17z/data=!3m1!4b1!4m6!3m5!1s0x1:0x2!8m2!3d50.1234567!4d8.1239876",
     ("50.1234567", "8.1239876")),
    # DMS, encoded and not
    ("https://www.google.com/maps/place/10%C2%B010'10.0%22N+20%C2%B020'20.0%22E", ("10.169444", "20.338889")),
])
def test_extract_coordinates(url, expected):
    crds = gtw.extract_coordinates_with_regex(url)
    assert (crds["latitude"], crds["longitude"]) == expected


@pytest.mark.parametrize("url", [
    "https://www.google.com/maps/place/X/@34.1,33.1,17z",   # viewport only, needs Places API
    "https://www.google.com/maps/dir/A/B/@41.91,12.48,14z",  # route
    "https://www.google.com/maps/@0.0,0.0,22z",              # google has no idea
    "https://www.google.com/maps/@95.1,33.1,15z",            # out of range
    "https://www.google.com/maps/search/34%C2%B0N",          # broken DMS used to raise HTTP 500
    "",
])
def test_extract_coordinates_none(url):
    assert gtw.extract_coordinates_with_regex(url) is None


def test_extract_coordinates_last_resort_skips_invalid_pairs():
    url = "https://www.google.com/maps/place/X/@0.0,0.0,22z/foo/@34.1,33.2"
    assert gtw.extract_coordinates_with_regex(url, last_resort=True) == {"latitude": "34.1", "longitude": "33.2"}


@pytest.mark.parametrize("text, expected", [
    ("10°10'10.0\"N 20°20'20.0\"E", {"latitude": "10.169444", "longitude": "20.338889"}),
    ("12°20'44.4\"S+45°40'44.5\"W", {"latitude": "-12.345667", "longitude": "-45.679028"}),
    ("no coordinates here", None),
])
def test_parse_direct_coordinates(text, expected):
    assert gtw.parse_direct_coordinates(text) == expected


# --- input handling ---

@pytest.mark.parametrize("text, expected", [
    ("Example Cafe · Someone https://maps.app.goo.gl/AbCdEfGhIjKlMnOpQ?g_st=iw",
     "https://maps.app.goo.gl/AbCdEfGhIjKlMnOpQ?g_st=iw"),
    ("  maps.app.goo.gl/abc  ", "https://maps.app.goo.gl/abc"),
    ("https://maps.app.goo.gl/abc", "https://maps.app.goo.gl/abc"),
    ("Example Residences, Example City", "Example Residences, Example City"),
])
def test_normalize_user_input(text, expected):
    assert gtw.normalize_user_input(text) == expected


@pytest.mark.parametrize("url, valid", [
    ("https://maps.app.goo.gl/abc", True),
    ("https://www.google.com/maps/@34.1,33.1,15z", True),
    ("https://maps.google.com/?cid=1", True),
    ("google.com/maps?q=10.12,20.34", True),
    ("https://consent.google.com/x", True),
    ("https://evil.com/maps/@34.1,33.1", False),
    ("https://google.com.evil.com/", False),
    ("https://evilgoogle.com/", False),
    ("http://localhost:5000/", False),
    ("http://169.254.169.254/latest/meta-data", False),
    ("https://maps.app.goo.gl/" + "a" * 2100, False),
    ("", False),
])
def test_is_valid_google_url(url, valid):
    assert gtw.is_valid_google_url(url) is valid


@pytest.mark.parametrize("url, expected", [
    ("https://share.google/XyZ12abCDef34GhIj", True),
    ("https://SHARE.GOOGLE/abc", True),
    ("https://www.google.com/share.google?q=XyZ12abCDef34GhIj", True),
    ("https://maps.app.goo.gl/abc", False),
])
def test_is_share_google_link(url, expected):
    assert gtw.is_share_google_link(url) is expected


@pytest.mark.parametrize("url, expected", [
    ("https://maps.google.com/maps?cid=12345678901234567890", 12345678901234567890),
    ("https://maps.google.com/maps?q=X&ftid=0x1111111111111111:0x2222222222222222", 0x2222222222222222),
    ("https://www.google.com/maps/place/X/data=!4m2!3m1!1s0x47e66e2964e34e2d:0x8ddca9ee380ef7e0", 0x8ddca9ee380ef7e0),
    ("https://www.google.com/maps/search/foo", None),
])
def test_places_api_parse_cid(url, expected):
    assert gtw.places_api_parse_cid(url) == expected


@pytest.mark.parametrize("url, expected", [
    ("https://maps.google.com/maps?q=9C3X+2W+Example+House,+Example+St&ftid=0x1:0x2",
     "9C3X 2W Example House, Example St"),
    ("https://www.google.com/search?q=entrance+1+example+mall&ie=UTF-8", "entrance 1 example mall"),
    ("https://www.google.com/maps/place/%D0%B2%D1%83%D0%BB%D0%B8%D1%86%D1%8F+7/data=!4m2", "вулиця 7"),
    ("https://www.google.com/maps/place//@0,0,22z", None),
])
def test_search_query_from_url(url, expected):
    assert gtw.search_query_from_url(url) == expected


# --- network flows (faked) ---

def test_resolve_url_follows_google_redirects(fake_net):
    redirects, _, _ = fake_net
    redirects["https://maps.app.goo.gl/x"] = "https://www.google.com/maps/place/A"
    redirects["https://www.google.com/maps/place/A"] = "/maps/place/B"
    assert gtw.resolve_url("https://maps.app.goo.gl/x") == "https://www.google.com/maps/place/B"


def test_resolve_url_does_not_leave_google(fake_net):
    redirects, _, calls = fake_net
    redirects["https://maps.app.goo.gl/x"] = "http://169.254.169.254/latest/meta-data"
    assert gtw.resolve_url("https://maps.app.goo.gl/x") is None
    assert calls["head"] == ["https://maps.app.goo.gl/x"]


def test_places_api_not_called_without_cid(fake_net):
    _, _, calls = fake_net
    assert gtw.get_coordinates_from_place_id(None, "key") is None
    assert calls["places"] == []


def get(client, url):
    return client.get("/", query_string={"url": url})


def test_index_form(client):
    r = client.get("/")
    assert r.status_code == 200 and b"Google Maps URL to Waze" in r.data


def test_index_issue_5_short_link(client, fake_net):
    redirects, _, calls = fake_net
    redirects["https://maps.app.goo.gl/pin"] = (
        "https://www.google.com/maps/search/?api=1&query=-12.345678912345678%2C-45.67891234567891")
    r = get(client, "https://maps.app.goo.gl/pin")
    assert r.status_code == 302
    assert r.location == waze_ll("-12.345678912345678", "-45.67891234567891")
    assert calls["places"] == []


def test_index_long_redirect_from_mobile_app(client, fake_net):
    # links shared from the mobile app carry a long g_ep and used to fail the 512 length limit
    redirects, _, _ = fake_net
    long_url = (
        "https://www.google.com/maps/place/Some+Place,+Example+City/data=!4m6!3m5"
        "!1s0x0:0x1234567890abcdef!7e2!8m2!3d12.345678!4d98.7654321!18m1!1e1"
        "?utm_source=mstt_1&entry=gps&g_ep=" + "A" * 400 + "&skid=00000000-0000-0000-0000-000000000000")
    assert len(long_url) > 512
    redirects["https://maps.app.goo.gl/long"] = long_url
    r = client.post("/", data={"url": "https://maps.app.goo.gl/long"})
    assert r.status_code == 302 and r.location == waze_ll("12.345678", "98.7654321")


def test_index_place_via_places_api(client, fake_net):
    redirects, places, _ = fake_net
    redirects["https://maps.app.goo.gl/eiffel"] = (
        "https://www.google.com/maps/place/Eiffel+Tower/data=!4m2!3m1!1s0x47e66e2964e34e2d:0x8ddca9ee380ef7e0")
    places[0x8ddca9ee380ef7e0] = (48.8583701, 2.2944813)
    r = client.post("/", data={"url": "https://maps.app.goo.gl/eiffel"})
    assert r.status_code == 302 and r.location == waze_ll("48.8583701", "2.2944813")


def test_index_falls_back_to_waze_search(client, fake_net):
    redirects, _, _ = fake_net
    redirects["https://maps.app.goo.gl/plus"] = (
        "https://maps.google.com/maps?q=9C3X+2W+Example+House&ftid=0x1111111111111111:0x2222222222222222")
    r = get(client, "https://maps.app.goo.gl/plus")
    assert r.status_code == 302
    assert r.location == "https://ul.waze.com/ul?q=9C3X%202W%20Example%20House"


def test_index_broken_when_nothing_found(client, fake_net):
    r = get(client, "https://www.google.com/maps/place//@0,0,22z")
    assert r.status_code == 200 and b"Oops, Something Went Wrong!" in r.data
    # nobody gets notified automatically, the page must ask the user to report
    assert b"https://github.com/papko26/google-link-to-waze/issues/new" in r.data
    assert b"https://t.me/papko26" in r.data
    assert b"let the team know" not in r.data


@pytest.mark.parametrize("text, location", [
    ("10°10'10.0\"N 20°20'20.0\"E", waze_ll("10.169444", "20.338889")),
    ("10.12, 20.34", waze_ll("10.12", "20.34")),
])
def test_index_plain_coordinates(client, fake_net, text, location):
    r = get(client, text)
    assert r.status_code == 302 and r.location == location
    assert fake_net[2]["head"] == []


@pytest.mark.parametrize("url", ["https://share.google/abc", "Cafe https://share.google/abc"])
def test_index_share_google(client, fake_net, url):
    r = get(client, url)
    assert r.status_code == 200 and b"share.google Links Are Not Supported" in r.data
    assert fake_net[2]["head"] == []


@pytest.mark.parametrize("url", [
    "https://evil.com/maps/@34.1,33.1",
    "http://localhost:5000/",
    "Example Residences by Example Homes, Example City",
])
def test_index_rejects(client, fake_net, url):
    r = get(client, url)
    assert r.status_code == 200 and b"Not a Google Maps Link!" in r.data
    assert fake_net[2]["head"] == []
