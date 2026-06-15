import json
import platform
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import urllib.parse

st.set_page_config(page_title="Shopkeeper Finder", page_icon="🏪", layout="wide")
st.title("🏪 Shopkeeper Finder — Google Maps")
st.caption("Powered by Selenium + BeautifulSoup · No API key required")

CATEGORIES = {
    "All Shops":            "shops",
    "Grocery / Supermarket":"grocery stores",
    "Pharmacy / Medical":   "pharmacies",
    "Restaurant / Cafe":    "restaurants",
    "Clothing / Fashion":   "clothing stores",
    "Electronics":          "electronics stores",
    "Bakery":               "bakeries",
    "Jewellery":            "jewellery stores",
    "Hardware":             "hardware stores",
    "Salon / Beauty":       "beauty salons",
    "Mobile / Phone":       "mobile phone shops",
    "Stationery / Books":   "stationery stores",
    "Furniture":            "furniture stores",
    "Footwear":             "shoe stores",
    "Sports Venues & Courts": "sports venues and courts",
}

# Third-party booking/listing platforms per category.
# Each entry is (platform_name, domain) — used to search Google for a listing.
CATEGORY_PLATFORMS = {
    "Sports Venues & Courts": [
        ("Playo",    "playo.co"),
        ("District", "district.in"),
        ("Huddle",   "huddlespaces.com"),
        ("Playmore", "playmore.in"),
    ],
    "Restaurant / Cafe": [
        ("Zomato",   "zomato.com"),
        ("Swiggy",   "swiggy.com"),
        ("EazyDiner","eazydiner.com"),
        ("Dineout",  "dineout.in"),
    ],
    "Salon / Beauty": [
        ("Nykaa Salon", "nykaasalon.com"),
        ("BookMyShow Beauty", "bookmyshow.com/beauty"),
        ("Urban Company", "urbancompany.com"),
    ],
    "Grocery / Supermarket": [
        ("BigBasket", "bigbasket.com"),
        ("Blinkit",   "blinkit.com"),
        ("JioMart",   "jiomart.com"),
    ],
}


def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    if platform.system() == "Darwin":
        options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        service = Service(ChromeDriverManager().install())
    else:
        options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


def parse_card(item):
    """Parse a result card from the list view."""
    name_el = item.select_one("div.qBF1Pd")
    name = name_el.get_text(strip=True) if name_el else "N/A"

    rating_el = item.select_one("span.MW4etd")
    rating = rating_el.get_text(strip=True) if rating_el else "N/A"

    phone_el = item.select_one("span.UsdlK")
    phone = phone_el.get_text(strip=True) if phone_el else "N/A"

    category, address, description, hours = "N/A", "N/A", "N/A", "N/A"
    for div in item.select("div.W4Efsd"):
        nested = div.select("div.W4Efsd")
        if nested:
            # First nested = category + address
            spans = [s.get_text(strip=True) for s in nested[0].find_all("span", recursive=False)
                     if s.get_text(strip=True) and s.get_text(strip=True) != "·"]
            clean = [s.lstrip("·").strip() for s in spans if s.lstrip("·").strip()]
            if clean:
                category = clean[0]
            if len(clean) > 1:
                address = clean[-1]
            # Middle nested div = description (if 3 nested divs)
            if len(nested) == 3:
                description = nested[1].get_text(strip=True)
            # Last nested = hours
            last = nested[-1]
            h_spans = [s.get_text(strip=True) for s in last.find_all("span", recursive=False)
                       if s.get_text(strip=True) and s.get_text(strip=True) != "·"]
            h_clean = [h.lstrip("·").strip() for h in h_spans
                       if h.lstrip("·").strip() and h.lstrip("·").strip() != phone]
            if h_clean:
                hours = " ".join(h_clean[:2])
            break

    # Place URL from the <a> inside the card
    place_url = "N/A"
    link = item.select_one("a[href*='/maps/place/']")
    if link:
        href = link.get("href", "")
        place_url = f"https://www.google.com{href}" if href.startswith("/") else href

    return {
        "Name": name,
        "Category": category,
        "Description": description,
        "Address": address,
        "Rating": rating,
        "Phone": phone,
        "Opening Hours": hours,
        "Website": "N/A",
        "Full Address": "N/A",
        "Review Count": "N/A",
        "_url": place_url,
    }


def get_place_details(driver, url):
    """Visit a place detail page and extract website, full address, review count."""
    website, full_address, review_count = "N/A", "N/A", "N/A"
    try:
        driver.get(url)
        time.sleep(2.5)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Website: <a> tag inside RcCsl container with external href
        for container in soup.select("div.RcCsl"):
            a_tag = container.select_one("a.CsEnBe")
            if a_tag:
                href = a_tag.get("href", "")
                if href.startswith("http") and "google.com" not in href:
                    website = href
                    break

        # Full address: button inside RcCsl with long address-like text
        for container in soup.select("div.RcCsl"):
            btn = container.select_one("button.CsEnBe")
            if btn:
                text = btn.get_text(strip=True)
                if "," in text and len(text) > 25 and not text[0].isdigit() and "+" not in text[:3]:
                    full_address = text
                    break

        # Review count
        rv = soup.select_one("div.HHrUdb")
        if rv:
            review_count = rv.get_text(strip=True)

    except Exception:
        pass
    return website, full_address, review_count


def find_platform_links(driver, shop_name, city_name, platforms):
    """Search Google for a shop's listing on each platform; return found URLs as a list."""
    found = []
    for platform_name, domain in platforms:
        query = urllib.parse.quote(f"{shop_name} {city_name} site:{domain}")
        search_url = f"https://www.google.com/search?q={query}&hl=en"
        try:
            driver.get(search_url)
            time.sleep(1.5)
            # Google redirected to login — blocked, skip this platform
            if "accounts.google.com" in driver.current_url:
                continue
            soup = BeautifulSoup(driver.page_source, "html.parser")
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                parsed = urllib.parse.urlparse(href)
                # Match only if the actual hostname belongs to the platform domain
                if parsed.scheme in ("http", "https") and (
                    parsed.netloc == domain or parsed.netloc.endswith(f".{domain}")
                ):
                    found.append(href)
                    break
        except Exception:
            pass
    return found


def scrape(city, category_query, max_scrolls, fetch_details, status_placeholder, platforms=None):
    query = urllib.parse.quote(f"{category_query} in {city}")
    url = f"https://www.google.com/maps/search/{query}?hl=en"
    results_url = url

    driver = create_driver()
    try:
        status_placeholder.info("🌐 Opening Google Maps...")
        driver.get(url)
        time.sleep(3)

        # Dismiss consent dialog if present
        for xpath in ['//button[contains(.,"Accept all")]', '//button[contains(.,"Reject all")]']:
            try:
                driver.find_element(By.XPATH, xpath).click()
                time.sleep(1)
                break
            except Exception:
                pass

        status_placeholder.info("⏳ Waiting for results to load...")
        try:
            feed = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']"))
            )
        except Exception:
            return None, "Could not load Google Maps results. Google may have blocked the request."

        # Scroll to load more
        prev_count = 0
        for i in range(max_scrolls):
            status_placeholder.info(f"📜 Scrolling to load more results... (scroll {i+1}/{max_scrolls})")
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", feed)
            time.sleep(2)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            count = len(soup.select("div.Nv2PK"))
            if count == prev_count:
                break
            prev_count = count

        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = soup.select("div.Nv2PK")

        if not items:
            return None, "No results found. Google may have changed their HTML structure or blocked the request."

        seen = set()
        shops = []
        for item in items:
            card = parse_card(item)
            if card["Name"] == "N/A" or card["Name"] in seen:
                continue
            seen.add(card["Name"])
            shops.append(card)

        if not shops:
            return None, "Parsed 0 valid shops from the page."

        # Optionally fetch details (website, full address, review count)
        if fetch_details:
            for i, shop in enumerate(shops):
                status_placeholder.info(
                    f"🔍 Fetching details for **{shop['Name']}** ({i+1}/{len(shops)})..."
                )
                if shop["_url"] != "N/A":
                    website, full_address, review_count = get_place_details(driver, shop["_url"])
                    shops[i]["Website"] = website
                    shops[i]["Full Address"] = full_address
                    shops[i]["Review Count"] = review_count

        # Optionally search for third-party platform links
        if platforms:
            for i, shop in enumerate(shops):
                status_placeholder.info(
                    f"🔗 Searching platform links for **{shop['Name']}** ({i+1}/{len(shops)})..."
                )
                links = find_platform_links(driver, shop["Name"], city, platforms)
                shops[i]["Platform Links"] = json.dumps(links)

        return shops, None

    except Exception as e:
        return None, str(e)
    finally:
        driver.quit()


# ─── UI ──────────────────────────────────────────────────────────────────────

col1, col2 = st.columns([3, 2])
with col1:
    city = st.text_input("🏙️ City Name", placeholder="e.g. Mumbai, London, Dubai, Karachi")
with col2:
    category = st.selectbox("🏬 Category", list(CATEGORIES.keys()))

col3, col4, col5 = st.columns([1, 1, 1])
with col3:
    max_scrolls = st.slider("Scroll depth (more = more results)", 2, 10, 5)
with col4:
    fetch_details = st.checkbox(
        "Fetch website, full address & review count",
        value=False,
        help="Visits each result page individually — slower but more data"
    )
with col5:
    show_map_link = st.checkbox(
        "Include Google Maps link",
        value=False,
        help="Adds a direct Google Maps URL column to results and CSV"
    )

# Platform links option — only shown when the selected category has known platforms
available_platforms = CATEGORY_PLATFORMS.get(category, [])
fetch_platform_links = False
if available_platforms:
    platform_names = ", ".join(p[0] for p in available_platforms)
    fetch_platform_links = st.checkbox(
        f"Search platform listings ({platform_names})",
        value=False,
        help=f"Searches for each venue on {platform_names} and stores found URLs in a 'Platform Links' column (JSON array). Slower — one extra Google search per shop per platform."
    )

st.info(
    "ℹ️ **Note on Owner Name:** Google Maps does not expose owner names publicly. "
    "Fields available: Name, Category, Description, Address, Rating, Phone, Hours, Website, Review Count.",
    icon="ℹ️"
)
st.warning("⚠️ Google may block after several rapid requests. If it fails, wait a minute and try again.")

if st.button("🔍 Scrape Google Maps", type="primary", use_container_width=True):
    if not city.strip():
        st.error("Please enter a city name.")
        st.stop()

    category_query = CATEGORIES[category]
    platforms_to_search = available_platforms if fetch_platform_links else None
    status = st.empty()

    shops, error = scrape(city.strip(), category_query, max_scrolls, fetch_details, status, platforms_to_search)
    status.empty()

    if error:
        st.error(f"❌ {error}")
        st.stop()

    all_df = pd.DataFrame(shops)
    all_df = all_df.rename(columns={"_url": "Google Maps Link"})
    display_cols = [k for k in all_df.columns if k not in ("Google Maps Link", "Platform Links")]
    if show_map_link:
        display_cols.append("Google Maps Link")
    if fetch_platform_links and "Platform Links" in all_df.columns:
        display_cols.append("Platform Links")
    df = all_df[display_cols]

    st.success(f"✅ Found **{len(df)}** shopkeepers in **{city}** — {category}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Found", len(df))
    c2.metric("With Phone", (df["Phone"] != "N/A").sum())
    c3.metric("With Rating", (df["Rating"] != "N/A").sum())
    c4.metric("With Website", (df["Website"] != "N/A").sum())

    st.dataframe(df, use_container_width=True, hide_index=True)

    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_data,
        file_name=f"shopkeepers_{city.strip().replace(' ', '_').lower()}_{category.replace('/', '').replace(' ', '_').lower()}.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )