from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func, extract
from models import Donation, DonationItem, Expense, db
from utils.helpers import get_financial_year

api_bp = Blueprint('api', __name__)

@api_bp.route('/chart-data')
@login_required
def chart_data():
    fy = request.args.get('fy', get_financial_year())
    scope = request.args.get('scope', 'all')

    q_don = db.session.query(extract('month', Donation.donation_date).label('m'),
        func.sum(DonationItem.amount).label('t'))\
        .join(DonationItem).filter(Donation.status=='Confirmed', Donation.financial_year==fy)
    if scope == 'mine':
        q_don = q_don.filter(Donation.user_id == current_user.id)
    monthly_don = q_don.group_by('m').order_by('m').all()

    head_data = db.session.query(DonationItem.head, func.sum(DonationItem.amount).label('t'))\
        .join(Donation).filter(Donation.status=='Confirmed', Donation.financial_year==fy)
    if scope == 'mine':
        head_data = head_data.filter(Donation.user_id == current_user.id)
    head_data = head_data.group_by(DonationItem.head).all()

    mo_exp = db.session.query(extract('month', Expense.expense_date).label('m'),
        func.sum(Expense.amount).label('t'))\
        .filter(Expense.financial_year==fy).group_by('m').order_by('m').all()

    MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    return jsonify({
        'income':  {'labels':[MONTHS[int(r.m)-1] for r in monthly_don], 'values':[float(r.t) for r in monthly_don]},
        'expense': {'labels':[MONTHS[int(r.m)-1] for r in mo_exp],      'values':[float(r.t) for r in mo_exp]},
        'heads':   {'labels':[r.head.value for r in head_data],          'values':[float(r.t) for r in head_data]},
    })
