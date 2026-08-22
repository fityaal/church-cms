#!/usr/bin/env python3
"""
db_init.py – Initialize and seed the All Saints' Cathedral CMS database.
Run this once after setting up MySQL:

    mysql -u root -p -e "CREATE DATABASE church_cms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    python db_init.py
"""
import sys
from datetime import date, datetime, timedelta
import random

from app import create_app
from models import (db, User, UserRole, Donation, DonationItem, DonationHead,
                    Expense, ExpenseCategory, BankAccount, BankTransaction,
                    TransactionType, Announcement, ChurchEvent, ReceiptCounter,
                    PaymentMode)
from utils.helpers import get_financial_year, generate_receipt_number, generate_voucher_number
from config import DevelopmentConfig


def init_db():
    app = create_app(DevelopmentConfig)
    with app.app_context():
        print("⚙️  Creating all tables...")
        db.create_all()
        print("✅  Tables created.")

        # ── Check if already seeded ──────────────────────────────
        if User.query.count() > 0:
            print("ℹ️   Database already has data. Skipping seed.")
            print("    To re-seed, drop the database and run again.")
            return

        print("🌱  Seeding initial data...")

        # ── Admin User ───────────────────────────────────────────
        admin = User(
            mobile='9999999999',
            full_name='Rev. Thomas George',
            email='admin@allsaintsnagpur.org',
            role=UserRole.ADMIN,
            must_change_password=False,
            is_active=True
        )
        admin.set_password('Admin@123')
        db.session.add(admin)

        # ── Treasurer ────────────────────────────────────────────
        treasurer = User(
            mobile='9888888888',
            full_name='Mr. Samuel Mathews',
            email='treasurer@allsaintsnagpur.org',
            role=UserRole.TREASURER,
            must_change_password=False,
            is_active=True
        )
        treasurer.set_password('Treasurer@123')
        db.session.add(treasurer)

        # ── Priest ───────────────────────────────────────────────
        priest = User(
            mobile='9777777777',
            full_name='Rev. Daniel Philip',
            email='priest@allsaintsnagpur.org',
            role=UserRole.PRIEST,
            must_change_password=False,
            is_active=True
        )
        priest.set_password('Priest@123')
        db.session.add(priest)

        # ── Sample Donors ────────────────────────────────────────
        donors_data = [
            ('9111111111', 'Mr. John & Mrs. Mary Abraham', 'john.abraham@gmail.com', 'Flat 5, Civil Lines, Nagpur'),
            ('9222222222', 'Mrs. Elizabeth Thomas',        'elizabeth.thomas@yahoo.com', 'Sadar, Nagpur'),
            ('9333333333', 'Mr. Peter & Mrs. Susan Paul',  'peter.paul@gmail.com', 'Dharampeth, Nagpur'),
            ('9444444444', 'Mrs. Grace Williams',          'grace.williams@gmail.com', 'Ramdaspeth, Nagpur'),
            ('9555555555', 'Mr. Joshua & Mrs. Ruth David', 'joshua.david@gmail.com', 'Sitabuldi, Nagpur'),
            ('9666666666', 'Mrs. Priya Mathew',            'priya.mathew@outlook.com', 'Pratap Nagar, Nagpur'),
            ('9000000001', 'Mr. Samuel & Mrs. Rachel John','samuel.john@gmail.com', 'Wardhaman Nagar, Nagpur'),
            ('9000000002', 'Miss. Lydia George',           'lydia.george@gmail.com', 'Manewada, Nagpur'),
        ]
        donor_users = []
        for mobile, name, email, addr in donors_data:
            u = User(mobile=mobile, full_name=name, email=email, address=addr,
                     role=UserRole.DONOR, must_change_password=True, is_active=True)
            u.set_password('Church@123')
            db.session.add(u)
            donor_users.append(u)

        db.session.flush()  # get IDs

        # ── Receipt Counter ──────────────────────────────────────
        fy = get_financial_year()
        counter = ReceiptCounter(financial_year=fy, last_receipt_no=0, last_voucher_no=0)
        db.session.add(counter)
        db.session.flush()

        # ── Sample Donations ─────────────────────────────────────
        heads_amounts = [
            {DonationHead.STEWARDSHIP: 2000, DonationHead.WORSHIP_OFFERING: 500},
            {DonationHead.DONATION: 5000},
            {DonationHead.THANKS_OFFERING: 1000, DonationHead.FESTIVAL_OFFERING: 500},
            {DonationHead.SUNDAY_SCHOOL_OFFERING: 300, DonationHead.WORSHIP_OFFERING: 500},
            {DonationHead.STEWARDSHIP: 3000, DonationHead.DONATION: 2000},
            {DonationHead.COTTAGE_PRAYER_MEETING: 200, DonationHead.WORSHIP_OFFERING: 300},
            {DonationHead.BAPTISM_CERTIFICATE_FEE: 500},
            {DonationHead.STEWARDSHIP: 5000, DonationHead.THANKS_OFFERING: 1000},
            {DonationHead.FESTIVAL_OFFERING: 2000, DonationHead.DONATION: 1000},
            {DonationHead.STEWARDSHIP: 1500, DonationHead.MARRIAGE_BANS_FEE: 200},
        ]

        today = date.today()
        pay_modes = [PaymentMode.CASH, PaymentMode.UPI, PaymentMode.CHEQUE]
        base_date = today - timedelta(days=90)

        for i, (donor, hd) in enumerate(zip(donor_users * 2, heads_amounts)):
            don_date = base_date + timedelta(days=i * 9)
            receipt_no = f"ASC/{fy}/{i+1:04d}"
            counter.last_receipt_no = i + 1

            d = Donation(
                receipt_number=receipt_no,
                user_id=donor.id,
                donation_date=don_date,
                payment_mode=pay_modes[i % len(pay_modes)],
                payment_reference=f'CHQ{1000+i}' if pay_modes[i % len(pay_modes)] == PaymentMode.CHEQUE else None,
                status='Confirmed',
                financial_year=fy,
                created_by=admin.id,
                confirmed_by=treasurer.id,
                confirmed_at=datetime.utcnow()
            )
            db.session.add(d)
            db.session.flush()

            for head, amount in hd.items():
                db.session.add(DonationItem(donation_id=d.id, head=head, amount=amount))

        # ── Sample Expenses ──────────────────────────────────────
        expenses_data = [
            (today - timedelta(days=75), ExpenseCategory.SALARY, 'Monthly salary – Church Secretary', 'Mr. James Kurien', 25000, PaymentMode.NEFT, 'NEFT001'),
            (today - timedelta(days=60), ExpenseCategory.UTILITIES, 'Electricity bill – February 2025', 'MSEDCL', 3200, PaymentMode.UPI, 'UPI202502'),
            (today - timedelta(days=45), ExpenseCategory.MAINTENANCE, 'Roof waterproofing – North wing', 'Prakash Contractors', 18000, PaymentMode.CHEQUE, 'CHQ5501'),
            (today - timedelta(days=30), ExpenseCategory.WORSHIP, 'Communion wine and bread – Q1', 'CNI Supplies', 2500, PaymentMode.CASH, None),
            (today - timedelta(days=20), ExpenseCategory.EDUCATION, 'Sunday School materials – craft supplies', 'Staples India', 1800, PaymentMode.UPI, 'UPI202503'),
            (today - timedelta(days=15), ExpenseCategory.OUTREACH, 'Food packets – monthly distribution (50 families)', 'Nagpur Food Bank', 8500, PaymentMode.NEFT, 'NEFT002'),
            (today - timedelta(days=10), ExpenseCategory.ADMINISTRATION, 'Office stationery & printing', 'Print World', 1200, PaymentMode.CASH, None),
            (today - timedelta(days=5),  ExpenseCategory.UTILITIES, 'Water bill – March 2025', 'NMC', 850, PaymentMode.CASH, None),
        ]

        for i, (exp_date, cat, desc, payee, amount, mode, ref) in enumerate(expenses_data):
            fy_exp = get_financial_year(exp_date)
            voucher = f"ASC/EXP/{fy_exp}/{i+1:04d}"
            counter.last_voucher_no = i + 1
            db.session.add(Expense(
                voucher_number=voucher, expense_date=exp_date, category=cat,
                description=desc, payee=payee, amount=amount, payment_mode=mode,
                payment_reference=ref, financial_year=fy_exp, created_by=admin.id
            ))

        # ── Bank Account ─────────────────────────────────────────
        bank = BankAccount(
            account_name='General Fund',
            bank_name='State Bank of India',
            account_number='30123456789',
            ifsc_code='SBIN0001234',
            branch='Nagpur Main Branch',
            opening_balance=125000.00,
            is_active=True
        )
        db.session.add(bank)
        db.session.flush()

        db.session.add(BankTransaction(
            account_id=bank.id,
            transaction_date=today - timedelta(days=30),
            transaction_type=TransactionType.DEPOSIT,
            amount=50000,
            reference='NEFT-BULK-001',
            description='Bulk donation deposit – Feb 2025',
            created_by=treasurer.id
        ))

        # ── Announcements ────────────────────────────────────────
        anns = [
            ('Easter Sunday Special Service', 'Join us for the Easter Sunday celebration on April 20th at 7:00 AM with a special breakfast fellowship after the service. All are welcome!', 2),
            ('Annual General Meeting', 'The AGM of All Saints\' Cathedral will be held on the first Sunday of May. All members are requested to attend.', 1),
            ('Sunday School Enrollment Open', 'Enrollment for the new Sunday School year is now open. Register your children between ages 4–14 at the church office.', 0),
            ('Choir Practice', 'Choir practice every Wednesday at 6:30 PM. New members welcome!', 0),
        ]
        for title, content, priority in anns:
            db.session.add(Announcement(
                title=title, content=content, priority=priority,
                is_active=True, created_by=admin.id
            ))

        # ── Church Events ────────────────────────────────────────
        events_data = [
            ('Easter Sunday Service', 'Special Service', datetime.now() + timedelta(days=14), 'All Saints\' Cathedral – Main Nave'),
            ('Monthly Prayer Meeting', 'Prayer Meeting', datetime.now() + timedelta(days=5), 'Cathedral Hall'),
            ('Sunday School – Monthly Quiz', 'Sunday School', datetime.now() + timedelta(days=7), 'Sunday School Block'),
            ('Youth Fellowship Meet', 'Youth Event', datetime.now() + timedelta(days=21), 'Cathedral Hall'),
        ]
        for title, etype, ev_date, loc in events_data:
            db.session.add(ChurchEvent(
                title=title, event_type=etype, event_date=ev_date,
                location=loc, is_public=True, created_by=admin.id
            ))

        db.session.commit()
        print("\n✅  Database seeded successfully!\n")
        print("=" * 55)
        print("  LOGIN CREDENTIALS")
        print("=" * 55)
        print(f"  Admin      → 9999999999  /  Admin@123")
        print(f"  Treasurer  → 9888888888  /  Treasurer@123")
        print(f"  Priest     → 9777777777  /  Priest@123")
        print(f"  Donor      → 9111111111  /  Church@123")
        print(f"  (any donor → 91xxxxx / Church@123)")
        print("=" * 55)
        print(f"\n  Run:  python run.py")
        print(f"  Open: http://localhost:5000\n")


if __name__ == '__main__':
    init_db()
