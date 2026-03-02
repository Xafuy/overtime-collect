# 存储维护组加班申报系统 — 部署说明

## 在 Windows 上运行（推荐）

1. **安装 Python**  
   从 [python.org](https://www.python.org/downloads/) 下载并安装 Python 3.9 或以上，安装时勾选 **“Add Python to PATH”**。

2. **打开项目目录**  
   在资源管理器中进入项目文件夹（如 `C:\Users\你的用户名\Code\overtimecollect`），在地址栏输入 `cmd` 回车，会在该目录打开命令提示符。

3. **一键启动（首次会创建虚拟环境并安装依赖）**  
   双击运行项目根目录下的 **`运行.bat`**，或在命令行执行：
   ```bat
   运行.bat
   ```
   按提示完成首次迁移和创建管理员后，浏览器访问：**http://127.0.0.1:8000/**  

4. **仅启动服务（已配置过时）**  
   若已执行过迁移、创建过管理员，之后只需：
   ```bat
   .venv\Scripts\activate
   python manage.py runserver 0.0.0.0:8000
   ```
   或再次双击 **`运行.bat`**。

5. **常用地址**  
   - 填报首页：http://127.0.0.1:8000/  
   - 报表：http://127.0.0.1:8000/report/  
   - 规则说明：http://127.0.0.1:8000/notice/  
   - 后台管理：http://127.0.0.1:8000/admin/  

---

## 一、本地 / 内网快速运行（Linux / macOS）

```bash
# 1. 进入项目目录
cd /path/to/overtimecollect

# 2. 使用虚拟环境（若已有 .venv）
source .venv/bin/activate   # Linux/macOS
# 或:  .venv\Scripts\activate   # Windows

# 3. 安装依赖（若无虚拟环境可先执行: python3 -m venv .venv）
pip install -r requirements.txt

# 4. 数据库迁移（首次或模型变更后）
python manage.py migrate

# 5. 创建管理员账号（首次）
python manage.py createsuperuser

# 6. 启动服务
python manage.py runserver 0.0.0.0:8000
```

浏览器访问：`http://本机IP:8000/`。填报页为首页，报表在 `/report/`，后台在 `/admin/`。

---

## 二、生产环境简要配置

### 1. 环境变量（推荐）

在服务器上设置，避免把密钥写进代码：

```bash
export DJANGO_DEBUG=0
export DJANGO_SECRET_KEY='你的随机长字符串'
export DJANGO_ALLOWED_HOSTS='your-domain.com,192.168.1.100'
```

### 2. 修改 `config/settings.py` 读取环境变量

在文件顶部或关键配置处增加：

```python
import os

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-...")  # 生产务必用环境变量
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")
```

### 3. 使用 Gunicorn 对外提供 HTTP（可选）

```bash
pip install gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

若前面有 Nginx，可让 Nginx 反代到 `127.0.0.1:8000`，并配置静态与 `proxy_pass`。

### 4. 静态文件（当前使用 CDN 可跳过）

若以后改用本地静态文件，执行一次：

```bash
python manage.py collectstatic --noinput
```

并将 Nginx 或托管把 `/static/` 指到 `staticfiles` 目录。

### 5. 自动冻结上月加班记录（可选）

每月第 5 天及之后，可将**上一个自然月**的加班记录自动设为已冻结，避免误改历史数据。

- **手动执行**（例如每月 6 号跑一次）：
  ```bash
  python manage.py freeze_previous_month_overtime
  ```
- **仅查看将要冻结条数（不写入）**：
  ```bash
  python manage.py freeze_previous_month_overtime --dry-run
  ```
- **用 cron 每日自动执行**（推荐）：在服务器上 `crontab -e` 增加一行，每天凌晨执行一次，命令中日期 ≥5 时才会冻结上月：
  ```text
  0 1 * * * cd /path/to/overtimecollect && .venv/bin/python manage.py freeze_previous_month_overtime >> /var/log/overtime-freeze.log 2>&1
  ```
  Windows 可用「任务计划程序」在每月 6 号运行上述命令。

---

## 三、备份建议

- 使用 SQLite 时，定期拷贝 `db.sqlite3` 到安全位置即可。
- 若改用 MySQL/PostgreSQL，按你方规范做数据库备份与恢复。

---

## 四、常用命令速查

| 说明           | 命令 |
|----------------|------|
| 数据库迁移     | `python manage.py migrate` |
| 创建管理员     | `python manage.py createsuperuser` |
| 收集静态文件   | `python manage.py collectstatic` |
| 检查配置与模型 | `python manage.py check` |
| 冻结上月加班（每月第 5 天后） | `python manage.py freeze_previous_month_overtime` |
