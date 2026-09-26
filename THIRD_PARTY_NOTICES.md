# Third-party notices — v0.5.0

The project source and original assets are Apache-2.0. Dependencies retain their own terms. Versions below are from the actual Windows build environment; the installed wheel license texts and `licenses/` directory govern the exact notices. Re-audit upgrades. Model identity and licensing are documented separately in MODEL_LICENSES.md.

## Runtime dependencies

| Dependency | Version | License | Project URL | Usage / redistribution notes |
| --- | --- | --- | --- | --- |
| PySide6-Essentials | 6.11.2 | LGPL-3.0/GPL/commercial | [PySide6-Essentials](https://doc.qt.io/qtforpython-6/) | Qt UI, separate DLLs; preserve notices and LGPL materials/source pointers; allow compatible replacement |
| shiboken6 | 6.11.2 | LGPL-3.0/GPL/commercial | [shiboken6](https://doc.qt.io/qtforpython-6/) | Qt bindings |
| pypdfium2 | 5.13.0 | BSD-3-Clause/Apache-2.0; PDFium BSD and component terms | [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | PDF rendering; preserve PDFium BUILD_LICENSES |
| rapidocr | 3.9.2 | Apache-2.0 | [rapidocr](https://github.com/RapidAI/RapidOCR) | Local OCR; exact model attribution preserved separately |
| onnxruntime | 1.30.0 | MIT plus component notices | [onnxruntime](https://github.com/microsoft/onnxruntime) | CPU inference; retain LICENSE and ThirdPartyNotices.txt |
| opencv-python | 5.0.0.93 | Wheel scripts MIT; OpenCV Apache-2.0 and component terms | [opencv-python](https://github.com/opencv/opencv-python) | Image processing; preserve full wheel notices |
| Pillow | 12.3.0 | MIT-CMU | [Pillow](https://github.com/python-pillow/Pillow) | Image codecs; retain license |
| python-docx | 1.2.0 | MIT | [python-docx](https://github.com/python-openxml/python-docx) | DOCX exchange |
| fonttools | 4.65.0 | MIT and external component notices | [fonttools](https://github.com/fonttools/fonttools) | Font metadata; no user fonts bundled |
| numpy | 2.5.3 | BSD-3-Clause and bundled component terms | [numpy](https://github.com/numpy/numpy) | Arrays; preserve wheel license |
| shapely | 2.1.2 | BSD-3-Clause; GEOS LGPL-2.1 | [shapely](https://github.com/shapely/shapely) | Geometry; preserve bundled GEOS license and replacement/source obligations |
| pyclipper | 1.4.0 | MIT; Clipper Boost-1.0 | [pyclipper](https://github.com/fonttools/pyclipper) | Geometry; preserve component notices |
| PyYAML | 6.0.3 | MIT | [PyYAML](https://github.com/yaml/pyyaml) | OCR config |
| lxml | 6.1.3 | BSD-3-Clause; libxml2/libxslt component terms | [lxml](https://lxml.de/) | XML; preserve wheel notices |
| omegaconf | 2.3.1 | BSD-3-Clause | [omegaconf](https://github.com/omry/omegaconf) | OCR config |
| requests | 2.34.2 | Apache-2.0 | [requests](https://github.com/psf/requests) | Transitive network utility; built-in OCR is local |
| certifi | 2026.7.22 | MPL-2.0 | [certifi](https://github.com/certifi/python-certifi) | CA data; retain MPL notices and corresponding source access |
| charset-normalizer | 3.5.1 | MIT | [charset-normalizer](https://github.com/jawah/charset_normalizer) | HTTP encoding dependency |
| idna | 3.20 | BSD-3-Clause | [idna](https://github.com/kjd/idna) | HTTP names |
| urllib3 | 2.8.0 | MIT | [urllib3](https://github.com/urllib3/urllib3) | HTTP utility |
| antlr4-python3-runtime | 4.9.3 | BSD-3-Clause | [antlr4-python3-runtime](https://github.com/antlr/antlr4) | OmegaConf parser |
| colorlog | 6.12.0 | MIT | [colorlog](https://github.com/borntyping/python-colorlog) | Logging |
| flatbuffers | 25.12.19 | Apache-2.0 | [flatbuffers](https://github.com/google/flatbuffers) | Inference serialization |
| protobuf | 7.36.2 | BSD-3-Clause | [protobuf](https://github.com/protocolbuffers/protobuf) | Inference serialization |
| six | 1.17.0 | MIT | [six](https://github.com/benjaminp/six) | Compatibility dependency |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | [tqdm](https://github.com/tqdm/tqdm) | Progress utility; preserve both notice sets |
| typing_extensions | 4.16.0 | PSF-2.0 | [typing_extensions](https://github.com/python/typing_extensions) | Runtime typing |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | [packaging](https://github.com/pypa/packaging) | Version metadata |

Qt version matches the PySide6 Essentials wheel (6.11.2). PDFium is the revision bundled by pypdfium2 5.13.0; preserve that wheel's PDFium and dependency license texts rather than treating it as only Python code. The `imaging` extra can install opencv-python-headless instead of opencv-python; both use the OpenCV wheel licensing structure, and packaging collects whichever is actually installed.

## Development / test dependencies

| Dependency | Observed version | License | Project URL | Usage / redistribution notes |
| --- | --- | --- | --- | --- |
| pytest | 9.1.1 | MIT | [pytest](https://pytest.org/) | Core tests; not an application dependency |
| pytest-qt | 4.5.0 | MIT | [pytest-qt](https://github.com/pytest-dev/pytest-qt) | Qt tests; not an application dependency |
| PyInstaller | 6.22.3 | GPL with bootloader exception | [PyInstaller](https://pyinstaller.org/) | Build tool; exception permits application distribution under own license; not an application dependency |
| pyinstaller-hooks-contrib | 2026.7 | GPL/Apache license split in upstream files | [pyinstaller-hooks-contrib](https://github.com/pyinstaller/pyinstaller-hooks-contrib) | Build hooks; preserve relevant notices; not an application dependency |
| setuptools | 84.0.0 | MIT | [setuptools](https://github.com/pypa/setuptools) | Build metadata; not an application dependency |
| altgraph | 0.17.5 | MIT | [altgraph](https://github.com/ronaldoussoren/altgraph) | Build graph; not an application dependency |
| pefile | 2024.8.26 | MIT | [pefile](https://github.com/erocarrera/pefile) | PE build helper; not an application dependency |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | [pywin32-ctypes](https://github.com/enthought/pywin32-ctypes) | Build helper; not an application dependency |
| iniconfig | 2.3.0 | MIT | [iniconfig](https://github.com/pytest-dev/iniconfig) | Test config; not an application dependency |
| pluggy | 1.6.0 | MIT | [pluggy](https://github.com/pytest-dev/pluggy) | Test plugins; not an application dependency |
| Pygments | 2.21.0 | BSD-2-Clause | [Pygments](https://pygments.org/) | Test formatting; not an application dependency |
| colorama | 0.4.6 | BSD-3-Clause | [colorama](https://github.com/tartley/colorama) | Console formatting; not an application dependency |

PyMuPDF has been removed from all project dependency lists and the build environment. PDF fixture coverage is retained using existing PDFium and Qt QPdfWriter, with no new dependency. Defensive build exclusions remain. Python itself retains the PSF license and bundled standard-library notices in the portable runtime.

## Distribution

The Windows onedir package includes separate libraries and collected licenses. Root LICENSE and NOTICE do not replace LGPL/MPL/BSD/MIT or other third-party obligations. Never strip vendor notices or claim all dependencies are Apache-2.0. The public source tree contains no installed wheels, fonts, weight binaries or user data.
