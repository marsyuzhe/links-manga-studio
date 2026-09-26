from app.batches.service import BatchService
from app.pdf.importer import PdfImporter
from app.pages.page_service import PageService
from test_pdf import make_pdf


def test_thousand_page_stable_batches(project_factory, tmp_path):
    project = project_factory()
    PdfImporter(project.path).import_file(make_pdf(tmp_path / "many.pdf"))
    batches = BatchService(project.connection)
    ids = batches.create_for_unassigned()
    assert len(ids) == 10
    assert [row["page_count"] for row in batches.list_batches()] == [100] * 10
    original = batches.page_ids(ids[0])
    page = PageService(project.connection, project.path)
    page.move(original[0], 1)
    assert batches.page_ids(ids[0]) == original
    assert batches.create_for_unassigned() == []


def test_custom_batch_size(project_factory, tmp_path):
    project = project_factory()
    PdfImporter(project.path).import_file(make_pdf(tmp_path / "small.pdf", 51))
    batches = BatchService(project.connection)
    ids = batches.create_for_unassigned(25)
    assert [row["page_count"] for row in batches.list_batches()] == [25, 25, 1]
    assert len(set(ids)) == 3
