import random

from playwright_stealth import stealth_async
from geopy.geocoders import Nominatim

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/116.0"
]
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/14.0 Mobile/15A372 Safari/604.1"
)

# proxy_url = "http://prod-proxy.geonode.io:9000"
# proxy_credentials = "geonode_nLZ98XMquD-type-residential-country-in:aca8e241-f6df-40ea-a741-cd7bbc0dcddb"
# proxy_url = "http://sg.proxy.geonode.io:9000"
# proxy_credentials = "geonode_nLZ98XMquD-type-residential-country-in:aca8e241-f6df-40ea-a741-cd7bbc0dcddb"
proxy_url = "http://geo.iproyal.com:12321"
proxy_credentials = "acumensa2:Acumensa321_country-in_streaming-1"

async def get_init_page(p, latitude=None, longitude=None):
    browser = await p.chromium.launch(headless=True,
                                      args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
                                      proxy={"server": proxy_url, "username": proxy_credentials.split(":")[0],
                                             "password": proxy_credentials.split(":")[1]}

                                      )
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        # viewport={"width": 375, "height": 667},  # iPhone size
        # device_scale_factor=2,
        # is_mobile=True,
        # has_touch=True,
        # user_agent=random.choice(USER_AGENTS),  # Randomize User-Agent
        # extra_http_headers={
        #     "Accept-Language": "en-US,en;q=0.9",
        #     "Referer": "https://www.google.com/",
        #     "DNT": "1",  # Do Not Track
        #     "Upgrade-Insecure-Requests": "1"
        # },
        # geolocation={"latitude": latitude, "longitude": longitude},
        # permissions=["geolocation"],
        # locale="en-US"
    )
    page = await context.new_page()

    # async def handle_route(route, request):
    #     if request.resource_type in ["image", "stylesheet", "font", "media"]:
    #         await route.abort()
    #     else:
    #         await route.continue_()
    #
    # await page.route("**/*", handle_route)
    # await context.route("**/*", lambda route: route.abort() if route.request.resource_type in ["font",
    # "stylesheet", "media", "script"] else route.continue_())

    await stealth_async(page)
    page.set_default_timeout(500000)
    return page, browser, context


def get_lat_lon_from_pincode(pincode, country="India"):
    geolocator = Nominatim(user_agent="pincode_locator")
    location = geolocator.geocode(f"{pincode}, {country}")
    if location:
        return location.latitude, location.longitude
    else:
        return None
