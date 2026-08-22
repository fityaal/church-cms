import os
import getpass
from app import create_app
from config import ProductionConfig
from models import db, User, UserRole


def main():
    app = create_app(ProductionConfig)
    with app.app_context():
        db.create_all()
        mobile = os.environ.get("INITIAL_ADMIN_MOBILE", "").strip() or input("Admin mobile: ").strip()
        name = os.environ.get("INITIAL_ADMIN_NAME", "Church Administrator").strip()
        email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip() or None
        password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
        if not password:
            password = getpass.getpass("Admin password (min 8 chars): ")
        if len(password) < 8:
            raise SystemExit("Password must contain at least 8 characters.")
        if User.query.filter_by(mobile=mobile).first():
            raise SystemExit("A user with this mobile number already exists.")
        user = User(mobile=mobile, full_name=name, email=email, role=UserRole.ADMIN,
                    must_change_password=False, is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print("Admin account created successfully.")


if __name__ == "__main__":
    main()
