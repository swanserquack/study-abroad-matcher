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
from bs4 import BeautifulSoup
from bs4.builder import ParserRejectedMarkup
import orjson
import re

# ! In the HTML for the search page, the academic year selection menu has all the years it supports, this could be used for checking to make sure when a new year gets supported
# * Test code is FST-ST-13501-211-43
# * We can add language selection later for keyword search, need to figure out how to figure out if a provider supports multiple languages first

class KeioProvider(BaseProvider):
    university_name = "keio_university"

    def __init__(self) -> None:
        """
        Initializes the KeioProvider, this does not setup any networking stuff because sometimes (mainly testing) it is not needed.
        """
        super().__init__()
        self.base_url = "https://gslbs.keio.jp/pub-syllabus/"
        # Set it to only accept json data for certain requests
        self.headers = {"Accept": "application/json, text/javascript, */*; q=0.01",}


    def setup_provider(self) -> None:
        """
        Sets up the session by getting initial cookies and setting the language to English.
        This is a separate method to make initialization lightweight and testing easier, this is provider specific.
        """
        # This is just to get our 'auth' cookies
        self._get(self.base_url + "search")

        # We need to set the UI language to English to get cleaner 'subtitle' data
        lang_payload = {
        	"URL_TYPE_PNM_nZ9CpQJc": "general",
        	"ACTION_ID": "GMENU_LANG",
        	"SUB_ACTION_ID": "SYLLABUS_SEARCH_INIT",
        	"LANG_SEARCH_ACTION_TYPE": "",
        	"CURRENT_LANG": "true"
        }
        # Set the language to English
        self._post(self.base_url + "search", data=lang_payload)

    def search_by_keyword(self, keyword: str) -> list[CourseList]:
        course_list : list[CourseList]= []
        keyword_search_payload = {
        "URL_TYPE_PNM_nZ9CpQJc": "general",
        "ACTION_ID": "SYLLABUS_SEARCH_RESULT",
        "SUB_ACTION_ID": "SYLLABUS_SEARCH_KEYWORD_EXECUTE",
        "KEYWORD_TTBLYR": self._get_current_year(),
        "KEYWORD_SMSCD": "ALL", # Semester number, 5 for Fall and 3 for Spring, ALL for both
        "KEYWORD_HALFSEMESTER": "ALL", # Whether it's the first half or second half of the semester, ALL for both
        "KEYWORD_KBS_SMSCD": "ALL",
        "KEYWORD_CAMPUS": "ALL", # Campus code, ALL for all campuses, 01 for Mita, 02 for Hiyoshi, 04 for SFC, 05 for Yagami, 06 for Shinano, 09 for Shiba
        "KEYWORD_PRGANDFCD": "", # Faculty/Graduate School code, yet another propriatary code not the same as search by identifier codes :(, if I ever want to use this I will need to get the code from the options in the search page
        # Hidden field: KEYWORD_DEPCD, it maps to the Department/Major code but if we are not using it then it is not sent, also same issues as above
        # Hidden field: KEYWORD_LVL, it maps to the Year Level but if we are not using it then it is not sent
        "KEYWORD_KAMOKUNM": "",  # Course name input by the user, spaces joined by +
        "KEYWORD_TANTONM": "", # Lecturer name input by the user, spaces joined by +
        "KEYWORD_KEYWORD": keyword, # Pretty obvious, its the keyword input by the user, DO NOT TO ANY PREPROCESSING SUCH AS STRIPPING OR REPLACING SPACES WITH PLUSES, for some reason the server crashes out at this so DO NOT DO THIS
        # Hidden field: KEYWORD_DOWCD, Day of the week code, if not used then not sent, same format as SELECTED_TT_DWCD
        # Hidden field: KEYWORD_PDCD, Period code, if not used then not sent, 1-7 for periods 1-7, 9 for Others
        # Hidden field: KEYWORD_LESSONTYPE, Class format code, if not used then not sent, 1 face-to-face, 2 online (mainly real-time), 3 online (mainly on-demand), 4 online (completely on-demand)
        "KEYWORD_LESSONLANG": "ALL", # Language of instruction, ALL for all languages, 1 for Japanese, 2 for English, 9 for Others
        "KEYWORD_SCRGUTP": "ALL", # Applicable Rules and Regulation???? Only options I've seen so far are ALL and 17
        "KEYWORD_FLD1CD": "ALL", # Field Name 1, bunch of preset options but ALL for all fields, sent as string of option with spaces as +
        "KEYWORD_FLD2CD": "ALL", # Field Name 2, bunch of preset options but ALL for all fields, sent as string of option with spaces as +
        # Hidden field: KEYWORD_ACTIVELEARNING, Active Learning Method, if not used then not sent
        # Hidden field: KEYWORD_OTHER_COND, other misc conditions
        "KEYWORD_ENGSUPPORT": "ALL", # Seemingly not used for keyword search
        "KEYWORD_LECTURELOCATION": "ALL", # Seemingly not used for keyword search
        "KEYWORD_FLD1NM": "All", # Copy of KEYWORD_FLD1CD but with lowercase All???
        "KEYWORD_FLD2NM": "All", # Copy of KEYWORD_FLD2CD but with lowercase All???
        "NARABIJUN": "1", # Display order, not really relevant here
        "SELECTED_TT_DWCD": "1" # The day selected, 1-6 Mon-Sat, 9 for Others
        }
        
        for i in range(1,7):
            keyword_search_payload["SELECTED_TT_DWCD"] = str(i)
            # We want to also search the 'Others' category
            if i == 7:
                keyword_search_payload["SELECTED_TT_DWCD"] = str(9)
            _response = self._post(self.base_url + "result", data=keyword_search_payload, headers=self.headers)

            try:
                dictionary_response = orjson.loads(_response.text)
            except orjson.JSONDecodeError as error:
                raise ParseError(f"Failed to parse JSON response when searching for keyword '{keyword}'.") from error

            for course_data_entry in dictionary_response.get('searchResultDs', []):
                for course_entry in course_data_entry.get('sbjtDs', []):
                    course_list.append(CourseList(
                        # This is a better alterantive than 'SUBTITLE' as 'SUBTITLE' sometimes doesn't exist and most of the time contains Japanese
                        name=str(course_entry['SBJTNM']).strip(),
                        course_code=str(course_entry['KNUMBER']).strip(),
                        url=str(course_entry['SYLLABUS_DETAIL_URL']).strip()
                    ))

        if not course_list:
            raise CourseNotFoundError(f"No courses found for the keyword '{keyword}'.")
        return course_list

    def search_by_identifier(self, identifier: str) -> list[CourseList]:
        course_list : list[CourseList]= []
        
        # Format for the K-number (https://www.students.keio.ac.jp/en/com/class/registration/k-number.html), note that the subject type can include A-F letters, not in their official spec (example: https://gslbs.keio.jp/pub-syllabus/detail?ttblyr=2025&entno=18850&lang=en)
        pattern = re.compile(r"^[A-Z]{3}-[A-Z]{2}-[0-9]{4}[1-4A-F9]-[1-79][1-4][1-29]-[0-9]{2}$")
        if not pattern.match(identifier.strip()):
            raise ValidationError(f"The K-Number '{identifier}' is not valid. Enter a valid K-Number in the format 'XXX-XX-XXXXX-XXX-XX'.")

        parsed_knumber = self._parse_knumber(identifier)

        identifier_search_payload = {
            "URL_TYPE_PNM_nZ9CpQJc": "general",
            "ACTION_ID": "SYLLABUS_SEARCH_RESULT",
            "SUB_ACTION_ID": "SYLLABUS_SEARCH_KNUMBER_EXECUTE",
            "KNUMBER_TTBLYR": self._get_current_year(),
            "KNUMBER_KNFNM": parsed_knumber["course_admin_code"],
            "KNUMBER_KNDEPNM": parsed_knumber["department"],
            "KNUMBER_KNLVLCD": parsed_knumber["course_level"],
            "KNUMBER_KNMJRCLSCD": parsed_knumber["major_classification"],
            "KNUMBER_KNMNRCLSCD": parsed_knumber["minor_classification"],
            "KNUMBER_KNSBJTTPCD": parsed_knumber["subject_type"],
            "KNUMBER_KNLESSONCATCD": parsed_knumber["class_classification"],
            "KNUMBER_KNLESSONMODECD": parsed_knumber["class_format"],
            "KNUMBER_KNLESSONLANGCD": parsed_knumber["language_of_instruction"],
            "KNUMBER_KNSDYAREACD": parsed_knumber["academic_fields"],
            "NARABIJUN": "1", # Display order, not really relevant here
            "SELECTED_TT_DWCD": "1" # The day selected, 1-6 Mon-Sat, 9 for Others
        }

        for i in range(1,7):
            identifier_search_payload["SELECTED_TT_DWCD"] = str(i)
            # We want to also search the 'Others' category which is the 9 code
            if i == 7:
                identifier_search_payload["SELECTED_TT_DWCD"] = str(9)
            _response = self._post(self.base_url + "result", data=identifier_search_payload, headers=self.headers)
            try:
                dictionary_response = orjson.loads(_response.text)
            except orjson.JSONDecodeError as error:
                raise ParseError(f"Failed to parse JSON response when searching for K-Number '{identifier}'.") from error
            
            for course_data_entry in dictionary_response.get('searchResultDs', []):
                # * The API returns an empty list for sbjtDs when no results are found, but its still better to be safe
                for course_entry in course_data_entry.get('sbjtDs', []):
                    course_list.append(CourseList(
                        # This is a better alterantive than 'SUBTITLE' as 'SUBTITLE' sometimes doesn't exist and most of the time contains Japanese
                        name=str(course_entry['SBJTNM']),
                        course_code=str(course_entry['KNUMBER']),
                        url=str(course_entry['SYLLABUS_DETAIL_URL'])
                    ))

        if not course_list:
            raise CourseNotFoundError(f"No courses found for the K-Number '{identifier}'.")
        
        return course_list

    def fetch_course_details(self, course_info: CourseList) -> CourseData:
        """
        Fetches the specific course webpage and download its html, calls the 'parse_courses' method and
        returns a CourseData object given by the parse_courses funciton
        """
        response = self._get(self.base_url + course_info.url)
        parsed_data = self.parse_courses(response.text, course_info)
        return parsed_data
    
    def parse_courses(self, raw_content: str, course_info: CourseList) -> CourseData:
        """
        Parses the html content of a course page and returns a CourseData object.
        """
        try:
            soup = BeautifulSoup(raw_content, 'lxml')
        # This should never happen, but just in case lxml fails for some reason
        except ParserRejectedMarkup:
            soup = BeautifulSoup(raw_content, 'html.parser')
        
        semester_td = soup.select_one("th:-soup-contains('Academic Year/Semester') + td")
        semester = semester_td.get_text(strip=True) if semester_td else "N/A"

        # * For some courses (FPE-CO-03102-212-60), there are two of these, a 'Course Summary' and a 'Course Description/Objectives/Teaching Method/Intended Learning Outcome', the old code grabbed the wrong one. Additionally this code and the code at the top of the file both have different variations of the heading, so we need to check for both
        aims_div = soup.select_one("h3:-soup-contains('Course Contents/Objectives/Teaching Method/Intended Learning Outcome') + div.contents")
        if not aims_div:
            aims_div = soup.select_one("h3:-soup-contains('Course Description/Objectives/Teaching Method/Intended Learning Outcome') + div.contents")
        aims = aims_div.get_text(strip=True) if aims_div else ""
        
        description_td = soup.select_one("th:-soup-contains('Course Description') + td")
        description = description_td.get_text(strip=True) if description_td else ""

        return CourseData(
            name=course_info.name,
            course_code=course_info.course_code,
            semester=semester,
            description=description,
            aims=aims,
        )
    
    # * This is imperfect, all we do is pull apart the knumber, we don't validate a course is actually associated with it, so we use error handling when requesting the course data later on
    def _parse_knumber(self, knumber: str) -> dict[str, str]:
        # Get the course administrator codes for the faculty/graduate school 
        response = self._get(self.base_url + "search")

        soup = BeautifulSoup(response.text, 'lxml')
        select_tag = soup.find('select', {"name": "KNUMBER_KNFNM"})
        if select_tag is None:
            # If the select element isn't present, raise an error
            raise ScraperError("Failed to find course administrator on the search page")
        options = select_tag.find_all("option")

        # 'Premature optimisation is the root of all evil' - johnhw, me turning a loop into a generator expression
        course_admin_code = next((opt.get('value') for opt in options if opt.get('data-knfnm') == knumber[:3]), None)

        # Department/Major List to cross reference their number for the actual query
        major_list_payload = {
            "URL_TYPE_PNM_nZ9CpQJc": "general",
            "ACTION_ID": "SYLLABUS_SEARCH_KNUMBER_CHANGE_ITEM",
            "CHANGE_TARGET_SRC": "KNUMBER_KNFNM",
            "KNUMBER_TTBLYR": "2025",
            "KNUMBER_KNFNM": course_admin_code,
            "KNUMBER_KNDEPNM": "",
            "KNUMBER_KNMJRCLSCD": ""
        }

        # For some reason this request has a msgType of 'error'?? Don't worry if this is present, for some reason it is set to this quite consistently throughout various requests, it'd be more worrying for it to be success at this point.
        _response = self._post(self.base_url + "search", data=major_list_payload, headers=self.headers)
        dictionary_repsonse = orjson.loads(_response.text)
        major_list = dictionary_repsonse.get('changeTargetRs', {}).get('KNUMBER_KNDEPNM_ITEM', [])
        
        if not major_list:
            raise ScraperError("Failed to retrieve major/department list for parsing K-Number.")

        for i in range(len(major_list)):
            if major_list[i]['name'][0:2] == knumber[4:6]:
                department = major_list[i]['value']

        # Slice out the relevant parts of the knumber, already verified against the regex
        course_level = knumber[7]
        major_classification = knumber[8]
        minor_classification = knumber[9:11]
        subject_type = knumber[11]
        class_classification = knumber[13]
        class_format = knumber[14]
        language_of_instruction = knumber[15]
        academic_fields = knumber[17:19]

        parsed_knumber = {
            "course_admin_code": course_admin_code,
            "department": department,
            "course_level": course_level,
            "major_classification": major_classification,
            "minor_classification": minor_classification,
            "subject_type": subject_type,
            "class_classification": class_classification,
            "class_format": class_format,
            "language_of_instruction": language_of_instruction,
            "academic_fields": academic_fields
        }

        return parsed_knumber

    def _get_current_year(self) -> str:
        # Grab the main page
        response = self._get(self.base_url + "search")
        soup = BeautifulSoup(response.text, 'lxml')

        # Find the select element for academic year
        select_tag = soup.find('select', {"name": "KEYWORD_TTBLYR"})
        # If by some miracle it doesn't exist, just return 2025 (Pretty safe fallback as they have an option for 2010)
        if select_tag is None:
            return "2025"
        
        # Grab the selected option, this is by default the current year
        current_year_option = select_tag.find('option', selected=True)
        # Same as above
        if current_year_option is None:
            return "2025"
        # Getting the value is better I think, we could also get the text but I just like this more
        return str(current_year_option['value'])