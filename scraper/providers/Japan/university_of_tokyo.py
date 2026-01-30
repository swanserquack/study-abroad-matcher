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
from scraper.errors import ValidationError, CourseNotFoundError
from bs4 import BeautifulSoup
from bs4.builder import ParserRejectedMarkup
import re

# Yes the code I write is trash, I know. 
# ! The langauge selection only affects the interface so Japanese course descriptions/aims/ilos will still be in Japanese, not much I can do here (future translation feature?)
# Their MIMA system is soooo cool 

class UTokyoProvider(BaseProvider):
    university_name = "university_of_tokyo"

    def __init__(self) -> None:
        """
        Initialize the UTokyoScraper with setting up the session and base URL.
        """
        super().__init__()
        self.base_url = "https://catalog.he.u-tokyo.ac.jp/"

    def search_by_keyword(self, keyword: str) -> list[CourseList]:
        course_list : list[CourseList] = []
        page = 1
        # * Same as University of Glasgow here, the page automatically updates year so we don't need to worry
        # What does type=jd mean?
        response = self._get(self.base_url + f"result?type=jd&q={keyword}&interface_language=en")
        try:
            soup = BeautifulSoup(response.text, 'lxml')
        except ParserRejectedMarkup:
            soup = BeautifulSoup(response.text, 'html.parser')
        while True:
            # Find all the course containers
            maincontent_div = soup.find_all('div', class_='catalog-search-result-card')
            for course in maincontent_div:
                course_name_link = course.select_one('a')

                course_name = course.find('span', class_='catalog-search-result-card-header-name')
                course_name = course_name.getText(strip=True) if course_name else "N/A"

                raw_href = course_name_link.get('href') if course_name_link else None
                course_url = str(raw_href) if raw_href is not None else "N/A"

                # Normally each course has at least two cells, one which contains the text 'Code' and the other one which contains the actual code, if the course runs at different periods then there are multiple cells but we can just grab the first one (index 1)
                # The unchained version of this was even more of a mess than this so I kind of had to do some compromises here
                try:
                    course_code = course.find_all('div', class_='code-cell')[1].find_all('div')[1].getText(strip=True)
                except (IndexError, AttributeError):
                    course_code = "N/A"

                course_list.append(CourseList(
                    name=course_name,
                    course_code=course_code,
                    url=course_url
                ))

            # Check if we can go up a page
            nav_arrow = soup.find_all('i', class_='fe-arrow-right')
            # There are always two arrows in each page when we can paginate forward, one near the top for some decoration and the one at the bottom for pagination, thus if there are not two arrows we can't paginate anymore
            if len(nav_arrow) != 2:
                break

            page += 1
            # When using the pagination it automatically adds the &faculty_id=&facet={} parameters which since they are blank and seem to have no effect we are going to ignore
            response = self._get(self.base_url + f"result?type=jd&q={keyword}&interface_language=en&page={page}")
            soup = BeautifulSoup(response.text, 'lxml')
        if not course_list:
            raise CourseNotFoundError(f"No courses found for '{keyword}'.")
        return course_list
    
    # TODO: This identifier search works okayish, there is no other alternative so we have to use the keyword search, temporary fix in place which filters the results after we have stepped through all the pages, it would be better to not waste as much time paginating but this will do for now
    def search_by_identifier(self, identifier: str) -> list[CourseList]:
        # Matching spec listed here: https://www.u-tokyo.ac.jp/content/course-numbering.pdf
        pattern = re.compile(r"^[CFG][A-Z]{2}-[A-Z]{2}[1-7][A-Z0-9]{3}[LSEPTZ][1-59]$") 
        if not pattern.match(identifier.strip()):
            raise ValidationError(f"The course code '{identifier}' is not valid. Enter a valid Course Code in the format 'XXX-XXXXXXXX'.")
        # * The identifier does not need to be capitalised as it has little effect on the search results
        # Just reuse the keyword search as the search function works for both name and code
        course_list = self.search_by_keyword(identifier)
        # Filter the results to only include those that match the identifier, we need the upper in case the user put in a lowercase code
        course_list = [course for course in course_list if course.course_code.upper() == identifier.strip().upper()]
        return course_list
    
    def fetch_course_details(self, course_info: CourseList) -> CourseData:
        response = self._get(self.base_url + course_info.url + "&interface_language=en") # Just to make sure that the interface is in English, not sure if this actually makes a difference
        parsed_data = self.parse_courses(response.text, course_info)
        return parsed_data

    def parse_courses(self, raw_content: str, course_info: CourseList) -> CourseData:
        try:
            soup = BeautifulSoup(raw_content, 'lxml')
        except ParserRejectedMarkup:
            soup = BeautifulSoup(raw_content, 'html.parser')

        # * There are 5 potential semesters, S1, S2, A1, A2 and W (There are only 61 courses which use W). The website has a css class which is used just for those thing so we plan to just search and see if we have any of those
        # ? I did think about checking for text however in my opinion that would be too fragile as the actual course description *could* contain those strings. Is this much better? Maybe just a bit 
        semester_classes = ['color-semester-a1', 'color-semester-a2', 'color-semester-s1', 'color-semester-s2', 'color-semester-w']
        semester = ""
        for semester_css_class in semester_classes:
            semester_span = soup.find('span', class_=semester_css_class)
            if semester_span is not None:
                semester += ' ' + semester_span.getText(strip=True)

        # Get rid of space at the start if semesters are found
        semester = semester.strip()
        if semester == "":
            semester = "N/A"

        # I don't really agree with their definiton of this text area being the aims, I'd say its more of a general description but hey if they say so 
        aims_div = soup.find('div', class_='catalog-page-detail-lecture-aim')
        aims = aims_div.getText(strip=True) if aims_div is not None else "N/A"

        # ! For this university sometimes the aims text is basically the description of the course, nothing else fits either category well
        return CourseData(
            name=course_info.name,
            course_code=course_info.course_code,
            semester=semester,
            description=aims,
            aims=aims

        )
    
