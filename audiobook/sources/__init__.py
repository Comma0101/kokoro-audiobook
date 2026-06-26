from .base import Source
from .file_source import FileSource
from .url_source import UrlSource

def get_source(input_str: str) -> Source:
    if input_str.startswith("http://") or input_str.startswith("https://"):
        return UrlSource()
    return FileSource()
