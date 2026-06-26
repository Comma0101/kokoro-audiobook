import trafilatura
from ..models import Chapter

class UrlSource:
    def load(self, input_str: str) -> list[Chapter]:
        downloaded = trafilatura.fetch_url(input_str)
        if downloaded is None:
            raise ValueError(f"Could not fetch url: {input_str}")
        
        doc = trafilatura.bare_extraction(downloaded)
        if not doc or not getattr(doc, "text", None):
            raise ValueError(f"Could not extract readable text from {input_str}")
            
        text = doc.text
        title = getattr(doc, "title", "Web Article") or "Web Article"
        
        text = " ".join(text.split())
        
        if not text.strip():
            raise ValueError(f"Could not extract readable text from {input_str}")
            
        return [Chapter(index=1, title=title.strip(), text=text)]
