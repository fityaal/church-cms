from datetime import date, datetime, timedelta
import random, string


def get_financial_year(dt=None):
    if dt is None:
        dt = date.today()
    if isinstance(dt, datetime):
        dt = dt.date()
    if dt.month >= 4:
        return f"{dt.year}-{str(dt.year+1)[-2:]}"
    return f"{dt.year-1}-{str(dt.year)[-2:]}"


def generate_receipt_number(donation_date=None):
    from models import ReceiptCounter, db
    fy = get_financial_year(donation_date)
    counter = ReceiptCounter.query.filter_by(financial_year=fy).first()
    if not counter:
        counter = ReceiptCounter(financial_year=fy, last_receipt_no=0, last_voucher_no=0)
        db.session.add(counter)
    counter.last_receipt_no += 1
    db.session.commit()
    return f"ASC/{fy}/{counter.last_receipt_no:04d}"


def generate_voucher_number(expense_date=None):
    from models import ReceiptCounter, db
    fy = get_financial_year(expense_date)
    counter = ReceiptCounter.query.filter_by(financial_year=fy).first()
    if not counter:
        counter = ReceiptCounter(financial_year=fy, last_receipt_no=0, last_voucher_no=0)
        db.session.add(counter)
    counter.last_voucher_no += 1
    db.session.commit()
    return f"ASC/EXP/{fy}/{counter.last_voucher_no:04d}"


def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))


def amount_in_words(amount):
    ones  = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
             'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen',
             'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    tens_ = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty',
             'Sixty', 'Seventy', 'Eighty', 'Ninety']

    def _two(n):
        if n < 20: return ones[n]
        return tens_[n//10] + (' ' + ones[n%10] if n%10 else '')

    def _three(n):
        if n == 0: return ''
        if n < 100: return _two(n)
        return ones[n//100] + ' Hundred' + (' and ' + _two(n%100) if n%100 else '')

    try:
        amount  = float(amount)
        rupees  = int(amount)
        paise   = round((amount - rupees) * 100)
        if rupees == 0 and paise == 0:
            return 'Zero Rupees Only'
        parts = []
        if rupees >= 10_000_000:
            parts.append(_three(rupees // 10_000_000) + ' Crore')
            rupees %= 10_000_000
        if rupees >= 100_000:
            parts.append(_three(rupees // 100_000) + ' Lakh')
            rupees %= 100_000
        if rupees >= 1_000:
            parts.append(_three(rupees // 1_000) + ' Thousand')
            rupees %= 1_000
        if rupees > 0:
            parts.append(_three(rupees))
        result = ' '.join(parts) + ' Rupees'
        if paise:
            result += f' and {_two(paise)} Paise'
        return result + ' Only'
    except Exception:
        return 'Zero Rupees Only'


def log_action(user_id, action, entity_type=None, entity_id=None, details=None, ip=None):
    from models import AuditLog, db
    try:
        entry = AuditLog(user_id=user_id, action=action, entity_type=entity_type,
                         entity_id=entity_id, details=details, ip_address=ip)
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_all_financial_years():
    years = []
    for y in range(2020, 2031):
        years.append(f"{y}-{str(y+1)[-2:]}")
    return sorted(years, reverse=True)
