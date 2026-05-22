import time
import os
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup - saving everything to Desktop like I usually do
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
output_folder = os.path.join(desktop_path, "GTO_All_Spots")
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

base_url = "https://app.gtowizard.com/solutions"

# These are the filters I need to run
# Wasn't sure about the rake parameter format so leaving None for some
filter_configs = [
    # Cash games - NL25 different stack depths (this is what my coach wanted)
    {"game_type": "Cash6mGeneral_6mNL25R25", "stack_depth": "20", "rake_setting": "NL25"},
    {"game_type": "Cash6mGeneral_6mNL25R25", "stack_depth": "50", "rake_setting": "NL25"},
    {"game_type": "Cash6mGeneral_6mNL25R25", "stack_depth": "100", "rake_setting": "NL25"},
    {"game_type": "Cash6mGeneral_6mNL25R25", "stack_depth": "200", "rake_setting": "NL25"},
    {"game_type": "Cash6mGeneral_6mNL25R25", "stack_depth": "300", "rake_setting": "NL25"},
    # NL10 
    {"game_type": "Cash6mGeneral_6mNL10R25", "stack_depth": "100", "rake_setting": "NL10"},
    # 8-max live games - not sure about rake
    {"game_type": "Cash8mLiveGeneral_8mcEVR25", "stack_depth": "100", "rake_setting": None},
    # Heads up
    {"game_type": "CashHuGeneral_cEVR25", "stack_depth": "100", "rake_setting": None},
    # Full ring 9-max
    {"game_type": "Cash9mGeneral_9mNL25R25", "stack_depth": "100", "rake_setting": "NL25"},
    # MTTs - might add more later
    {"game_type": "MTTGeneral_8m", "stack_depth": "100", "rake_setting": None},
]

def build_filter_url(game_type, stack_depth, rake):
    """Constructs the URL with all the filter params - took me a while to figure these out"""
    url_params = (
        f"solution_type=gwiz&gmfs_solution_tab=ai_sols&"
        f"gametype={game_type}&depth={stack_depth}&gmff_depth={stack_depth}&"
        f"gmfft_sort_key=0&gmfft_sort_order=desc&gmff_stacks_type=SYMMETRIC"
    )
    if rake:
        url_params += f"&gmff_rake={rake}"
    return f"{base_url}?{url_params}"

def get_spot_links():
    """Grab all the solution links from the table - this was tricky"""
    # Sometimes it loads slowly
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/solutions?'], tr[data-href]"))
        )
    except:
        # If timeout, just continue and hope for the best
        pass
    
    # Find all the links
    all_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'solutions?')]")
    unique_urls = set()
    
    for link in all_links:
        href = link.get_attribute("href")
        if href and "board=" in href:
            unique_urls.add(href)
        elif href and "history_spot" not in href and "soltab=strategy" in href:
            unique_urls.add(href)
    
    # Backup method if the first didn't work (some pages use different structure)
    if not unique_urls:
        rows = driver.find_elements(By.CSS_SELECTOR, "tr[data-href], div[data-url]")
        for row in rows:
            url = row.get_attribute("data-href") or row.get_attribute("data-url")
            if url and url.startswith("/solutions?"):
                unique_urls.add(f"https://app.gtowizard.com{url}")
    
    return list(unique_urls)

def check_if_valid_solution():
    """Make sure we're not looking at an error page (happens a lot actually)"""
    page_text = driver.page_source.lower()
    error_messages = [
        "there is no solution for this spot",
        "no solution for this spot",
        "doesn't have any meaningful range",
        "please select a heads-up post-flop spot"
    ]
    for msg in error_messages:
        if msg in page_text:
            return False
    return True

# Start the browser
print("="*70)
print("Starting GTO scraper - this might take a while")
print("="*70)
print(f"Saving screenshots to: {output_folder}")

# Setting up chrome with undetected driver to avoid bot detection
chrome_options = uc.ChromeOptions()
chrome_options.add_argument("--window-size=1920,1080")
driver = uc.Chrome(options=chrome_options)

# Need to login manually once
driver.get("https://app.gtowizard.com")
input("\n>>> Please login in the browser window, then press Enter to continue...\n")

spots_saved = 0
total_configs = len(filter_configs)

# Loop through all our filter combinations
for i, config in enumerate(filter_configs, 1):
    game_type = config["game_type"]
    stack_depth = config["stack_depth"]
    rake = config["rake_setting"]
    
    print(f"\n[{i}/{total_configs}] Working on: {game_type}, depth={stack_depth}, rake={rake}")
    
    # Load the solutions page with current filters
    target_url = build_filter_url(game_type, stack_depth, rake)
    print(f"    Loading solutions page...")
    driver.get(target_url)
    time.sleep(5)  # Give it a moment to render
    
    # Extract all spot URLs
    spot_urls = get_spot_links()
    print(f"    Found {len(spot_urls)} spots on this page")
    
    if not spot_urls:
        print("    No spots found, moving to next filter combo")
        continue
    
    # Visit each spot and take screenshots
    for idx, url in enumerate(spot_urls, 1):
        print(f"        [{idx}/{len(spot_urls)}] Loading spot...", end=" ", flush=True)
        try:
            driver.get(url)
            time.sleep(3)  # Wait for strategies to load
            
            if not check_if_valid_solution():
                print("Skipping - no solution available")
                continue
            
            # Build filename from the spot details
            filename = f"{game_type}_depth{stack_depth}"
            if rake:
                filename += f"_rake{rake}"
            
            # Add board or preflop info to filename if available
            if "board=" in url:
                board_match = re.search(r'board=([^&]+)', url)
                if board_match:
                    filename += f"_{board_match.group(1)[:15]}"
            elif "preflop_actions=" in url:
                actions_match = re.search(r'preflop_actions=([^&]+)', url)
                if actions_match:
                    filename += f"_{actions_match.group(1)[:20]}"
            
            filename += f"_{idx}.png"
            # Clean up filename (remove weird characters)
            filename = re.sub(r'[^a-zA-Z0-9_-]', '_', filename)[:100]
            
            filepath = os.path.join(output_folder, filename)
            driver.save_screenshot(filepath)
            print(f"Saved!")
            spots_saved += 1
            
        except Exception as e:
            print(f"Error: {e}")
        
        # Small pause between spots to be nice to their server
        time.sleep(0.5)
    
    # Pause between filter categories
    time.sleep(2)

print("\n" + "="*70)
print(f"All done! Saved {spots_saved} spots to {output_folder}")
print("="*70)
driver.quit()
