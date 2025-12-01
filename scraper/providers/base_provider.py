from scraper.models import CourseData, CourseList
from scraper.errors import NetworkError, HTTPStatusError
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
    university_name: str | None = None

    def __init__(self) -> None:
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

    def _request(self, method: str, url: str, *, timeout: float | tuple[float, float] = 15, allow_redirects: bool = True, **kwargs) -> requests.Response:
        """
        Internal helper to make HTTP requests with consistent error handling.
        Providers should prefer using `_get` / `_post` wrappers due to their consistent error handling.
        """
        try:
            response = self.session.request(method=method, url=url, timeout=timeout, allow_redirects=allow_redirects, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout as error:
            raise NetworkError(f"Timeout during {method.upper()} {url}") from error
        except requests.exceptions.ConnectionError as error:
            raise NetworkError(f"Connection error during {method.upper()} {url}") from error
        except requests.exceptions.HTTPError as error:
            status = getattr(error.response, "status_code", None)
            raise HTTPStatusError(status_code=status, url=url) from error

    def _get(self, url: str, *, params: dict | None = None, headers: dict | None = None, timeout: float | tuple[float, float] = 15, allow_redirects: bool = True) -> requests.Response:
        return self._request("GET", url, params=params, headers=headers, timeout=timeout, allow_redirects=allow_redirects)

    def _post(self, url: str, *, data: dict | None = None, json: dict | None = None, headers: dict | None = None, timeout: float | tuple[float, float] = 20) -> requests.Response:
        return self._request("POST", url, data=data, json=json, headers=headers, timeout=timeout)
        
    @abstractmethod
    def search_by_keyword(self, keyword: str) -> list[CourseList]:
        """
            This is the method to search for courses by keyword
            that should return a CourseList object,
            which contains the name, course code and url of the course
            for use in the parsing and getting of data for each course
        """
        raise NotImplementedError

    @abstractmethod
    def search_by_identifier(self, identifier: str) -> list[CourseList]:
        """
            This is the method to search for courses by identifier
            that should return a CourseList object,
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