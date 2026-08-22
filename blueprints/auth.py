from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from models import User, UserRole, db
from utils.helpers import generate_otp, log_action
from datetime import datetime, timedelta
from config import Config

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard') if current_user.is_staff else url_for('donor.dashboard'))

    if request.method == 'POST':
        mobile   = request.form.get('mobile', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(mobile=mobile).first()
        if user and user.is_active and user.check_password(password):
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            log_action(user.id, 'LOGIN', ip=request.remote_addr)

            if user.must_change_password:
                flash('Welcome! Please set a new password to continue.', 'warning')
                return redirect(url_for('auth.change_password'))

            next_page = request.args.get('next')
            return redirect(next_page or (url_for('admin.dashboard') if user.is_staff else url_for('donor.dashboard')))
        else:
            flash('Invalid mobile number or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log_action(current_user.id, 'LOGOUT', ip=request.remote_addr)
    logout_user()
    flash('You have been logged out. God bless you!', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        cur  = request.form.get('current_password', '')
        new  = request.form.get('new_password', '')
        conf = request.form.get('confirm_password', '')

        if not current_user.check_password(cur):
            flash('Current password is incorrect.', 'danger')
        elif new != conf:
            flash('New passwords do not match.', 'danger')
        elif len(new) < 8:
            flash('Password must be at least 8 characters.', 'danger')
        else:
            current_user.set_password(new)
            current_user.must_change_password = False
            db.session.commit()
            log_action(current_user.id, 'PASSWORD_CHANGED', ip=request.remote_addr)
            flash('Password updated successfully!', 'success')
            return redirect(url_for('admin.dashboard') if current_user.is_staff else url_for('donor.dashboard'))

    return render_template('auth/change_password.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    step = request.form.get('step', '1') if request.method == 'POST' else '1'

    if request.method == 'POST' and step == '1':
        mobile = request.form.get('mobile', '').strip()
        user   = User.query.filter_by(mobile=mobile, is_active=True).first()
        if user:
            otp = generate_otp()
            user.otp_code  = otp
            user.otp_expiry = datetime.utcnow() + timedelta(minutes=Config.OTP_EXPIRY_MINUTES)
            db.session.commit()
            # TODO: Send OTP via SMS gateway
            flash(f'[Dev] OTP for {mobile}: {otp}', 'info')
            session['reset_mobile'] = mobile
            return render_template('auth/forgot_password.html', step=2)
        flash('Mobile number not registered.', 'danger')

    elif request.method == 'POST' and step == '2':
        mobile = session.get('reset_mobile', '')
        otp    = request.form.get('otp', '').strip()
        new_pw = request.form.get('new_password', '')
        conf   = request.form.get('confirm_password', '')
        user   = User.query.filter_by(mobile=mobile).first()

        if not user:
            flash('Session expired. Try again.', 'danger')
            return redirect(url_for('auth.forgot_password'))
        if user.otp_code != otp or not user.otp_expiry or datetime.utcnow() > user.otp_expiry:
            flash('Invalid or expired OTP.', 'danger')
            return render_template('auth/forgot_password.html', step=2)
        if new_pw != conf or len(new_pw) < 8:
            flash('Passwords do not match or too short.', 'danger')
            return render_template('auth/forgot_password.html', step=2)

        user.set_password(new_pw)
        user.must_change_password = False
        user.otp_code  = None
        user.otp_expiry = None
        db.session.commit()
        session.pop('reset_mobile', None)
        flash('Password reset successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', step=1)
