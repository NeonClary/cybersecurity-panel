from io import BytesIO
from typing import List, Tuple
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def format_messages_for_export(messages: List[dict]) -> str:
    """
    Convert chat messages into a structured exportable string.
    """
    return "\n\n".join([f"{m['role']}:\n{m['content'].strip()}" for m in messages])


def generate_txt_file(text: str) -> BytesIO:
    buffer = BytesIO()
    buffer.write(text.encode("utf-8"))
    buffer.seek(0)
    return buffer


def generate_docx_file(text: str) -> BytesIO:
    doc = Document()
    for block in text.split("\n\n"):
        doc.add_paragraph(block)
        doc.add_paragraph("")  # spacing

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def generate_pdf_file(text: str) -> BytesIO:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    width, height = letter
    y = height - 40
    line_height = 14

    for line in text.splitlines():
        if y < 40:
            c.showPage()
            y = height - 40
        c.drawString(40, y, line)
        y -= line_height

    c.save()
    buffer.seek(0)
    return buffer


def export_chat_as_file(messages: List[dict], format: str) -> Tuple[BytesIO, str, str]:
    """
    Export chat messages to the requested file format.
    Returns: (file_stream, filename, media_type)
    """
    text = format_messages_for_export(messages)

    if format == "txt":
        stream = generate_txt_file(text)
        return stream, "chat_export.txt", "text/plain"

    elif format == "docx":
        stream = generate_docx_file(text)
        return stream, "chat_export.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    elif format == "pdf":
        stream = generate_pdf_file(text)
        return stream, "chat_export.pdf", "application/pdf"

    else:
        raise ValueError(f"Unsupported export format: {format}")
