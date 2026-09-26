# Links Manga Studio v0.5.0 — Initial Public Release

Links Manga Studio 是 Windows 本地漫画 OCR、翻译、擦除与排版工作台。作者：**Links Tam**。

## 主要功能

- 导入图片、文件夹与 PDF，PDF 可直接创建项目。
- 本地 OCR 校对，通过 TextBlock 或 DOCX 批次交换译文，擦除后在同一文本框回填。
- 项目字体样式、Auto Fit、质量检查与具名撤销/重做。
- 深色、浅色、系统主题；中文与英文界面。
- `.lmw` 本地项目，支持复制或引用原始文件。

## 安装

由作者手动发布后，从 Release 下载 Windows ZIP 和 `.sha256`，核验哈希并完整解压，运行 `LinksMangaWorkspace.exe`，保持 `runtime/` 与 EXE 同级。旧 EXE 文件名用于兼容；产品名称是 Links Manga Studio。

## 限制和版权

支持 Windows x64；OCR、竖排和复杂擦除需要人工检查。相似字体建议不保证找回原字体。程序未签名，不提供漫画素材，使用者负责取得处理及分发素材的授权。

第三方通知见 THIRD_PARTY_NOTICES.md 和 ZIP 内 licenses；模型审查见 MODEL_LICENSES.md。项目已采用 Apache-2.0，三个 OCR 权重已按确切哈希核对上游 Apache-2.0 许可。当前为首次公开发布候选版，尚未上传 GitHub。
