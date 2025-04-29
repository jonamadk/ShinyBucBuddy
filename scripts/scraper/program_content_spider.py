import time
import requests
from bs4 import BeautifulSoup
import json
import os


class ProgramContentSpider:
    def __init__(self):
        self.missing_descriptions = []  # Store links with missing descriptions

    def fetch_program_content(self, program_type, program_link, program_name):
        """
        Fetch the program content from a given link, including headers, descriptions,
        and course/degree requirements information. If content is missing, log the link.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = requests.get(program_link, headers=headers, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                description_content = soup.select_one('program_description side') or \
                                      soup.select_one('.program_description')
                description_text = ' '.join(description_content.stripped_strings) if description_content else ''

                additional_content = soup.select_one('.custom_leftpad_20')
                additional_text = ' '.join(additional_content.stripped_strings) if additional_content else ''

                if not description_text and not additional_text:
                    print(f"No description or course-related content found for {program_link}")
                    self.missing_descriptions.append({
                        "document_title": program_type,
                        # "document_name": program_name,
                        "document_link": program_link
                    })
                    return []

                sections = []
                if description_content:
                    headers = description_content.find_all('h2') 
                    if headers:
                        for header in headers:
                            # section_title = header.get_text(strip=True)
                            content = []

                            next_sibling = header.find_next_sibling()
                            while next_sibling and next_sibling.name != 'h2':
                                if next_sibling.name:
                                    content.append(next_sibling.get_text(strip=True))
                                next_sibling = next_sibling.find_next_sibling()

                            sections.append({
                                # "section": section_title,
                                "document_content": ' '.join(content).replace('\u00a0', '').replace('\n', ' ').replace("\u2019", "")
                            })
                    else:
                        
                        if program_type not in ["Certificate","Doctorate and masters"]:
                        
                            # Handle case where there are no <h2> headers
                            paragraphs = description_content.find_all('p')
                            general_info_content = []
                            for p in paragraphs:
                                general_info_content.append(' '.join(p.stripped_strings))

                            sections.append({
                                # "section": "General Information",
                                "document_content": ' '.join(general_info_content).replace('\u00a0', '').replace('\n', ' ').replace("\u2019", "")
                            })
                
                if additional_text:
                    sections.append({
                        # "section": "Course and Degree Requirements",
                        "document_content": additional_text.replace('\u00a0', '').replace('\n', ' ').replace("\u2019", "")
                    })

                return sections

            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1} failed for {program_link}: {e}")
                time.sleep(2 ** attempt)

        print(f"Failed to fetch content from {program_link} after {max_retries} attempts")
        self.missing_descriptions.append({
            "document_title": program_type,
            # "document_name": program_name,
            "document_link": program_link
        })
        return []

    def save_program_content(self, data):
        """
        Save program content data to JSON files, sanitizing filenames.
        """
        output_dir = "documents"
        os.makedirs(output_dir, exist_ok=True)

        for program_type, program_data in data.items():
            # Sanitize the filename
            sanitized_program_type = program_type.replace('/', ' and ').replace("’", "").replace("'", "")
            
            file_path = os.path.join(output_dir, f"{sanitized_program_type}.json")

            try:
                with open(file_path, "w") as file:
                    json.dump(program_data, file, indent=4)
                print(f"Saved data for {program_type} to {file_path}.")
            except Exception as e:
                print(f"Error saving data for {program_type}: {e}")


    def save_missing_descriptions(self):
        output_dir = "missing_data"
        os.makedirs(output_dir, exist_ok=True)

        file_path = os.path.join(output_dir, "missing_descriptions.json")
        try:
            with open(file_path, "w") as file:
                json.dump(self.missing_descriptions, file, indent=4)
            print(f"Saved missing descriptions to {file_path}.")
        except Exception as e:
            print(f"Error saving missing descriptions: {e}")
