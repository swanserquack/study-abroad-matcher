# The ScraperEngine class is the main orchestrator of the scraping process.
# It is responsible for coordinating with the provider to scrape the data.
from scraper.providers.base_provider import BaseProvider
from scraper.models import CourseData
import os, orjson, datetime
from dataclasses import is_dataclass, asdict
from rich.progress import Progress, MofNCompleteColumn

class ScraperEngine:
    """
    The ScraperEngine is responsible for orchestrating the scraping process.
    It takes a provider as input and uses it to scrape the data.
    """
    def __init__(self, provider: BaseProvider):
        # This allows the engine to hold the *specific* provider it was given, i.e if it was given a keio provider it will hold and use a keio provider
        self.provider = provider
        self.progress = Progress(    
            *Progress.get_default_columns(),
            MofNCompleteColumn()
        )
    
    def run(self, search_method: str, value: str) -> None:
        """
        The main method of the engine, it orchestrates the scraping process.
        1. It gets the course list from the provider.
        2. It iterates through the course list and gets the details for each course.
        3. It parses the details and returns the data.
        """
        self.progress.start()

        # Some providers may require a setup step, i.e getting cookies
        setup_method = getattr(self.provider, 'setup_provider', None)
        if callable(setup_method):
            setup_method()
        
        if search_method == "keyword":
            course_list = self.provider.search_by_keyword(value)
        elif search_method == "course_identifier":
            course_list = self.provider.search_by_identifier(value)

        all_courses_data : list[CourseData] = []
        course_list_length = len(course_list)

        print(f"Found {course_list_length} courses. Starting scrape...")

        getting_details = self.progress.add_task("[green]Getting course details...", total=course_list_length, start=True)
        for course in course_list:
            course_data = self.provider.fetch_course_details(course)
            all_courses_data.append(course_data)
            self.progress.update(getting_details, advance=1)

        self.progress.stop()

        output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(output_dir, exist_ok=True)

        uni_name = self.provider.university_name
        today = datetime.date.today().isoformat()
        filename = f"{uni_name}_{value.replace(" ", "_")}_{today}_courses.json"
        
        output_path = os.path.join(output_dir, filename)

        serializable = [c.model_dump() for c in all_courses_data]
        
        with open(output_path, "wb") as fh:
            fh.write(orjson.dumps(serializable, option=orjson.OPT_INDENT_2))

        print(f"Wrote {len(serializable)} courses to {output_path}")
        print(f"Successfully scraped {len(all_courses_data)} courses.")