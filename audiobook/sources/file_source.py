from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import fitz
from ..models import Chapter

def _clean_text(text: str) -> str:
    """Collapse runaway whitespace."""
    return " ".join(text.split())

class FileSource:
    def load(self, input_str: str) -> list[Chapter]:
        ext = Path(input_str).suffix.lower()
        if ext == ".txt":
            return self._parse_txt(input_str)
        elif ext == ".epub":
            return self._parse_epub(input_str)
        elif ext == ".pdf":
            return self._parse_pdf(input_str)
        elif ext == ".docx":
            return self._parse_docx(input_str)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _parse_txt(self, path: str) -> list[Chapter]:
        stem = Path(path).stem
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        text = _clean_text(text)
        if not text.strip():
            return []
        return [Chapter(index=1, title=stem, text=text)]

    def _parse_docx(self, path: str) -> list[Chapter]:
        stem = Path(path).stem
        with ZipFile(path) as docx:
            document_xml = docx.read("word/document.xml")

        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        root = ET.fromstring(document_xml)
        paragraphs = []
        for para in root.findall(".//w:p", ns):
            runs = [node.text or "" for node in para.findall(".//w:t", ns)]
            text = "".join(runs).strip()
            if text:
                paragraphs.append(text)

        text = _clean_text(" ".join(paragraphs))
        if not text.strip():
            return []
        return [Chapter(index=1, title=stem, text=text)]

    def _parse_epub(self, path: str) -> list[Chapter]:
        book = epub.read_epub(path)
        chapters = []
        spine_ids = [item[0] for item in book.spine]
        index = 1
        for item_id in spine_ids:
            item = book.get_item_with_id(item_id)
            if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            soup = BeautifulSoup(item.get_content(), "html.parser")
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=" ")
            text = _clean_text(text)
            if not text.strip():
                continue
            title = f"Part_{index}"
            for tag in ["h1", "h2", "h3"]:
                heading = soup.find(tag)
                if heading and heading.get_text(strip=True):
                    title = _clean_text(heading.get_text())
                    break
            chapters.append(Chapter(index=index, title=title, text=text))
            index += 1
        return chapters

    def _parse_pdf(self, path: str) -> list[Chapter]:
        doc = fitz.open(path)
        toc = doc.get_toc()
        chapters = []
        
        if not toc:
            text = ""
            for page in doc:
                text += page.get_text("text") + " "
            text = _clean_text(text)
            if text.strip():
                chapters.append(Chapter(index=1, title=Path(path).stem, text=text))
            return chapters
            
        valid_toc = [entry for entry in toc if entry[2] >= 1]
        
        if not valid_toc:
            text = ""
            for page in doc:
                text += page.get_text("text") + " "
            chapters.append(Chapter(index=1, title=Path(path).stem, text=_clean_text(text)))
            return chapters

        index = 1
        for i, entry in enumerate(valid_toc):
            level, title, page_num = entry
            start_page = page_num - 1
            
            if i + 1 < len(valid_toc):
                end_page = valid_toc[i + 1][2] - 1
            else:
                end_page = len(doc)
                
            start_page = max(0, min(start_page, len(doc) - 1))
            end_page = max(start_page, min(end_page, len(doc)))
            
            text = ""
            for p in range(start_page, end_page):
                text += doc[p].get_text("text") + " "
                
            text = _clean_text(text)
            if text.strip():
                chapters.append(Chapter(index=index, title=title.strip(), text=text))
                index += 1
                
        return chapters
