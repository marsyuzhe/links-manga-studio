# Links Manga Studio

Local-first manga OCR, translation, cleaning and typesetting studio for Windows.

Created by Links Tam.

[English](README.md) | 简体中文

![Windows](https://img.shields.io/badge/platform-Windows-blue) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE) ![Version](https://img.shields.io/badge/version-0.6.0-grey)

Windows 本地漫画翻译工作台：导入图片、文件夹或 PDF，校对 OCR，翻译、擦除原文、排版并导出成品。**没有 API Key 也能完成人工翻译。**

## 漫画工作区

![深色工作区](docs/images/workspace-dark.png)

左侧管理页面与批次，中间处理画布，右侧编辑原文、译文和排版属性。顶部按导入 → OCR → 导出原文 → 擦除 → 回填 → 导出的顺序提供入口。

![浅色工作区](docs/images/workspace-light.png)

## 翻译中心与术语库

可选的 AI 翻译使用您自己的云端账号，或您已启动的本地模型服务。软件不捆绑大型语言模型。译文草稿需要审核，默认保护已有人工译文。

![翻译中心](docs/images/translation-center.png)

术语库与人物备注保存在项目中，便于保持名字和称呼一致。

![术语库](docs/images/glossary.png)

## 第一次使用

从本仓库 **Releases** 下载 Windows ZIP，完整解压，再运行 **LinksMangaWorkspace.exe**。不要只取 EXE，也不要在压缩包内运行。

![启动窗口](docs/images/startup.png)

以上五张截图均为合成素材。先读 [快速开始](QUICK_START.md)，细节见 [简中用户指南](docs/USER_GUIDE.zh-CN.md)。源码开发见 [开发者指南](docs/DEVELOPER_GUIDE.md)。

## 项目与隐私

项目是本地 `.lmw` 文件夹。Copy 模式复制素材；Reference 模式依赖原文件位置。升级前备份整个项目及外部引用素材。

OCR、人工翻译、擦除和排版在本机完成。云端翻译会发送所选文本及启用的上下文；本地翻译需要自行安装并启动外部服务。API Key 由您填写，使用 Windows 凭据管理器保存，不写入项目。

## 已知边界

自动测试使用合成项目和模拟服务。真实付费 API、本地模型与可见 Windows DPI/交互仍需用户验收。支持 PDF 页面导入，成品格式以导出对话框为准。见 [发布说明](RELEASE_NOTES_0.6.0.md)。

## 开源许可

源码 Apache-2.0；依赖与 OCR 模型遵循各自许可。见 [第三方声明](THIRD_PARTY_NOTICES.md)、[模型许可](MODEL_LICENSES.md)、[许可审查](LICENSE_REVIEW.md)。

[架构](docs/ARCHITECTURE.md) · [贡献指南](CONTRIBUTING.md) · [安全报告](SECURITY.md)
