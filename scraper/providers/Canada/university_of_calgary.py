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
from scraper.errors import ValidationError, CourseNotFoundError, ParseError, ScraperError
from scraper.helpers.peoplesoft import PeopleSoftCourseSearch
from rich import print
from rich.panel import Panel
from rich.progress import Progress, MofNCompleteColumn
from collections import OrderedDict
import orjson
import re

# * The API for Calgary (coursedog) has a ton of useful information on tap - such as dependencies, if its got a final exam etc - when I build up a proper UI later I will need to extend out a specific CourseData for Calgary to take advantage of all this extra data
# * GOLD MINE: GET request to https://app.coursedog.com/api/v1/ucalgary_peoplesoft/general/courseTemplate/questions provides a ton of information about each field, such as a description and a ton of details about it
# * GET request to https://app.coursedog.com/api/v1/ca/ucalgary_peoplesoft/search-configurations/3HheDcKChSNwS1Wr1Khr provides information about what filters are available and kind of what fields to use in request for filters
class UCalgaryProvider(BaseProvider):
    university_name = "university_of_calgary"

    def __init__(self) -> None:
        super().__init__()
        self.search_base_url = "https://app.coursedog.com/api/v1/cm/ucalgary_peoplesoft/courses/"
        self.description_dict = {}

    def search_by_keyword(self, keyword: str) -> list[CourseList]:
        print(Panel("[yellow] Note: University of Calgary provides semester information through an alternate API. Building a course index with semester information may take a while.[/yellow]", title="Info"))
        course_list: list[CourseList] = []
        # ! There is a static payload which is sent with the request, however it like 200 lines of just sending a filter, I'd prefer not to send it (seems to work fine without it) and just do filtering on device
        # * The api is kind of documented here: https://coursedogcurriculum.docs.apiary.io/#reference/courses/search-courses
        
        # * The formatDependents determines if the response should include what pre-requisites are associated with that course, I think orderBy can take any field that is available through the API, the effectiveDatesRange is just basically a semester filter I think, I set the limit to more than the total available courses to not have to deal with pagination. We are using effectiveDates range to only get courses that are for the current semster, its already on my todo list to figure out some way to make dates dynamically update. The other fields we just need for filtering on device.
        # ! You need to include the origin header or it will 401
        # ? Why is the effective dates set to such a weird range? They dont match up at all with the academic calendar, for now until I figure this out I'm just going to roll with it.
        response = self._post(self.search_base_url + f"search/{keyword}?catalogId=R7TegZ8xGZCLE3avlAjI&skip=0&limit=6000&orderBy=code&formatDependents=false&effectiveDatesRange=2026-06-21,2026-06-30&ignoreEffectiveDating=false&columns=code,longName,customFields.rawCourseId,courseNumber,status,career,description", headers={"origin": "https://calendar.ucalgary.ca"})
        try:
            dictionary_response = orjson.loads(response.text)
        except orjson.JSONDecodeError as error:
            raise ParseError(f"Failed to parse JSON response when searching for keyword '{keyword}'.") from error
        
        # Dont really need .get here as even if there are no results, it returns an empty list
        # ? Even if we used the filtering provided by the provider by sending that large header, it would still need to be manually updated since there is no obvious way to get the current filters from the web page so we just say f it we ball and do it on device
        for course_entry in dictionary_response.get("data", []):
            # Follow filtering rules which are normally sent to the server, if there is no value we should fail
            if course_entry.get("status", "") != "Active":
                continue
            elif not course_entry.get("career", ""):
                continue
            elif "A" in course_entry.get("courseNumber", "A") or "B" in course_entry.get("courseNumber", "B"):
                continue
            elif course_entry.get("customFields", {}).get("rawCourseId", "150073") in ["150073", "160740", "160726", "161071", "103199", "150054", "150087", "150135", "150178", "150211", "150243", "150250", "161388", "150345", "150382", "150390"]:
                continue
            course_list.append(CourseList(
                name=str(course_entry.get("longName", "")).strip(),
                course_code=str(course_entry.get("code", "")).strip(),
                url=str(course_entry.get("customFields", {}).get("rawCourseId", "")).strip()
            ))
            # Save descriptions to prevent further requests
            self.description_dict[str(course_entry.get("customFields", {}).get("rawCourseId", "")).strip()] = str(course_entry.get("description", "N/A")).strip()
            
        if not course_list:
            raise CourseNotFoundError(f"No courses found for the keyword '{keyword}'.")
        
        # Build the peoplesoft index for use in building the semester index below
        self.peoplesoft_course_list = self._get_peoplesoft_courses(course_list)

        # Get rid of duplicates, stolen from: https://stackoverflow.com/questions/32296933/removing-duplicates-of-a-list-of-sets 
        self.peoplesoft_course_list = list(OrderedDict.fromkeys(self.peoplesoft_course_list).keys())

        # Build semester index for later use
        self.semester_index = {}
        for course in self.peoplesoft_course_list:
            course_code = course[0].strip().replace(" ", "")
            base = re.sub(r'[AB]$', '', course_code)
            self.semester_index.setdefault(base, []).append(course[2])
        # print(self.peoplesoft_course_list)
        return course_list
    
    def search_by_identifier(self, identifier: str) -> list[CourseList]:
        # Basically just a slight variation on Yonsei's pattern
        pattern = re.compile(r"^[A-Za-z]{3,4}[1-7][0-9]{2}$")
        if not pattern.match(identifier.strip()):
            raise ValidationError(f"The identifier '{identifier}' is not valid. Enter a valid Course Code in the format 'XXX123'.")
        
        course_list = self.search_by_keyword(identifier)
        return course_list
    
    def fetch_course_details(self, course_info: CourseList) -> CourseData:
        parsed_data = self.parse_courses(self.description_dict.get(course_info.url, "N/A"), course_info)
        return parsed_data
    
    def parse_courses(self, raw_content: str, course_info: CourseList) -> CourseData:
        # Grab the semesters from the peoplesoft index we built earlier
        semesters = self.semester_index.get(course_info.course_code.strip(), [])
        # If they run in multiple semesters
        semester = " + ".join(semesters) if semesters else "Not running or N/A"
        
        return CourseData(
            name=course_info.name,
            course_code=course_info.course_code,
            semester=semester,
            description=self.description_dict.get(course_info.url, "N/A"),
            aims=self.description_dict.get(course_info.url, "N/A"),
        )
    
    def _get_peoplesoft_courses(self, course_info: list[CourseList]) -> list[str]:
        # Get the course list for each course prefix we have for both semester's from peoplesoft
        peoplesoft_parser = PeopleSoftCourseSearch("https://csprd.my.ucalgary.ca/psc/csprd/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL", "https://csprd.my.ucalgary.ca/psc/csprd/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?public=yes/&languageCd=ENG")
        course_prefixes_level = []
        all_courses = []

        # Figure out what search queries to run/course prefixes + levels
        for course in course_info:
            course_code_splitter = re.search(r"([A-Z]{3,4})([1-7][0-9]{2})$", course.course_code)
            if course_code_splitter is None:
                raise ScraperError(f"Failed to parse course code '{course.course_code}' for course '{course.name}'.")
            # Dawg this if statement is my masterpiece, I think I should get an honorary degree just for this if statement...kidding. If the prefix is NOT already in the list and the first digit of the course number is NOT already in the list for THAT prefix, add it
            if course_code_splitter.group(1) not in course_prefixes_level and course_code_splitter.group(2)[0] not in [level[1] for level in course_prefixes_level if level[0] == course_code_splitter.group(1)]:
                course_prefixes_level.append((course_code_splitter.group(1), course_code_splitter.group(2)[0]))
        
        # Set up a progress bar for peoplesoft index building
        progress = Progress(
            *Progress.get_default_columns(),
            MofNCompleteColumn()
        )
        progress.start()
        
        # Each prefix needs to be searched for both semesters
        total_operations = len(course_prefixes_level) * 2
        building_index = progress.add_task("[cyan]Building PeopleSoft index...", total=total_operations, start=True)
        
        # Semester mapping for display
        semester_names = {"2257": "Fall 2025", "2261": "Winter 2026"}
        
        for prefix in course_prefixes_level:
            # print("Working through prefix:", prefix)
            # 2257 = Fall 2025, 2261 = Winter 2026
            # Dynamic semester building next thing on my TODO list work on
            for semester in ["2257", "2261"]:
                # print("Working through semester:", semester)
                semester_display = semester_names.get(semester, semester)
                progress.update(building_index, description=f"[cyan]Building PeopleSoft index... ({prefix[0]}{prefix[1]}xx - {semester_display})")

                peoplesoft_results_page = peoplesoft_parser.get_search_results(semester=semester, subject=prefix[0], course_number=int(prefix[1]))
                parsed_courses = peoplesoft_parser.parse_results_page(peoplesoft_results_page)
                peoplesoft_parser.new_search()
                all_courses.extend(parsed_courses)

                progress.update(building_index, advance=1)
        
        progress.stop()

        return all_courses