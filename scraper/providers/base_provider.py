from scraper.models import CourseData, CourseList
from abc import ABC, abstractmethod
import requests
from requests.adapters import HTTPAdapter, Retry

class BaseProvider(ABC):
    """
        All university's !! MUST !! follow this 'standard'
        this allows us to easily implement new universities as we have a standard
        format and it also makes it easier to add new methods as
        needed
    """

    """
        This is a name that is specific to this university, allows for easy identification of 
        data belonging to this university
        Ref: https://academia.stackexchange.com/questions/30636/how-to-abbreviate-the-name-of-a-university-when-there-is-no-official-abbreviatio 
        Current standard will be to use full name.with underscores in place of spaces and fully lowercase
    """
    # TODO: Make this compatible with type annotation
    university_name: str = None

    def __init__(self):
        # Make sure to set up exponential backoff to prevent banging services, requests_cache does not work for some reason 
        # So we would need to do it ourselves
        # Stolen from https://substack.thewebscraping.club/p/rate-limit-scraping-exponential-backoff
        retry_strategy = Retry(
            total=5,                        # Total number of retries
            backoff_factor=2,               # Base delay factor (seconds)
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
            backoff_jitter=0.5 # Add a random jitter of no more than 500ms
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        # A session is very helpful for any universities that use cookies, and is a good thing to have even if they don't
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    
    def __init_subclass__(cls, **kwargs) -> None:
        """
        This is called whenever a child class is defined and checks weither we have 
        a university_name defined for identification or not
        """
        super().__init_subclass__(**kwargs)

        if cls.__name__ == "BaseProvider":
            return
        
        if not cls.university_name:
            raise TypeError(
                f"Class '{cls.__name__}' cannot be defined without a 'university_name'. "
                f"Please set a unique string name for use within the program (e.g., university_name = 'keio_university')."
            )

    @abstractmethod
    def get_course_list(self) -> list[CourseList]:
        """
            This is a method that should return a CourseList object,
            which contains the name, course code and url of the course
            for use in the parsing and getting of data for each course
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_course_details(self, course: CourseList) -> CourseData:
        """
            This is a method that returns the data to be written out
            to the file, which is a CourseData object. This method should
            handle fetching the raw HTML and then parsing it internally by
            calling the 'parse_courses' method.

            Args:
                course: A CourseList object - a list of the basics of a course
        """
        raise NotImplementedError
    
    @abstractmethod
    def parse_courses(self, html_content: str, course_info: CourseList) -> CourseData:
        """
            This is a method that takes in the text response from fetch_course_details
            and parses it into a CourseData object, this exists to enforce a common format
            and for testing the parsing.
        """
        raise NotImplementedError