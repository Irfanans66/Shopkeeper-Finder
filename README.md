# Shopkeeper Finder

A Streamlit web app that scrapes Google Maps to find local shopkeepers by city and category — no API key required.

---

## How It Works

The app launches a headless Chrome browser via Selenium, navigates to a Google Maps search, scrolls to load results, and parses the HTML using BeautifulSoup. Optionally, it visits each shop's detail page to extract richer data like website and full address.

```
User Input → Build Search URL → Launch Headless Chrome → Scroll Results → Parse Cards → (Optional) Fetch Details → Display Table + CSV
```

---

## Features

- Search by city and shop category
- Extracts: Name, Category, Description, Address, Rating, Phone, Opening Hours
- Optional deep fetch: Website, Full Address, Review Count
- Export results as CSV
- No Google Maps API key needed

---

## Requirements

- Python 3.8+
- Google Chrome installed at `/Applications/Google Chrome.app` (Mac default)

Install dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt` dependencies:

| Package | Purpose |
|---|---|
| `streamlit` | Web UI |
| `selenium` | Headless browser automation |
| `webdriver-manager` | Auto-installs matching ChromeDriver |
| `beautifulsoup4` | HTML parsing |
| `pandas` | Data table and CSV export |

> Note: `requirements.txt` currently lists `googlemaps` which is unused — `selenium` + `beautifulsoup4` handle all scraping.

---

## Run the App

```bash
streamlit run app.py
```

Opens in your browser at `http://localhost:8501`.

---

## Usage

1. Enter a **city name** (e.g. `Mumbai`, `London`, `Dubai`)
2. Select a **category** from the dropdown
3. Set **scroll depth** — higher means more results but slower
4. Optionally check **"Fetch website, full address & review count"** for richer data (visits each result individually — much slower)
5. Click **Scrape Google Maps**
6. Download results as CSV

---

## Supported Categories

| UI Label | Search Query Used |
|---|---|
| All Shops | shops |
| Grocery / Supermarket | grocery stores |
| Pharmacy / Medical | pharmacies |
| Restaurant / Cafe | restaurants |
| Clothing / Fashion | clothing stores |
| Electronics | electronics stores |
| Bakery | bakeries |
| Jewellery | jewellery stores |
| Hardware | hardware stores |
| Salon / Beauty | beauty salons |
| Mobile / Phone | mobile phone shops |
| Stationery / Books | stationery stores |
| Furniture | furniture stores |
| Footwear | shoe stores |
| Sports Venues & Courts | sports venues and courts |

---

## Data Fields

| Field | Source | Notes |
|---|---|---|
| Name | List card | Shop display name |
| Category | List card | e.g. "Grocery store" |
| Description | List card | Short blurb if available |
| Address | List card | Short address from card |
| Rating | List card | e.g. "4.2" |
| Phone | List card | If shown on card |
| Opening Hours | List card | e.g. "Open · Closes 9 PM" |
| Website | Detail page* | External URL only |
| Full Address | Detail page* | Complete address |
| Review Count | Detail page* | e.g. "(1,243)" |

\* Only populated when "Fetch details" checkbox is enabled.

---

## Internal Architecture

### `create_driver()`
Launches a headless Chrome instance with bot-detection mitigations:
- Spoofed user-agent string
- `navigator.webdriver` hidden via CDP command
- Automation flags removed from Chrome switches

### `scrape(city, category_query, max_scrolls, fetch_details, status_placeholder)`
Main orchestrator:
1. Builds URL: `https://www.google.com/maps/search/<query>+in+<city>?hl=en`
2. Opens the URL and dismisses consent dialogs if present
3. Waits for `div[role='feed']` (the results panel)
4. Scrolls the feed `max_scrolls` times, stopping early if no new results appear
5. Parses all `div.Nv2PK` cards (one per shop)
6. Deduplicates by name
7. Optionally calls `get_place_details()` for each shop

### `parse_card(item)`
Extracts fields from a single result card using CSS selectors:
- `div.qBF1Pd` → Name
- `span.MW4etd` → Rating
- `span.UsdlK` → Phone
- `div.W4Efsd` nested spans → Category, Address, Hours
- `a[href*='/maps/place/']` → Place URL (used for detail fetching)

### `get_place_details(driver, url)`
Navigates to a shop's Google Maps page and extracts:
- Website: `a.CsEnBe` inside `div.RcCsl` pointing to a non-Google URL
- Full Address: `button.CsEnBe` with comma-separated text longer than 25 chars
- Review Count: `div.HHrUdb`

---

## Limitations

- **Fragile selectors**: Relies on Google Maps' obfuscated CSS class names (e.g. `Nv2PK`, `qBF1Pd`). These can change without notice and break parsing.
- **Rate limiting**: Google may block requests after repeated rapid scrapes. If it fails, wait a minute before retrying.
- **No owner names**: Google Maps does not expose owner/proprietor names publicly.
- **Mac-only Chrome path**: `options.binary_location` is hardcoded to the macOS Chrome path. Change this for Linux/Windows.
- **Result cap**: Google Maps typically shows ~20 results per search regardless of scroll depth.

---

## Customization

**Add a new category** — edit the `CATEGORIES` dict in `app.py`:
```python
CATEGORIES = {
    ...
    "Your Label": "your search query",
}
```

**Run on Linux/Windows** — update the Chrome binary path in `create_driver()`:
```python
# Linux
options.binary_location = "/usr/bin/google-chrome"

# Windows
options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
```