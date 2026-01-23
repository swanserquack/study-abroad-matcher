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
import orjson
import re

# ! Limit of 200 courses per request applies, you can seemingly bypass by using the 'Look Up All English Course'
class YonseiProvider(BaseProvider):
    university_name = "yonsei_university"
    korean_course_names : dict[str, str] = {}

    def __init__(self):
        super().__init__()
        self.base_url = "https://underwood1.yonsei.ac.kr/"

    def setup_provider(self) -> None:
        # Setup the initial cookies 
        self._get(self.base_url + "com/lgin/SsoCtr/initExtPageWork.do?link=handbList&locale=en")

    
    def search_by_keyword(self, keyword: str) -> list[CourseList]:
        course_list: list[CourseList] = []

        # ! Keyword search does send this data, but it does not seem to effect the results, so we will use as broad of a search as possible but it shouldn't matter
        keyword_search_payload = {
            "_menuId": "MTA5MzM2MTI3MjkzMTI2NzYwMDA=", # Currently unknown, Constant? Doesn't seem to have any relation to cookies/session. Base64 decode just gives numbers.
            "_menuNm": "", # Currently unknown 
            "_pgmId": "NDE0MDA4NTU1NjY=", # Currently unknown, Constant? Doesn't seem to have any relation to cookies/session. Base64 decode just gives numbers.
            "@d1#syy": "2026", # The year selected for search
            "@d1#smtDivCd": "10", # The semester selected for search (10: 1st sem, 11: Summer, 20: 2nd sem, 21: Winter)
            "@d1#campsBusnsCd": "s1", # Categories (s1: Undergraduate Programs, s3: Graduate Programs, s7: Medical Center (Sinchon), s2: Undergraduate Programs (Mirae), s4: Graduate Programs (Mirae), s8: 의료원(미래) (Medical Center (?)))
            "@d1#univCd": "", # * College/Classification: This is dynamic based on previous selections so I can't really create a map for it, will need to be dynamically fetched like keio university if needed
            "@d1#faclyCd": "", # Department (Blank for all, General Education Basic: 1825)
            "@d1#hy": "", # Grade (Blank for not specified/all, 0-9?)
            "@d1#cdt": "%", # Credit (% for full credit, 1 for 1 credit, 2 for 2 credits, 3 for 3 credits, * for other credits)
            "@d1#kwdDivCd": "1", # Keyword type (1: Course Code, 2: Course Title, 3: Professor, 4: Time, 5: English Course, 6: Course outline)
            "@d1#searchGbn": "1", # Search button/type pressed (1: Dropdown filtering search (The button within the section with the dropdown filters), 2: Keyword search, 3: Look Up All English Course, 4: Look Up All Online Lecture), every button apart form the dropdown filtering search ignores current dropdown selections
            "@d1#kwd": "", # The actual keyword input
            "@d1#allKwd": keyword, # Keyword within the dropdown filtering
            "@d1#engChg": "", # View Course Title English? (Blank for no, 0 for yes)
            "@d1#prnGbn": "false", # Currently unknown
            "@d1#lang": "", # Currently unknown,set language for students if logged in?
            "@d1#campsDivCd": "", # Campus (Blank for all, S: Sinchon Campus, G: International Campus, F: Mirae Campus, I: Ilsan Campus)
            "@d1#stuno": "", # Currently unknown, student number for logged in students?
            "@d#": "@d1#", # Currently unknown
            "@d1#": "dmCond", # Currently unknown
            "@d1#tp": "dm", # Currently unknown
            "": ""
        }

        response = self._post(self.base_url + "sch/sles/SlessyCtr/findAtnlcHandbList.do", data=keyword_search_payload)
        try:
            dictionary_response = orjson.loads(response.text)
        except orjson.JSONDecodeError as error:
            raise ParseError(f"Failed to parse JSON response when searching for keyword '{keyword}'.") from error
    
        # Won't loop if it cant be found, thus triggering the CourseNotFoundError later
        for course_entry in dictionary_response.get("dsSles251", []):
            course_list.append(CourseList(
                name=str(course_entry.get("subjtEngNm", "")).strip(),
                course_code=str(course_entry.get("subjtnb", "")).strip(),
                url=str(course_entry.get("syySmtDivNm", "")).strip(), # ? We don't have a seperate page for each course, so to save refetching the course list when getting each courses details, we store the semester here, love storing things in things that arn't meant for it
            ))
            # Save the korean course name for use later when getting course details
            self.korean_course_names[str(course_entry.get("subjtnb", "")).strip()] = str(course_entry.get("subjtNm2", "")).strip()

        if not course_list:
            raise CourseNotFoundError(f"No courses found for the keyword '{keyword}'.")
        return course_list
    
    def search_by_identifier(self, identifier: str) -> list[CourseList]:
        pattern = re.compile(r"^[A-Za-z]{3}[0-9]{4}$")
        if not pattern.match(identifier.strip()):
            raise ValidationError(f"The course code '{identifier}' is not valid. Enter a valid Course Code in the format 'XXX-XXXXXXXX'.")
        course_list = self.search_by_keyword(identifier)
        return course_list
    
    # TODO: Revisit this to properly extract aims and ilos
    # ! Yonsei university does have aims in a pop-out window which displays it in a page format (not really pdf or png), not to overreact but this is complex, they do a bunch of checks like system time and ip before even opening the window, they then send url encode -> base64 encoded data to you (in cyber chef do from base64 THEN URL decode) which then gets you some text but the rest is just a bunch of numbers in a JSONish format, my best guess is that this is fed into SignaturePad (github.com/szimek/signature_pad) as an array of point groups??? Once I'm in a place that I'm happy with this project, I will probably revisit this since it seems fun to reverse engineer this but for now we are just using the course overview for the aims and ilos.
    def fetch_course_details(self, course_info: CourseList) -> CourseData:
        course_details_header = {
            "_menuId": "MTA5MzM2MTI3MjkzMTI2NzYwMDA=", # Currently unknown, Constant? Doesn't seem to have any relation to cookies/session. Base64 decode just gives numbers.
            "_menuNm": "", # Currently unknown
            "_pgmId": "NDE0MDA4NTU1NjY=", # Currently unknown, Constant? Doesn't seem to have any relation to cookies/session. Base64 decode just gives numbers.
            "@d1#syy": "2026", # The year selected for search
            "@d1#smtDivCd": "10", # The semester selected for search (10: 1st sem, 11: Summer, 20: 2nd sem, 21: Winter)
            "@d1#sysinstDivCd": "H1", # Currently unknown
            "@d1#subjtnb": course_info.course_code, # The course code we are searching the details for
            "@d1#subjtNm": self.korean_course_names.get(course_info.course_code, ""), # The korean course name, we get and save this in the previous search function so we don't need to re fetch it
            "@d#": "@d1#", # Currently unknown
            "@d1#": "dmCond", # Currently unknown
            "@d1#tp": "dm", # Currently unknown
            "": ""
        }
        response = self._post(self.base_url + "sch/sles/SlessyCtr/findSubjtDescList.do", data=course_details_header)
        parsed_data = self.parse_courses(response.text, course_info)
        return parsed_data
    
    def parse_courses(self, raw_content: str, course_info: CourseList) -> CourseData:
        try:
            dictionary_response = orjson.loads(raw_content)
        except orjson.JSONDecodeError as error:
            raise ParseError(f"Failed to parse JSON content for course '{course_info.course_code}'.") from error
        
        # Sometimes this aims will be in Korean, not much I can do about this
        aims = dictionary_response.get("_METADATA_", {}).get("result", [])

        if not aims:
            raise ScraperError(f"Could not find aims for course '{course_info.course_code}'.")

        return CourseData(
            name=course_info.name,
            course_code=course_info.course_code,
            semester=course_info.url, # Stored semester in url field earlier to minimize refetching
            description=aims, # TODO: Figure out yonsei's course description system to fix this
            aims=aims
        )