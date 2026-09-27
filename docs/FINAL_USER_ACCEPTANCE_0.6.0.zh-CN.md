# 0.6.0 最终 Windows 用户验收

本表供用户在自己的真实 Windows 桌面填写。自动 offscreen、模拟服务、逻辑几何矩阵不替代这些项目。**当前每项均为 NOT TESTED**；不要凭截图改为 PASS。

记录：应用 ZIP/SHA256：____；Windows 版本：____；显示缩放：____；显示器：____；日期：____。

| 操作 | 通过条件 | 当前状态 | 用户结果/备注 |
|---|---|---|---|
| 完整解压后启动/退出两次 | 无白屏/崩溃，最近项目保留 | NOT TESTED | |
| 启动页新建/打开/最近项目 | 点击正确、布局清晰 | NOT TESTED | |
| 深色/浅色/系统主题、中文/英文 | 文字与点击位置正常，重启保留 | NOT TESTED | |
| 中文路径与中文图名 | 导入/显示/重开无乱码 | NOT TESTED | |
| Copy 项目，移动外部原图后重开 | 项目内图正常 | NOT TESTED | |
| Reference 项目，移动后重新定位 | Missing Source 明确且可恢复 | NOT TESTED | |
| 图片/文件夹/PDF 拖入启动与工作区 | 预览、建项目、取消、导入均合理 | NOT TESTED | |
| 空目录/重复/坏图 | 提示明确，其他页面可访问 | NOT TESTED | |
| 普通漫画 OCR | 框、原文、阅读顺序可校对 | NOT TESTED | |
| 千页列表快速滚动/切页 | 后面页面可到达，旧异步结果不覆盖当前页 | NOT TESTED | |
| Fit、100%、50–400% Zoom、抓手 | 正常显示，平移与缩放一致 | NOT TESTED | |
| Ctrl+Tab 专注、窗口拉伸/最大化 | Canvas 可用、面板无严重裁切 | NOT TESTED | |
| 当前系统 DPI | 菜单、页列表、属性、点击位置正常 | NOT TESTED | |
| 其他 DPI/显示器 | 单独记录实际值；无环境不声明 PASS | NOT TESTED | |
| 人工译文输入与重开 | 无服务也能编辑，内容保留 | NOT TESTED | |
| 云 API 实际连接与少量翻译 | 自己的 Key/模型可用，草稿可审核 | NOT TESTED | |
| 实际 Ollama/LM Studio 模型 | 外部服务启动后可翻译，停止后报错明确 | NOT TESTED | |
| 保护人工/已审核译文 | 默认跳过，显式覆盖有确认 | NOT TESTED | |
| 暂停/取消/恢复/失败重试 | 状态与实际请求一致，无重复覆盖 | NOT TESTED | |
| 历史任务/加载更早任务 | 旧记录可访问，未凭空删除 | NOT TESTED | |
| 术语/人物编辑与 CSV | 冲突提示，重开保留，撤销有效 | NOT TESTED | |
| 擦除、回填与再次编辑 | 同一 UID 保留、原框可重复编辑 | NOT TESTED | |
| 字体选择/缺失替换/Auto Fit | 字体可用、溢出提示，预览符合成品 | NOT TESTED | |
| Quality Check | 可定位真实问题，不意外改数据 | NOT TESTED | |
| Word 导出、编辑、回导 | ID 对应、预览清晰，译文正确 | NOT TESTED | |
| Undo/Redo | 支持的编辑正确恢复，无破坏原图 | NOT TESTED | |
| 成品导出 | 页数/页序/清晰度/回填正确，无应用水印 | NOT TESTED | |
| 旧项目升级/完整备份回退 | 人工译文、样式、UID 不丢 | NOT TESTED | |
| Diagnostics/Open Log Folder | 环境信息正确、能找到日志 | NOT TESTED | |

API Key 仅在本机设置中输入，不发给开发者。错误报告写复现步骤、版本和结果；先删除日志中的私人路径、漫画文字和凭据。收费服务请先试最小范围。最后记录 PASS / FAIL / NOT TESTED；FAIL 先修复，再发布。

