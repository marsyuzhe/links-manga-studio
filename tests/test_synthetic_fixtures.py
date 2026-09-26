"""Generated public fixtures remain usable without checked-in artwork."""
from PySide6.QtGui import QImage
import pypdfium2 as pdfium

from fixtures.synthetic import multi_page_pdf, sample_page


def test_generated_page_and_pdf(qapp, tmp_path):
    page = sample_page(tmp_path / "第001页.png", vertical=True)
    image = QImage(str(page))
    assert not image.isNull() and (image.width(), image.height()) == (640, 900)
    pdf = multi_page_pdf(tmp_path / "synthetic.pdf", count=3)
    with pdfium.PdfDocument(str(pdf)) as document:
        assert len(document) == 3
