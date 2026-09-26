# Links Manga Studio v0.5.0：新手手动 GitHub 发布指南

作者：Links Tam。材料准备日期：2026-09-26。GitHub **NOT PUBLISHED**，Remote **NOT CONFIGURED / USER CONTROLLED**，Release **NOT CREATED**。本文命令由你本人执行；准备材料期间没有执行连接远程、提交、打标签或上传。

## 0. 当前已确认的许可与发布前检查

本项目源码、文档和原创资产正式采用 **Apache-2.0**；LICENSE 为官方完整正文，NOTICE 保留作者及第三方署名。无需再选择主许可证。三个 OCR 权重的确切 SHA256 已核对 RapidOCR 上游模型许可清单，确认 Apache-2.0 再分发；详见 MODEL_LICENSES.md。PyMuPDF 已移除，正式 PDF 后端仍是 PDFium。

公开前复核 LICENSE、NOTICE 与第三方文件齐全；运行可见 Windows 人工验收，逐项完成 GITHUB_RELEASE_CHECKLIST.md。所有 GitHub 公开操作由你本人执行。

## 1. 安装 Git、准备身份

打开 Windows PowerShell，运行 `git --version`。若提示找不到命令，从 [Git for Windows](https://gitforwindows.org/) 安装，关闭并重新打开终端。

Git 提交会公开作者姓名和邮箱。使用 `Links Tam`；在 GitHub Settings → Emails 查找你的 GitHub 提供的 noreply 邮箱，不要把私人邮箱、Token 或密码写进仓库。

## 2. 为本项目建立正确的本地边界

当前应用目录属于一个更大的父级 Git 仓库；父仓库目前没有提交，也没有远程。**不要在该父目录执行 `git add .`。不要删除父级 `.git`。** 推荐把审核过的文件复制到父仓库之外的独立目录。

以下命令只复制 Git 判定为非忽略的应用文件，不复制 dist、build、虚拟环境或项目数据。路径采用环境变量，避免把开发者个人路径写入公开文档。

```powershell
$source = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'ChatGPT\漫画翻译\links_manga_workspace'
# 如果你的应用不在此位置，只修改上一行 source。
$destination = Join-Path $env:USERPROFILE 'Projects\links-manga-studio'
if (Test-Path -LiteralPath $destination) { throw '目标目录已经存在，请选择一个新的空目录，避免混入旧文件。' }
if (-not (Test-Path -LiteralPath (Join-Path $source 'pyproject.toml'))) { throw 'source 不是应用目录。' }
$parent = Split-Path $source -Parent
$candidates = @(git -C $parent ls-files --cached --others --exclude-standard -- links_manga_workspace)
if ($LASTEXITCODE -ne 0 -or $candidates.Count -eq 0) { throw '无法取得待公开文件列表。' }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($candidate in $candidates) {
    $relative = $candidate.Substring('links_manga_workspace/'.Length)
    $original = Join-Path $source $relative
    $copy = Join-Path $destination $relative
    New-Item -ItemType Directory -Path (Split-Path $copy -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $original -Destination $copy
}
Set-Location -LiteralPath $destination
```

在新目录确认 `git rev-parse --show-toplevel`：预期此时提示不是 Git 仓库；如果它显示某个父目录，停止并改选该仓库之外的位置。

**仅对这个没有 Git 的独立副本**运行：

```powershell
git init -b main
git config user.name 'Links Tam'
$commitEmail = Read-Host '粘贴 GitHub Settings / Emails 中你的 noreply 邮箱'
git config user.email $commitEmail
```

如果以后已经建立独立仓库，不再执行 init 或重新复制，直接在其目录继续工作。不要机械地对现有仓库重新初始化。

## 3. 复核将上传的文件，然后创建本地提交

独立副本已经包含正式 Apache-2.0 LICENSE 和 NOTICE。查看 `.gitignore`；不要忽略审核后强行加入模型或大文件。

```powershell
git status --short
git ls-files --others --exclude-standard
git add .
git status --short
git diff --cached --stat
git diff --cached --check
git ls-files
```

`git add`仅将文件放入待提交区，不会上传。`git ls-files`显示实际将被 Git 跟踪的内容。应看到 app、assets、docs、tests、tools、.github 和根目录文档；不能看到 dist、build、.venv、dev_data、真实漫画、模型权重、字体、日志、SQLite、配置、`.lmw` 或私人文件。

若第一次提交前误加入文件，用 `git rm --cached -- '文件名'` 移出待提交区（保留磁盘文件），修正 `.gitignore` 后再检查。目录用 `git rm -r --cached -- '目录名'`。若密钥已公开，先撤销密钥；不要认为删除当前文件就清除了历史，不要自行 force push。

在副本中按 README 安装依赖并运行测试，检查截图和文档后提交：

```powershell
git commit -m 'Initial public release: Links Manga Studio v0.5.0'
git log -1 --format=fuller
git status
```

检查提交作者和邮箱。提交成功并且工作区干净后再连接远程。遇到错误时先阅读提示，不要使用 `--force` 或绕过检查。

## 4. 在浏览器创建 GitHub 仓库

1. 登录自己的 GitHub 账户。
2. 右上角 **+ → New repository**。
3. Owner 选自己的账户；Repository name 建议 `links-manga-studio`。
4. Description：`Local-first manga OCR, translation, cleaning and typesetting studio for Windows.`
5. Visibility 选择 **Public**，这意味着任何人都能看到提交内容。
6. 不自动创建 README，不选择在线 .gitignore；本地已经有这些文件。
7. 不在线选择 License；使用本地完整 Apache-2.0 LICENSE，避免在线产生重复文件。
8. 点击 **Create repository**，复制页面显示的 HTTPS 仓库 URL。

## 5. 第一次 Push（仅由你执行）

在独立副本目录执行。URL 应类似 `https://github.com/你的账户/links-manga-studio.git`。

```powershell
git remote -v
$repositoryUrl = Read-Host '粘贴刚创建的仓库 HTTPS URL'
git remote add origin $repositoryUrl
git remote -v
git push -u origin main
```

若 origin 已存在，不重复 add；检查是否确为你的目标仓库，确认后才调整。Git 可能打开浏览器进行身份认证。不要用 GitHub 登录密码当 HTTPS Git 密码，不要把 Token 写在 URL、代码或截图里。若被拒绝是因为远程不为空，不要 force push；先检查是否误建了在线 README、推错仓库或分支。

## 6. 仓库 About、社区和 Actions

仓库主页右侧 About 的齿轮中填写 Description（同上）；Website 可以留空。Topics：`manga`、`ocr`、`translation`、`typesetting`、`localization`、`pyside6`、`python`、`windows`、`desktop-app`、`comic`。

由你检查 Settings → General 的 Issues 开关；Discussions 可选。Security / Settings 中按 SECURITY.md 开启私密漏洞报告并提供行为准则的私密联系方式。在 Actions 页面确认 Windows Python 3.11/3.12 核心测试运行；如账户策略阻止 Actions，由你审核并设置。本地通过不能预先保证 GitHub runner 通过。

上传品牌图：仓库主页 About → 齿轮 → 填 Description/Topics，Website 留空 → Save。然后 Settings → General → Social Preview 上传 `docs/images/github-social-preview.png`（1280 × 640），检查 README Hero。Topics 可额外加入 `rapidocr`。

Settings → General 建议 Issues On，Projects 可选，Wiki 可选或关闭，Discussions 首发可选。Private vulnerability reporting 在 Settings → Security 或 Security → Reporting 的相近入口开启；按实际 GitHub 界面操作。Push 后打开 Actions 等待两个 Windows 测试任务；失败时查看日志并修复。通过后可从 workflow 菜单复制 status badge 到 README，账户未知时不预先编造 badge。

## 7. 创建 Release

1. 仓库主页 → **Releases → Draft a new release**。
2. **Choose a tag** 输入 `v0.5.0`，选择 **Create new tag**；Target 选 `main` 的已检查提交。网页发布时会创建该标签，无需再手动创建同名本地标签。
3. Title：`Links Manga Studio v0.5.0 — Initial Public Release`。
4. Description 复制根目录 RELEASE_NOTES.md；中文可从 RELEASE_NOTES.zh-CN.md复制。本地许可已确认；根据实际发布时间更新候选版表述，不要提前声称已上线。
5. 上传 `Links-Manga-Studio-0.5.0-windows-x64.zip` 和 `Links-Manga-Studio-0.5.0-windows-x64.zip.sha256` 两个文件。它们在原应用的 dist 目录，不在源码副本内。
6. 不上传整个 dist 文件夹、.venv、build、dev_data 或源项目数据。GitHub 自动附带的 Source code ZIP 不是 Windows 程序包。
7. 如果希望明确说明早期版本，勾选 **Set as a pre-release**；认为已适合普通用户则不勾，由你决定。
8. 先 **Save draft** 并复核附件、版本与许可，再由你 **Publish release**。

### 校验 SHA256

下载两个附件到同一目录，进入该目录：

```powershell
$zip = 'Links-Manga-Studio-0.5.0-windows-x64.zip'
$actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
$expected = ((Get-Content -LiteralPath ($zip + '.sha256') -Raw).Trim() -split '\s+')[0]
if ($actual -ne $expected) { throw 'SHA256 不一致，请勿使用，重新下载并检查。' }
'SHA256 PASS'
```

当前候选包哈希见 PUBLICATION_AUDIT.md。若你改变打包内容，重新计算并更新 `.sha256`，不能沿用旧值。

## 8. 发布后检查

用退出登录的浏览器查看：README、中文链接、截图、许可证、下载是否可见；Actions 是否绿色；Issues 是否可用；Release 两个附件能否下载。将 ZIP 解压到新目录，确认首次 Recent Projects 为空，按用户验收清单操作。保留 SHA256 和本地候选包。没有签名的程序可能提示信誉警告；只验证自己的产物，不建议用户关闭系统防护。

## 9. 下一版本：简单流程

在独立仓库修改代码和版本号 → 测试 → `git add .` → `git diff --cached` → `git commit -m 'Prepare v0.5.1'` → `git push` → 重新构建 ZIP 和 SHA256 → 网页创建 `v0.5.1` 标签与新 Release。不要移动已公开的 v0.5.0 标签，不覆盖旧版本附件。

## 10. GitHub Desktop 可选

也可在完成独立副本和本地提交后安装 GitHub Desktop，登录 → File → Add local repository，选择独立副本；检查 Changes 和 History，再使用 Publish repository（取消 Keep this code private 才公开）。**不要同时再创建另一个同名空仓库**；如果已经按网页流程创建仓库，用标准命令行流程或在 Desktop 配置并检查该远程。Release 附件仍在网页上传。

## 官方操作参考

- [创建仓库](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [将本地代码加入 GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
- [创建 Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)

这些链接于准备日期核查；GitHub 页面文字以后可能变化。所有公开操作由 Links Tam 本人完成。
