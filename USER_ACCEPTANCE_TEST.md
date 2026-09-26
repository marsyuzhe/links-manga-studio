# 人工验收操作说明（Windows）

以下由用户在真实可见窗口中执行。开发自动化只使用终端和 Qt offscreen；这些手工步骤未自动标记 PASS。

## 0.3.0 工作流重点

1. 在启动页将两张图片或一个 PDF 拖入，检查清单确认框、自动建项目和导入结果。已有项目再拖入素材，分别选择“添加到当前项目”“创建新项目”“取消”。
2. 在空项目检查画布上的 5 步轻提示。通过设置切换简单/高级模式；在视图菜单展开页面信息和底部任务区，关闭重开后检查状态保存；按 Tab 两次检查画布专注模式与恢复。
3. 对 OCR 页面使用左侧 OCR 文本搜索和“低置信度”筛选。单击文字框检查边框和手柄；双击检查右侧译文编辑器获得焦点。拖动、缩放和旋转框后保存重开，检查几何位置。
4. 在译文页输入译文，按 Ctrl+Enter 或点击“擦除并回填译文”。检查原文字消失、译文位于原框，Text UID 保持；Ctrl+Z 一次同时恢复两项，Ctrl+Y 一次重做。空译文点击主按钮，应提示且原图保持。
5. 分别试“仅擦除”“仅回填译文”“恢复当前擦除”。导出当前页、批次、全项目原文 DOCX，检查每个 Text UID、原文和页 UID；再试 TSV。随后通过翻译菜单进行 Word 译文交换。

1. 解压 ZIP 到中文路径（例如 `D:\漫画项目\工作台测试\`），双击 `LinksMangaWorkspace.exe`。确认没有黑色 CMD 窗口，启动页不白屏，图标在窗口、任务栏和 Alt+Tab 中显示。
2. 在 Settings → Language 切换简体中文和 English，关闭重开，确认语言持久化。检查菜单、按钮和右侧编辑区在当前 Windows Display Scaling 下的布局。
3. 各建一个 Copy 和 Reference 项目；导入中文文件名图片及多页 PDF。检查缩略图、画布、Inspector、状态栏。删除 Copy 项目外部原图后重开；移动 Reference 源图后检查 Missing Source，并尝试 Relocate Source。
   另从启动窗口直接打开 PDF 并确认自动创建项目；再把 PDF、图片和图片文件夹分别拖入窗口导入。
4. 千页项目快速滚动到 100/300/500/800/1000 页，连续快速切页至少 50 次，最后停第 50 页；等待后台任务后确认画布仍是第 50 页。检查 Previous/Next 边界、Fit、100%、50%/200%/400% Zoom、Space+Drag 或中键平移。
5. 对清晰文字页执行 OCR，点击蓝色识别框；修改原文、阅读顺序、译文、位置/尺寸/旋转、字体和擦字。进入 Mask 编辑器试用 Brush、Erase、Zoom 和 Pan，保存重开，再执行 Ctrl+Z/Ctrl+Y。
   在左侧 OCR Text 列表中选框，分别导出当前页、当前批次和全项目原文。用 Quick Erase 擦除单框、多选框和当前页全部框；确认 Text UID 保持不变。开启 Fill Translation 文字工具，点击橙色框在原位置输入译文，检查自动排版并再次修改。检查底部 Tasks、Logs、Export 标签。
6. 建立批次，分别导出 Light/Standard/Full DOCX。在 Word 中填写至少两条译文、交换表格行，保存并回导。检查回导报告和译文映射。另用副本删除书签，确认系统报告缺失而不猜测。
7. 导出当前页、批次和整个项目，检查 PNG/JPEG/WEBP 与画布预览的位置一致。让一个 Reference 源文件暂时丢失，确认其他页继续；恢复后继续任务。
8. File → Back Up Project，检查 SQLite、`project.json` 和 Mask。Help → Diagnostics 与 Open Log Folder，确认路径和环境信息。
9. 最大化、还原、缩小与拉伸窗口；记录实际 DPI 比例。未测试的其他 DPI 或其他 Windows 电脑应写 NOT TESTED。

反馈 Bug 请提供版本、Windows 版本、缩放比例、复现步骤、日志与可分享的最小测试项目。应用日志位于 `%APPDATA%\LinksMangaWorkspace\logs\app.log`。
