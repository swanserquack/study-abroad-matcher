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

from scraper.providers.base_provider import BaseProvider
from scraper.models import CourseList, CourseData
from scraper.errors import ValidationError, CourseNotFoundError, ScraperError
from bs4 import BeautifulSoup
from bs4.builder import ParserRejectedMarkup
import re

class WasedaProvider(BaseProvider):
    university_name = "waseda_university"

    def __init__(self) -> None:
        super().__init__()
        self.base_url = "https://www.wsl.waseda.jp/syllabus/"

    def search_by_keyword(self, keyword: str) -> list[CourseList]:
        course_list : list[CourseList] = []
        # For the first page this is just an empty string
        page = ''
        # There are a ton of parameters, but we only need to include the ones with values (it seems), I'm not going to bother documenting the unused ones apart from the ones I already have
        request_body = {
            # Number of results per page
            'p_number': (None, '100'),
            'p_page': (None, str(page)), # Current page number
            'pfrontPage': (None, 'now'), # Currently unknown
            'keyword': (None, keyword), # Search keyword
            'kamoku': (None, ''), # Course title, blank when empty
            'kyoin': (None, ''), # Instructor name, blank when empty
            'p_gakki': (None, ''), # Term - based off index of currently selected option, blank when no selection
            'p_youbi': (None, ''), # Day of the week - based off index of currently selected option, blank when no selection
            'p_jigen': (None, ''), # Class period - based off index of currently selected option * 11 (1st = 11, 2nd = 22 etc), blank when no selection
            'p_gengo': (None, ''), # Language - based off index of currently selected option (plus a leading zero i.e. 05), blank when no selection
            'p_jyugyohoho': (None, ''), # Class method - when empty is an empty string, otherwise each selected option becomes it own field with 'p_jyugyohoho[]' as the identifier and the raw japanese text as the value
            'p_open': (None, ''), # Open course - empty when not selected, 0 when selected
            'p_gakubu': (None, ''), # School - empty when not selected, otherwise based off internal school ID which then causes a refresh of the search form with a new option for management
            'p_keya': (None, ''), # Management - empty when not selected, otherwise based off internal management ID
            'ControllerParameters': (None, 'JAA103SubCon'), # Controller identifier???? What is a controller in this context???
            'pLng' : (None, 'en') # Language parameter, 'en' for english, 'jp' for japanese
        }
        page = 1
        response = self._post(self.base_url + "/index.php", files=request_body)
        # * Waseda use xhtml rather than html, so we use the xml parser otherwise it complains
        soup = BeautifulSoup(response.text, 'xml')
        while True:
            main_course_list_table = soup.find('table', class_='ct-vh') if soup.find('table', class_='ct-vh') else None
            if main_course_list_table is None:
                raise ScraperError("Failed to find main course list table in the response HTML.")

            for row in main_course_list_table.find_all('tr')[1:]: # Skip header row
                cells = row.find_all('td')

                course_name_link = cells[2].find('a')
                course_name = course_name_link.getText(strip=True) if course_name_link else "N/A"

                try:
                    course_code = cells[1].getText(strip=True)
                except (IndexError, AttributeError):
                    course_code = "N/A"

                course_url = str(course_name_link['onclick']) if course_name_link else "N/A"

                course_list.append(CourseList(
                    name=course_name,
                    course_code=course_code,
                    url=course_url,
                ))

            # The actual raw html is Next> but I'm assuming the xml parser just parses it out
            next_arrow = soup.find('a', text='Next') if soup.find('a', text='Next') else None

            if next_arrow is None:
                break

            page += 1
            request_body['p_page'] = (None, str(page))
            response = self._post(self.base_url + "/index.php", files=request_body)
            soup = BeautifulSoup(response.text, 'xml')
        
        if not course_list:
            raise CourseNotFoundError(f"No courses found for '{keyword}'.")
        
        return course_list
    
    def search_by_identifier(self, identifier: str) -> list[CourseList]:
        # Format taken from https://www.waseda.jp/top/en/news/23433 , kind of guessing for lower bounds of numbers
        pattern = re.compile(r"^[A-Z]{4}[1-46-7][0-9][1-9][LSWFPGTBOX]$")
        if not pattern.match(identifier.strip().upper()):
            raise ValidationError(f"The course code '{identifier}' is not valid. Enter a valid Course Code in the format 'XXXX101L'.")
        course_list = self.search_by_keyword(identifier.upper())
        return course_list
    
    def fetch_course_details(self, course_info: CourseList) -> CourseData:
        # We cut out the function call, split the two parameters by the comma, take the second parameter (the course id), strip whitespace and the surrounding quotes
        response = self._get(self.base_url + "JAA104.php" + f"?pKey={course_info.url[12:-1].split(",")[1].strip().replace("'", "")}&pLng=en")
        parsed_data = self.parse_courses(response.text, course_info)
        return parsed_data
    
    def parse_courses(self, raw_content: str, course_info: CourseList) -> CourseData:
        try:
            soup = BeautifulSoup(raw_content, 'xml')
        except ParserRejectedMarkup:
            soup = BeautifulSoup(raw_content, 'html.parser')

        # Find both of the tables as we use both of them for different information
        course_information_tables = soup.find_all('table', class_='ct-common ct-sirabasu')
        
        semester = "N/A"
        # Too long to be turned into a oneliner
        # ! Fragile
        if course_information_tables and (td := course_information_tables[0].find_all('tr')[3].find("td")):
            semester = td.getText(strip=True)

        aims = "N/A"
        # ! Fragile
        if course_information_tables and (td := course_information_tables[1].find_all('tr')[1].find("td")):
            aims = td.getText(strip=True)

        # TODO: When getting rid of ILO's, replace with description extraction
        return CourseData(
            name=course_info.name,
            course_code=course_info.course_code,
            semester=semester,
            aims=aims,
            ilos=aims
        )