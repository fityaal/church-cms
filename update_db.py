from app import create_app
from models import db, ExpenditureHead, Expense
from config import DevelopmentConfig
from sqlalchemy import text

def update_db():
    app = create_app(DevelopmentConfig)
    with app.app_context():
        print("⚙️  Updating database schema...")
        
        # 1. Create missing tables (this will create expenditure_heads)
        db.create_all()
        print("✅  Missing tables created.")

        # 2. Alter expenses table to change category to VARCHAR(100)
        # We use raw SQL because SQLAlchemy won't automatically alter existing columns with create_all()
        try:
            db.session.execute(text("ALTER TABLE expenses MODIFY category VARCHAR(100)"))
            db.session.commit()
            print("✅  Altered expenses table (category column).")
        except Exception as e:
            print(f"⚠️   Note: Could not alter expenses table (it might already be VARCHAR). Error: {e}")
            db.session.rollback()

        # 3. Seed expenditure_heads if empty
        if ExpenditureHead.query.count() == 0:
            print("🌱  Seeding default expenditure heads...")
            default_heads = [
                'Salary & Staff',
                'Building Maintenance',
                'Utilities & Bills',
                'Worship & Sacraments',
                'Outreach & Mission',
                'Education & Sunday School',
                'Administration',
                'Charity & Welfare',
                'Capital Expenditure',
                'Other Expenses'
            ]
            for head_name in default_heads:
                db.session.add(ExpenditureHead(name=head_name))
            db.session.commit()
            print("✅  Default expenditure heads seeded.")
        
        print("🎉  Database update complete!")

if __name__ == "__main__":
    update_db()
