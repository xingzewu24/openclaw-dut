# 大连理工大学全能校园助手 (openclaw-dlut)

本 Skill 为 Claude Code 提供大工校园助手能力，覆盖超星学习通作业管理、教务系统、校园生活、学术工具等功能。

## 配置

- 配置文件: `config.json`（从 `config.example.json` 复制并填入凭证）
- 首次使用运行 `python scripts/setup.py` 进入交互式配置向导
- 超星学习通: `https://dut.fanya.chaoxing.com`
- 课程列表通过超星 API 自动获取
- 所有脚本位于 `scripts/` 目录
- PPT 模板位于 `templates/`
- 手写字体位于 `fonts/`（12 款）

## 执行约定

- 使用 `python` 执行脚本；macOS/Linux 若未配置 python 别名可改用 `python`
- 优先通过 `python -c "import ..."` 调用函数接口获取结构化数据
- 需要展示给用户时才直接运行 CLI 命令

---

## 功能与命令映射

当用户提到以下场景时，执行对应命令：

### 作业 & DDL

| 用户意图 | 命令 |
|---------|------|
| 查未交作业 / DDL | `python scripts/chaoxing_api.py ddls` |
| 学期DDL全景 | `python scripts/chaoxing_api.py ddls-all` |
| 列出课程 | `python scripts/chaoxing_api.py courses` |
| 查成绩 | `python scripts/chaoxing_api.py grades` |
| 查用户信息 | `python scripts/chaoxing_api.py me` |
| 查课程文件 | `python scripts/chaoxing_api.py files <course_id> [搜索词]` |
| 使用其他账号 | `python scripts/chaoxing_api.py --profile <name> <subcommand>` |

### 日历同步

| 用户意图 | 命令 |
|---------|------|
| 同步DDL到日历 | `python scripts/calendar_sync.py` |
| 导出DDL为ICS | `python scripts/dlut_timetable_ics.py ddls [输出路径]` |
| 导出课程日历 | `python scripts/dlut_timetable_ics.py calendar [输出路径]` |
| 合并导出所有 | `python scripts/dlut_timetable_ics.py all [输出路径]` |
| 查教学周 | `python scripts/dlut_timetable_ics.py week` |

- macOS: 直接同步到 Apple 日历
- Windows: 生成 ICS 文件并用默认日历打开

### 教务系统

| 用户意图 | 命令 |
|---------|------|
| 查课表 | `python scripts/dlut_jxgl.py courses` |
| 查考试安排 | `python scripts/dlut_jxgl.py exams` |
| 查期末成绩 | `python scripts/dlut_jxgl.py grades` |
| 导出考试为 ICS | `python scripts/dlut_jxgl.py exams-ics` |
| 考试同步到日历 | `python scripts/dlut_jxgl.py exams-sync` |
| 测试教务登录 | `python scripts/dlut_jxgl.py login` |

凭证从 `config.json` 自动读取（jxgl_username + jxgl_password）。通过 CAS SSO 登录，首次使用运行 `python scripts/setup.py` 配置。

### 校园信息

| 用户意图 | 命令 |
|---------|------|
| 教学周 | `python scripts/dlut_info.py week` |
| 校历 | `python scripts/dlut_info.py calendar` |
| 校区概况 | `python scripts/dlut_info.py campus` |
| 空教室 | `python scripts/dlut_classroom.py empty [--building 综一]` |
| 图书馆信息 | `python scripts/dlut_library.py info` |
| 图书馆座位 | `python scripts/dlut_library.py seats` |
| 大工新闻 | `python scripts/dlut_news.py news [n]` |
| 教务通知 | `python scripts/dlut_news.py jwc [n]` |
| 教研教改通知 | `python scripts/dlut_news.py gk [n]` |
| 所有通知 | `python scripts/dlut_news.py all` |

### 邮箱

| 用户意图 | 命令 |
|---------|------|
| 查未读 | `python scripts/dlut_mail.py unread --limit 10` |
| 搜索邮件 | `python scripts/dlut_mail.py search -k "关键词"` |
| 邮件摘要 | `python scripts/dlut_mail.py summary` |
| 发邮件(纯文本) | `python scripts/dlut_mail.py send --to xxx@dlut.edu.cn --subject "标题" --body "正文"` |
| 发邮件(HTML) | `python scripts/dlut_mail.py send --to xxx@dlut.edu.cn --subject "标题" --body "正文" --html` |

凭证从 `config.json` 自动读取（dlut_username + dlut_password）。

### PPT 生成

| 用户意图 | 命令 |
|---------|------|
| 列出模板 | `python scripts/generate_ppt.py --list-templates` |
| 生成PPT | `python scripts/generate_ppt.py --title "标题" --markdown content.md --template "模板名" --output output.pptx` |
| 关闭样式优化 | 加 `--no-polish` 参数 |

默认行为：自动清空模板示例页、按版式名匹配大工模板、优化文字样式。

### 手写 PDF

| 用户意图 | 命令 |
|---------|------|
| 从文件生成 | `python scripts/handwrite_pdf.py input.txt output.pdf --style casual` |
| 直接传文本 | `python scripts/handwrite_pdf.py output.pdf --text "内容" -s neat` |
| 加信纸横线 | 加 `--ruled` 参数 |

风格: `neat`(工整) / `casual`(随意) / `messy`(潦草)。字体目录: `fonts/`

### 课件内容提取

| 用户意图 | 命令 |
|---------|------|
| 提取文件内容 | `python scripts/file_extractor.py <文件或目录> [输出目录]` |

支持 PPT/PDF/DOCX，可批量处理目录。

### 镜像换源

| 用户意图 | 命令 |
|---------|------|
| pip换源 | `python scripts/dlut_mirror.py pip` |
| conda换源 | `python scripts/dlut_mirror.py conda` |
| brew换源 | `python scripts/dlut_mirror.py brew` |
| docker换源 | `python scripts/dlut_mirror.py docker` |
| npm换源 | `python scripts/dlut_mirror.py npm` |
| 列出镜像 | `python scripts/dlut_mirror.py list` |

### 在线工具 & 校园照片

| 用户意图 | 命令 |
|---------|------|
| 工具列表 | `python scripts/dlut_tools.py list` |
| LaTeX指引 | `python scripts/dlut_tools.py latex` |
| 论文模板指引 | `python scripts/dlut_tools.py thesis` |
| 校园照片 | `python scripts/dlut_visual.py albums` |
| 搜索照片 | `python scripts/dlut_visual.py search "关键词"` |

### 作业辅导 (高级)

| 用户意图 | 命令 |
|---------|------|
| 扫描未交作业 | `python scripts/auto_homework.py scan` |
| 紧急作业 | `python scripts/auto_homework.py urgent [hours]` |
| 生成作业上下文 | `python scripts/auto_homework.py context <course_id> <assignment_id>` |
| 完整流水线 | `python scripts/auto_homework.py full <course_id> <assignment_id>` |
| 持续监控 | `python scripts/auto_homework.py watch` |

### 助教批改

| 用户意图 | 命令 |
|---------|------|
| 查提交列表 | `python scripts/grading_assistant.py submissions <cid> <aid>` |
| 下载提交 | `python scripts/grading_assistant.py download <cid> <aid>` |
| 生成批改上下文 | `python scripts/grading_assistant.py context <cid> <aid>` |
| 打分 | `python scripts/grading_assistant.py grade <cid> <aid> <uid> <score> [comment]` |

---

## 安全规则

1. **提交作业前必须向用户确认**课程、作业和文件内容
2. **发邮件前必须向用户确认**收件人、标题和正文
3. **打分前必须向用户确认**学生、分数和评语
4. 超星 Cookie 过期时提示用户重新运行 `python scripts/chaoxing_api.py courses`
5. `config.json` 包含明文密码，不要在输出中暴露

## 依赖

```
pip3 install requests beautifulsoup4 python-pptx pdfplumber handright Pillow reportlab pycryptodome
```

Windows 用户用 `pip` 代替 `pip3`。
