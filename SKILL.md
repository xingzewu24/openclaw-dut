---
name: dlut-campus
version: 2.0.0
license: MIT
description: |
  大连理工大学全能校园助手。覆盖超星学习通作业管理、教务系统、校园生活、学术工具等功能。
  触发场景:
  (1) 查看/追踪作业DDL、提交状态、成绩
  (2) 下载课件、AI总结、作业辅导
  (3) 同步DDL到日历
  (4) 查看大工邮箱未读、搜索、发邮件
  (5) 查教学周、校历、校区概况
  (6) 查图书馆、空教室
  (7) 镜像换源
  (8) 大工新闻、教务通知、教研教改通知
  (9) 生成大工PPT
  (10) 提交作业、助教批改
  (11) 查教务系统课表、考试安排、期末成绩
  (12) 手写PDF生成
  (13) 课件内容提取
  触发词: 超星, 学习通, 课程, 作业, DDL, 截止, 成绩, 课件, PPT, 总结, 复习, 提交作业, 讨论区, 批改, 图书馆, 教室, 空教室, 教学周, 第几周, 校历, 放假, 邮箱, 邮件, 镜像, pip, conda, 换源, 新闻, 教务, 通知, 教研, 教改, PPT模板, 手写, 课表, 课程表, 考试, 考试安排, 期末成绩, 绩点, GPA, 选课, LaTeX, 论文模板, 校区, 手写PDF, 信纸, 课件提取
---

# 大连理工大学全能校园助手

## 配置

- 配置文件: `config.json`（从 `config.example.json` 复制并填入凭证）
- 首次使用运行 `python scripts/setup.py` 进入交互式配置向导
- 超星学习通: `https://dut.fanya.chaoxing.com`
- 当前用户的课程列表通过超星 API 自动获取
- 所有脚本位于 `scripts/` 目录，用 `python` 执行。macOS/Linux 若未配置 python 别名可改用 `python3`
- PPT 模板位于 `templates/`
- 手写字体位于 `fonts/`（12 款中文字体）

---

## 刚需功能（每周都用）

### 1. DDL 追踪

**触发**: "我有什么作业"、"DDL"、"截止"、"未交作业"

```bash
python scripts/chaoxing_api.py ddls                      # 查未交作业（按截止时间分三类）
python scripts/chaoxing_api.py ddls-all                  # 学期全景报告
```

未交作业按时间分类：
- **⏳ 未截止待交**：含 🆕 未开始（显示开始时间）和待交（显示剩余时间）
- **❌ 已截止未交**：标注过期时长
- **❓ 无截止时间**：超星没暴露任何时间信息

每条作业返回 `due_at`（ISO 截止时间）、`start_at`（开始时间）、`status_text`（超星原始状态）。

### 2. DDL → 日历

**触发**: "同步日历"、"导出DDL"、"导入日历"

```bash
python scripts/dlut_timetable_ics.py ddls ~/Desktop/ddls.ics   # 导出DDL为ICS
python scripts/dlut_timetable_ics.py calendar ~/Desktop/cal.ics # 导出课程日历
python scripts/dlut_timetable_ics.py all ~/Desktop/all.ics      # 合并导出所有事件
python scripts/calendar_sync.py                                 # 直接同步到系统日历
```

macOS: 直接同步到 Apple 日历; Windows: 生成 ICS 文件并用默认日历打开。

### 3. 教学周 / 校历 / 校区

**触发**: "今天第几周"、"教学周"、"校历"、"什么时候放假"、"校区"

```bash
python scripts/dlut_info.py week         # 当前第几周
python scripts/dlut_info.py calendar     # 完整学期校历
python scripts/dlut_info.py campus       # 各校区概况
```

### 4. 教务通知

**触发**: "教务通知"、"教务处"、"选课通知"、"考试安排"、"教研教改"

```bash
python scripts/dlut_news.py jwc 10       # 教务处通知
python scripts/dlut_news.py gk 10        # 教研教改通知
python scripts/dlut_news.py news 10      # 大工新闻网
python scripts/dlut_news.py all          # 全部获取
```

### 5. 教务系统（课表/考试/成绩）

**触发**: "课表"、"考试安排"、"期末成绩"、"绩点"、"GPA"

```bash
python scripts/dlut_jxgl.py login       # 测试教务登录
python scripts/dlut_jxgl.py courses     # 查当前学期课表
python scripts/dlut_jxgl.py exams       # 查考试安排
python scripts/dlut_jxgl.py grades      # 查所有学期成绩
python scripts/dlut_jxgl.py exams-ics   # 导出考试为 ICS
python scripts/dlut_jxgl.py exams-sync  # 考试同步到日历
```

凭证从 `config.json` 自动读取（jxgl_username + jxgl_password）。通过 CAS SSO 登录 `jxgl.dlut.edu.cn`，首次使用运行 `python scripts/setup.py` 配置。

---

## 高频功能（每月多次）

### 6. 大工邮箱

**触发**: "邮箱"、"邮件"、"未读"、"发邮件"

```bash
python scripts/dlut_mail.py unread --limit 10
python scripts/dlut_mail.py search -k "作业"
python scripts/dlut_mail.py summary
python scripts/dlut_mail.py send --to someone@dlut.edu.cn --subject "标题" --body "正文"
python scripts/dlut_mail.py send --to someone@dlut.edu.cn --subject "标题" --body "正文" --html  # HTML格式
```

凭证从 `config.json` 自动读取（dlut_username + dlut_password）。

### 7. 大工新闻

**触发**: "大工新闻"、"学校新闻"

```bash
python scripts/dlut_news.py news 10     # 新闻（默认10条）
python scripts/dlut_news.py all         # 全部
```

---

## 实用功能（需要时用）

### 8. 图书馆

**触发**: "图书馆"、"开馆时间"、"座位"

```bash
python scripts/dlut_library.py info     # 各图书馆基本信息
python scripts/dlut_library.py seats    # 座位预约信息
```

### 9. 空教室

**触发**: "空教室"、"哪里有教室"、"自习"

```bash
python scripts/dlut_classroom.py empty
python scripts/dlut_classroom.py empty --building 综一
```

### 10. 大工 PPT

**触发**: "做PPT"、"PPT模板"、"生成PPT"

```bash
python scripts/generate_ppt.py --list-templates
python scripts/generate_ppt.py \
  --title "标题" \
  --markdown content.md \
  --template "大连理工大学通用PPT模板.pptx" \
  --output output.pptx
python scripts/generate_ppt.py --title "标题" --markdown content.md --template "模板" --no-polish  # 关闭样式优化
```

模板目录: `templates/`

默认行为：
- 自动清空模板自带示例页
- 优先按版式名称匹配大工模板
- 自动把标题和正文放进正确的模板区域
- 默认执行文字样式优化（大工蓝色主题）

### 11. 手写 PDF 生成

**触发**: "手写PDF"、"手写"、"信纸"

```bash
python scripts/handwrite_pdf.py input.txt output.pdf --style casual  # 从文件
python scripts/handwrite_pdf.py output.pdf --text "要手写的内容" -s neat  # 直接传文本
python scripts/handwrite_pdf.py input.txt output.pdf --style messy --ruled  # 添加信纸横线
```

风格: `neat`(工整) / `casual`(随意) / `messy`(潦草)

字体目录: `fonts/`（12 款中文字体）

### 12. 课件内容提取

**触发**: "提取课件"、"课件内容"、"提取PDF/PPT"

```bash
python scripts/file_extractor.py <文件或目录> [输出目录]
```

支持 PPT/PDF/DOCX 文件，可批量处理目录。

---

## 工具功能

### 13. 镜像换源

**触发**: "换源"、"pip源"、"镜像"

```bash
python scripts/dlut_mirror.py pip       # pip 换源
python scripts/dlut_mirror.py conda     # conda 换源
python scripts/dlut_mirror.py brew      # Homebrew 换源（仅 macOS/Linux）
python scripts/dlut_mirror.py docker    # Docker CE 换源
python scripts/dlut_mirror.py npm       # npm 换源
python scripts/dlut_mirror.py list      # 列出所有可用镜像
```

### 14. 在线工具

**触发**: "LaTeX"、"在线工具"、"论文模板"

```bash
python scripts/dlut_tools.py list       # 列出所有可用工具
python scripts/dlut_tools.py latex      # LaTeX 编辑器指引
python scripts/dlut_tools.py thesis     # 学位论文模板指引
```

### 15. 校园照片

**触发**: "校园照片"、"校园风景"

```bash
python scripts/dlut_visual.py albums
python scripts/dlut_visual.py search "图书馆"
```

---

## 超星学习通高级功能

### 课程 & 课件

```bash
python scripts/chaoxing_api.py courses                  # 列出课程
python scripts/chaoxing_api.py files <course_id>        # 查看课程文件
python scripts/chaoxing_api.py files <course_id> 搜索词  # 搜索课程文件
python scripts/chaoxing_api.py grades                   # 查成绩
python scripts/chaoxing_api.py me                       # 查用户信息
python scripts/chaoxing_api.py --profile teacher ddls   # 使用不同账号配置
```

### 提交作业

**提交前必须向用户确认课程、作业和文件**

```python
from scripts.chaoxing_api import submit_assignment
submit_assignment(course_id, assignment_id, [file_paths])
```

### 全自动作业流水线

**触发**: "自动作业"、"紧急作业"、"作业巡检"

```bash
python scripts/auto_homework.py scan                            # 扫描所有未交作业
python scripts/auto_homework.py urgent 24                       # 24小时内到期的紧急作业
python scripts/auto_homework.py context <course_id> <assignment_id>  # 生成作业上下文
python scripts/auto_homework.py full <course_id> <assignment_id>     # 完整流水线
python scripts/auto_homework.py watch                           # 持续监控模式
```

### 助教批改

**打分前必须向用户确认学生、分数和评语**

```bash
python scripts/grading_assistant.py submissions <course_id> <assignment_id>       # 查看提交列表
python scripts/grading_assistant.py download <course_id> <assignment_id>          # 下载所有提交
python scripts/grading_assistant.py context <course_id> <assignment_id>           # 生成批改上下文
python scripts/grading_assistant.py grade <course_id> <assignment_id> <user_id> <score> [comment]  # 打分
```

---

## 依赖

```bash
pip3 install requests beautifulsoup4 python-pptx pdfplumber handright Pillow reportlab pycryptodome
# Windows: pip install requests beautifulsoup4 python-pptx pdfplumber handright Pillow reportlab pycryptodome
```

## 注意事项

1. **提交作业** 前必须向用户确认
2. **发邮件** 前必须向用户确认
3. **打分** 前必须向用户确认
4. 超星 Cookie 过期时需重新运行 `python scripts/chaoxing_api.py courses` 触发重新登录
5. `config.json` 包含明文密码，不要在输出中暴露
6. 日历同步在 macOS 上直接写入 Apple 日历，Windows 上生成 ICS 文件并用默认日历打开
7. 教室等部分数据为硬编码，如有变动需更新脚本
