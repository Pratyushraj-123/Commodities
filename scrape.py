import urllib.request
import ssl
import re
import json
import time
import os

JS_FILE = "prices.js"
JSON_FILE = "prices.json"

# Default fallback values matching the dashboard defaults
DEFAULT_PRICES = {
    "gold": 4509.0,
    "silver": 76.11,
    "platinum": 1973.0,
    "palladium": 1387.0,
    "copper": 13200.0,
    "nickel": 19143.0,
    "zinc": 3100.0,
    "lithium": 24300.0,
    "uranium": 93.0,
    "cobalt": 34000.0,
    "rareearth": 245.0,
    "antimony": 22500.0,
    "tungsten": 3050.0,
    "vanadium": 10500.0,
    "niobium": 50.0,
    "titanium": 14500.0,
    "fluorite": 580.0
}

def load_stored_prices():
    # Attempt to load from JSON first, then JS, then defaults
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading prices.json: {e}")
            
    if os.path.exists(JS_FILE):
        try:
            with open(JS_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                match = re.search(r'window\.LIVE_COMMODITY_PRICES\s*=\s*(\{.*?\});', content, re.DOTALL)
                if match:
                    return json.loads(match.group(1))
        except Exception as e:
            print(f"Error parsing prices.js: {e}")
            
    return DEFAULT_PRICES.copy()

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

def run_scraper():
    print("Scraping latest commodities data from Trading Economics...")
    prices = load_stored_prices()
    
    usd_cny = fetch_usd_cny()
    
    url = "https://tradingeconomics.com/commodities"
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=8.0) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Simple regex to extract name and price from TE table
            pattern = re.compile(
                r'href="/commodity/([^"]+)"[^>]*>.*?<b>([^<]+)</b>.*?<td id="p" class="datatable-item"[^>]*>\s*([\d,.]+)\s*</td>',
                re.DOTALL | re.IGNORECASE
            )
            
            matches = pattern.findall(html)
            te_data = {}
            for path, name, val in matches:
                clean_val_str = re.sub(r'[^\d.]', '', val.strip())
                try:
                    te_data[path.lower()] = float(clean_val_str)
                except ValueError:
                    pass
            
            if not te_data:
                raise Exception("Failed to parse any commodity data from Trading Economics HTML.")
            
            # Apply mappings and conversions
            # 1. Gold (USD/oz)
            if "gold" in te_data:
                prices["gold"] = te_data["gold"]
            
            # 2. Silver (USD/oz)
            if "silver" in te_data:
                prices["silver"] = te_data["silver"]
                
            # 3. Platinum (USD/oz)
            if "platinum" in te_data:
                prices["platinum"] = te_data["platinum"]
                
            # 4. Palladium (USD/oz)
            if "palladium" in te_data:
                prices["palladium"] = te_data["palladium"]
                
            # 5. Copper (USD/Lbs -> USD/Tonne)
            if "copper" in te_data:
                prices["copper"] = round(te_data["copper"] * 2204.62262, 1)
                
            # 6. Nickel (USD/t)
            if "nickel" in te_data:
                prices["nickel"] = te_data["nickel"]
                
            # 7. Zinc (USD/t)
            if "zinc" in te_data:
                prices["zinc"] = te_data["zinc"]
                
            # 8. Lithium (CNY/t -> USD/t)
            if "lithium" in te_data:
                prices["lithium"] = round(te_data["lithium"] / usd_cny, 1)
                
            # 9. Uranium (USD/lb)
            if "uranium" in te_data:
                prices["uranium"] = te_data["uranium"]
                
            # 10. Cobalt (USD/t)
            if "cobalt" in te_data:
                prices["cobalt"] = te_data["cobalt"]
                
            # 11. Rare Earths (Neodymium CNY/t -> NdPr scale)
            if "neodymium" in te_data:
                prices["rareearth"] = round((te_data["neodymium"] / 945000.0) * 245.0, 1)
                
            # 12. Titanium (Titanium CNY/kg -> Titanium USD/t scale)
            if "titanium" in te_data:
                prices["titanium"] = round((te_data["titanium"] / 48.5) * 14500.0, 1)

            # Date format: dd MMM yyyy, HH:MM
            prices["_last_updated"] = time.strftime("%d %b %Y, %H:%M")
            print(f"Scrape completed successfully at {prices['_last_updated']}!")
            save_stored_prices(prices)
            
    except Exception as e:
        print(f"Error occurred during scraping: {e}")
        # Make sure timestamp is updated so dashboard knows when it checked
        prices["_last_updated"] = time.strftime("%d %b %Y, %H:%M") + " (Fallback)"
        save_stored_prices(prices)
        raise e

if __name__ == "__main__":
    run_scraper()
