from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, send_file, jsonify)
from flask_login import login_required, current_user
from sqlalchemy import func, extract
from models import (User, UserRole, Donation, DonationItem, DonationHead,
                    Expense, ExpenditureHead, BankAccount, BankTransaction,
                    TransactionType, ChurchEvent, Announcement, PrayerRequest,
                    AuditLog, PaymentMode, db)
from utils.helpers import (generate_receipt_number, generate_voucher_number,
                            get_financial_year, get_all_financial_years,
                            log_action)
from utils.pdf_generator import generate_receipt_pdf
from config import Config
from datetime import datetime, date
import io

admin_bp = Blueprint('admin', __name__)


# ── Access guards ─────────────────────────────────────────────
def staff_required(f):
    @wraps(f)
    @login_required
    def dec(*a, **kw):
        if not current_user.is_staff:
            flash('Access denied.', 'danger')
            return redirect(url_for('donor.dashboard'))
        return f(*a, **kw)
    return dec


def admin_only(f):
    @wraps(f)
    @login_required
    def dec(*a, **kw):
        if not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('admin.dashboard'))
        return f(*a, **kw)
    return dec


# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/')
@admin_bp.route('/dashboard')
@staff_required
def dashboard():
    # ── Database Auto-Fix ─────────────────────────────────────
    from models import db, ExpenditureHead
    from sqlalchemy import text, inspect
    try:
        inspector = inspect(db.engine)
        if not inspector.has_table('expenditure_heads'):
            db.create_all()
            db.session.execute(text("ALTER TABLE expenses MODIFY category VARCHAR(100)"))
            if ExpenditureHead.query.count() == 0:
                default_heads = ['Salary & Staff', 'Building Maintenance', 'Utilities & Bills', 'Worship & Sacraments', 'Outreach & Mission', 'Education & Sunday School', 'Administration', 'Charity & Welfare', 'Capital Expenditure', 'Other Expenses']
                for h in default_heads: db.session.add(ExpenditureHead(name=h))
            
            # Update UserRole Enum in MySQL
            db.session.execute(text("ALTER TABLE users MODIFY role ENUM('ADMIN','TREASURER','PRIEST','PRESBYTER_IN_CHARGE','ASSOCIATE_PASTOR','SECRETARY','OFFICE_ASSISTANT','DONOR')"))
            
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"DB Fix Error: {e}")
    # ──────────────────────────────────────────────────────────

    fy = get_financial_year()

    total_receipts  = Donation.query.filter_by(status='Confirmed', financial_year=fy).count()
    total_collection= db.session.query(func.coalesce(func.sum(DonationItem.amount),0))\
        .join(Donation).filter(Donation.status=='Confirmed', Donation.financial_year==fy).scalar()
    total_expenses  = db.session.query(func.coalesce(func.sum(Expense.amount),0))\
        .filter(Expense.financial_year==fy).scalar()
    total_donors    = User.query.filter_by(role=UserRole.DONOR, is_active=True).count()
    pending_count   = Donation.query.filter_by(status='Pending').count()

    head_data = db.session.query(DonationItem.head,
                                  func.sum(DonationItem.amount).label('total'))\
        .join(Donation).filter(Donation.status=='Confirmed', Donation.financial_year==fy)\
        .group_by(DonationItem.head).all()

    monthly_income = db.session.query(
        extract('month', Donation.donation_date).label('m'),
        func.sum(DonationItem.amount).label('total')
    ).join(DonationItem).filter(Donation.status=='Confirmed', Donation.financial_year==fy)\
     .group_by('m').order_by('m').all()

    monthly_expense = db.session.query(
        extract('month', Expense.expense_date).label('m'),
        func.sum(Expense.amount).label('total')
    ).filter(Expense.financial_year==fy).group_by('m').order_by('m').all()

    head_data = [{"head": row.head.value, "total": float(row.total)} for row in head_data]

    monthly_income = [{"m": int(row.m), "total": float(row.total)} for row in monthly_income]

    monthly_expense = [{"m": int(row.m), "total": float(row.total)} for row in monthly_expense]

    recent_donations = Donation.query.filter_by(status='Confirmed')\
        .order_by(Donation.created_at.desc()).limit(8).all()
    announcements    = Announcement.query.filter_by(is_active=True)\
        .order_by(Announcement.priority.desc()).limit(4).all()
    bank_accounts    = BankAccount.query.filter_by(is_active=True).all()

    return render_template('admin/dashboard.html',
        fy=fy,
        total_receipts=float(total_receipts),
        total_collection=float(total_collection),
        total_expenses=float(total_expenses),
        net_balance=float(total_collection)-float(total_expenses),
        total_donors=total_donors,
        pending_count=pending_count,
        head_data=head_data,
        monthly_income=monthly_income,
        monthly_expense=monthly_expense,
        recent_donations=recent_donations,
        announcements=announcements,
        bank_accounts=bank_accounts,
    )


# ══════════════════════════════════════════════════════════════
# DONATIONS
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/donations')
@staff_required
def donations():
    page   = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    fy     = request.args.get('fy',     get_financial_year())
    search = request.args.get('search', '')
    head   = request.args.get('head',   '')
    start_date = request.args.get('start_date', '')
    end_date   = request.args.get('end_date',   '')

    q = Donation.query.join(User, Donation.user_id == User.id)
    if status: q = q.filter(Donation.status == status)
    if fy:     q = q.filter(Donation.financial_year == fy)
    if start_date:
        try:
            q = q.filter(Donation.donation_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        except ValueError:
            start_date = ''
    if end_date:
        try:
            q = q.filter(Donation.donation_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        except ValueError:
            end_date = ''
    if search: q = q.filter(
        db.or_(User.full_name.ilike(f'%{search}%'),
               Donation.receipt_number.ilike(f'%{search}%'),
               User.mobile.ilike(f'%{search}%')))
    if head:
        q = q.join(DonationItem).filter(DonationItem.head == DonationHead[head])

    donations = q.order_by(Donation.created_at.desc())\
                 .paginate(page=page, per_page=Config.ITEMS_PER_PAGE)

    total_amt = db.session.query(func.coalesce(func.sum(DonationItem.amount),0))\
        .join(Donation).filter(Donation.status=='Confirmed', Donation.financial_year==fy).scalar()

    return render_template('admin/donations.html',
        donations=donations, heads=list(DonationHead),
        financial_years=get_all_financial_years(),
        selected_fy=fy, selected_status=status,
        selected_head=head, search=search,
        start_date=start_date, end_date=end_date,
        total_amt=float(total_amt))


@admin_bp.route('/donations/new', methods=['GET', 'POST'])
@staff_required
def new_donation():
    donors = User.query.filter_by(role=UserRole.DONOR, is_active=True)\
                 .order_by(User.full_name).all()

    if request.method == 'POST':
        user_id       = request.form.get('user_id', type=int)
        don_date_str  = request.form.get('donation_date', date.today().isoformat())
        don_date      = datetime.strptime(don_date_str, '%Y-%m-%d').date()
        pay_mode      = request.form.get('payment_mode')
        pay_ref       = request.form.get('payment_reference', '').strip()
        override_name = request.form.get('donor_name_override', '').strip() or None
        notes         = request.form.get('notes', '')

        items = []
        for head in DonationHead:
            raw = request.form.get(f'head_{head.name}', '').strip()
            rem = request.form.get(f'remarks_{head.name}', '').strip()
            if raw:
                try:
                    amt = float(raw)
                    if amt > 0:
                        items.append((head, amt, rem))
                except ValueError:
                    pass

        if not items:
            flash('Enter at least one donation amount.', 'danger')
            return render_template('admin/donation_form.html', donors=donors,
                heads=list(DonationHead), payment_modes=list(PaymentMode),
                today=date.today().isoformat())

        fy         = get_financial_year(don_date)
        receipt_no = generate_receipt_number(don_date)

        donation = Donation(
            receipt_number=receipt_no, user_id=user_id,
            donation_date=don_date, payment_mode=PaymentMode[pay_mode],
            payment_reference=pay_ref or None,
            donor_name_override=override_name,
            status='Confirmed', financial_year=fy,
            created_by=current_user.id,
            confirmed_by=current_user.id,
            confirmed_at=datetime.utcnow(), notes=notes)
        db.session.add(donation)
        db.session.flush()

        for head, amt, rem in items:
            db.session.add(DonationItem(donation_id=donation.id, head=head, amount=amt, remarks=rem))

        db.session.commit()
        log_action(current_user.id, 'DONATION_CREATED', 'Donation', donation.id,
                   f'Receipt:{receipt_no}', request.remote_addr)
        flash(f'Receipt {receipt_no} created successfully!', 'success')
        return redirect(url_for('admin.view_receipt', did=donation.id))

    return render_template('admin/donation_form.html', donors=donors,
        heads=list(DonationHead), payment_modes=list(PaymentMode),
        today=date.today().isoformat())


@admin_bp.route('/donations/<int:did>/confirm', methods=['POST'])
@staff_required
def confirm_donation(did):
    d = Donation.query.get_or_404(did)
    if d.status == 'Pending':
        d.status = 'Confirmed'
        d.confirmed_at = datetime.utcnow()
        d.confirmed_by = current_user.id
        db.session.commit()
        log_action(current_user.id, 'DONATION_CONFIRMED', 'Donation', did, ip=request.remote_addr)
        flash(f'Donation {d.receipt_number} confirmed.', 'success')
    return redirect(request.referrer or url_for('admin.donations'))


@admin_bp.route('/donations/<int:did>/edit', methods=['GET', 'POST'])
@staff_required
def edit_donation(did):
    d = Donation.query.get_or_404(did)
    donors = User.query.filter_by(role=UserRole.DONOR, is_active=True).order_by(User.full_name).all()
    
    if request.method == 'POST':
        d.user_id = request.form.get('user_id', type=int)
        don_date_str = request.form.get('donation_date')
        d.donation_date = datetime.strptime(don_date_str, '%Y-%m-%d').date()
        d.payment_mode = PaymentMode[request.form.get('payment_mode')]
        d.payment_reference = request.form.get('payment_reference', '').strip() or None
        d.donor_name_override = request.form.get('donor_name_override', '').strip() or None
        d.notes = request.form.get('notes', '')
        d.financial_year = get_financial_year(d.donation_date)

        # Clear existing items and add new ones
        DonationItem.query.filter_by(donation_id=d.id).delete()
        
        items_added = False
        for head in DonationHead:
            raw = request.form.get(f'head_{head.name}', '').strip()
            rem = request.form.get(f'remarks_{head.name}', '').strip()
            if raw:
                try:
                    amt = float(raw)
                    if amt > 0:
                        db.session.add(DonationItem(donation_id=d.id, head=head, amount=amt, remarks=rem))
                        items_added = True
                except ValueError:
                    pass
        
        if not items_added:
            db.session.rollback()
            flash('Enter at least one donation amount.', 'danger')
            return render_template('admin/donation_form.html', donors=donors,
                heads=list(DonationHead), payment_modes=list(PaymentMode),
                donation=d, today=d.donation_date.isoformat())

        db.session.commit()
        log_action(current_user.id, 'DONATION_UPDATED', 'Donation', d.id,
                   f'Receipt:{d.receipt_number}', request.remote_addr)
        flash(f'Receipt {d.receipt_number} updated successfully!', 'success')
        return redirect(url_for('admin.view_receipt', did=d.id))

    return render_template('admin/donation_form.html', donors=donors,
        heads=list(DonationHead), payment_modes=list(PaymentMode),
        donation=d, today=d.donation_date.isoformat())


@admin_bp.route('/donations/<int:did>/receipt')
@staff_required
def view_receipt(did):
    d = Donation.query.get_or_404(did)
    return render_template('admin/receipt_view.html', donation=d)


@admin_bp.route('/donations/<int:did>/receipt/pdf')
@login_required
def download_receipt(did):
    d = Donation.query.get_or_404(did)
    if not current_user.is_staff and current_user.id != d.user_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    pdf = generate_receipt_pdf(d)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf',
                     as_attachment=True,
                     download_name=f"Receipt_{d.receipt_number.replace('/','_')}.pdf")


@admin_bp.route('/donations/<int:did>/delete', methods=['POST'])
@admin_only
def delete_donation(did):
    d = Donation.query.get_or_404(did)
    rn = d.receipt_number
    db.session.delete(d)
    db.session.commit()
    flash(f'Donation {rn} deleted.', 'warning')
    return redirect(url_for('admin.donations'))


# ══════════════════════════════════════════════════════════════
# EXPENSES
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/expenses')
@staff_required
def expenses():
    page       = request.args.get('page', 1, type=int)
    fy         = request.args.get('fy',         get_financial_year())
    category   = request.args.get('category',   '')
    search     = request.args.get('search',     '')
    start_date = request.args.get('start_date', '')
    end_date   = request.args.get('end_date',   '')

    q = Expense.query
    if fy:       q = q.filter(Expense.financial_year == fy)
    if category: q = q.filter(Expense.category == category)
    if start_date:
        try:
            q = q.filter(Expense.expense_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        except ValueError:
            start_date = ''
    if end_date:
        try:
            q = q.filter(Expense.expense_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        except ValueError:
            end_date = ''
    if search:   q = q.filter(
        db.or_(Expense.description.ilike(f'%{search}%'),
               Expense.voucher_number.ilike(f'%{search}%'),
               Expense.payee.ilike(f'%{search}%')))

    expenses  = q.order_by(Expense.expense_date.desc())\
                 .paginate(page=page, per_page=Config.ITEMS_PER_PAGE)
    total_amt = db.session.query(func.coalesce(func.sum(Expense.amount),0))\
                .filter(Expense.financial_year==fy).scalar()

    cat_totals = db.session.query(Expense.category,
                                   func.sum(Expense.amount).label('total'))\
        .filter(Expense.financial_year==fy).group_by(Expense.category).all()

    heads = ExpenditureHead.query.filter_by(is_active=True).all()

    return render_template('admin/expenses.html',
        expenses=expenses, categories=heads,
        financial_years=get_all_financial_years(),
        selected_fy=fy, selected_category=category, search=search,
        start_date=start_date, end_date=end_date,
        total_amt=float(total_amt), cat_totals=cat_totals)


@admin_bp.route('/expenses/new', methods=['GET', 'POST'])
@staff_required
def new_expense():
    if request.method == 'POST':
        exp_date = datetime.strptime(request.form.get('expense_date'), '%Y-%m-%d').date()
        amount   = float(request.form.get('amount', 0))
        category = request.form.get('category')
        pay_mode = request.form.get('payment_mode')
        fy       = get_financial_year(exp_date)
        voucher  = generate_voucher_number(exp_date)

        exp = Expense(
            voucher_number=voucher, expense_date=exp_date,
            category=category,
            description=request.form.get('description','').strip(),
            payee=request.form.get('payee','').strip() or None,
            amount=amount, payment_mode=PaymentMode[pay_mode],
            payment_reference=request.form.get('payment_reference','').strip() or None,
            financial_year=fy, notes=request.form.get('notes',''),
            created_by=current_user.id)
        db.session.add(exp)
        db.session.commit()
        log_action(current_user.id, 'EXPENSE_CREATED', 'Expense', exp.id,
                   f'Voucher:{voucher}', request.remote_addr)
        flash(f'Expense voucher {voucher} saved.', 'success')
        return redirect(url_for('admin.expenses'))

    heads = ExpenditureHead.query.filter_by(is_active=True).all()
    return render_template('admin/expense_form.html',
        categories=heads, payment_modes=list(PaymentMode),
        today=date.today().isoformat())


@admin_bp.route('/expenses/<int:eid>/delete', methods=['POST'])
@admin_only
def delete_expense(eid):
    e = Expense.query.get_or_404(eid)
    vn = e.voucher_number
    db.session.delete(e)
    db.session.commit()
    flash(f'Expense {vn} deleted.', 'warning')
    return redirect(url_for('admin.expenses'))


# ══════════════════════════════════════════════════════════════
# DONORS / MEMBERS
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/donors')
@staff_required
def donors():
    page   = request.args.get('page',   1, type=int)
    search = request.args.get('search', '')
    q = User.query.filter_by(role=UserRole.DONOR)
    if search:
        q = q.filter(db.or_(User.full_name.ilike(f'%{search}%'),
                             User.mobile.ilike(f'%{search}%'),
                             User.email.ilike(f'%{search}%')))
    donors = q.order_by(User.full_name).paginate(page=page, per_page=Config.ITEMS_PER_PAGE)
    return render_template('admin/donors.html', donors=donors, search=search)


@admin_bp.route('/donors/new', methods=['GET', 'POST'])
@staff_required
def new_donor():
    if request.method == 'POST':
        mobile = request.form.get('mobile','').strip()
        if User.query.filter_by(mobile=mobile).first():
            flash('Mobile number already registered.', 'danger')
            return render_template('admin/donor_form.html')

        user = User(mobile=mobile,
                    full_name=request.form.get('full_name','').strip(),
                    email=request.form.get('email','').strip() or None,
                    address=request.form.get('address','').strip(),
                    role=UserRole.DONOR, must_change_password=True)
        user.set_password(Config.DEFAULT_PASSWORD)
        db.session.add(user)
        db.session.commit()
        log_action(current_user.id, 'DONOR_CREATED', 'User', user.id,
                   f'Mobile:{mobile}', request.remote_addr)
        flash(f'Member registered. Default password: {Config.DEFAULT_PASSWORD}', 'success')
        return redirect(url_for('admin.donors'))
    return render_template('admin/donor_form.html')


@admin_bp.route('/donors/<int:uid>')
@staff_required
def donor_detail(uid):
    donor    = User.query.get_or_404(uid)
    donations= Donation.query.filter_by(user_id=uid, status='Confirmed')\
                   .order_by(Donation.donation_date.desc()).all()
    total    = sum(d.total_amount for d in donations)
    fy_totals= {}
    for d in donations:
        fy_totals[d.financial_year] = fy_totals.get(d.financial_year, 0) + d.total_amount
    head_totals = {}
    for d in donations:
        for item in d.items:
            key = item.head.value
            head_totals[key] = head_totals.get(key, 0) + float(item.amount)
    return render_template('admin/donor_detail.html',
        donor=donor, donations=donations, total=total,
        fy_totals=fy_totals, head_totals=head_totals)


@admin_bp.route('/donors/<int:uid>/edit', methods=['GET', 'POST'])
@staff_required
def edit_donor(uid):
    donor = User.query.get_or_404(uid)
    if request.method == 'POST':
        donor.full_name = request.form.get('full_name','').strip()
        donor.email     = request.form.get('email','').strip() or None
        donor.address   = request.form.get('address','').strip()
        db.session.commit()
        flash('Member details updated.', 'success')
        return redirect(url_for('admin.donor_detail', uid=uid))
    return render_template('admin/donor_form.html', donor=donor)


@admin_bp.route('/donors/<int:uid>/toggle', methods=['POST'])
@admin_only
def toggle_donor(uid):
    donor = User.query.get_or_404(uid)
    donor.is_active = not donor.is_active
    db.session.commit()
    flash(f"Member {'activated' if donor.is_active else 'deactivated'}.", 'success')
    return redirect(url_for('admin.donors'))


@admin_bp.route('/donors/<int:uid>/reset-password', methods=['POST'])
@admin_only
def reset_donor_password(uid):
    donor = User.query.get_or_404(uid)
    donor.set_password(Config.DEFAULT_PASSWORD)
    donor.must_change_password = True
    db.session.commit()
    flash(f'Password reset to default: {Config.DEFAULT_PASSWORD}', 'success')
    return redirect(url_for('admin.donor_detail', uid=uid))


@admin_bp.route('/donors/<int:uid>/delete', methods=['POST'])
@admin_only
def delete_donor(uid):
    donor = User.query.get_or_404(uid)
    name = donor.full_name
    db.session.delete(donor)
    db.session.commit()
    flash(f'Member {name} deleted.', 'warning')
    return redirect(url_for('admin.donors'))


@admin_bp.route('/staff/<int:uid>/edit', methods=['GET', 'POST'])
@admin_only
def edit_staff(uid):
    user = User.query.get_or_404(uid)
    if request.method == 'POST':
        user.full_name = request.form.get('full_name','').strip()
        user.email     = request.form.get('email','').strip() or None
        user.role      = UserRole[request.form.get('role')]
        db.session.commit()
        flash('Staff details updated.', 'success')
        return redirect(url_for('admin.staff'))
    return render_template('admin/staff_form.html', roles=UserRole, staff=user)


@admin_bp.route('/staff/<int:uid>/delete', methods=['POST'])
@admin_only
def delete_staff(uid):
    user = User.query.get_or_404(uid)
    if user.id == current_user.id:
        flash('You cannot delete yourself.', 'danger')
        return redirect(url_for('admin.staff'))
    name = user.full_name
    db.session.delete(user)
    db.session.commit()
    flash(f'Staff {name} deleted.', 'warning')
    return redirect(url_for('admin.staff'))


# ══════════════════════════════════════════════════════════════
# REPORTS
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/reports')
@staff_required
def reports():
    fy      = request.args.get('fy',   get_financial_year())
    rtype   = request.args.get('type', 'summary')
    start_date = request.args.get('start_date', '')
    end_date   = request.args.get('end_date', '')
    parsed_start_date = None
    parsed_end_date = None
    if start_date:
        try:
            parsed_start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            start_date = ''
    if end_date:
        try:
            parsed_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            end_date = ''
    data    = {}

    if rtype == 'summary':
        head_totals = db.session.query(
            DonationItem.head,
            func.sum(DonationItem.amount).label('total'),
            func.count(Donation.id).label('cnt')
        ).join(Donation).filter(Donation.status=='Confirmed', Donation.financial_year==fy)
        if parsed_start_date:
            head_totals = head_totals.filter(Donation.donation_date >= parsed_start_date)
        if parsed_end_date:
            head_totals = head_totals.filter(Donation.donation_date <= parsed_end_date)
        head_totals = head_totals.group_by(DonationItem.head).all()

        exp_totals = db.session.query(
            Expense.category, func.sum(Expense.amount).label('total')
        ).filter(Expense.financial_year==fy)
        if parsed_start_date:
            exp_totals = exp_totals.filter(Expense.expense_date >= parsed_start_date)
        if parsed_end_date:
            exp_totals = exp_totals.filter(Expense.expense_date <= parsed_end_date)
        exp_totals = exp_totals.group_by(Expense.category).all()

        total_in  = sum(float(h.total or 0) for h in head_totals)
        total_out = sum(float(e.total or 0) for e in exp_totals)
        
        # Convert rows to dicts for JSON compatibility and float math in template
        head_totals = [{"head_label": h.head.value, "total": float(h.total or 0), "cnt": h.cnt, "head_name": h.head.name} for h in head_totals]
        exp_totals = [{"category": e.category, "total": float(e.total or 0)} for e in exp_totals]

        data = dict(head_totals=head_totals, exp_totals=exp_totals,
                    total_in=total_in, total_out=total_out, net=total_in-total_out)

    elif rtype == 'monthly':
        mo_inc = db.session.query(
            extract('month', Donation.donation_date).label('m'),
            func.sum(DonationItem.amount).label('total')
        ).join(DonationItem).filter(Donation.status=='Confirmed', Donation.financial_year==fy)
        if parsed_start_date:
            mo_inc = mo_inc.filter(Donation.donation_date >= parsed_start_date)
        if parsed_end_date:
            mo_inc = mo_inc.filter(Donation.donation_date <= parsed_end_date)
        mo_inc = mo_inc.group_by('m').order_by('m').all()

        mo_exp = db.session.query(
            extract('month', Expense.expense_date).label('m'),
            func.sum(Expense.amount).label('total')
        ).filter(Expense.financial_year==fy)
        if parsed_start_date:
            mo_exp = mo_exp.filter(Expense.expense_date >= parsed_start_date)
        if parsed_end_date:
            mo_exp = mo_exp.filter(Expense.expense_date <= parsed_end_date)
        mo_exp = mo_exp.group_by('m').order_by('m').all()

        mo_inc = [{"m": int(r.m), "total": float(r.total or 0)} for r in mo_inc]
        mo_exp = [{"m": int(r.m), "total": float(r.total or 0)} for r in mo_exp]
        data = dict(mo_inc=mo_inc, mo_exp=mo_exp)

    elif rtype == 'donors':
        top = db.session.query(
            User.full_name, User.mobile,
            func.sum(DonationItem.amount).label('total'),
            func.count(Donation.id).label('cnt')
        ).join(Donation, Donation.user_id==User.id).join(DonationItem)\
         .filter(Donation.status=='Confirmed', Donation.financial_year==fy)
        if parsed_start_date:
            top = top.filter(Donation.donation_date >= parsed_start_date)
        if parsed_end_date:
            top = top.filter(Donation.donation_date <= parsed_end_date)
        top = top.group_by(User.id).order_by(func.sum(DonationItem.amount).desc()).limit(50).all()
        
        top = [{"full_name": r.full_name, "mobile": r.mobile, "total": float(r.total or 0), "cnt": r.cnt} for r in top]
        data = dict(top_donors=top)

    elif rtype == 'headwise':
        for_head = request.args.get('head_filter', '')
        q = db.session.query(
            User.full_name, User.mobile, DonationItem.head,
            func.sum(DonationItem.amount).label('total')
        ).join(Donation, Donation.user_id==User.id).join(DonationItem)\
         .filter(Donation.status=='Confirmed', Donation.financial_year==fy)
        if parsed_start_date:
            q = q.filter(Donation.donation_date >= parsed_start_date)
        if parsed_end_date:
            q = q.filter(Donation.donation_date <= parsed_end_date)
        if for_head:
            q = q.filter(DonationItem.head == DonationHead[for_head])
        rows = q.group_by(User.id, DonationItem.head)\
                .order_by(func.sum(DonationItem.amount).desc()).all()
        
        rows = [{"full_name": r.full_name, "mobile": r.mobile, "head_label": r.head.value, "total": float(r.total or 0)} for r in rows]
        data = dict(rows=rows, heads=list(DonationHead), for_head=for_head)

    return render_template('admin/reports.html', data=data, rtype=rtype,
        financial_years=get_all_financial_years(), selected_fy=fy,
        start_date=start_date, end_date=end_date)


# ══════════════════════════════════════════════════════════════
# EXPENDITURE HEADS
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/expenditure-heads')
@admin_only
def expenditure_heads():
    heads = ExpenditureHead.query.all()
    return render_template('admin/expenditure_heads.html', heads=heads)


@admin_bp.route('/expenditure-heads/new', methods=['POST'])
@admin_only
def new_expenditure_head():
    name = request.form.get('name', '').strip()
    if name:
        if ExpenditureHead.query.filter_by(name=name).first():
            flash('Expenditure head already exists.', 'danger')
        else:
            head = ExpenditureHead(name=name)
            db.session.add(head)
            db.session.commit()
            flash('Expenditure head added.', 'success')
    return redirect(url_for('admin.expenditure_heads'))


@admin_bp.route('/expenditure-heads/<int:hid>/edit', methods=['POST'])
@admin_only
def edit_expenditure_head(hid):
    head = ExpenditureHead.query.get_or_404(hid)
    name = request.form.get('name', '').strip()
    if name:
        head.name = name
        db.session.commit()
        flash('Expenditure head updated.', 'success')
    return redirect(url_for('admin.expenditure_heads'))


@admin_bp.route('/expenditure-heads/<int:hid>/delete', methods=['POST'])
@admin_only
def delete_expenditure_head(hid):
    head = ExpenditureHead.query.get_or_404(hid)
    db.session.delete(head)
    db.session.commit()
    flash('Expenditure head deleted.', 'warning')
    return redirect(url_for('admin.expenditure_heads'))


# ══════════════════════════════════════════════════════════════
# BANK ACCOUNTS
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/bank')
@staff_required
def bank_accounts():
    accounts = BankAccount.query.filter_by(is_active=True).all()
    return render_template('admin/bank_accounts.html', accounts=accounts)


@admin_bp.route('/bank/new', methods=['GET', 'POST'])
@admin_only
def new_bank_account():
    if request.method == 'POST':
        acc = BankAccount(
            account_name=request.form.get('account_name'),
            bank_name=request.form.get('bank_name'),
            account_number=request.form.get('account_number'),
            ifsc_code=request.form.get('ifsc_code'),
            branch=request.form.get('branch'),
            opening_balance=float(request.form.get('opening_balance', 0)))
        db.session.add(acc)
        db.session.commit()
        flash('Bank account added.', 'success')
        return redirect(url_for('admin.bank_accounts'))
    return render_template('admin/bank_account_form.html')


@admin_bp.route('/bank/<int:aid>/transaction', methods=['GET', 'POST'])
@staff_required
def bank_transaction(aid):
    acc = BankAccount.query.get_or_404(aid)
    if request.method == 'POST':
        txn = BankTransaction(
            account_id=aid,
            transaction_date=datetime.strptime(request.form.get('txn_date'), '%Y-%m-%d').date(),
            transaction_type=TransactionType[request.form.get('txn_type')],
            amount=float(request.form.get('amount', 0)),
            reference=request.form.get('reference',''),
            description=request.form.get('description',''),
            created_by=current_user.id)
        db.session.add(txn)
        db.session.commit()
        flash('Transaction recorded.', 'success')
        return redirect(url_for('admin.bank_accounts'))
    return render_template('admin/bank_transaction_form.html', account=acc,
        txn_types=list(TransactionType), today=date.today().isoformat())


# ══════════════════════════════════════════════════════════════
# STAFF MANAGEMENT
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/staff')
@admin_only
def staff():
    staff = User.query.filter(User.role != UserRole.DONOR).order_by(User.full_name).all()
    return render_template('admin/staff.html', staff=staff, roles=UserRole)


@admin_bp.route('/staff/new', methods=['GET', 'POST'])
@admin_only
def new_staff():
    if request.method == 'POST':
        mobile = request.form.get('mobile','').strip()
        if User.query.filter_by(mobile=mobile).first():
            flash('Mobile already registered.', 'danger')
            return render_template('admin/staff_form.html', roles=UserRole)
        role = request.form.get('role')
        user = User(mobile=mobile,
                    full_name=request.form.get('full_name','').strip(),
                    email=request.form.get('email','').strip() or None,
                    role=UserRole[role], must_change_password=True)
        user.set_password(Config.DEFAULT_PASSWORD)
        db.session.add(user)
        db.session.commit()
        flash(f'Staff added. Default password: {Config.DEFAULT_PASSWORD}', 'success')
        return redirect(url_for('admin.staff'))
    return render_template('admin/staff_form.html', roles=UserRole)


# ══════════════════════════════════════════════════════════════
# EVENTS & ANNOUNCEMENTS
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/events', methods=['GET', 'POST'])
@staff_required
def events():
    if request.method == 'POST':
        ev = ChurchEvent(
            title=request.form.get('title'),
            event_type=request.form.get('event_type'),
            event_date=datetime.strptime(request.form.get('event_date'), '%Y-%m-%dT%H:%M'),
            location=request.form.get('location'),
            description=request.form.get('description'),
            is_public=bool(request.form.get('is_public')),
            created_by=current_user.id)
        db.session.add(ev)
        db.session.commit()
        flash('Event created.', 'success')
        return redirect(url_for('admin.events'))
    evs = ChurchEvent.query.order_by(ChurchEvent.event_date.desc()).all()
    return render_template('admin/events.html', events=evs)


@admin_bp.route('/events/<int:eid>/delete', methods=['POST'])
@staff_required
def delete_event(eid):
    ev = ChurchEvent.query.get_or_404(eid)
    db.session.delete(ev)
    db.session.commit()
    flash('Event deleted.', 'warning')
    return redirect(url_for('admin.events'))


@admin_bp.route('/announcements', methods=['GET', 'POST'])
@staff_required
def announcements():
    if request.method == 'POST':
        ann = Announcement(
            title=request.form.get('title'),
            content=request.form.get('content'),
            priority=int(request.form.get('priority', 0)),
            is_active=True, created_by=current_user.id)
        db.session.add(ann)
        db.session.commit()
        flash('Announcement posted.', 'success')
        return redirect(url_for('admin.announcements'))
    anns = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin/announcements.html', announcements=anns)


@admin_bp.route('/announcements/<int:aid>/toggle', methods=['POST'])
@staff_required
def toggle_announcement(aid):
    ann = Announcement.query.get_or_404(aid)
    ann.is_active = not ann.is_active
    db.session.commit()
    return redirect(url_for('admin.announcements'))


# ══════════════════════════════════════════════════════════════
# AUDIT LOG
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/audit-log')
@admin_only
def audit_log():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc())\
                   .paginate(page=page, per_page=Config.ITEMS_PER_PAGE)
    return render_template('admin/audit_log.html', logs=logs)


# ══════════════════════════════════════════════════════════════
# PRAYER REQUESTS (admin view)
# ══════════════════════════════════════════════════════════════
@admin_bp.route('/prayer-requests')
@staff_required
def prayer_requests():
    reqs = PrayerRequest.query.order_by(PrayerRequest.created_at.desc()).all()
    return render_template('admin/prayer_requests.html', reqs=reqs)


@admin_bp.route('/prayer-requests/<int:rid>/status', methods=['POST'])
@staff_required
def update_prayer_status(rid):
    pr = PrayerRequest.query.get_or_404(rid)
    pr.status = request.form.get('status', pr.status)
    db.session.commit()
    flash('Prayer request status updated.', 'success')
    return redirect(url_for('admin.prayer_requests'))
