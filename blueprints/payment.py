from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Donation, DonationItem, DonationHead, PaymentMode, db
from utils.helpers import generate_receipt_number, get_financial_year, log_action
from config import Config
from datetime import datetime

payment_bp = Blueprint('payment', __name__)

def _collect_items():
    items, total = [], 0
    for head in DonationHead:
        raw = request.form.get(f'head_{head.name}','').strip()
        if raw:
            try:
                amt = float(raw)
                if amt > 0:
                    items.append((head, amt))
                    total += amt
            except ValueError:
                pass
    return items, total

@payment_bp.route('/initiate', methods=['POST'])
@login_required
def initiate():
    items, total = _collect_items()
    if not items:
        flash('Please enter at least one donation amount.', 'danger')
        return redirect(url_for('donor.donate'))
    try:
        import razorpay
        # Verify that Razorpay keys are not placeholders
        if not Config.RAZORPAY_KEY_ID or Config.RAZORPAY_KEY_ID.startswith('rzp_test_xxxx'):
             raise Exception("Razorpay API keys are not configured. Please contact the administrator.")

        client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))
        order  = client.order.create({'amount': int(total*100), 'currency': 'INR',
            'receipt': f"ASC_{current_user.id}_{datetime.utcnow().timestamp():.0f}"})
        fy         = get_financial_year()
        receipt_no = generate_receipt_number()
        don = Donation(receipt_number=receipt_no, user_id=current_user.id,
            donation_date=datetime.utcnow().date(), payment_mode=PaymentMode.ONLINE,
            status='Pending', financial_year=fy, razorpay_order_id=order['id'],
            created_by=current_user.id)
        db.session.add(don)
        db.session.flush()
        for head, amt in items:
            db.session.add(DonationItem(donation_id=don.id, head=head, amount=amt))
        db.session.commit()
        return render_template('donor/payment_gateway.html',
            order=order, donation=don, total=total, razorpay_key=Config.RAZORPAY_KEY_ID)
    except Exception as e:
        import logging
        logging.error(f"Payment initiation error: {str(e)}")
        flash(f'Payment initiation failed: {str(e)}', 'danger')
        return redirect(url_for('donor.donate'))

@payment_bp.route('/verify', methods=['POST'])
@login_required
def verify():
    try:
        import razorpay
        client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))
        client.utility.verify_payment_signature({
            'razorpay_order_id':   request.form.get('razorpay_order_id'),
            'razorpay_payment_id': request.form.get('razorpay_payment_id'),
            'razorpay_signature':  request.form.get('razorpay_signature')})
        don = Donation.query.filter_by(
            razorpay_order_id=request.form.get('razorpay_order_id')).first()
        if don:
            don.status            = 'Confirmed'
            don.razorpay_payment_id = request.form.get('razorpay_payment_id')
            don.confirmed_at      = datetime.utcnow()
            db.session.commit()
            log_action(current_user.id, 'ONLINE_PAYMENT_CONFIRMED', 'Donation', don.id)
            flash('Payment successful! Thank you for your generous donation. 🙏', 'success')
            return redirect(url_for('donor.view_receipt', did=don.id))
        flash('Payment verified but record not found.', 'warning')
    except Exception:
        flash('Payment verification failed. Please contact the church office.', 'danger')
    return redirect(url_for('donor.dashboard'))

@payment_bp.route('/cancel/<int:did>', methods=['POST'])
@login_required
def cancel(did):
    don = Donation.query.filter_by(id=did, user_id=current_user.id, status='Pending').first_or_404()
    don.status = 'Cancelled'
    db.session.commit()
    flash('Payment cancelled.', 'info')
    return redirect(url_for('donor.dashboard'))
