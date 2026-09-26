from pathlib import Path
import pytest
from app.importers.folder_importer import natural_key, scan_folder


@pytest.mark.parametrize("names,expected", [
    (["10.jpg", "2.jpg", "1.jpg"], ["1.jpg", "2.jpg", "10.jpg"]),
    (["page10.jpg", "page02.jpg", "page1.jpg"], ["page1.jpg", "page02.jpg", "page10.jpg"]),
    (["第10页.jpg", "第2页.jpg", "第1页.jpg"], ["第1页.jpg", "第2页.jpg", "第10页.jpg"]),
])
def test_natural_sort(names, expected):
    assert sorted(names, key=natural_key) == expected


def test_scan_uppercase_empty_unsupported_and_missing(tmp_path):
    assert scan_folder(tmp_path).paths == []
    (tmp_path / "001.JPG").write_bytes(b"broken")
    (tmp_path / "readme.txt").write_text("ignored")
    scan = scan_folder(tmp_path)
    assert len(scan.paths) == 1 and scan.ignored == 1
    with pytest.raises(FileNotFoundError):
        scan_folder(tmp_path / "missing")
