import os
import json
from collections import defaultdict
from scraper.etsu_spider import EtsuSpider
from scraper.program_content_spider import ProgramContentSpider
from scraper.faculty_data_spider import FacultyDataSpider
from scraper.get_etsu_urls import get_etsu_urls 
from scraper.etsu_scraper import scrape_etsu_urls # Assuming we create this function
import glob
import argparse

class ScrapingPipeline:
    def __init__(self, base_dir="scraped_data"):
        self.base_dir = base_dir
        self.program_url_dir = os.path.join(base_dir, "program_urls")
        self.documents_dir = os.path.join(base_dir, "documents")
        self.missing_dir = os.path.join(base_dir, "missing_data")
        
        # Create directories if they don't exist
        os.makedirs(self.program_url_dir, exist_ok=True)
        os.makedirs(self.documents_dir, exist_ok=True)
        os.makedirs(self.missing_dir, exist_ok=True)


    def step1_get_urls(self):
        """Get all allowed ETSU URLs and scrape them with hybrid approach."""
        print("Step 1: Fetching allowed ETSU URLs...")
        urls_output_path = os.path.join(self.base_dir, "etsu_urls.json")
        urls = get_etsu_urls(urls_output_path)  # Call the function with a custom path
        
        if urls:
            # Scrape general ETSU pages
            output_path = os.path.join(self.documents_dir, "etsu_general_data.json")
            scrape_etsu_urls(urls, output_path)
            print("General ETSU pages scraped successfully")
        else:
            print("Failed to retrieve URLs; skipping scraping step.")


    def step2_scrape_program_links(self):
        """Scrape program links and types"""
        print("Step 2: Scraping program links...")
        programs_list = {
            "Graduate": "https://catalog.etsu.edu/content.php?catoid=57&navoid=3119",
            "Undergraduate": "https://catalog.etsu.edu/content.php?catoid=58&navoid=3362",
        }

        spider = EtsuSpider()
        for program_type_name, url in programs_list.items():
            data = spider.fetch_program_links(url)
            filename = os.path.join(self.program_url_dir, 
                                 f"{program_type_name.lower()}_programs.json")
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Saved {program_type_name} program links")

    def step3_scrape_program_content(self):
        """Scrape program content details"""
        print("Step 3: Scraping program content...")
        spider = ProgramContentSpider()
        program_data_by_type = defaultdict(list)

        for filename in os.listdir(self.program_url_dir):
            if filename.endswith('.json'):
                with open(os.path.join(self.program_url_dir, filename), 'r') as file:
                    programs_list = json.load(file)
                    for program_category in programs_list:
                        program_type = program_category['program_type']
                        for program in program_category['programs']:
                            sections = spider.fetch_program_content(
                                program_type, 
                                program['program_link'], 
                                program['program_name']
                            )
                            for section in sections:
                                program_data = {
                                    "document_title": program_type,
                                    "document_link": program['program_link'],
                                    "document_content": section["document_content"] + " " + program['program_name']
                                }
                                program_data_by_type[program_type].append(program_data)

        spider.save_program_content(program_data_by_type)
        if spider.missing_descriptions:
            spider.save_missing_descriptions()

    def step4_scrape_faculty_data(self):
        """Scrape faculty bio data"""
        print("Step 4: Scraping faculty data...")
        spider = FacultyDataSpider()
        main_url = "https://www.etsu.edu/cbat/computing/faculty-staff"
        
        faculty_data = spider.fetch_faculty_data(main_url)
        detailed_faculty_data = []
        
        for faculty in faculty_data:
            bio_url = faculty.get("document_link", "N/A")
            detailed_data = spider.fetch_faculty_details(bio_url)
            if detailed_data:
                detailed_data['document_content'] = (
                    f"Name: {detailed_data['document_name']}, "
                    f"Title: {detailed_data['document_title']}, "
                    f"Email: {detailed_data['email']}, "
                    f"Phone: {detailed_data['phone']} " + 
                    detailed_data['document_content']
                )
                data = {k: v for k, v in detailed_data.items() 
                       if k not in ["email", "phone", "document_name"]}
                detailed_faculty_data.append(data)
        
        spider.save_faculty_data(detailed_faculty_data)

    def step5_merge_data(self):
        """Merge all scraped data into a single file"""
        print("Step 5: Merging all data...")
        merged_data = []
        json_files = glob.glob(os.path.join(self.documents_dir, "*.json"))
        
        for file in json_files:
            with open(file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    merged_data.extend(data)
        
        output_path = os.path.join(self.base_dir, 'final_merged_data.json')
        with open(output_path, 'w') as f:
            json.dump(merged_data, f, indent=4)
        print(f"Merged {len(json_files)} files into {output_path}")

    def run_all(self):
        """Run the complete pipeline"""
        self.step1_get_urls()
        self.step2_scrape_program_links()
        self.step3_scrape_program_content()
        self.step4_scrape_faculty_data()
        self.step5_merge_data()

def main():
    parser = argparse.ArgumentParser(description='ETSU Data Scraping Pipeline')
    parser.add_argument('--step', 
                       choices=['all', 'urls', 'program_links', 'program_content', 
                              'faculty', 'merge'],
                       default='all',
                       help='Which step(s) to run')
    
    args = parser.parse_args()
    pipeline = ScrapingPipeline()
    
    if args.step == 'all':
        pipeline.run_all()
    elif args.step == 'urls':
        pipeline.step1_get_urls()
    elif args.step == 'program_links':
        pipeline.step2_scrape_program_links()
    elif args.step == 'program_content':
        pipeline.step3_scrape_program_content()
    elif args.step == 'faculty':
        pipeline.step4_scrape_faculty_data()
    elif args.step == 'merge':
        pipeline.step5_merge_data()

if __name__ == "__main__":
    main()