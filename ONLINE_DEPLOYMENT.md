# All Saints' Cathedral CMS — Free Online Deployment

## Architecture
- Flask application: Render Free Web Service
- Database: Aiven Free MySQL
- Payments: Razorpay (test or live credentials supplied separately)
- HTTPS: Render managed TLS

## 1. Create the Aiven MySQL service
1. Create an Aiven account. The current Aiven Free MySQL plan is $0/month, has no expiry, requires no credit card, and provides 1 GB storage/RAM on one node. It is intended for small workloads.
2. Create **MySQL** service on the **Free** plan.
3. Open the service and note: host, port, username, password and database name.
4. Download the CA certificate from the Aiven service Overview page if you want certificate verification.

## 2. Prepare the database
On the Windows PC containing this package, set the Aiven variables in Command Prompt, then run:

    python db_init_production.py
    python create_admin.py

This creates the schema and expenditure heads, then creates the first administrator. It does not insert the sample donations/expenses from the original development seeder.

## 3. GitHub
Create a **private** repository, e.g. `church-cms`. Copy this package into the repository root. Do not commit `.env`, passwords, CA keys, or a database dump.

    git init
    git add .
    git commit -m "Production deployment package"
    git branch -M main
    git remote add origin https://github.com/YOUR-USER/church-cms.git
    git push -u origin main

## 4. Render
Create **New > Web Service**, connect the private GitHub repository, and use:
- Runtime: Python 3
- Branch: main
- Build: `pip install -r requirements.txt`
- Start: `gunicorn --workers 2 --threads 2 --timeout 120 --bind 0.0.0.0:$PORT run:app`
- Plan: Free
- Health check: `/health`

## 5. Render environment variables
Set:
- `PYTHON_VERSION=3.13.4`
- `FLASK_ENV=production`
- `SECRET_KEY` = a long random secret
- `MYSQL_HOST` = Aiven host
- `MYSQL_PORT` = Aiven port
- `MYSQL_USER` = Aiven username
- `MYSQL_PASSWORD` = Aiven password
- `MYSQL_DB` = Aiven database name (usually `defaultdb`)
- `MYSQL_SSL=true`
- `MYSQL_SSL_VERIFY=false` for the first deployment; after testing, use the Aiven CA and set verification to true
- `MYSQL_SSL_CA_PEM` = contents of the downloaded Aiven CA certificate when verification is enabled
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` = leave blank or use test keys until payment testing is complete
- `MAIL_USERNAME` / `MAIL_PASSWORD` = optional; do not put them in GitHub

## 6. First login
Use the administrator account created by `create_admin.py`. Do not use the old development credentials.

## 7. Custom domain
Render Free supports custom domains and managed TLS. In Render: Service > Settings > Custom Domains > Add Custom Domain. Render will show the DNS record(s) required. Add those records at your domain registrar.

## Important free-tier limitations
- Render Free web services spin down after 15 minutes idle and may take about a minute to wake.
- Render Free web services have ephemeral local storage. This package therefore does not rely on local SQLite or permanent uploaded files for financial records; receipt PDFs are generated in memory.
- Aiven Free MySQL is 1 GB and single-node and may power off an unused service; it is not intended for high-traffic production. Keep independent backups.
- SMTP ports 25/465/587 are blocked from Render Free web services, so outbound email from Flask-Mail will not work from Render Free. OTP reset in the current application is still development-style and should be replaced with an email/SMS provider or another secure reset workflow before relying on it for production.

## Backups
Regularly export the Aiven MySQL database and keep at least one offline copy.
