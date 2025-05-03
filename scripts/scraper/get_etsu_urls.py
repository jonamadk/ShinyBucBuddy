"""
    Script to get all allowed URLs from the ETSU website for scraping.
"""

import requests
import xml.etree.ElementTree as ET
import json
import re
from datetime import datetime

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

def is_relevant_url(url):
    """Check if URL is relevant based on patterns."""
    # Patterns to keep
    # These patterns are more specific to the ETSU site and should be kept
    # while excluding irrelevant ones. 
    # The patterns are designed to match various sections of the ETSU website.
    keep_patterns = [
    # Libraries
    r'libraries\.etsu\.edu',              # Sherrod Library
    r'etsu\.edu/medlib/',                # Medical Library
    r'libanswers\.etsu\.edu',            # Sherrod Library Help Services
    r'dc\.etsu\.edu',                    # Digital Commons @ ETSU

    # Academic Colleges
    r'etsu\.edu/cas/',                   # College of Arts and Sciences
    r'etsu\.edu/cbat/',                  # College of Business and Technology
    r'etsu\.edu/crhs/',                  # Clinical and Rehabilitative Health Sciences
    r'etsu\.edu/coe/',                   # Clemmer College of Education
    r'etsu\.edu/nursing/',               # College of Nursing
    r'etsu\.edu/cph/',                   # College of Public Health
    r'etsu\.edu/com/',                   # Quillen College of Medicine
    r'etsu\.edu/pharmacy/',              # Gatton College of Pharmacy
    r'etsu\.edu/gradschool/',            # Graduate and Continuing Studies
    r'etsu\.edu/honors/',                # Honors College
    r'etsu\.edu/online/',                # School of Continuing Studies
    r'etsu\.edu/academics/continuingstudies/',  # Continuing Studies

    # Specific Academic Departments (examples, add more as needed)
    r'etsu\.edu/cbat/computing/',        # Computing (already in original pattern)
    r'etsu\.edu/cas/psychology/',        # Psychology
    r'etsu\.edu/pharmacy/pharmsci/',     # Pharmaceutical Sciences
    r'etsu\.edu/cas/appalachianstudies/', # Appalachian Studies

    # Administrative Departments
    r'catalog\.etsu\.edu',               # Academic Catalog (Registrar)
    r'etsu\.edu/admissions/',            # Admissions
    r'etsu\.edu/reg/',                   # Registrar
    r'etsu\.edu/finaid/',                # Financial Aid
    r'etsu\.edu/its/',                   # Information Technology Services
    r'etsu\.edu/research/',              # Research and Sponsored Programs
    r'etsu\.edu/students/',              # Student Life and Enrollment
    r'etsu\.edu/human-resources/',       # Human Resources
    r'etsu\.edu/coe/stem/',              # STEM Education and Lending Library

    # Generic Patterns
    r'faculty-staff',                    # Faculty and staff pages
    r'programs?/',                       # Program pages
    r'degrees?/',                        # Degree pages
    r'curriculum',                       # Curriculum pages
    r'majors?/',                         # Major pages
    r'minors?/'                          # Minor pages
    ]
    
    exclude_patterns = [
        # Year-based exclusions (before 2022)
        r'/(20[0-1][0-9]|202[0-1])(/|$)',  # Years 2000–2021 in URL paths
        r'-[0-1][0-9]-[0-3][0-9]-(20[0-1][0-9]|202[0-1])',  # Date formats like MM-DD-YYYY or YYYY-MM-DD for 2000–2021
        r'/\d{1,2}-[a-zA-Z]+-(20[0-1][0-9]|202[0-1])',     # Date formats like DD-Month-YYYY (e.g., 15-May-2021)

        # ETSU-specific outdated content
        r'etsu\.edu/announcements/',        # Old announcements
        r'etsu\.edu/blog/',                 # Blogs, which may include outdated posts
        r'etsu\.edu/etsu-news/',            # Legacy news sections
        r'etsu\.edu/students/[^/]+/archive/',  # Student organization archives (e.g., https://www.etsu.edu/students/org/archive/)

        # Generic outdated or irrelevant content
        r'/archive(s)?/[^/]*$',            # Archive pages, but not Archives of Appalachia (protected by keep_patterns)
        r'/deprecated/',                   # Deprecated pages
        r'/test/',                         # Test or staging pages
        r'/_development/',                 # Development or beta pages
        r'/backup/',                       # Backup pages
        r'/old-site/',                     # Old website versions
        r'/retired/',                      # Retired pages
        r'/125-chapter/',                  # Old strategic planning pages (retained from original)

        # Course-specific exclusions (often tied to specific semesters)
        r'etsu\.edu/[^/]+/syllabus/',      # Old course syllabi
        r'etsu\.edu/[^/]+/schedule/',      # Past semester schedules
        r'etsu\.edu/[^/]+/courses/20[0-1][0-9]',  # Courses from 2000–2019
        r'etsu\.edu/[^/]+/courses/202[0-1]',      # Courses from 2020–2021
    ]
    
    # Check exclude patterns first
    if any(re.search(pattern, url, re.IGNORECASE) for pattern in exclude_patterns):
        return False
        
    # Then check for relevant patterns
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in keep_patterns)

def is_allowed(url):
    """Check if the URL is allowed and relevant."""
    # First check against disallowed paths
    for path in disallowed_paths:
        if path in url:
            return False
            
    # Then check if it's a PHP file and relevant
    return url.endswith(".php") and is_relevant_url(url)

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
        response.raise_for_status()

        # Parse the XML content
        root = ET.fromstring(response.content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

        # Extract all URLs first
        all_urls = [
            elem.text for elem in root.findall('.//ns:url/ns:loc', namespaces=namespace)
        ]

        # Filter URLs
        filtered_urls = [url for url in all_urls if is_allowed(url)]

        # Store filtered URLs in a JSON file
        with open(output_path, 'w') as json_file:
            json.dump({'urls': filtered_urls}, json_file, indent=2)

        print(f"Found {len(all_urls)} total URLs")
        print(f"Filtered to {len(filtered_urls)} relevant URLs")
        print(f"Saved to '{output_path}'")
        return filtered_urls

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch sitemap: {e}")
        return []
    except Exception as e:
        print(f"Error processing sitemap: {e}")
        return []

if __name__ == "__main__":
    get_etsu_urls()