from scraper.providers.base_provider import BaseProvider
from scraper.models import CourseList, CourseData
from scraper.errors import ValidationError, CourseNotFoundError
from bs4 import BeautifulSoup
from bs4.builder import ParserRejectedMarkup
import re

# * Needs to be full name as we also have Glasgow Caledonian University
class UniversityOfGlasgowProvider(BaseProvider):
    university_name = "university_of_glasgow"
    def __init__(self) -> None:
        """
        Initializes the University of Glasgow provider.
        """
        super().__init__()
        self.base_url = "https://www.gla.ac.uk/coursecatalogue/"

    def search_by_keyword(self, keyword: str) -> list[CourseList]:
        course_list : list[CourseList]= []
        page = 1
        # d = REG code for the school the course belongs to, s = subject area, l = course level, c = course credits, wt = 'typically offered' (sem 1, sem 2, etc), HIDDEN PARAMETER v = visiting student courses (true/false) and HIDDEN PARAMETER c4l = cirriculum for life (true/false)
        response = self._get(self.base_url + f"searchresults?q={keyword}&d=&s=&l=&c=&wt=&_search=Search")
        soup = BeautifulSoup(response.text, 'lxml')
        while True:
            maincontent_div = soup.find_all('div', class_='catSearchResult')

            for course in maincontent_div:
                course_name_link = course.select_one('a')
                course_name = course_name_link.getText(strip=True) if course_name_link else "N/A"

                raw_href = course_name_link.get('href') if course_name_link else None
                course_url = str(raw_href) if raw_href is not None else "N/A"

                course_code = course.find(text=True, recursive=False)
                course_code = str(course_code) if course_code is not None else "N/A"
                course_code = course_code.strip()
                
                # print(course_name, course_url, course_code_str)
                course_list.append(CourseList(
                    name=course_name,
                    course_code=course_code,
                    url=course_url
                ))

            # check for a 'Next' navigation link to continue paging
            nav_link = soup.find('a', class_='catSearchNavLink')
            if not nav_link or nav_link.get_text(strip=True) != 'Next':
                break

            page += 1
            response = self._get(self.base_url + f"searchresults/?p={page}")
            soup = BeautifulSoup(response.text, 'lxml')
        if not course_list:
            # We can't be specific about whether its name or code not found here since we use the same function for both
            raise CourseNotFoundError(f"No course found for '{keyword}'.")
        return course_list

    def search_by_identifier(self, identifier: str) -> list[CourseList]:
        # There isn't really a specific regex pattern we can use so we use a more general one
        pattern = re.compile(r"^[A-Za-z]{4,7}[0-9]{4}$")
        if not pattern.match(identifier.strip()):
            raise ValidationError(f"The course code '{identifier}' is not valid. Enter a valid Course Code in the format 'CXXXX9999'.")
        # Just reuse the keyword search as the search function works for both name and code
        course_list = self.search_by_keyword(identifier)
        return course_list

    def fetch_course_details(self, course_info: CourseList) -> CourseData:
        response = self._get("https://www.gla.ac.uk" + course_info.url)
        parsed_data = self.parse_courses(response.text, course_info)
        return parsed_data
    
    def parse_courses(self, html_content: str, course_info: CourseList) -> CourseData:
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except ParserRejectedMarkup:
            soup = BeautifulSoup(html_content, 'html.parser')

        # There is some corrolation between the course code and the position of these fields but not always reliable enough to use that, sticking to text
        semester_td = soup.select_one("li:-soup-contains('Typically Offered:')")
        semester = semester_td.find(text=True, recursive=False) if semester_td is not None else "N/A"
        semester = str(semester).strip()

        aims_div = soup.select_one('h3:-soup-contains("Course Aims") + div')
        aims = aims_div.get_text(strip=True) if aims_div else "N/A"

        ilos = soup.select_one("h3:-soup-contains('Intended Learning Outcomes of Course') + div")
        ilo_text = ilos.get_text(strip=True) if ilos else "N/A"
        # This is good enough of an output and general enough of parsing for now
        return CourseData(
            name=course_info.name,
            course_code=course_info.course_code,
            semester=semester,
            aims=aims,
            ilos=ilo_text
        )