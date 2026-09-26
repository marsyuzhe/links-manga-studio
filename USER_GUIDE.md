# Links Manga Studio 用户指南（0.5.0）

设置中可切换深色、浅色或跟随 Windows 系统，切换立即生效并在重启后保留。启动页可直接打开 PDF，也可拖入 PDF、图片或文件夹。最近项目菜单可打开项目、打开所在文件夹或从列表移除。

## 0.4.1 视觉工作区

启动页可拖入漫画，也可新建、打开项目或直接打开 PDF。打开项目后，顶部单行工具栏展示常用流程；左侧工具轨提供选择、抓手、文字、擦除、Mask 和缩放，旁边按页面/OCR/批次/项目切换。画布位于中央；右侧优先显示译文及“擦除并回填译文”。底部任务、日志、导出与质量检查默认折叠。Tab 切换专注模式时保留画布和顶部工具栏。设置 → 首选项可调整简洁模式和图片缓存上限。完整可见窗口检查步骤见 `docs/UI_ACCEPTANCE_0.4.md`。

## 0.4 字体与排版

选中文字框后，在右侧“样式”选择 speech、narration、thought、sfx、note 或 custom 角色。项目菜单的 **Project Styles** 可修改角色的默认字体、字号范围、边距、行距、颜色和对齐方式；未单独覆盖的文字框会继承变更。单框样式可应用到当前页、批次或项目；**Reset Style Override** 可恢复继承。项目打开时若提示缺失字体，可用 **Replace Missing Fonts** 批量替换。字体浏览器可搜索、收藏、查看最近字体、临时预览和查看相似风格建议。建议只是视觉特征的启发式排序，请人工确认。

“排版”标签显示 Auto Fit 结果：fit、warning 或 overflow。可调整最小/最大字号、框内边距、行距及横排/竖排模式。中文标点换行有基础避头尾规则。项目菜单 **Quality Check** 可列出未校对 OCR、缺失译文、排版溢出、缺失字体等问题；双击问题定位至对应页面和文字框。质量检查不修改项目。译文编辑会在短暂输入停顿后自动写入数据库；切换文字框时会先保存待提交内容。

## 0.3 工作流界面

拖入 PDF、图片或文件夹后先确认清单。若已有项目，可选择导入当前项目或创建新项目。顶部工具栏提供导入、OCR、原文导出、擦除并回填、成品导出。菜单分别按文件、编辑、视图、项目、OCR、翻译、导出、设置和帮助分组。右侧译文面板输入内容后按“擦除并回填译文”；空译文不会擦除。一次 Ctrl+Z 可同时恢复原图与译文，Ctrl+Y 重做。原文导出支持 DOCX/TSV，范围可选当前页、批次或项目。左侧 OCR 列表可搜索、筛选；右侧默认简单模式，设置菜单可切换高级模式。视图菜单可展开页面信息、底部任务区；Tab 切换画布专注模式。

## 启动与建项目

解压 ZIP，保持 `LinksMangaWorkspace.exe` 与 `runtime/` 在同一目录，双击 EXE。首次使用可选 **New Project**，也可点 **Open PDF as New Project** 选取 PDF 并自动创建 Copy 项目。**Copy Into Project** 会复制图片或 PDF 至项目的 `sources/`；**Reference Original Files** 保留源文件路径，适合大文件，但需要自行保管原始文件。以后用 **Open Project** 或 **Recent Projects** 打开 `.lmw` 目录。

## 导入和浏览

在主窗口点击 **Import Images**、**Import Folder**、**Import PDF**，也可把 PDF、图片或文件夹拖入窗口。左侧 Pages/Batches/OCR Text/Project 标签切换列表；中央画布可用 **Previous / Next**、**Fit to Window**、**100%**，滚轮缩放后可拖动画布。右侧标签分别编辑属性、原文、译文、擦除和排版。若 Reference 素材移动，页面会显示 **Missing Source**；选择 **Relocate Source** 指向正确文件。空文件夹、重复导入和损坏文件会给出提示，并写入日志。

## OCR 与校对

从顶部工具栏启动当前页 OCR，或从 OCR 菜单识别全部页并继续未完成任务。OCR 在本机 CPU 上运行，首次启动可能稍慢。左侧 OCR Text 列表和画布蓝色文字框均可选取 TextBlock，右侧可修改原文、译文、阅读顺序和样式。顶部 **Export Original Text** 可按当前页、批次或整个项目导出 DOCX/TSV。**Quick Erase** 在编辑菜单中可擦除当前、列表选中或当前页全部 OCR 框；橙色框表示已擦除。顶部 **擦除并回填译文** 是推荐操作。双击画布文字框，或开启 **Fill Translation** 文字工具后点击橙色框，也可直接编辑译文；排版会按框大小自动适配。识别结果需要人工检查，尤其是竖排、手写或复杂拟声词。常用编辑支持 Ctrl+Z 撤销、Ctrl+Y 重做。

## Word 翻译交换

创建批次后选择 Light、Standard 或 Full Word 导出。编辑文档中的译文列，保留内部书签，然后通过 Word 导入功能回写。导入报告会列出成功、冲突、缺失和重复项目；未匹配的内容不会猜测写入。

## 擦字、嵌字和图片导出

选中文字框后可使用 Fill、Inpaint 或 Mask 擦字，再设定字体、大小、颜色、旋转与自动适配。原始图片不会被覆盖。可导出当前页、批次或整个项目为 PNG、JPEG、WEBP。大量页面导出可能耗时，任务可续跑。

## 备份、语言与故障排查

文字、译文、阅读顺序、样式及页序修改会立即写入项目数据库，关闭项目后可重新打开。File → **Back Up Project** 备份项目元数据、数据库和 Mask；大文件素材不包含在该备份中，Reference 外部文件必须另行备份。恢复时先关闭项目，复制整个 `.lmw` 项目目录，再将已备份的 `project.json`、`project.sqlite3` 和 `masks/` 放回该副本，并重新打开副本；请保留原项目供回退。语言可在 Settings 菜单切换简体中文或 English。Help → **Diagnostics** 查看环境信息；Help → **Open Log Folder** 查看日志。若应用无法启动，确认完整解压 ZIP、`runtime/` 未被移动，随后查看 `%APPDATA%` 下 Links Manga Workspace 的日志。

当前版本的人工 Windows 验收步骤见 `USER_ACCEPTANCE_TEST.md`，功能限制见 `RELEASE_NOTES.md`。
