from scraper.providers.base_provider import BaseProvider
from scraper.models import CourseList, CourseData
import orjson
# * This is imported in this provider only as other provides might not need it (as they return JSON or some other format)
from bs4 import BeautifulSoup

class KeioProvider(BaseProvider):
    university_name = "keio_university"

    def __init__(self, language: str = "2"):
        """
        Initializes the KeioProvider, this does not setup any networking stuff because sometimes (mainly testing) it is not needed.

        Args:
            language (str): The language to search for courses in. 
                            "1" for Japanese, "2" for English and "9" for Others. Defaults to "2".
                            User will have control over language when user interface is implemented
        """
        super().__init__()
        self.language = language
        self.base_url = "https://gslbs.keio.jp/pub-syllabus/"

    def setup_provider(self):
        """
        Sets up the session by getting initial cookies and setting the language to English.
        This is a separate method to make initialization lightweight and testing easier, this is provider specific.
        """
        # This is just to get our 'auth' cookies
        self.session.get(self.base_url + "search", allow_redirects=True)

        # We need to set the UI language to English to get cleaner 'subtitle data'
        lang_payload = {
        	"URL_TYPE_PNM_nZ9CpQJc": "general",
        	"ACTION_ID": "GMENU_LANG",
        	"SUB_ACTION_ID": "SYLLABUS_SEARCH_INIT",
        	"LANG_SEARCH_ACTION_TYPE": "",
        	"CURRENT_LANG": "true"
        }
        # Set the language to English
        self.session.post(self.base_url + "search", data=lang_payload)

    def get_course_list(self) -> list[CourseList]:
        course_list : list[CourseList]= []
        # TODO: For now we are just grabbing the entire course list, later when UI is implemented we change this to be a keyword search
        # We use the Knumber search instead of keyword for more concide payload, we should never need the keyword search as we are getting the whole course list
        course_list_payload = {
            "URL_TYPE_PNM_nZ9CpQJc": "general",
            "ACTION_ID": "SYLLABUS_SEARCH_RESULT",
            "SUB_ACTION_ID": "SYLLABUS_SEARCH_KNUMBER_EXECUTE",
            "KNUMBER_TTBLYR": "2025",
            "KNUMBER_KNFNM": "",
            "KNUMBER_KNLESSONLANGCD": self.language,
            "NARABIJUN": "1",
            "SELECTED_TT_DWCD": "1" # The day selected, 1-6 Mon-Sat, 9 for Others
        }
        # Set it to only accept json data
        headers = {"Accept": "application/json, text/javascript, */*; q=0.01",}

        for i in range(1,7):
            course_list_payload["SELECTED_TT_DWCD"] = str(i)
            response = self.session.post("https://gslbs.keio.jp/pub-syllabus/result", data=course_list_payload, headers=headers)
            dictionary_repsonse = orjson.loads(response.text)
            for course_data_entry in dictionary_repsonse['searchResultDs']:
                for course_entry in course_data_entry['sbjtDs']:
                    course_list.append(CourseList(
                        # This is a better alterantive than 'SUBTITLE' as 'SUBTITLE' sometimes doesn't exist and most of the time contains Japanese
                        name=str(course_entry['SBJTNM']),
                        course_code=str(course_entry['KNUMBER']),
                        url=str(course_entry['SYLLABUS_DETAIL_URL'])
                    ))

        # We should now be returning all the courses from the course list in a specific language.
        return course_list
    
    def fetch_course_details(self, course_info: CourseList) -> CourseData:
        """
        Fetches the specific course webpage and download its html, calls the 'parse_courses' method and
        returns a CourseData object given by the parse_courses funciton
        """
        response = self.session.get(self.base_url + course_info['url'])
        # TODO: Error handling
        parsed_data = self.parse_courses(response.text, course_info)
        return parsed_data
    
    def parse_courses(self, html_content: str, course_info: CourseList) -> CourseData:
        """
        Parses the html content of a course page and returns a CourseData object.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        semester_td = soup.select_one("th:-soup-contains('Academic Year/Semester') + td")
        semester = semester_td.get_text(strip=True) if semester_td else "N/A"

        aims_div = soup.select_one("div.syllabus-section div.contents")
        aims = aims_div.get_text(strip=True) if aims_div else ""
        
        # ! For this university the aims are also the ilos, just input the same data into both
        return CourseData(
            name=course_info['name'],
            course_code=course_info['course_code'],
            semester=semester,
            aims=aims,
            ilos=aims
        )