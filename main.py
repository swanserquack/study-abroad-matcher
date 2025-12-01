from scraper.engine import ScraperEngine
from scraper.providers import get_provider_class, PROVIDER_REGISTRY
from scraper.errors import (
    ScraperError,
    ValidationError,
    CourseNotFoundError,
    NetworkError,
    HTTPStatusError,
    ParseError
)
import questionary
from rich.console import Console

# Use console for later extensability if needed
console = Console()

# TODO: Language mapping could work by having languages map to a value and then each provider would have their own internal global -> local language mapping
# print("Available universities:")
# print(list(PROVIDER_REGISTRY.keys()))

provider_keys = list(PROVIDER_REGISTRY.keys())

# Create mapping from display text to provider key
display_to_key = {key.replace("_", " ").title(): key for key in provider_keys}

choices = list(display_to_key.keys())
option_map = {
    "Search by keyword": "keyword",
    "Search by course identifier": "course_identifier",
    "Exit": "exit"
}

while True:
    # ? If for now we force every provider to provide search for both keyword and course identifier since most if not all universities list course codes on their website then later if we stumble along one that doesnt we can either consider making them optional or implement a check here to check which search methods are available
    search_method = questionary.select(
        "Do you want to search by keyword or course identifier?",
        choices=["Search by keyword", "Search by course identifier", "Exit"],
    ).ask()

    # Map display text back to provider key
    search_method = option_map[search_method]

    if search_method == "exit":
        print("Exiting...")
        raise SystemExit()

    selection = questionary.select(
        "Select a university",
        choices=choices,
        use_arrow_keys=True,
        use_jk_keys=False,
        use_emacs_keys=False,
        use_search_filter=True
    ).ask()

    # Map display text back to provider key
    provider_key = display_to_key[selection]

    if search_method == "keyword":
        keyword = questionary.text(f"Enter the keyword to search {selection} for: ").ask()
        while keyword.isascii() is False:
            console.print("Please enter a valid ASCII keyword.", style="bold red")
            keyword = questionary.text(f"Enter the keyword to search {selection} for: ").ask()

    elif search_method == "course_identifier":
        identifier = questionary.text(f"Enter the course identifier to search {selection} for: ").ask()
        while identifier.isascii() is False:
            console.print("Please enter a valid ASCII course identifier.", style="bold red")
            identifier = questionary.text(f"Enter the course identifier to search {selection} for: ").ask()

    ProviderClass = get_provider_class(provider_key)
    if not ProviderClass:
        raise ScraperError(f"Provider {provider_key} not found.")

    provider = ProviderClass()
    engine = ScraperEngine(provider)

    try:
        if search_method == "keyword":
            engine.run(search_method, keyword)
        elif search_method == "course_identifier":
            engine.run(search_method, identifier)

    # The identifier the user input is invalid in some way
    except ValidationError as error:
        console.print(f"Validation error: {error}", style="bold red")
        continue
    # We get a valid resposne from the provider but its contents are malformed/unexpected
    except ParseError as error:
        console.print(f"Parse error: {error}", style="bold red")
        continue
    # The course is not found, either the identifier is 'valid' but no such course exists, or the keyword search returned no results
    except CourseNotFoundError as error:
        console.print(f"No results: {error}", style="yellow")
        continue
    # Either Timeout or Connection error or HTTP error
    except (NetworkError, HTTPStatusError) as error:
        console.print(f"Network/HTTP error: {error}", style="bold yellow")
        continue
    # Catch all other scraper related errors
    except ScraperError as error:
        console.print(f"Scraper error: {error}", style="bold red")
        continue