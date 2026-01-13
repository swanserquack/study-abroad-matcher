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