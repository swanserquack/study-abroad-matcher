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
from pathlib import Path
from bs4 import BeautifulSoup
import datetime
import orjson
import re

# * The API for Calgary (coursedog) has a ton of useful information on tap - such as dependencies, if its got a final exam etc - when I build up a proper UI later I will need to extend out a specific CourseData for Calgary to take advantage of all this extra data
# * GET request to https://app.coursedog.com/api/v1/ucalgary_peoplesoft/general/courseTemplate/questions provides a ton of information about each field, such as a description and a ton of details about it
# * GET request to https://app.coursedog.com/api/v1/ca/ucalgary_peoplesoft/search-configurations/3HheDcKChSNwS1Wr1Khr provides information about what filters are available and kind of what fields to use in request for filters
class UCalgaryProvider(BaseProvider):
    university_name = "university_of_calgary"

    def __init__(self) -> None:
        super().__init__()
        self.base_url = "https://app.coursedog.com/api/v1/cm/ucalgary_peoplesoft/courses/"
        self.description_dict : dict[str, str] = {}
        # Assume the cache to be invalid initially
        self.cache_invalid = True
        self.newly_cached_prefixes : list[tuple[str, str]] = []
        self.cache_path = "data/cache/ucalgary_peoplesoft_index_cache.json"

    def search_by_keyword(self, keyword: str) -> list[CourseList]:
        print(Panel("[yellow] Note: University of Calgary provides semester information through an alternate API. Building a course index with semester information may take a while.[/yellow]", title="Info"))
        course_list: list[CourseList] = []
        # ! There is a static payload which is sent with the request, however it like 200 lines of just sending a filter, I'd prefer not to send it (seems to work fine without it) and just do filtering on device
        # * The overall coursedog api is kind of documented here: https://coursedogcurriculum.docs.apiary.io/#reference/courses/search-courses
        
        # * The formatDependents determines if the response should include what pre-requisites are associated with that course, I think orderBy can take any field that is available through the API, the effectiveDatesRange is just basically a semester filter I think, I set the limit to more than the total available courses to not have to deal with pagination. We are using effectiveDates range to only get courses that are for the current semster. The other fields we just need for filtering on device. Columns is just the data we want returned back, if nothing is specified it returns everything it has.
        # ! You need to include the origin header or it will 401
        # ? Why is the effective dates set to such a weird range? They dont match up at all with the academic calendar, for now until I figure this out I'm just going to roll with it.
        current_effective_dates = self._get_current_effective_dates()
        response = self._post(self.base_url + f"search/{keyword}?catalogId=R7TegZ8xGZCLE3avlAjI&skip=0&limit=6000&orderBy=code&formatDependents=false&effectiveDatesRange={current_effective_dates}&ignoreEffectiveDating=false&columns=code,longName,customFields.rawCourseId,courseNumber,status,career,description", headers={"origin": "https://calendar.ucalgary.ca"})
        try:
            dictionary_response = orjson.loads(response.text)
        except orjson.JSONDecodeError as error:
            raise ParseError(f"Failed to parse JSON response when searching for keyword '{keyword}'.") from error
        
        # Dont really need .get here as even if there are no results, it returns an empty list
        # ? Even if we used the filtering provided by the provider by sending that large header, it would still need to be manually updated since the format in the script tags on the webpage is unhelpful - it gives the values of what to filter but not what conditions (i.e just gives career but not that it should be empty). so we just say f it we ball and do it on device
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

        # Cache the index we built
        self._cache_layer()

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
        """
        ! Warning this is a hefty function.

        This function gets the course list for each course prefix we have for both semester's from peoplesoft.
        """
        
        # Create the parser for peoplesoft
        peoplesoft_parser = PeopleSoftCourseSearch("https://csprd.my.ucalgary.ca/psc/csprd/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL", "https://csprd.my.ucalgary.ca/psc/csprd/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?public=yes/&languageCd=ENG")
        course_prefixes_level : list[tuple[str, str]] = []
        all_courses = []

        # Figure out what search queries to run/course prefixes + levels
        for course in course_info:
            # Seperate the course code into its prefix and number components.
            course_code_splitter = re.search(r"([A-Z]{3,4})([1-7][0-9]{2})$", course.course_code)
            if course_code_splitter is None:
                raise ScraperError(f"Failed to parse course code '{course.course_code}' for course '{course.name}'.")
            # Dawg this if statement is my masterpiece, I think I should get an honorary degree just for this if statement...kidding. If the prefix is NOT already in the list and the first digit of the course number is NOT already in the list for THAT prefix, add it
            if course_code_splitter.group(1) not in course_prefixes_level and course_code_splitter.group(2)[0] not in [level[1] for level in course_prefixes_level if level[0] == course_code_splitter.group(1)]:
                course_prefixes_level.append((course_code_splitter.group(1), course_code_splitter.group(2)[0]))

        # Check if the cache file exists
        my_file = Path(self.cache_path)
        file_exists = False
        if my_file.is_file():
            file_exists = True
            # Read in the cache
            with open(self.cache_path, "r") as f:
                content = f.read()
                if content:
                    cache = orjson.loads(content)
                else:
                    cache:  dict = {'course_prefixes_level': []}
        else:
            cache = {}

        # If there is a cache expiration date, we default to assuming that the cache is invalid
        if 'cache_expiration' in cache:
            expiration_date = datetime.datetime.fromisoformat(cache['cache_expiration'])
            # If the current date is before the expiration date, consider the cache valid
            if datetime.datetime.today() < expiration_date:
                self.cache_invalid = False
            else:
                # If the cache is expired, we want to wipe it and build a new one
                cache = {}
        
        # How many prefixes do we actually need to fetch from the server?
        prefixes_to_fetch = []
        for prefix in course_prefixes_level:
            # If the file exists, the cache is valid and the prefix is already in the cache, we do not need to fetch it again so we just skip it
            if file_exists and not self.cache_invalid and any(prefix[0] == cached_key[0] and prefix[1] == cached_key[1] for cached_key in cache['course_prefixes_level']):
                continue
            else:
                # Need to fetch this prefix from the server
                prefixes_to_fetch.append(prefix)
        
        # Set the prefixes we need to fetch
        course_prefixes_level = prefixes_to_fetch

        # If we have no prefixes to fetch, we can just load everything from the cache
        if not course_prefixes_level:
            # For every item in the cache
            for cached_key, semesters in cache.items():
                # If we get here we already know the cache is valid and it contains everything that we need, we don't need to update the list of cached prefixes at all since we aren't fetching anything new, so we just skip it, also this errors out when removing duplicates as it is a list (??)
                if cached_key in ('course_prefixes_level'):
                    continue
                # We want to cache the full string for cache_expiration or else it will split the date
                if cached_key in ('cache_expiration'):
                    all_courses.append((cached_key, "", semesters))
                    continue
                # For every semester the course runs in, append it
                for semester in semesters:
                    all_courses.append((cached_key, "", semester))
            # We can return here as we dont need to fetch anything from peoplesoft
            return all_courses
        
        # Set up a progress bar for peoplesoft index building
        progress = Progress(
            *Progress.get_default_columns(),
            MofNCompleteColumn()
        )
        progress.start()
        
        # Each prefix needs to be searched for both semesters, we always only look at two semesters (Fall and Winter) for now
        total_operations = len(course_prefixes_level) * 2
        building_index = progress.add_task("[cyan]Building PeopleSoft index...", total=total_operations, start=True)
        
        # Semester mapping for display
        semester_names = self._get_peoplesoft_semester_codes()
        
        for prefix in course_prefixes_level:
            # print("Working through prefix:", prefix)
            for semester in semester_names.keys():
                # print("Working through semester:", semester)
                semester_display = semester_names.get(semester, semester)
                progress.update(building_index, description=f"[cyan]Building PeopleSoft index... ({prefix[0]}{prefix[1]}xx - {semester_display})")

                peoplesoft_results_page = peoplesoft_parser.get_search_results(semester=semester, subject=prefix[0], course_number=int(prefix[1]))
                parsed_courses = peoplesoft_parser.parse_results_page(peoplesoft_results_page)
                peoplesoft_parser.new_search()
                all_courses.extend(parsed_courses)

                progress.update(building_index, advance=1)
        
        progress.stop()
        self.newly_cached_prefixes = course_prefixes_level
        return all_courses

    def _get_current_effective_dates(self) -> str:
        response = self._get("https://calendar.ucalgary.ca/courses")
        soup = BeautifulSoup(response.text, 'lxml')

        # Find the script tag that contains the effectiveDatesRange
        pattern = re.compile(r'effectiveDatesRange')
        script_tag  = soup.find("script", text=pattern)

        # Same as final return
        if script_tag is None:
            return "2026-06-21,2026-06-30"
        
        script_tag_text = script_tag.string or ""

        if script_tag_text:
            # Regex to find this: effectiveDatesRange:{effectiveStartDate: "2026-06-21",effectiveEndDate: "2026-06-30"}
            new_pattern = re.compile(r'effectiveDatesRange:\s{0,100}\{\s{0,100}effectiveStartDate:\s{0,100}"([0-9]{4}-[0-9]{2}-[0-9]{2})",\s{0,100}effectiveEndDate:\s{0,100}"([0-9]{4}-[0-9]{2}-[0-9]{2})"\s{0,100}\}')
            # Search for the pattern in the script tag text
            match = new_pattern.search(script_tag_text)

            if match:
                start_date = match.group(1)
                end_date = match.group(2)
                # Specific format for the url
                url_string = f"{start_date},{end_date}"
                return url_string

        # If it can't be found, return to hardcoded value
        return "2026-06-21,2026-06-30"
    
    def _get_peoplesoft_semester_codes(self) -> dict[str, str]:
        # Get all of our initial cookies and stuff setup
        self._get("https://csprd.my.ucalgary.ca/psp/csprd/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?public=yes/&languageCd=ENG")

        # Now actually get the html for the webpage
        response = self._get("https://csprd.my.ucalgary.ca/psc/csprd/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?public=yes/&languageCd=ENG")
        soup = BeautifulSoup(response.text, 'lxml')

        # Find the select tag which is a drop-down for selecting which semester
        select_tag = soup.find('select', {"id": "CLASS_SRCH_WRK2_STRM$35$"})
        if select_tag is None:
            return {"2257": "Fall 2025", "2261": "Winter 2026"}
        
        # Find all the options within the select tag, this is from the oldest on the top to the newest on the bottom
        options = select_tag.find_all('option')
        if not options:
            return {"2257": "Fall 2025", "2261": "Winter 2026"}
        
        # Reverse it to place the newest on top and the oldest on the bottom
        options.reverse()
        semesters = {}

        fall_flag = False
        winter_flag = False
        for option in options:
            # If its the first Fall semester we see, we add the year to the end of the string "Fall" and put it in the dictionary with the specific ucalgary code as the key
            if "Fall" in option.text and not fall_flag:
                semesters[option['value']] = "Fall " + option.text.strip().split()[-1]
                fall_flag = True
            # Same as above but for Winter
            elif "Winter" in option.text and not winter_flag:
                semesters[option['value']] = "Winter " + option.text.strip().split()[-1]
                winter_flag = True
            # If we have encountered both then break
            if fall_flag and winter_flag:
                break

        # Ensure Fall comes before Winter in the dict, regardles of how they are ordered on the webpage, just makes the output cleaner. We could just sort by digit number but meh, this works.
        semesters = dict(sorted(semesters.items(), key=lambda item: ("Fall" not in item[1], item[0])))
        return semesters
    
    def _cache_layer(self) -> None:
        # If the cache is invalid, we want to rebuild it from scratch, this branch also triggers when the cache header doesn't exist in the file yet
        if self.cache_invalid:
            # Check if the path exists, if not create it
            data_folder = Path("data/cache")
            if not data_folder.exists():
                data_folder.mkdir(parents=True)
            # Open as write to wipe the file
            with open(self.cache_path, "w+", encoding="utf-8") as f:
                # Setup an inital data structure to build upon
                new_cache: dict = {'course_prefixes_level': []}
                # For every prefix that we had to fetch
                for prefix in self.newly_cached_prefixes:
                    # If the prefix isn't already in the newly built cache, add it
                    if prefix not in new_cache['course_prefixes_level']:
                        new_cache['course_prefixes_level'].append(prefix)
                # Add all the courses to the cache
                for course in self.semester_index:
                    # If the course isn't already in the newly built cache, add it
                    if course not in new_cache:
                        new_cache[course] = self.semester_index[course]
                # Add a one day expiration date to the cache
                new_cache['cache_expiration'] = datetime.datetime.today() + datetime.timedelta(days=1)
                # Decode automatically turns datetime into iso format
                f.write(orjson.dumps(new_cache).decode("utf-8"))
        # If the cache is not invalid, we just want to append what wasn't already in there, keep the old cache expiration date though
        elif not self.cache_invalid:
            # If we go down this path there is a file called ucalgary_peoplesoft_index_cache.json so we dont need to worry about the file not existing
            with open(self.cache_path, "r+", encoding="utf-8") as f:
                content = f.read()
                if content:
                    cache = orjson.loads(content)
                else:
                    cache = {'course_prefixes_level': []}
                # Update the cache with any newly cached prefixes
                for prefix in self.newly_cached_prefixes:
                    if prefix not in cache['course_prefixes_level']:
                        cache['course_prefixes_level'].append(prefix)
                # Add any new courses to the cache
                for course in self.semester_index:
                    if course not in cache:
                        cache[course] = self.semester_index[course]
                # Move back to beginning of file and truncate
                f.seek(0)
                f.truncate()
                f.write(orjson.dumps(cache).decode("utf-8"))