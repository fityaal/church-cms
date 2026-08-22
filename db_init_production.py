import os
from app import create_app
from config import ProductionConfig
from models import db, User, UserRole, ExpenditureHead


def main():
    app = create_app(ProductionConfig)
    with app.app_context():
        db.create_all()
        if ExpenditureHead.query.count() == 0:
            heads = [
                "Salary & Staff", "Building Maintenance", "Utilities & Bills",
                "Worship & Sacraments", "Outreach & Mission",
                "Education & Sunday School", "Administration",
                "Charity & Welfare", "Capital Expenditure", "Other Expenses"
            ]
            db.session.add_all([ExpenditureHead(name=h) for h in heads])
        db.session.commit()
        print("Database tables and expenditure heads are ready.")
        print(f"Users currently in database: {User.query.count()}")


if __name__ == "__main__":
    main()
