from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import func, extract
from models import (Donation, DonationItem, DonationHead, Expense,
                    ChurchEvent, Announcement, PrayerRequest, db)
from utils.helpers import get_financial_year, get_all_financial_years
from utils.pdf_generator import generate_receipt_pdf
from config import Config
from datetime import datetime
import io

donor_bp = Blueprint('donor', __name__)

def active_required(f):
    @wraps(f)
    @login_required
    def dec(*a, **kw):
        if not current_user.is_active:
            flash('Your account is inactive. Contact the church office.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*a, **kw)
    return dec

@donor_bp.route('/')
@donor_bp.route('/dashboard')
@active_required
def dashboard():
    fy = get_financial_year()
    my_donations = Donation.query.filter_by(user_id=current_user.id, status='Confirmed')\
        .order_by(Donation.donation_date.desc()).limit(5).all()
    total_year = db.session.query(func.coalesce(func.sum(DonationItem.amount),0))\
        .join(Donation).filter(Donation.user_id==current_user.id,
        Donation.status=='Confirmed', Donation.financial_year==fy).scalar()
    total_life = db.session.query(func.coalesce(func.sum(DonationItem.amount),0))\
        .join(Donation).filter(Donation.user_id==current_user.id,
        Donation.status=='Confirmed').scalar()
    head_data = db.session.query(DonationItem.head,
        func.sum(DonationItem.amount).label('total'))\
        .join(Donation).filter(Donation.user_id==current_user.id,
        Donation.status=='Confirmed', Donation.financial_year==fy)\
        .group_by(DonationItem.head).all()
    events = ChurchEvent.query.filter(ChurchEvent.is_public==True,
        ChurchEvent.event_date>=datetime.now()).order_by(ChurchEvent.event_date).limit(4).all()
    announcements = Announcement.query.filter_by(is_active=True)\
        .order_by(Announcement.priority.desc()).limit(3).all()
    return render_template('donor/dashboard.html',
        my_donations=my_donations, total_year=float(total_year),
        total_life=float(total_life), head_data=head_data,
        events=events, announcements=announcements, fy=fy)

@donor_bp.route('/my-donations')
@active_required
def my_donations():
    page = request.args.get('page', 1, type=int)
    fy   = request.args.get('fy', '')
    start_date = request.args.get('start_date', '')
    end_date   = request.args.get('end_date', '')
    q = Donation.query.filter_by(user_id=current_user.id, status='Confirmed')
    if fy: q = q.filter(Donation.financial_year==fy)
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
    donations = q.order_by(Donation.donation_date.desc())\
        .paginate(page=page, per_page=Config.ITEMS_PER_PAGE)
    fy_list = db.session.query(Donation.financial_year)\
        .filter_by(user_id=current_user.id).distinct().all()
    fy_list = sorted([y[0] for y in fy_list if y[0]], reverse=True)
    total_q = db.session.query(func.coalesce(func.sum(DonationItem.amount),0))\
        .join(Donation).filter(Donation.user_id==current_user.id,
        Donation.status=='Confirmed')
    if fy:
        total_q = total_q.filter(Donation.financial_year==fy)
    if start_date:
        total_q = total_q.filter(Donation.donation_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        total_q = total_q.filter(Donation.donation_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    total = total_q.scalar()
    return render_template('donor/my_donations.html', donations=donations,
        fy_list=fy_list, selected_fy=fy, start_date=start_date, end_date=end_date,
        total=float(total))

@donor_bp.route('/receipt/<int:did>')
@active_required
def view_receipt(did):
    d = Donation.query.filter_by(id=did, user_id=current_user.id).first_or_404()
    return render_template('donor/receipt_view.html', donation=d)

@donor_bp.route('/receipt/<int:did>/download')
@active_required
def download_receipt(did):
    d = Donation.query.filter_by(id=did, user_id=current_user.id).first_or_404()
    pdf = generate_receipt_pdf(d)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True,
        download_name=f"Receipt_{d.receipt_number.replace('/','_')}.pdf")

@donor_bp.route('/annual-statement')
@active_required
def annual_statement():
    fy = request.args.get('fy', get_financial_year())
    donations = Donation.query.filter_by(user_id=current_user.id,
        status='Confirmed', financial_year=fy)\
        .order_by(Donation.donation_date).all()
    head_totals = {}
    for d in donations:
        for item in d.items:
            head_totals[item.head.value] = head_totals.get(item.head.value,0)+float(item.amount)
    total = sum(head_totals.values())
    fy_list = db.session.query(Donation.financial_year)\
        .filter_by(user_id=current_user.id).distinct().all()
    fy_list = sorted([y[0] for y in fy_list if y[0]], reverse=True)
    return render_template('donor/annual_statement.html', donations=donations,
        head_totals=head_totals, total=total, selected_fy=fy, fy_list=fy_list)

@donor_bp.route('/donate')
@active_required
def donate():
    return render_template('donor/donate.html', heads=list(DonationHead))

@donor_bp.route('/church-expenses')
@active_required
def church_expenses():
    page = request.args.get('page', 1, type=int)
    fy   = request.args.get('fy', get_financial_year())
    start_date = request.args.get('start_date', '')
    end_date   = request.args.get('end_date', '')
    q = Expense.query.filter_by(financial_year=fy)
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
    expenses = q.order_by(Expense.expense_date.desc())\
        .paginate(page=page, per_page=Config.ITEMS_PER_PAGE)
    total_q = db.session.query(func.coalesce(func.sum(Expense.amount),0))\
        .filter(Expense.financial_year==fy)
    if start_date:
        total_q = total_q.filter(Expense.expense_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        total_q = total_q.filter(Expense.expense_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    total = total_q.scalar()
    cat_totals = db.session.query(Expense.category,
        func.sum(Expense.amount).label('total'))\
        .filter(Expense.financial_year==fy)
    if start_date:
        cat_totals = cat_totals.filter(Expense.expense_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        cat_totals = cat_totals.filter(Expense.expense_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    cat_totals = cat_totals.group_by(Expense.category).all()
    fy_list = get_all_financial_years()
    return render_template('donor/church_expenses.html', expenses=expenses,
        total=float(total), cat_totals=cat_totals, selected_fy=fy, fy_list=fy_list,
        start_date=start_date, end_date=end_date)

@donor_bp.route('/prayer-requests', methods=['GET','POST'])
@active_required
def prayer_requests():
    if request.method == 'POST':
        pr = PrayerRequest(user_id=current_user.id,
            name=current_user.full_name,
            request=request.form.get('request','').strip(),
            is_anonymous=bool(request.form.get('is_anonymous')),
            is_public=bool(request.form.get('is_public')))
        db.session.add(pr)
        db.session.commit()
        flash('Prayer request submitted. God bless you!', 'success')
        return redirect(url_for('donor.prayer_requests'))
    public_reqs = PrayerRequest.query.filter_by(is_public=True, status='Active')\
        .order_by(PrayerRequest.created_at.desc()).all()
    my_reqs = PrayerRequest.query.filter_by(user_id=current_user.id)\
        .order_by(PrayerRequest.created_at.desc()).all()
    return render_template('donor/prayer_requests.html',
        public_requests=public_reqs, my_requests=my_reqs)

@donor_bp.route('/profile', methods=['GET','POST'])
@active_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name','').strip()
        current_user.email     = request.form.get('email','').strip() or None
        current_user.address   = request.form.get('address','').strip()
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('donor.profile'))
    return render_template('donor/profile.html')

@donor_bp.route('/events')
@active_required
def events():
    upcoming = ChurchEvent.query.filter(ChurchEvent.is_public==True,
        ChurchEvent.event_date>=datetime.now())\
        .order_by(ChurchEvent.event_date).all()
    past = ChurchEvent.query.filter(ChurchEvent.is_public==True,
        ChurchEvent.event_date<datetime.now())\
        .order_by(ChurchEvent.event_date.desc()).limit(10).all()
    return render_template('donor/events.html', upcoming=upcoming, past=past)
