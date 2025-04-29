import os 
from datetime import timedelta

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "Documents")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Scraping configuration
SCRAPING_CONFIG = { 'base_url': 'https://catalog.etsu.edu',   
                    'programs_urls':{        
                        "Graduate": "https://catalog.etsu.edu/content.php?catoid=57&navoid=3119",   
                        "Undergraduate": "https://catalog.etsu.edu/content.php?catoid=58&navoid=3362",
                                    },   
                    'faculty_url': "https://www.etsu.edu/cbat/computing/faculty-staff",   
                    'max_retries': 3,  
                    'timeout': 30,   
                    'delay': 1
                 }

# Chrome WebDriver settings
CHROME_DRIVER_PATH = "/Users/puskarjoshi/Downloads/chromedriver-mac-arm64/chromedriver"
CHROME_OPTIONS = [    "--headless",    "--disable-gpu",    "--no-sandbox"]

# Output file paths
FILE_PATHS = {    
    'etsu_urls': os.path.join(OUTPUT_DIR, "etsu_urls.json"),    
    'merged_data': os.path.join(OUTPUT_DIR, "combined_data_with_metadata.json"),    
    'temp_dir': os.path.join(OUTPUT_DIR, "temp")

}
