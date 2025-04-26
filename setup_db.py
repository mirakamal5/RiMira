from app import app, db, User, Log  # Import Log model
from werkzeug.security import generate_password_hash
from datetime import datetime

def setup_database():
    with app.app_context():  # Ensure we are within the application context
        # Drop all existing tables (optional if you want a clean start)
        db.drop_all()
        
        # Create all tables (including Log table)
        db.create_all()

        # Create an admin user
        admin_user = User(
            username='admin',
            password=generate_password_hash('admin123', method='pbkdf2:sha256'),
            role='admin'
        )

        # Add the admin user to the database
        db.session.add(admin_user)
        db.session.commit()

        # Optionally, add a log entry for the database setup (for demonstration)
        log_entry = Log(
            username='admin',
            action='Set up the database and created the admin user',
            timestamp=datetime.utcnow()
        )
        db.session.add(log_entry)
        db.session.commit()

        print('✅ Database setup complete! Admin user created (username: admin, password: admin123)')

if __name__ == '__main__':
    setup_database()
