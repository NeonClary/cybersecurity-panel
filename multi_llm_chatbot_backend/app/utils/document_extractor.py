from io import BytesIO
import PyPDF2
import tempfile
import docx2txt
import os

def extract_text_from_file(file_bytes: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        reader = PyPDF2.PdfReader(BytesIO(file_bytes))
        return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())

    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            return docx2txt.process(tmp_path)
        finally:
            os.unlink(tmp_path)  # Clean up temp file

    elif content_type == "text/plain":
        return file_bytes.decode("utf-8")

    else:
        raise ValueError("Unsupported file type.")