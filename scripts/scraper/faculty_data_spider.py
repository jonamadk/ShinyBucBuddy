from bs4 import BeautifulSoup
import requests
import json
import os
from urllib.parse import urljoin

class FacultyDataSpider:
    def fetch_faculty_data(self, main_url):
        response = requests.get(main_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        base_url = "https://www.etsu.edu"

        faculty_data = []

        # Find all JSON-LD script tags and corresponding <h3> elements
        scripts = soup.find_all("script", type="application/ld+json")
        bio_links = soup.select("h3 a")  # Select all <a> tags within <h3>

        for script, link in zip(scripts, bio_links):
            try:
                data = json.loads(script.string)
                if data["@type"] == "Person":
                    faculty = {
                        "document_name": data.get("name", "No name found"),
                        "document_title": data.get("jobTitle", "No title found"),
                        "phone": data.get("telephone", "No phone found"),
                        "document_link": urljoin(base_url, link.get("href", "No bio URL found")),  # Get href from <a>
                        "email": "info@etsu.edu"  # Default or fetched email if available
                    }
                    faculty_data.append(faculty)
            except json.JSONDecodeError:
                continue  # Skip if JSON is invalid

        return faculty_data

    def fetch_faculty_details(self, bio_url):
        if not bio_url or bio_url == 'N/A':
            print("Invalid or missing URL. Skipping.")
            return None
        response = requests.get(bio_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get name, title, email, phone, and bio
        name = soup.find('h1').get_text(strip=True)
        title_tag = soup.find('h2', role='doc-subtitle')
        title = title_tag.get_text(strip=True) if title_tag else 'No title found'
        
        email = soup.find('a', href=lambda href: href and "mailto" in href).get_text(strip=True) if soup.find('a', href=lambda href: href and "mailto" in href) else "N/A"
        phone = soup.find('a', href=lambda href: href and "tel" in href).get_text(strip=True) if soup.find('a', href=lambda href: href and "tel" in href) else "N/A"
        
        bio_section = soup.find('main', class_='bio')
        bio_paragraph = bio_section.find('p') if bio_section else None
        bio = bio_paragraph.get_text(" ", strip=True) if bio_paragraph else "N/A"

        if bio:
            bio = ' '.join(bio.split())
        return {
            'document_name': name,
            'document_title': title,
            'email': email,
            'phone': phone, 
            'document_link': bio_url,
            'document_content': bio,
        }

    def save_faculty_data(self, faculty_data):
        directory_path = os.path.join(os.path.dirname(__file__), 'documents')
        os.makedirs(directory_path, exist_ok=True)
        
        filename = os.path.join(directory_path, 'computing_faculty_data.json')
        with open(filename, 'w') as file:
            json.dump(faculty_data, file, indent=4)
        
        print(f"Saved faculty data in {filename}")