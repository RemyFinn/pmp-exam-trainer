# PMP 做题系统

FastAPI + React + PostgreSQL 的 PMP 刷题系统。支持四套模拟题、混合练习、错题集、思路总结、计时、题库管理和多用户独立错题记录。

## 本地启动

推荐本地也使用 Docker PostgreSQL，保证和阿里云部署一致。

```bash
cd /Users/remy/Desktop/PMP学习/pmp-practice-system
cp .env.example .env
docker compose up -d postgres

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm run build

export $(grep -v '^#' .env | xargs)
python -m app.import_data
python scripts/import_strategies.py
python -m uvicorn app.main:app --reload --port 8000
```

浏览器访问 `http://localhost:8000`，使用 `.env` 中的 `FIRST_ADMIN_USERNAME` 和 `FIRST_ADMIN_PASSWORD` 登录。

## 从旧 SQLite 迁移

如果已有 `data/pmp.sqlite`，可以迁移到一个新的 PostgreSQL 数据库。旧作答记录和错题会归属到 `IMPORT_OWNER_USERNAME`，未设置时使用 `FIRST_ADMIN_USERNAME`。

```bash
export $(grep -v '^#' .env | xargs)
python scripts/migrate_sqlite_to_postgres.py
```

迁移完成后再运行：

```bash
python scripts/verify_api.py
```

## 阿里云 1Panel 部署

1. 在阿里云 ECS 安装 Docker 和 1Panel。
2. 在 1Panel 创建应用编排，使用本仓库的 `docker-compose.yml`。
3. 设置环境变量：
   - `POSTGRES_DB`
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
   - `SESSION_SECRET`
   - `FIRST_ADMIN_USERNAME`
   - `FIRST_ADMIN_PASSWORD`
   - `FIRST_ADMIN_DISPLAY_NAME`
   - `COOKIE_SECURE=1`
4. 给 PostgreSQL 配置持久化数据卷，定期备份 `postgres_data`。
5. 在 1Panel 网站/反向代理中绑定域名到 Web 容器的 `8000` 端口，并开启 HTTPS。
6. 部署后访问 `/api/health`，返回 `{"ok": true}` 表示服务可用。

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

## 常用命令

```bash
npm run build
.venv/bin/python -m compileall app scripts
BASE_URL=http://127.0.0.1:8000 VERIFY_USERNAME=remy VERIFY_PASSWORD=change-me-now python scripts/verify_api.py
```
