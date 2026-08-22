# All Saints' Cathedral, Nagpur — Church Management System
### Diocese of Nagpur (C.N.I.) | Flask + MySQL + Razorpay

---

## 📋 Overview

A **full-featured Church Management System** built with Python Flask and MySQL, tailored for All Saints' Cathedral, Nagpur. The system covers:

| Module | Features |
|--------|----------|
| 🧾 Donations | 11-head receipt system matching printed format, sequential numbering, PDF generation |
| 💳 Online Giving | Razorpay integration (UPI, Cards, Net Banking, Wallets) with instant digital receipts |
| 📊 Analytics | Real-time dashboards with Chart.js — income vs expense, head-wise, monthly trends |
| 👥 Donor Portal | Login via mobile, view history, download receipts, annual statement |
| 📋 Expenses | Category-wise expenditure tracking with voucher numbering |
| 🏦 Bank Accounts | Multi-account tracking with deposit/withdrawal ledger |
| 📄 Reports | Financial summary, monthly trend, top donors, head-wise analysis |
| 📅 Events | Church events calendar visible to all members |
| 🙏 Prayer Wall | Submit and view congregation prayer requests |
| 🛡️ Audit Log | Every action logged with user, timestamp, and IP |

---

## 🔐 Role-Based Access

| Role | Access |
|------|--------|
| **Admin** | Full access — all modules, user management, audit log, delete |
| **Treasurer** | Finance + donations + expenses + reports + donor management |
| **Priest** | Events + announcements + prayer requests + view reports |
| **Donor** | Own receipts + annual statement + church expenses (read-only) + events |

---

## ⚙️ Installation

### 1. Prerequisites

```bash
# Python 3.9+
python --version

# MySQL 5.7+ or 8.0+
mysql --version
```

### 2. Create MySQL Database

```sql
CREATE DATABASE church_cms 
  CHARACTER SET utf8mb4 
  COLLATE utf8mb4_unicode_ci;

CREATE USER 'church_user'@'localhost' IDENTIFIED BY 'YourPassword123';
GRANT ALL PRIVILEGES ON church_cms.* TO 'church_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Clone & Setup

```bash
# Navigate to project folder
cd church_cms

# Create virtual environment
python -m venv venv
source venv/bin/activate    # Linux/Mac
venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment

Create a `.env` file in the project root:

```env
# Database
MYSQL_HOST=localhost
MYSQL_USER=church_user
MYSQL_PASSWORD=YourPassword123
MYSQL_DB=church_cms

# Security
SECRET_KEY=your-very-long-random-secret-key-here-minimum-32-chars

# Razorpay (get from https://dashboard.razorpay.com)
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxx

# Email (for OTP/notifications — optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Production
FLASK_ENV=development
```

Or update `config.py` directly with your values.

### 5. Initialize Database & Seed

```bash
python db_init.py
```

This creates all tables and seeds:
- Admin, Treasurer, Priest accounts
- 8 sample donors
- 10 sample donation receipts
- 8 sample expenses
- Bank account with transaction
- 4 announcements and events

### 6. Run the Application

```bash
python run.py
```

Open: **http://localhost:5000**

---

## 🔑 Default Login Credentials

| Role | Mobile | Password |
|------|--------|----------|
| Admin | 9999999999 | Admin@123 |
| Treasurer | 9888888888 | Treasurer@123 |
| Priest | 9777777777 | Priest@123 |
| Sample Donor | 9111111111 | Church@123 |

> ⚠️ **Change all passwords immediately after first login in production.**

---

## 💳 Razorpay Setup

1. Sign up at [razorpay.com](https://razorpay.com)
2. Go to **Settings → API Keys** → Generate Key
3. Update `.env` with your `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`
4. For testing, use `rzp_test_...` keys
5. For production, use `rzp_live_...` keys and complete KYC

---

## 📁 Project Structure

```
church_cms/
├── run.py                  # Entry point
├── app.py                  # Flask app factory
├── config.py               # Configuration
├── models.py               # Database models (SQLAlchemy)
├── db_init.py              # DB initializer + seeder
├── requirements.txt
├── blueprints/
│   ├── auth.py             # Login, logout, password reset
│   ├── admin.py            # Admin & staff routes
│   ├── donor.py            # Donor portal routes
│   ├── payment.py          # Razorpay payment flow
│   ├── api.py              # JSON API for charts
│   └── errors.py           # 404/403/500 handlers
├── utils/
│   ├── helpers.py          # Receipt numbering, amount-in-words, audit log
│   └── pdf_generator.py    # ReportLab PDF receipt (A5 format)
├── templates/
│   ├── base.html           # Sidebar layout with nav
│   ├── auth/               # Login, change password, forgot password
│   ├── admin/              # Dashboard, donations, expenses, reports, donors...
│   ├── donor/              # Donor portal templates
│   └── errors/             # 404, 403, 500 pages
└── static/
    ├── css/
    ├── js/
    └── uploads/
```

---

## 🧾 Receipt Numbering Format

```
ASC / 2024-25 / 0001
└─┘   └──────┘   └──┘
Cathedral  F.Year  Seq No (4-digit, resets each year)

Voucher: ASC/EXP/2024-25/0001
```

---

## 📊 Database Tables

| Table | Purpose |
|-------|---------|
| `users` | All users (admin, staff, donors) |
| `donations` | Donation receipts |
| `donation_items` | Head-wise breakdown per receipt |
| `expenses` | Expenditure records |
| `bank_accounts` | Church bank accounts |
| `bank_transactions` | Deposits & withdrawals |
| `church_events` | Events calendar |
| `prayer_requests` | Member prayer requests |
| `announcements` | Church notices |
| `receipt_counters` | Sequential numbering by F.Y. |
| `audit_logs` | Full activity trail |

---

## 🚀 Production Deployment (Ubuntu + Gunicorn + Nginx)

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "run:app"

# Nginx config (sites-available/church_cms)
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# SSL with Certbot
sudo certbot --nginx -d your-domain.com
```

---

## 🪟 Windows One-Click Installer (.exe)

You can generate a distributable Windows app and installer:

### 1) Build standalone app EXE

```powershell
python -m pip install pyinstaller waitress
powershell -ExecutionPolicy Bypass -File .\build_windows_exe.ps1
```

Output:
- `dist\ChurchCMS.exe`

### 2) Build installer EXE (optional but recommended)

1. Install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Download MySQL offline zip and place at:
   - `installer\assets\mysql\mysql-8.0.41-winx64.zip`
3. Open `installer\ChurchCMS.iss`
4. Click **Build** in Inno Setup

Output:
- `dist\ChurchCMSInstaller.exe`

### Notes

- Installer includes the web app runtime and starts app on `http://127.0.0.1:5000`.
- Installer configures offline MySQL service (`MySQL80`) and creates `church_cms` using current app defaults.
- Installer registers `ChurchCMS_AutoStart` scheduled task (run at logon).
- Uploaded files are stored in `%APPDATA%\ChurchCMS\uploads`.

---

## 📱 Mobile Responsive

The portal is fully responsive. Donors can:
- Login via mobile browser
- View receipts on phone
- Download PDF receipts
- Pay online via UPI/PhonePe/GPay through Razorpay

---

## 🛡️ Security Features

- Bcrypt password hashing (Werkzeug)
- CSRF protection via Flask sessions
- Role-based route guards
- Complete audit log (user + IP + action + timestamp)
- OTP-based password reset
- Account deactivation without deletion

---

## 📞 Support

For technical support or customisation:
- System developed for: **All Saints' Cathedral, Nagpur**
- Diocese of Nagpur (C.N.I.)
- Contact church office: +91-712-2520000

---

*Built with ❤️ for All Saints' Cathedral, Nagpur — Serving the community since 1865*
