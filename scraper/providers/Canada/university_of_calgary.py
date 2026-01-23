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
from rich import print
from rich.panel import Panel
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
        print(Panel("[yellow] Note: University of Calgary does not provide semester information through their public API. Semester is marked as 'N/A' in the results.[/yellow]", title="Info"))
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
        # Their semester information is not available through their coursedog data, there is a 'semester' in their startTerm data but this just seems to relate to the semester when the course started. There is a semster search available through their public facing peoplesoft class search but I have yet to find a way to get data from this just via requests. It would require either a full browser or finding out how the specific fields are sent to the service. Hits azure???
        return CourseData(
            name=course_info.name,
            course_code=course_info.course_code,
            semester="N/A",
            description=self.description_dict.get(course_info.url, "N/A"),
            aims=self.description_dict.get(course_info.url, "N/A"),
        )