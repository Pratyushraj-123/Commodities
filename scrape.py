import urllib.request
import urllib.parse
import ssl
import re
import json
import time
import os
import socket
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

# Set global socket timeout to 5.0s to prevent network requests from hanging indefinitely
socket.setdefaulttimeout(5.0)

JS_FILE = "prices.js"
JSON_FILE = "prices.json"

# Default fallback values matching the dashboard defaults
DEFAULT_PRICES = {
    "gold": 4509.0,
    "silver": 76.11,
    "platinum": 1973.0,
    "palladium": 1387.0,
    "copper": 6.0,          # USD/lb
    "nickel": 19143.0,
    "zinc": 3100.0,
    "lithium": 176175.0,    # CNY/t
    "uranium": 93.0,
    "cobalt": 34000.0,
    "rareearth": 245.0,
    "antimony": 22500.0,
    "tungsten": 3050.0,
    "vanadium": 10500.0,
    "niobium": 50.0,
    "titanium": 48.5,       # CNY/kg
    "fluorite": 580.0
}

DEFAULT_INDEXES = {
    "dow": {"name": "Dow Jones", "price": 50591.52, "change": -52.76, "pct": -0.10, "flag": "🇺🇸", "updated": "13 Jun, 16:07", "hist": [49200, 49350, 49500, 49800, 50100, 50350, 50400, 50200, 50150, 50250, 50450, 50600, 50591.52]},
    "nasdaq": {"name": "Nasdaq", "price": 26674.73, "change": 18.55, "pct": 0.07, "flag": "🇺🇸", "updated": "13 Jun, 01:29"},
    "asx200": {"name": "ASX 200", "price": 8450.20, "change": 45.10, "pct": 0.54, "flag": "🇦🇺", "updated": "13 Jun, 16:10"},
    "asx300": {"name": "ASX 300", "price": 8390.40, "change": 40.20, "pct": 0.48, "flag": "🇦🇺", "updated": "13 Jun, 16:10"},
    "ftse": {"name": "FTSE 100", "price": 10400.07, "change": -104.94, "pct": -1.00, "flag": "🇬🇧", "updated": "13 Jun, 16:07"}
}

INDEX_TICKERS = {
    "dow": {"name": "Dow Jones", "ticker": "^DJI", "flag": "🇺🇸"},
    "nasdaq": {"name": "Nasdaq", "ticker": "^IXIC", "flag": "🇺🇸"},
    "asx200": {"name": "ASX 200", "ticker": "^AXJO", "flag": "🇦🇺"},
    "asx300": {"name": "ASX 300", "ticker": "^AXKO", "flag": "🇦🇺"},
    "ftse": {"name": "FTSE 100", "ticker": "^FTSE", "flag": "🇬🇧"}
}

SELECTED_ASX_COMPANIES = {
    "PC2": "PC Gold", "TM1": "Terra Metals", "FRS": "Forrestania Resources",
    "BNZ": "BENZ Mining Corp", "MM1": "Midas Minerals", "BCN": "Beacon Minerals",
    "SLS": "Solstice Minerals", "MM8": "Medallion Metals", "WTM": "Waratah Minerals Ltd",
    "LRV": "Larvotto Resources", "TVN": "Tivan Ltd", "TGN": "Tungsten Mining",
    "EQR": "EQ Resources Ltd", "ENR": "Encounter Resources", "MI6": "Minerals 260",
    "OBM": "Ora Banda Mining Ltd", "DVP": "Develop Global", "CYL": "Catalyst Metals",
    "SPD": "Southern Palladium", "BGD": "Barton Gold Holdings", "AZY": "Antipa Minerals",
    "STN": "Saturn Metals Ltd", "MKR": "Manuka Resources", "CRS": "Caprice Resources",
    "TNC": "True North Copper", "GML": "Gateway Mining Ltd", "AQI": "Alicanto Minerals Ltd",
    "GA8": "Goldarc Resources", "SKY": "SKY Metals Ltd", "BCA": "Black Canyon Ltd",
    "CBE": "Cobre Ltd", "USL": "Unico Silver Ltd", "BM1": "Ballard Mining Ltd",
    "LM1": "Leeuwin Metals Ltd", "FFM": "Firefly Metals Ltd", "BRE": "Brazilian Rare Earths Ltd",
    "LIN": "Lindian Resources Ltd", "CYM": "Cyprium Metals", "SGQ": "ST George Mining",
    "BPM": "BPM Minerals", "BMR": "Ballymore Resources", "FML": "Focus Minerals",
    "TTM": "Titan Minerals", "NMR": "Native Mineral Resources", "LSA": "Lachlan Star Ltd",
    "SKS": "SKS Technologies Group Ltd", "MP1": "Megaport Ltd", "EDU": "EDU Holdings Ltd",
    "GNP": "Genusplus Group Ltd", "4DX": "4DMEDICAL Ltd", "PME": "Pro Medicus Ltd",
    "EIQ": "Echoiq Ltd", "NEU": "Neuren Pharmaceuticals Ltd", "LTR": "Liontown Ltd",
    "PLS": "PLS Group Ltd", "WC8": "Wildcat Resources Ltd"
}

def load_stored_prices():
    prices = None
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                prices = json.load(f)
        except Exception as e:
            print(f"Error reading prices.json: {e}")
            
    if not prices and os.path.exists(JS_FILE):
        try:
            with open(JS_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                match = re.search(r'window\.LIVE_COMMODITY_PRICES\s*=\s*(\{.*?\});', content, re.DOTALL)
                if match:
                    prices = json.loads(match.group(1))
        except Exception as e:
            print(f"Error parsing prices.js: {e}")
            
    if not prices:
        prices = DEFAULT_PRICES.copy()
        
    if "indexes" not in prices:
        prices["indexes"] = DEFAULT_INDEXES.copy()
        
    return prices


def save_stored_prices(prices):
    # Save to JSON
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(prices, f, indent=2)
        print(f"Successfully saved to {JSON_FILE}")
    except Exception as e:
        print(f"Error writing to {JSON_FILE}: {e}")
        
    # Save to JS
    try:
        with open(JS_FILE, "w", encoding="utf-8") as f:
            f.write(f"window.LIVE_COMMODITY_PRICES = {json.dumps(prices, indent=2)};")
        print(f"Successfully saved to {JS_FILE}")
    except Exception as e:
        print(f"Error writing to {JS_FILE}: {e}")

# SSL context to bypass verification issues on local/GitHub runners
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
}

def fetch_usd_cny():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/CNY=X?interval=1d&range=1d"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5.0) as response:
            data = json.loads(response.read().decode())
            meta = data['chart']['result'][0]['meta']
            rate = float(meta['regularMarketPrice'])
            if rate > 5.0 and rate < 10.0:
                print(f"Live USD/CNY rate fetched: {rate}")
                return rate
    except Exception as e:
        print(f"Error fetching live USD/CNY rate, using fallback 7.25: {e}")
    return 7.25

def fetch_index_price(ticker):
    encoded_ticker = ticker.replace('^', '%5E').replace('&', '%26')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5.0) as response:
            data = json.loads(response.read().decode())
            meta = data['chart']['result'][0]['meta']
            price = float(meta['regularMarketPrice'])
            prev_close = float(meta['chartPreviousClose'])
            change = price - prev_close
            pct = (change / prev_close) * 100
            return {
                "price": round(price, 2),
                "change": round(change, 2),
                "pct": round(pct, 2),
                "updated": time.strftime("%d %b, %H:%M")
            }
    except Exception as e:
        print(f"Error fetching index {ticker}: {e}")
        return None

def fetch_index_history(ticker):
    encoded_ticker = ticker.replace('^', '%5E').replace('&', '%26')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}?interval=1d&range=1y"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5.0) as response:
            data = json.loads(response.read().decode())
            result = data['chart']['result'][0]
            quotes = result.get('indicators', {}).get('quote', [{}])[0]
            close_prices = quotes.get('close', [])
            return [round(c, 2) for c in close_prices if c is not None]
    except Exception as e:
        print(f"Error fetching history for {ticker}: {e}")
        return None

def fetch_single_stock_quote(code, name):
    ticker = f"{code}.AX"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5.0) as response:
            data = json.loads(response.read().decode())
            meta = data['chart']['result'][0]['meta']
            price = float(meta.get('regularMarketPrice', 0))
            prev_close = float(meta.get('chartPreviousClose', 0))
            change = price - prev_close
            pct = (change / prev_close) * 100 if prev_close else 0
            return code, {
                "name": name,
                "code": code,
                "price": round(price, 3),
                "change": round(change, 3),
                "pct": round(pct, 2)
            }
    except Exception:
        return code, None

def fetch_watchlist_prices():
    print(f"Fetching quotes for {len(SELECTED_ASX_COMPANIES)} ASX watchlist companies...")
    watchlist = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_single_stock_quote, code, name) for code, name in SELECTED_ASX_COMPANIES.items()]
        for future in futures:
            try:
                code, res = future.result(timeout=6.0)
                if res:
                    watchlist[code] = res
            except Exception:
                pass
    print(f"Watchlist fetch completed: {len(watchlist)} / {len(SELECTED_ASX_COMPANIES)} stocks updated.")
    return watchlist

def fetch_asx_announcements():
    import datetime
    now = datetime.datetime.now()
    today_str_1 = now.strftime("%d %b %Y")       # e.g., "20 Jul 2026"
    today_str_2 = now.strftime("%d %B %Y")       # e.g., "20 July 2026"
    today_day = str(now.day)
    
    OFFICIAL_FILING_KEYWORDS = [
        "announcement", "quarterly", "report", "results", "half year", "full year",
        "exploration", "drilling", "resource", "trading halt", "presentation",
        "agm", "mou", "agreement", "acquisition", "offtake", "appointment",
        "notice of meeting", "investor update", "placement", "entitlement", "secures", "funding", "contract"
    ]
    
    MEDIA_COMMENTARY_PHRASES = [
        "why is", "turning heads", "share price in focus", "retreats", "slips",
        "shares jump", "shares fall", "shares slide", "facing a", "under pressure",
        "caught in the", "takes a breather", "is the exploration story", "what today",
        "dips alongside", "surges to the top", "whats behind"
    ]
    
    print(f"Fetching genuine official ASX company announcements released TODAY ({today_str_1})...")
    codes = list(SELECTED_ASX_COMPANIES.keys())
    chunk_size = 20
    seen_codes = set()
    today_announcements = []
    
    official_query = '("ASX Announcement" OR "Quarterly Report" OR "Financial Results" OR "Exploration Update" OR "Trading Halt" OR "Investor Presentation" OR "AGM" OR "MOU" OR "Agreement")'
    
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i:i+chunk_size]
        query_codes = " OR ".join([f"ASX:{c}" for c in chunk])
        full_query = f"({query_codes}) AND {official_query}"
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(full_query)}&hl=en-AU&gl=AU&ceid=AU:en"
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=6.0) as response:
                xml_data = response.read().decode('utf-8', errors='ignore')
                root = ET.fromstring(xml_data)
                items = root.findall('./channel/item')
                for item in items:
                    raw_title = item.findtext('title') or ""
                    link = item.findtext('link') or ""
                    pubDate = item.findtext('pubDate') or ""
                    
                    title_lower = raw_title.lower()
                    
                    # Exclude general media commentary
                    if any(phrase in title_lower for phrase in MEDIA_COMMENTARY_PHRASES):
                        continue
                        
                    # Must contain genuine official filing keywords
                    if not any(kw in title_lower for kw in OFFICIAL_FILING_KEYWORDS):
                        continue
                    
                    # Filter strictly for today's release date
                    is_today = (today_str_1 in pubDate) or (today_str_2 in pubDate) or (f" {today_day} " in pubDate and now.strftime("%b") in pubDate)
                    if not is_today:
                        continue
                    
                    clean_title = re.sub(r'\s*-\s*[^-]+$', '', raw_title).strip()
                    
                    matched_code = None
                    for c in chunk:
                        if c in raw_title or f"({c})" in raw_title or f"ASX:{c}" in raw_title:
                            matched_code = c
                            break
                            
                    if matched_code and matched_code not in seen_codes:
                        seen_codes.add(matched_code)
                        today_announcements.append({
                            "code": matched_code,
                            "name": SELECTED_ASX_COMPANIES.get(matched_code, matched_code),
                            "title": clean_title,
                            "link": f"https://www.marketindex.com.au/asx/{matched_code.lower()}/announcements",
                            "date": pubDate[:16] if pubDate else today_str_1
                        })
        except Exception as e:
            print(f"Error fetching announcements chunk {i}: {e}")
            
    print(f"Announcements fetch completed: {len(today_announcements)} genuine official company announcements released TODAY.")
    return today_announcements

def run_scraper():
    print("Scraping latest commodities data from Trading Economics...")
    prices = load_stored_prices()
    
    usd_cny = fetch_usd_cny()
    
    # Scrape 56 ASX watchlist stock quotes and announcements
    try:
        prices["watchlist"] = fetch_watchlist_prices()
    except Exception as e:
        print(f"Error updating watchlist: {e}")
        
    try:
        prices["announcements"] = fetch_asx_announcements()
    except Exception as e:
        print(f"Error updating announcements: {e}")
    
    # Clean up any indexes that are no longer in INDEX_TICKERS
    if "indexes" in prices:
        prices["indexes"] = {k: v for k, v in prices["indexes"].items() if k in INDEX_TICKERS}
    else:
        prices["indexes"] = {}

    # Scrape Stock Market Indexes
    print("Fetching stock market indexes from Yahoo Finance...")
    for idx_key, idx_info in INDEX_TICKERS.items():
        res = fetch_index_price(idx_info["ticker"])
        if res:
            if idx_key not in prices["indexes"]:
                prices["indexes"][idx_key] = {}
            prices["indexes"][idx_key].update({
                "name": idx_info["name"],
                "price": res["price"],
                "change": res["change"],
                "pct": res["pct"],
                "flag": idx_info["flag"],
                "updated": res["updated"]
            })
            if idx_key == "dow":
                hist = fetch_index_history(idx_info["ticker"])
                if hist:
                    prices["indexes"][idx_key]["hist"] = hist
            print(f"  {idx_info['name']}: {res['price']} ({res['change']} / {res['pct']}%)")
    
    url = "https://tradingeconomics.com/commodities"
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=8.0) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Extract name, price, change, and pct change from TE table
            pattern = re.compile(
                r'href="/commodity/([^"]+)"[^>]*>.*?<b>([^<]+)</b>.*?<td id="p" class="datatable-item"[^>]*>\s*([\d,.]+)\s*</td>\s*<td id="nch"[^>]*>.*?([-\d,.]+)\s*</td>\s*<td id="pch"[^>]*>.*?([-\d,.]+)\s*%?\s*</td>',
                re.DOTALL | re.IGNORECASE
            )
            
            matches = pattern.findall(html)
            te_data, te_chg, te_pct = {}, {}, {}
            for path, name, val, chg, pchg in matches:
                c_val = re.sub(r'[^\d.]', '', val.strip())
                c_chg = re.sub(r'[^\d.-]', '', chg.strip())
                c_pct = re.sub(r'[^\d.-]', '', pchg.strip())
                try:
                    p_key = path.lower()
                    te_data[p_key] = float(c_val)
                    te_chg[p_key] = float(c_chg) if c_chg else 0.0
                    te_pct[p_key] = float(c_pct) if c_pct else 0.0
                except ValueError:
                    pass
            
            if not te_data:
                # Fallback simple regex if table structure differs
                pattern_simple = re.compile(
                    r'href="/commodity/([^"]+)"[^>]*>.*?<b>([^<]+)</b>.*?<td id="p" class="datatable-item"[^>]*>\s*([\d,.]+)\s*</td>',
                    re.DOTALL | re.IGNORECASE
                )
                for path, name, val in pattern_simple.findall(html):
                    c_val = re.sub(r'[^\d.]', '', val.strip())
                    try:
                        te_data[path.lower()] = float(c_val)
                    except ValueError:
                        pass
                        
            if not te_data:
                raise Exception("Failed to parse any commodity data from Trading Economics HTML.")
            
            # Map metals with daily change & percentage change
            metals_keys = [
                ("gold", "gold"), ("silver", "silver"), ("platinum", "platinum"), ("palladium", "palladium"),
                ("copper", "copper"), ("nickel", "nickel"), ("zinc", "zinc"), ("lithium", "lithium"),
                ("uranium", "uranium"), ("cobalt", "cobalt"), ("rareearth", "neodymium"),
                ("antimony", "antimony"), ("tungsten", "tungsten"), ("vanadium", "vanadium"),
                ("niobium", "niobium"), ("titanium", "titanium"), ("fluorite", "fluorite")
            ]
            
            for m_id, te_k in metals_keys:
                if te_k in te_data:
                    prices[m_id] = te_data[te_k]
                    prices[f"{m_id}_change"] = te_chg.get(te_k, 0.0)
                    prices[f"{m_id}_pct"] = te_pct.get(te_k, 0.0)
            
            # 2. Silver (USD/oz)
            if "silver" in te_data:
                prices["silver"] = te_data["silver"]
                
            # 3. Platinum (USD/oz)
            if "platinum" in te_data:
                prices["platinum"] = te_data["platinum"]
                
            # 4. Palladium (USD/oz)
            if "palladium" in te_data:
                prices["palladium"] = te_data["palladium"]
                
            # 5. Copper (USD/Lbs)
            if "copper" in te_data:
                prices["copper"] = te_data["copper"]
                
            # 6. Nickel (USD/t)
            if "nickel" in te_data:
                prices["nickel"] = te_data["nickel"]
                
            # 7. Zinc (USD/t)
            if "zinc" in te_data:
                prices["zinc"] = te_data["zinc"]
                
            # 8. Lithium (CNY/t)
            if "lithium" in te_data:
                prices["lithium"] = te_data["lithium"]
                
            # 9. Uranium (USD/lb)
            if "uranium" in te_data:
                prices["uranium"] = te_data["uranium"]
                
            # 10. Cobalt (USD/t)
            if "cobalt" in te_data:
                prices["cobalt"] = te_data["cobalt"]
                
            # 11. Rare Earths (Neodymium CNY/t -> NdPr scale)
            if "neodymium" in te_data:
                prices["rareearth"] = round((te_data["neodymium"] / 945000.0) * 245.0, 1)
                
            # 12. Titanium (Titanium CNY/kg)
            if "titanium" in te_data:
                prices["titanium"] = te_data["titanium"]

            # Date format: dd MMM yyyy, HH:MM
            prices["_last_updated"] = time.strftime("%d %b %Y, %H:%M")
            print(f"Scrape completed successfully at {prices['_last_updated']}!")
            save_stored_prices(prices)
            return prices
            
    except Exception as e:
        print(f"Error occurred during scraping: {e}")
        # Make sure timestamp is updated so dashboard knows when it checked
        prices["_last_updated"] = time.strftime("%d %b %Y, %H:%M") + " (Fallback)"
        save_stored_prices(prices)
        raise e

if __name__ == "__main__":
    run_scraper()
