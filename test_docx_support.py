from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from audiobook.sources.file_source import FileSource

ROOT = Path(__file__).parent
SERVER = (ROOT / "audiobook" / "server.py").read_text(encoding="utf-8")


def write_minimal_docx(path: Path) -> None:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>First paragraph</w:t></w:r></w:p>
    <w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with ZipFile(path, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", "")
        docx.writestr("word/document.xml", document_xml)


def test_file_source_extracts_docx_text():
    with TemporaryDirectory() as tmp:
        docx_path = Path(tmp) / "memo.docx"
        write_minimal_docx(docx_path)

        chapters = FileSource().load(str(docx_path))

        assert len(chapters) == 1
        assert chapters[0].title == "memo"
        assert chapters[0].text == "First paragraph Second paragraph"


def test_server_accepts_docx_upload_extension():
    assert '".docx"' in SERVER
    assert "Only .txt, .pdf, .epub, .docx allowed." in SERVER


if __name__ == "__main__":
    test_file_source_extracts_docx_text()
    test_server_accepts_docx_upload_extension()
    print("docx support tests passed")
