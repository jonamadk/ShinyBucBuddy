"""
    Script to get all allowed URLs from the ETSU website for scraping.
"""

import requests
import xml.etree.ElementTree as ET
import json

# Disallowed paths as of Dec 3rd 2024
disallowed_paths = [
    "/_19t/",
    "/_testing/",
    "/_training/",
    "/_syllabi-test/",
    "/_zz-dev/",
    "/_zz-development/",
    "/_23t/",
    "/etsu/news/",
    "/etsu-news/",
    "/old_delete_news/",
    "/news/",
    "/students/mcc/programs/discover/forms/map.php",
    "/etsu-news/2020/03-march/covid-19-testing.php",
    "/zz_final_testing/",
    "/_zz_development/",
    "/zz_nav-testing/"
]

def is_allowed(url):
    """Check if the URL is allowed based on disallowed paths."""
    for path in disallowed_paths:
        if path in url:
            return False
    return url.endswith(".php")

def get_etsu_urls(output_path='etsu_urls.json'):
    """
    Fetch and filter allowed URLs from the ETSU sitemap, saving them to a JSON file.
    
    Args:
        output_path (str): Path to save the JSON file with URLs (default: 'etsu_urls.json')
    
    Returns:
        list: List of filtered URLs
    """
    try:
        # Fetch the sitemap
        response = requests.get('https://www.etsu.edu/sitemap.xml')
        response.raise_for_status()  # Ensure the request was successful

        # Parse the XML content
        root = ET.fromstring(response.content)

        # Define the namespace
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

        # Extract and filter URLs
        urls = [
            elem.text for elem in root.findall('.//ns:url/ns:loc', namespaces=namespace)
            if is_allowed(elem.text)
        ]

        # Store filtered URLs in a JSON file
        with open(output_path, 'w') as json_file:
            json.dump({'urls': urls}, json_file, indent=2)

        print(f"Extracted {len(urls)} .php URLs and saved to '{output_path}'.")
        return urls

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch sitemap: {e}")
        return []
    except Exception as e:
        print(f"Error processing sitemap: {e}")
        return []

if __name__ == "__main__":
    # For standalone execution
    get_etsu_urls()