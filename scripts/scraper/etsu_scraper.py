"""
    Hybrid web scraper using requests/BeautifulSoup for static content and Selenium 
    as a fallback for JS-heavy pages. Optimized with threading for faster scraping.
"""

import requests
from bs4 import BeautifulSoup
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_selenium():
    """Initialize Selenium with headless Chrome."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    driver_path = "/Users/puskarjoshi/Downloads/chromedriver-mac-arm64/chromedriver"  # Update path
    service = Service(driver_path)
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logging.error(f"Failed to initialize Selenium: {e}")
        return None

def scrape_with_bs4(url):
    """Scrape content using requests and BeautifulSoup with lxml parser."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')  # Use lxml for faster parsing
        
        title = soup.title.string if soup.title else "No Title"
        content = soup.body.get_text(separator="\n", strip=True) if soup.body else "No Content"
        
        if len(content.strip()) < 50:  # Threshold for JS check
            return None, "Content too short, likely needs JS rendering"
        
        return {
            "document_title": title,
            "document_link": url,
            "document_content": content
        }, None
    except requests.exceptions.RequestException as e:
        return None, f"BS4 failed: {e}"

def scrape_with_selenium(driver, url):
    """Scrape content using Selenium."""
    try:
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'lxml')  # Use lxml here too
        title = soup.title.string if soup.title else "No Title"
        content = soup.body.get_text(separator="\n", strip=True) if soup.body else "No Content"
        
        return {
            "document_title": title,
            "document_link": url,
            "document_content": content
        }, None
    except Exception as e:
        return None, f"Selenium failed: {e}"

def scrape_url(url, driver=None):
    """Scrape a single URL with BS4, falling back to Selenium if needed."""
    data, error = scrape_with_bs4(url)
    if data:
        return data
    
    if "JS rendering" in str(error) and driver:
        data, selenium_error = scrape_with_selenium(driver, url)
        if data:
            return data
        logging.error(f"Failed to scrape {url}: {selenium_error}")
    else:
        logging.error(f"Failed to scrape {url}: {error}")
    return None

def scrape_etsu_urls(urls, output_path="etsu_scraped_data.json", max_workers=5):
    """Scrape URLs with hybrid BS4/Selenium approach using threading."""
    scraped_data = []
    url_count = len(urls)
    driver = setup_selenium()  # Single Selenium instance for fallbacks
    
    # Use ThreadPoolExecutor for parallel BS4 scraping
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(scrape_url, url, driver): url for url in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                if result:
                    scraped_data.append(result)
                    logging.info(f"Scraped: {url}. {len(scraped_data)}/{url_count}")
            except Exception as e:
                logging.error(f"Error processing {url}: {e}")
    
    if driver:
        driver.quit()
    
    with open(output_path, 'w') as output_file:
        json.dump(scraped_data, output_file, indent=2)
    
    logging.info(f"Scraping completed. Data saved to '{output_path}'.")
    return scraped_data

def main():
    input_path = "etsu_urls.json"
    with open(input_path, 'r') as file:
        data = json.load(file)
    scrape_etsu_urls(data['urls'])

if __name__ == "__main__":
    main()