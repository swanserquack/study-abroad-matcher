class ScraperError(Exception):
    """Base exception for all scraper-related errors."""
    pass


class ValidationError(ScraperError):
    """Raised when validation fails (e.g., invalid course code format)."""
    pass


class ProviderError(ScraperError):
    """Generic provider-related error."""
    pass


class NetworkError(ScraperError):
    """Raised for connectivity and timeout issues when making HTTP requests."""
    pass


class HTTPStatusError(ScraperError):
    """Raised when an HTTP request returns an unexpected status code."""

    def __init__(self, status_code: int | None, url: str, message: str | None = None):
        self.status_code = status_code
        self.url = url
        super().__init__(message or f"HTTP error {status_code} for URL: {url}")


class ParseError(ScraperError):
    """Raised when parsing a response (e.g., JSON or HTML) fails unexpectedly."""
    pass


class CourseNotFoundError(ScraperError):
    """Raised when a search returns no matching courses."""
    pass