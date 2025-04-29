from bs4 import BeautifulSoup
import requests
import json
import os
import sys
from urllib.parse import urljoin

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SCRAPING_CONFIG
from utils.logger import setup_logger

logger = setup_logger('etsu_spider')


class EtsuSpider:
    def __init__(self):
        self.base_url = SCRAPING_CONFIG['base_url']
        self.logger = logger

    def fetch_program_links(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status() # Raise an error for bad responses
            soup = BeautifulSoup(response.text, 'html.parser')
            
            program_data = []
            for p_tag in soup.find_all('ul', class_='program-list'):
                program_type = p_tag.find_previous('p').strong.text
                if program_type == "Doctorate/Master\u2019s":
                    program_type = "Doctorate and Masters"
                programs = []

                for li in p_tag.find_all('li'):
                    program_name = li.find('a').text
                    relative_link = li.find('a')['href']
                    program_link = urljoin(url, relative_link)  # Create the full URL
                    
                    programs.append({
                        'program_name': program_name,
                        'program_link': program_link
                    })
                
                program_data.append({
                    'program_type': program_type,
                    'programs': programs
                })
            self.logger.info(f"Found {len(program_data)} programs")
            return program_data
        
        except Exception as e:
            self.logger.error(f"Error fetching program links: {str(e)}")
            return []


    def save_program_data(self, program_type_name, program_data):
        try:
            directory_path = os.path.join(os.path.dirname(__file__), '../url_source/programURLInfo')
            os.makedirs(directory_path, exist_ok=True)
            
            filename = os.path.join(directory_path, f"{program_type_name.lower().replace(' ', '_')}_programs.json")
            with open(filename, 'w') as file:
                json.dump(program_data, file, indent=4)
            
            print(f"Saved scraped data for {program_type_name} in {filename}")
            self.logger.info(f"Saved scraped data for {program_type_name} in {filename}")
            self.logger.info(f"Saved {len(program_data)} programs for {program_type_name}")

        except Exception as e:
            self.logger.error(f"Error saving program data: {str(e)}")
