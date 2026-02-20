# Copyright (C) 2026 swanserquack
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import re
from bs4 import BeautifulSoup, ParserRejectedMarkup
import requests
from requests.adapters import HTTPAdapter, Retry

class PeopleSoftCourseSearch:
    """
    A helper class to interact with the PeopleSoft course search system.
    This is meant to be provider agnostic and reusable across different providers.
    However there's only so much generalization possible with a sample size of 1 so right now its pretty UCalgary specific.
    When we discover more universities using Peoplesoft we can refactor further if needed.
    """
    def __init__(self, base_url: str, intial_url: str):

        self.session = requests.Session()
        # Yes officer, we are a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0',
            'Accept': '*/*',
            'Accept-Language': 'en-GB,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://csprd.my.ucalgary.ca',
            'Connection': 'keep-alive',
        })
        # Read more info on backoff in base_provider.py
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_jitter=0.5
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.base_url = base_url
        self.initial_url = intial_url
        # Some kind of state number used by PeopleSoft to track requests??
        self.state_num = 0


    def new_search(self) -> requests.Response:
        """
        Reset the search state for a new search.
        Call this before performing another search with the same session.
        """
        # print("[Reset] Preparing for new search...")
        self.state_num += 1
        response = self.session.post(self.base_url, data={
            'ICAJAX': '1',
            'ICNAVTYPEDROPDOWN': '1',
            'ICType': 'Panel',
            'ICElementNum': '0',
            'ICStateNum': str(self.state_num),
            'ICAction': 'CLASS_SRCH_WRK2_SSR_PB_MODIFY',
            'ICModelCancel': '0',
            'ICXPos': '0',
            'ICYPos': '0',
            'ResponsetoDiffFrame': '-1',
            'TargetFrameName': 'None',
            'FacetPath': 'None',
            'ICFocus': '',
            'ICSaveWarningFilter': '0',
            'ICChanged': '-1',
            'ICSkipPending': '0',
            'ICAutoSave': '0',
            'ICResubmit': '0',
            'ICActionPrompt': 'false',
            'ICPanelName': '',
            'ICFind': '',
            'ICAddCount': '',
            'ICAppClsData': '',
        })
        return response

    def get_search_results(self, semester:str, subject:str, course_number:int) -> str:
        # Get all our initial cookies, IDs, etc. This needs to be called each time as without it PeopleSoft returns cached results
        # Kind of weird but whatever
        self.session.get(self.initial_url)
        self.state_num += 1

        # Grabbed from real requests
        semester_server_update_data = {
            'ICAJAX': '1',
            'ICNAVTYPEDROPDOWN': '1',
            'ICType': 'Panel',
            'ICElementNum': '0',
            'ICStateNum': str(self.state_num),
            'ICAction': 'CLASS_SRCH_WRK2_STRM$35$',
            'ICModelCancel': '0',
            'ICXPos': '0',
            'ICYPos': '0',
            'ResponsetoDiffFrame': '-1',
            'TargetFrameName': 'None',
            'FacetPath': 'None',
            'ICFocus': '',
            'ICSaveWarningFilter': '0',
            'ICChanged': '-1',
            'ICSkipPending': '0',
            'ICAutoSave': '0',
            'ICResubmit': '0',
            'ICActionPrompt': 'false',
            'ICPanelName': '',
            'ICFind': '',
            'ICAddCount': '',
            'ICAppClsData': '',
            'CLASS_SRCH_WRK2_STRM$35$': semester,
        }
        # Update the server to set our semester to the appropriate semester
        self.session.post(self.base_url, data=semester_server_update_data)
        self.state_num += 1
        
        # Grabbed from real requests
        search_request_data = {
            'ICAJAX': '1',
            'ICNAVTYPEDROPDOWN': '1',
            'ICType': 'Panel',
            'ICElementNum': '0',
            'ICStateNum': str(self.state_num),
            'ICAction': 'CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH',
            'ICModelCancel': '0',
            'ICXPos': '0',
            'ICYPos': '0',
            'ResponsetoDiffFrame': '-1',
            'TargetFrameName': 'None',
            'FacetPath': 'None',
            'ICFocus': '',
            'ICSaveWarningFilter': '0',
            'ICChanged': '-1',
            'ICSkipPending': '0',
            'ICAutoSave': '0',
            'ICResubmit': '0',
            'ICActionPrompt': 'false',
            'ICPanelName': '',
            'ICFind': '',
            'ICAddCount': '',
            'ICAppClsData': '',
            'CLASS_SRCH_WRK2_STRM$35$': semester,
            'SSR_CLSRCH_WRK_SUBJECT_SRCH$0': subject,
            'SSR_CLSRCH_WRK_CATALOG_NBR$1': course_number,
            'SSR_CLSRCH_WRK_SSR_OPEN_ONLY$chk$3': 'N',
        }
        # Actually submit our search request
        self.session.post(self.base_url, data=search_request_data)
        self.state_num += 1

        # Grabbed from real requests
        search_retrieval_data = {
            'ICAJAX': '1',
            'ICNAVTYPEDROPDOWN': '1',
            'ICType': 'Panel',
            'ICElementNum': '0',
            'ICStateNum': str(self.state_num),
            'ICAction': '#ICSave',
            'ICModelCancel': '0',
            'ICXPos': '0',
            'ICYPos': '0',
            'ResponsetoDiffFrame': '-1',
            'TargetFrameName': 'None',
            'FacetPath': 'None',
            'ICFocus': '',
            'ICSaveWarningFilter': '0',
            'ICChanged': '-1',
            'ICSkipPending': '0',
            'ICAutoSave': '0',
            'ICResubmit': '0',
            'ICActionPrompt': 'false',
            'ICPanelName': '',
            'ICFind': '',
            'ICAddCount': '',
            'ICAppClsData': '',
        }
        # Grab the results page
        response = self.session.post(self.base_url, data=search_retrieval_data)

        return response.text
    

    def parse_results_page(self, html_content: str) -> list[tuple[str, str, str]]:
        """
        Parse the results page and return a list of the courses found.
        This is extremely UCalgary specific as seen with the specific regex and HTML structure parsing.
        As said earlier, only have a sample size of 1.
        """
        try:
            soup = BeautifulSoup(html_content, 'xml')
        except ParserRejectedMarkup:
                soup = BeautifulSoup(html_content, 'lxml')
        courses : list[tuple[str,str,str]] = []
        semester = None

        # Grab all FIELD elements
        fields = soup.find_all('FIELD')

        for field in fields:
            # Extract string content from FIELD
            if field.string:
                field_content = field.string
                # Parse the HTML content inside the FIELD
                field_soup = BeautifulSoup(field_content, 'html.parser')

                # Extract the semester with which we searched for if not already found, setting up code for this now so that we can build dynamic semester/dates easier
                if semester is None:
                    semester_element = field_soup.find('span', id='DERIVED_CLSRCH_SSS_PAGE_KEYDESCR')
                    if semester_element:
                        full_text = semester_element.get_text(strip=True)
                        # Extract semester from the text, example: "University of Calgary | Winter 2025"
                        if '|' in full_text:
                            semester = full_text.split('|')[1].strip()
                
                # Ensure that the semester is set to something even if we fail to extract it, makes it easier to debug and ensure that semester is a str
                semester = semester if semester else "Unknown Semester"


                # Find all course header/title boxes 
                course_elements = field_soup.find_all('td', class_='PAGROUPBOXLABELLEVEL1')
                
                for element in course_elements:
                    # Extract text from the element
                    text = element.get_text(strip=True)
                    
                    # Pattern to match course code and title, regex knowledge slowly building...
                    # Set to match A-Z instead of specific ucalgary prefixes to allow for reusability
                    # Set to match A-Z from 1 for now 
                    # Regex 101 shows this loops around collapsibile section text a ton, look into this???
                    pattern = r'^([A-Z]+\s+[0-9]+(?:\.[0-9]+)?[AB]?)\s{0,1000}-\s{0,1000}([^\n]{0,1000})$'
                    match = re.search(pattern, text)
                    
                    if match:
                        # Grab from the regex groups, course code only used in building the semester index, not elsewhere
                        course_code = str(match.group(1).strip())
                        course_title = str(match.group(2).strip())
                        # print(course_code, course_title, semester)

                        course_code = course_code if course_code else "NULL"
                        course_title = course_title if course_title else "Unknown Title"

                        courses.append((course_code, course_title, semester))
                        
                

        return courses