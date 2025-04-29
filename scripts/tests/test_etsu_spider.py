import requests
import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper.etsu_spider import EtsuSpider
from config import SCRAPING_CONFIG

class TestEtsuSpider(unittest.TestCase):
    def setUp(self):
        self.spider = EtsuSpider()
        self.test_url = SCRAPING_CONFIG['base_url']
        
        # Sample HTML content for testing
        self.mock_html = '''
        <html>
            <p><strong>Doctorate/Master's</strong></p>
            <ul class="program-list">
                <li>
                    <a href="/preview_program.php?catoid=58&poid=17035">Computing, M.S.</a>
                </li>
            </ul>
            <p><strong>Undergraduate</strong></p>
            <ul class="program-list">
                <li>
                    <a href="/preview_program.php?catoid=58&poid=17036">Computing, B.S.</a>
                </li>
            </ul>
        </html>
        '''

    def test_initialization(self):
        """Test spider initialization"""
        self.assertEqual(self.spider.base_url, SCRAPING_CONFIG['base_url'])
        self.assertIsNotNone(self.spider.logger)

    @patch('requests.get')
    def test_fetch_program_links(self, mock_get):
        """Test program links fetching"""
        # Mock the response
        mock_response = MagicMock()
        mock_response.text = self.mock_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        programs = self.spider.fetch_program_links(self.test_url)

        # Verify the structure and content
        self.assertEqual(len(programs), 2)
        self.assertEqual(programs[0]['program_type'], "Doctorate/Master's")
        self.assertEqual(programs[1]['program_type'], 'Undergraduate')
        
        # Check program details
        self.assertEqual(len(programs[0]['programs']), 1)
        self.assertEqual(programs[0]['programs'][0]['program_name'], 'Computing, M.S.')
        self.assertTrue(programs[0]['programs'][0]['program_link'].startswith(self.test_url))

    @patch('requests.get')
    def test_fetch_program_links_error(self, mock_get):
        """Test error handling in fetch_program_links"""
        mock_get.side_effect = Exception("Network error")
        programs = self.spider.fetch_program_links(self.test_url)
        self.assertEqual(programs, [])

    @patch('requests.get')
    def test_fetch_program_links_empty_response(self, mock_get):
        """Test handling of empty HTML response"""
        mock_response = MagicMock()
        mock_response.text = '<html></html>'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        programs = self.spider.fetch_program_links(self.test_url)
        self.assertEqual(len(programs), 0)

    def test_save_program_data(self):
        """Test saving program data to file"""
        test_data = [{
            'program_type': 'Test Program',
            'programs': [{'program_name': 'Test', 'program_link': 'http://test.com'}]
        }]
        
        # Create a temporary directory for testing
        test_dir = os.path.join(os.path.dirname(__file__), 'test_output')
        os.makedirs(test_dir, exist_ok=True)
        
        try:
            # Test saving data
            self.spider.save_program_data('test_program', test_data)
            
            # Verify file exists and content is correct
            expected_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'url_source/programURLInfo/test_program_programs.json'
            )
            self.assertTrue(os.path.exists(expected_path))
            
            with open(expected_path, 'r') as f:
                saved_data = json.load(f)
            self.assertEqual(saved_data, test_data)
            
        finally:
            # Cleanup
            if os.path.exists(expected_path):
                os.remove(expected_path)

    def test_save_program_data_invalid_path(self):
        """Test saving to invalid directory path"""
        test_data = [{
            'program_type': 'Test Program',
            'programs': [{'program_name': 'Test', 'program_link': 'http://test.com'}]
        }]
        
        with self.assertLogs(level='ERROR'):
            self.spider.save_program_data('/invalid/path', test_data)

    @patch('requests.get')
    def test_fetch_program_links_bad_response(self, mock_get):
        """Test handling of bad HTTP response"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        programs = self.spider.fetch_program_links(self.test_url)
        self.assertEqual(programs, [])

    def test_save_program_data_empty_data(self):
        """Test saving empty program data"""
        empty_data = []
        self.spider.save_program_data('empty_test', empty_data)
        
        expected_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'url_source/programURLInfo/empty_test_programs.json'
        )
        
        try:
            with open(expected_path, 'r') as f:
                saved_data = json.load(f)
            self.assertEqual(saved_data, empty_data)
        finally:
            if os.path.exists(expected_path):
                os.remove(expected_path)

    @patch('requests.get')
    def test_fetch_program_links_malformed_html(self, mock_get):
        """Test handling of malformed HTML"""
        mock_response = MagicMock()
        mock_response.text = '<html><p><strong>Invalid HTML'
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        programs = self.spider.fetch_program_links(self.test_url)
        self.assertEqual(len(programs), 0)

    def tearDown(self):
        """Clean up after tests"""
        # Remove any test files/directories created during testing
        test_dir = os.path.join(os.path.dirname(__file__), 'test_output')
        if os.path.exists(test_dir):
            import shutil
            shutil.rmtree(test_dir)

if __name__ == '__main__':
    unittest.main(verbosity=2)