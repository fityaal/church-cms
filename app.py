from flask import Flask, redirect, url_for, jsonify
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_migrate import Migrate
from models import db, User
from config import Config
from datetime import datetime
import os
from werkzeug.middleware.proxy_fix import ProxyFix

login_manager = LoginManager()
mail          = Mail()
migrate       = Migrate()


def _bootstrap_defaults():
    # Create tables on first startup. Production user creation is handled by
    # create_admin.py so default credentials are never published by the app.
    from models import db, User, UserRole, ExpenditureHead

    db.create_all()

    if not getattr(Config, "SEED_DEFAULTS", False):
        if ExpenditureHead.query.count() == 0:
            default_heads = [
                'Salary & Staff', 'Building Maintenance', 'Utilities & Bills',
                'Worship & Sacraments', 'Outreach & Mission',
                'Education & Sunday School', 'Administration',
                'Charity & Welfare', 'Capital Expenditure', 'Other Expenses'
            ]
            for head in default_heads:
                db.session.add(ExpenditureHead(name=head))
            db.session.commit()
        return

    if User.query.count() == 0:
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

    if ExpenditureHead.query.count() == 0:
        default_heads = [
            'Salary & Staff', 'Building Maintenance', 'Utilities & Bills',
            'Worship & Sacraments', 'Outreach & Mission',
            'Education & Sunday School', 'Administration',
            'Charity & Welfare', 'Capital Expenditure', 'Other Expenses'
        ]
        for head in default_heads:
            db.session.add(ExpenditureHead(name=head))

    db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set before starting the application.")

    # Render terminates TLS at its edge; trust the forwarded host/proto headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view          = 'auth.login'
    login_manager.login_message       = 'Please login to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(uid):
        return User.query.get(int(uid))

    # Jinja2 globals & filters
    from models import DonationHead
    app.jinja_env.globals['now']         = datetime.utcnow()
    app.jinja_env.globals['heads_order'] = list(DonationHead)

    def do_enumerate(iterable, start=0):
        return enumerate(iterable, start)

    app.jinja_env.globals['enumerate'] = do_enumerate
    app.jinja_env.filters['enumerate'] = do_enumerate

    # Blueprints
    from blueprints.auth    import auth_bp
    from blueprints.admin   import admin_bp
    from blueprints.donor   import donor_bp
    from blueprints.payment import payment_bp
    from blueprints.api     import api_bp
    from blueprints.errors  import errors_bp

    app.register_blueprint(auth_bp,    url_prefix='/auth')
    app.register_blueprint(admin_bp,   url_prefix='/admin')
    app.register_blueprint(donor_bp,   url_prefix='/donor')
    app.register_blueprint(payment_bp, url_prefix='/payment')
    app.register_blueprint(api_bp,     url_prefix='/api')
    app.register_blueprint(errors_bp)

    with app.app_context():
        _bootstrap_defaults()

    @app.route('/health')
    def health():
        return jsonify(status="ok", service="church-cms")

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('admin.dashboard') if current_user.is_staff
                            else url_for('donor.dashboard'))
        return redirect(url_for('auth.login'))

    return app
