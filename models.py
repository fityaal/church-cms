from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import enum

db = SQLAlchemy()

# ══════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════
class UserRole(enum.Enum):
    ADMIN                = 'Admin'
    TREASURER            = 'Treasurer'
    PRIEST               = 'Priest'
    PRESBYTER_IN_CHARGE  = 'Presbyter In Charge'
    ASSOCIATE_PASTOR     = 'Associate Pastor'
    SECRETARY            = 'Secretary'
    OFFICE_ASSISTANT     = 'Office Assistant'
    DONOR                = 'Donor'

class DonationHead(enum.Enum):
    STEWARDSHIP              = 'Stewardship'
    DONATION                 = 'Donation'
    WORSHIP_OFFERING         = 'Worship Offering'
    THANKS_OFFERING          = 'Thanks Offering'
    SUNDAY_SCHOOL_OFFERING   = 'Sunday School Offering'
    COTTAGE_PRAYER_MEETING   = 'Cottage Prayer Meeting Offering'
    MARRIAGE_BANS_FEE        = 'Marriage Bans Fee'
    BAPTISM_CERTIFICATE_FEE  = 'Baptism Certificate Fee'
    FESTIVAL_OFFERING        = 'Festival Offering'
    SALE_AUCTION             = 'Sale / Auction'
    OTHER                    = 'Other'

class PaymentMode(enum.Enum):
    CASH   = 'Cash'
    CHEQUE = 'Cheque'
    UPI    = 'UPI'
    ONLINE = 'Online'
    NEFT   = 'NEFT/RTGS'

class ExpenseCategory(enum.Enum):
    SALARY         = 'Salary & Staff'
    MAINTENANCE    = 'Building Maintenance'
    UTILITIES      = 'Utilities & Bills'
    WORSHIP        = 'Worship & Sacraments'
    OUTREACH       = 'Outreach & Mission'
    EDUCATION      = 'Education & Sunday School'
    ADMINISTRATION = 'Administration'
    CHARITY        = 'Charity & Welfare'
    CAPITAL        = 'Capital Expenditure'
    OTHER          = 'Other Expenses'

class TransactionType(enum.Enum):
    DEPOSIT    = 'Deposit'
    WITHDRAWAL = 'Withdrawal'

class ExpenditureHead(db.Model):
    __tablename__ = 'expenditure_heads'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    is_active   = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<ExpenditureHead {self.name}>'

# ══════════════════════════════════════════════════════════════
# USER
# ══════════════════════════════════════════════════════════════
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id                  = db.Column(db.Integer, primary_key=True)
    mobile              = db.Column(db.String(15),  unique=True, nullable=False, index=True)
    email               = db.Column(db.String(120), unique=True, nullable=True)
    full_name           = db.Column(db.String(120), nullable=False)
    password_hash       = db.Column(db.String(256), nullable=False)
    role                = db.Column(db.Enum(UserRole), default=UserRole.DONOR, nullable=False)
    is_active           = db.Column(db.Boolean, default=True)
    must_change_password= db.Column(db.Boolean, default=True)
    address             = db.Column(db.Text, nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    last_login          = db.Column(db.DateTime, nullable=True)
    otp_code            = db.Column(db.String(6),  nullable=True)
    otp_expiry          = db.Column(db.DateTime,   nullable=True)

    donations    = db.relationship('Donation',  foreign_keys='Donation.user_id',
                                   backref='donor', lazy='dynamic')

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

    @property
    def is_staff(self):
        return self.role in (UserRole.ADMIN, UserRole.TREASURER, UserRole.PRIEST,
                            UserRole.PRESBYTER_IN_CHARGE, UserRole.ASSOCIATE_PASTOR,
                            UserRole.SECRETARY, UserRole.OFFICE_ASSISTANT)

    @property
    def total_donated(self):
        from sqlalchemy import func
        result = db.session.query(func.sum(DonationItem.amount))\
            .join(Donation)\
            .filter(Donation.user_id == self.id, Donation.status == 'Confirmed')\
            .scalar()
        return float(result or 0)

    def __repr__(self):
        return f'<User {self.full_name} | {self.mobile}>'


# ══════════════════════════════════════════════════════════════
# DONATION
# ══════════════════════════════════════════════════════════════
class Donation(db.Model):
    __tablename__ = 'donations'

    id                  = db.Column(db.Integer, primary_key=True)
    receipt_number      = db.Column(db.String(30),  unique=True, nullable=False, index=True)
    user_id             = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    donation_date       = db.Column(db.Date,    nullable=False)
    payment_mode        = db.Column(db.Enum(PaymentMode), nullable=False)
    payment_reference   = db.Column(db.String(100), nullable=True)
    status              = db.Column(db.String(20),  default='Pending')   # Pending/Confirmed/Cancelled
    donor_name_override = db.Column(db.String(120), nullable=True)
    financial_year      = db.Column(db.String(10),  nullable=True, index=True)
    notes               = db.Column(db.Text, nullable=True)
    created_by          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    confirmed_by        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    confirmed_at        = db.Column(db.DateTime, nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    razorpay_order_id   = db.Column(db.String(100), nullable=True)
    razorpay_payment_id = db.Column(db.String(100), nullable=True)

    items = db.relationship('DonationItem', backref='donation',
                            lazy='dynamic', cascade='all, delete-orphan')

    @property
    def total_amount(self):
        return sum(float(i.amount) for i in self.items)

    @property
    def donor_display_name(self):
        return self.donor_name_override or (self.donor.full_name if self.donor else 'Unknown')

    def __repr__(self):
        return f'<Donation {self.receipt_number}>'


class DonationItem(db.Model):
    __tablename__ = 'donation_items'

    id          = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id'), nullable=False)
    head        = db.Column(db.Enum(DonationHead), nullable=False)
    amount      = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    remarks     = db.Column(db.String(200), nullable=True)


# ══════════════════════════════════════════════════════════════
# EXPENSE
# ══════════════════════════════════════════════════════════════
class Expense(db.Model):
    __tablename__ = 'expenses'

    id                = db.Column(db.Integer, primary_key=True)
    voucher_number    = db.Column(db.String(30), unique=True, nullable=False, index=True)
    expense_date      = db.Column(db.Date,    nullable=False)
    category          = db.Column(db.String(100), nullable=False) # Changed from Enum to String
    description       = db.Column(db.String(500), nullable=False)
    payee             = db.Column(db.String(200), nullable=True)
    amount            = db.Column(db.Numeric(12, 2), nullable=False)
    payment_mode      = db.Column(db.Enum(PaymentMode), nullable=False)
    payment_reference = db.Column(db.String(100), nullable=True)
    financial_year    = db.Column(db.String(10),  nullable=True, index=True)
    notes             = db.Column(db.Text, nullable=True)
    approved_by       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    approver = db.relationship('User', foreign_keys=[approved_by])
    creator  = db.relationship('User', foreign_keys=[created_by])


# ══════════════════════════════════════════════════════════════
# BANK ACCOUNT & TRANSACTIONS
# ══════════════════════════════════════════════════════════════
class BankAccount(db.Model):
    __tablename__ = 'bank_accounts'

    id              = db.Column(db.Integer, primary_key=True)
    account_name    = db.Column(db.String(100), nullable=False)
    bank_name       = db.Column(db.String(100), nullable=False)
    account_number  = db.Column(db.String(30),  nullable=False)
    ifsc_code       = db.Column(db.String(20),  nullable=True)
    branch          = db.Column(db.String(100), nullable=True)
    opening_balance = db.Column(db.Numeric(15, 2), default=0)
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship('BankTransaction', backref='account', lazy='dynamic')

    @property
    def current_balance(self):
        from sqlalchemy import func
        deposits = db.session.query(func.sum(BankTransaction.amount))\
            .filter(BankTransaction.account_id == self.id,
                    BankTransaction.transaction_type == TransactionType.DEPOSIT).scalar() or 0
        withdrawals = db.session.query(func.sum(BankTransaction.amount))\
            .filter(BankTransaction.account_id == self.id,
                    BankTransaction.transaction_type == TransactionType.WITHDRAWAL).scalar() or 0
        return float(self.opening_balance) + float(deposits) - float(withdrawals)


class BankTransaction(db.Model):
    __tablename__ = 'bank_transactions'

    id               = db.Column(db.Integer, primary_key=True)
    account_id       = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), nullable=False)
    transaction_date = db.Column(db.Date,    nullable=False)
    transaction_type = db.Column(db.Enum(TransactionType), nullable=False)
    amount           = db.Column(db.Numeric(15, 2), nullable=False)
    reference        = db.Column(db.String(100), nullable=True)
    description      = db.Column(db.String(500), nullable=False)
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════
# SUPPORTING MODELS
# ══════════════════════════════════════════════════════════════
class ChurchEvent(db.Model):
    __tablename__ = 'church_events'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    event_type  = db.Column(db.String(50),  nullable=True)
    event_date  = db.Column(db.DateTime,    nullable=False)
    end_date    = db.Column(db.DateTime,    nullable=True)
    location    = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text,        nullable=True)
    is_public   = db.Column(db.Boolean, default=True)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class PrayerRequest(db.Model):
    __tablename__ = 'prayer_requests'

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name         = db.Column(db.String(120), nullable=False)
    request      = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    is_public    = db.Column(db.Boolean, default=False)
    status       = db.Column(db.String(20), default='Active')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


class Announcement(db.Model):
    __tablename__ = 'announcements'

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    is_active  = db.Column(db.Boolean, default=True)
    priority   = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)


class ReceiptCounter(db.Model):
    __tablename__ = 'receipt_counters'

    id               = db.Column(db.Integer, primary_key=True)
    financial_year   = db.Column(db.String(10), unique=True, nullable=False)
    last_receipt_no  = db.Column(db.Integer, default=0)
    last_voucher_no  = db.Column(db.Integer, default=0)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action      = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50),  nullable=True)
    entity_id   = db.Column(db.Integer,     nullable=True)
    details     = db.Column(db.Text,        nullable=True)
    ip_address  = db.Column(db.String(45),  nullable=True)
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])
