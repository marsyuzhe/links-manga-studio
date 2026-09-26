import struct
from conftest import make_image
from app.images.image_loader import ImageLoader
from app.images.thumbnail_service import ThumbnailService


def test_thumbnail_unicode_disk_cache_and_version(tmp_path):
    path = make_image(tmp_path / "中文目录" / "第001页.jpg", 1000, 1600)
    page = {"path": str(path), "source_file_id": "uuid"}
    thumbnails = ThumbnailService(tmp_path)
    image = thumbnails.get(page)
    target = thumbnails.path_for(page)
    assert max(image.width(), image.height()) == 256
    timestamp = target.stat().st_mtime_ns
    assert not thumbnails.get(page).isNull()
    assert target.stat().st_mtime_ns == timestamp
    thumbnails.VERSION = 2
    assert thumbnails.path_for(page) != target


def test_exif_normalized_dimensions(tmp_path):
    path = make_image(tmp_path / "rotated.jpg", 80, 120)
    jpeg = path.read_bytes()
    tiff = b"II" + struct.pack("<HIH", 42, 8, 1) + struct.pack("<HHI", 274, 3, 1) + struct.pack("<H", 6) + b"\0\0" + struct.pack("<I", 0)
    payload = b"Exif\0\0" + tiff
    path.write_bytes(jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(payload)+2) + payload + jpeg[2:])
    image = ImageLoader().load(path)
    metadata = ImageLoader().metadata(path)
    assert (image.width(), image.height()) == (120, 80)
    assert (metadata["width"], metadata["height"]) == (120, 80)
