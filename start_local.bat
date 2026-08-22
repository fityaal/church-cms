@echo off
setlocal
set FLASK_ENV=development
set SECRET_KEY=local-development-only-change-me
set MYSQL_HOST=127.0.0.1
set MYSQL_PORT=3306
set MYSQL_USER=root
set MYSQL_PASSWORD=
set MYSQL_DB=church_cms
set SEED_DEFAULTS=true
python run.py
