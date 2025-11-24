# The ScraperEngine class is the main orchestrator of the scraping process.
# It is responsible for coordinating with the provider to scrape the data.
from scraper.providers.base_provider import BaseProvider
from scraper.models import CourseData
import os, orjson, datetime
from dataclasses import is_dataclass, asdict

class ScraperEngine:
    """
    The ScraperEngine is responsible for orchestrating the scraping process.
    It takes a provider as input and uses it to scrape the data.
    """
    def __init__(self, provider: BaseProvider):
        # This allows the engine to hold the *specific* provider it was given, i.e if it was given a keio provider it will hold and use a keio provider
        self.provider = provider
    
    def run(self):
        """
        The main method of the engine, it orchestrates the scraping process.
        1. It gets the course list from the provider.
        2. It iterates through the course list and gets the details for each course.
        3. It parses the details and returns the data.
        """
        # Some providers may require a setup step, i.e getting cookies
        if hasattr(self.provider, 'setup_provider'):
            self.provider.setup_provider()

        course_list = self.provider.get_course_list()
        all_courses_data : list[CourseData] = []
        course_list_length = len(course_list)

        print(f"Found {course_list_length} courses. Starting scrape...")

        for progress, course in enumerate(course_list):
            # ! We are currently limiting to 30 courses gathered as we work on user input/interface
            if progress == 30:
                break
            print("Scraping course", progress, "Progress:", round((progress / course_list_length * 100), 2), "%")
            course_data = self.provider.fetch_course_details(course)
            all_courses_data.append(course_data)
        
        # * This is just here for now until we move to a probably pydantic approach or find another better solution
        def _to_serializable(o):
            if hasattr(o, "dict"):
                return o.dict()
            if is_dataclass(o):
                return asdict(o)
            if hasattr(o, "__dict__"):
                return vars(o)
            return o

        output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(output_dir, exist_ok=True)

        uni_name = self.provider.university_name
        today = datetime.date.today().isoformat()
        filename = f"{today}_{uni_name}_courses.json"
        
        output_path = os.path.join(output_dir, filename)

        serializable = [_to_serializable(c) for c in all_courses_data]
        
        with open(output_path, "wb") as fh:
            fh.write(orjson.dumps(serializable, option=orjson.OPT_INDENT_2))

        print(f"Wrote {len(serializable)} courses to {output_path}")
        print(f"Successfully scraped {len(all_courses_data)} courses.")