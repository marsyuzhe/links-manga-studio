# OCR model license and provenance — verified 2026-09-26

**Redistribution Confirmed** for all three OCR weights in this release candidate. This conclusion is based on an explicit upstream artifact notice, not an inference from RapidOCR code licensing. Exact ZIP bytes match the hashes in the installed RapidOCR 3.9.2 registry and the upstream notice.

| File | Upstream model / version | Bytes | SHA256 | Source URL | License | Redistribution | In ZIP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `PP-OCRv6_det_small.onnx` | PP-OCRv6_small_det | 9,929,594 | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` | [download](https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv6/det/PP-OCRv6_det_small.onnx) | Apache-2.0 | Redistribution Confirmed | Yes |
| `PP-OCRv6_rec_small.onnx` | PP-OCRv6_small_rec | 21,234,383 | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` | [download](https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv6/rec/PP-OCRv6_rec_small.onnx) | Apache-2.0 | Redistribution Confirmed | Yes |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | ch_ppocr_mobile_v2.0_cls | 585,532 | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` | [download](https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx) | Apache-2.0 | Redistribution Confirmed | Yes |

## Primary evidence

- [RapidOCR artifact-specific notice](https://github.com/RapidAI/RapidOCR/blob/main/python/MODEL_LICENSES.md), section 6, names all three files with these exact SHA256 values and covers them under Apache-2.0. The complete retrieved notice is preserved in `licenses/RapidOCR/UPSTREAM_MODEL_LICENSES.md`.
- [RapidOCR README model terms](https://github.com/RapidAI/RapidOCR#models) explicitly applies the upstream terms to converted ONNX artifacts.
- Official PaddlePaddle [small detection ONNX model card](https://huggingface.co/PaddlePaddle/PP-OCRv6_small_det_onnx) and [small recognition ONNX model card](https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_onnx) identify Apache-2.0.
- [PaddleOCR legacy model list](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version2.x/ppocr/model_list.en.md) identifies the v2.0 angle classifier. Its exact RapidOCR conversion is expressly included in the artifact-specific notice.
- Original project: [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR). Conversion/package project: [RapidOCR](https://github.com/RapidAI/RapidOCR). Registry: [default_models.yaml](https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/default_models.yaml).

## Conversion and attribution

These are ONNX representations converted/repackaged by RapidOCR from official PaddleOCR models. Upstream weights remain copyright Baidu and/or applicable PaddleOCR rights holders; conversion scripts belong to RapidOCR Authors. The packaging version is RapidOCR 3.9.2. Separate converter version and command-line flags were not established; do not invent them. Exact converted-artifact identity is established by SHA256, and need not equal another official ONNX representation.

Links Manga Studio does not modify weight bytes. Keep Apache-2.0 LICENSE, NOTICE, upstream attribution and conversion notice with redistributed models; mark future changes, retain relevant notices, and do not imply endorsement. See root NOTICE and licenses/RapidOCR. These technical records are not legal advice.

## Non-OCR package examples

The ONNX Runtime wheel also contributes `datasets/logreg_iris.onnx`, `mul_1.onnx` and `sigmoid.onnx`. These are inference package examples, not OCR weights. Their provenance is the installed ONNX Runtime 1.30.0 wheel and its MIT license / ThirdPartyNotices.txt, preserved in licenses/onnxruntime. No independent model release version is claimed.

Model binaries remain excluded from the source repository. Re-review new models or changed hashes before packaging; confirmation here is limited to these exact three artifacts.
