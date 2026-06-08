# PMP 做题系统

本地 Web 做题系统，导入四套 PMP 模拟题 Markdown 和 Excel 阅卷结果，使用 FastAPI + SQLite 保存题库、错题集和作答记录。

## 首次初始化

```bash
cd /Users/remy/Desktop/PMP学习/pmp-practice-system
python3 -m venv .venv
source .venv/bin/activate
python -m pip install fastapi uvicorn openpyxl pypdf pdfplumber
npm install
npm run build
python -m app.import_data
python scripts/import_strategies.py
```

Windows：

```powershell
cd C:\Users\Finn\Desktop\pmp-exam-trainer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install fastapi uvicorn openpyxl pypdf pdfplumber
npm install
npm run build
python -m app.import_data
python scripts/import_strategies.py
```

## 日常启动

```bash
cd /Users/remy/Desktop/PMP学习/pmp-practice-system
source .venv/bin/activate
npm run build
python -m uvicorn app.main:app --reload --port 8000
```

Windows：

```powershell
cd C:\Users\Finn\Desktop\pmp-exam-trainer
.\.venv\Scripts\Activate.ps1
npm run build
python -m uvicorn app.main:app --reload --port 8000
```

浏览器访问：

```text
http://localhost:8000
```

## 数据源

导入脚本默认读取：

- `/Users/remy/Desktop/PMP学习/7模拟7题目.md`
- `/Users/remy/Desktop/PMP学习/8模拟8题目.md`
- `/Users/remy/Desktop/PMP学习/9模拟9题目.md`
- `/Users/remy/Desktop/PMP学习/10模拟10题目.md`
- `/Users/remy/Desktop/PMP学习/PMP模拟七_阅卷结果.xlsx`
- `/Users/remy/Desktop/PMP学习/PMP模拟八_阅卷结果.xlsx`
- `/Users/remy/Desktop/PMP学习/PMP模拟九_阅卷结果.xlsx`
- `/Users/remy/Desktop/PMP学习/PMP模拟十_阅卷结果.xlsx`

思路总结导入脚本默认读取：

- `/Users/remy/Library/Mobile Documents/com~apple~CloudDocs/Book/PMP/PMP模拟七主要解题思路总结.pdf`
- `/Users/remy/Library/Mobile Documents/com~apple~CloudDocs/Book/PMP/PMP模拟八主要解题思路总结.pdf`
- `/Users/remy/Library/Mobile Documents/com~apple~CloudDocs/Book/PMP/模拟九-模拟十题目分类.pdf`

SQLite 数据库位于 `data/pmp.sqlite`。
