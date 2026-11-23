class ScraperException(Exception):
    """Base exception for Sushiscan Scraper."""
    def __init__(self, message: str, level: str = "error") -> None:
        super().__init__(message)
        self.message = message
        self.level = level

class NotFound404(ScraperException):
    pass

class InvalidWebsite(ScraperException):
    pass

class InvalidStatusCode(ScraperException):
    pass

class InvalidRangeFormat(ScraperException):
    pass

class NoResultsFound(ScraperException):
    pass

class ChapterDownloadError(ScraperException):
    pass
