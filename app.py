import os
import socket
import hashlib
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Initialize Flask app and configurations
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///file_sharing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'shared_treasures'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app.secret_key = os.urandom(24)


if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# Initialize the database
db = SQLAlchemy(app)

# Define the User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'user' or 'admin'

# Define the File model
class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), unique=True, nullable=False)
    size = db.Column(db.Integer, nullable=False)
    upload_time = db.Column(db.DateTime, nullable=False)

# Define the Log model
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    action = db.Column(db.String(200), nullable=False)  # "uploaded file.txt" or "deleted file.png"
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Login successful!', 'success')

            


            # Redirect to appropriate dashboard based on user role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))  # Regular user dashboard

        else:
            flash('Invalid credentials, please try again.', 'danger')

    return render_template('login.html')

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Hash the password before saving
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password, role=role)

        # Save user to the database
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')

            log_activity(f"User {username} registered successfully with role {role}.")
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", 'danger')

    return render_template('register.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


def log_activity(action):
    if 'username' in session:  # Check if the username is in the session
        username = session['username']  # Get the username from the session
        log_entry = Log(username=username, action=action, timestamp=datetime.utcnow())
        db.session.add(log_entry)
        db.session.commit()



# Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('You must be logged in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    files = File.query.all()  # Fetch all uploaded files from the database

    # Fetch logs if the user is an admin
    logs = []
    if session.get('role') == 'admin':
        logs = Log.query.all()  # Get all logs for admin

    return render_template('dashboard.html', files=files, logs=logs)

# File upload route
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        flash('Login required', 'warning')
        return redirect(url_for('login'))

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('dashboard'))

    if not allowed_file(file.filename):
        flash('Invalid file type', 'danger')
        return redirect(url_for('dashboard'))

    # Get file data
    filename = secure_filename(file.filename)
    file_data = file.read()
    file_size = len(file_data)
    file_hash = hashlib.sha256(file_data).hexdigest()
    original_name, ext = os.path.splitext(filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # check for duplicates in DB AND filesystem
    db_duplicate = File.query.filter_by(filename=filename).first()
    fs_duplicate = os.path.exists(os.path.join('shared_treasures', filename))
    
    if db_duplicate or fs_duplicate:
        action = request.form.get('duplicate_action', 'version')  # 'overwrite' or 'version'
        
        if action == 'overwrite':
            # Delete old records/files
            if db_duplicate:
                db.session.delete(db_duplicate)
            if fs_duplicate:
                os.remove(os.path.join('shared_treasures', filename))
            print(f"♻️ Overwriting existing file: {filename}")
        else:
            # Create new version (file_v2.pdf)
            version = 1
            while True:
                new_name = f"{original_name}_v{version}{ext}"
                if not File.query.filter_by(filename=new_name).first() and not os.path.exists(os.path.join('shared_treasures', new_name)):
                    filename = new_name
                    break
                version += 1
            print(f"🆕 Created new version: {filename}")
    
    with open(file_path, 'wb') as f:
        while chunk := file.read(1024):  # Read and write 1024 bytes at a time
            f.write(chunk)


    new_file = File(filename=filename, size=file_size, upload_time=datetime.utcnow())
    db.session.add(new_file)
    db.session.commit()
    log_activity(f'Uploaded file: {filename}')

    flash('File uploaded successfully', 'success')
    return redirect(url_for('dashboard'))

# Your provided download method
@app.route('/download/<filename>')
def download_file(filename):
    if 'user_id' not in session:
        flash('You must be logged in to download files.', 'warning')
        return redirect(url_for('login'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    else:
        flash("File not found!", "danger")
        return redirect(url_for('dashboard'))


# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/get_available_files', methods=['GET'])
def get_available_files():
    # Ensure you're checking the 'shared_treasures' directory for files
    shared_treasures_dir = 'shared_treasures'  # Adjust path if necessary
    if os.path.exists(shared_treasures_dir):
        files = os.listdir(shared_treasures_dir)  # List all files in the directory
        return {'files': files}
    else:
        return {'files': []}  # Return an empty list if the directory doesn't exist
    # Admin Dashboard Routes

# Admin Dashboard Route
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('You must be logged in as an admin to access this page.', 'warning')
        return redirect(url_for('login'))
    
    # Fetch all users, files, and activity logs
    users = User.query.all()
    files = File.query.all()
    logs = Log.query.all()
    
    return render_template('admin_dashboard.html', users=users, files=files, logs=logs)

# View and Delete Users
@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('You must be logged in as an admin to access this page.', 'warning')
        return redirect(url_for('login'))

    users = User.query.all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)  # Fetch the user or return a 404 error if not found
    try:
        log_activity(f"Deleted user: {user.username}")
        db.session.delete(user)  # Delete the user from the session
        db.session.commit()  # Commit the transaction to persist the changes
        return redirect(url_for('admin_dashboard'))  # Redirect back to the admin dashboard
    except Exception as e:
        db.session.rollback()  # Rollback the transaction if something goes wrong
        return f"There was an issue deleting the user: {str(e)}", 500


# View and Delete Files
@app.route('/admin/files')
def admin_files():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('You must be logged in as an admin to access this page.', 'warning')
        return redirect(url_for('login'))

    files = File.query.all()
    return render_template('admin_files.html', files=files)
SHARED_TREASURES = 'shared_treasures'  # Folder where files are stored

@app.route('/admin/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    file = File.query.get_or_404(file_id)
    
    try:
        # Generate the full file path from the 'shared_treasures' folder
        file_path = os.path.join(SHARED_TREASURES, file.filename)
        
        # Check if the file exists and delete it
        if os.path.exists(file_path):
            os.remove(file_path)  # Delete the file from the server
            log_activity(f'Deleted file: {file.filename}') 
        # Now delete the file record from the database
        db.session.delete(file)
        db.session.commit()
        
        
        
        return redirect(url_for('admin_dashboard'))  # Redirect to the admin dashboard
    except Exception as e:
        db.session.rollback()  # Rollback the transaction if there's any error
        return f"There was an issue deleting the file: {str(e)}", 500
# View Activity Logs
@app.route('/admin/logs')
def admin_logs():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('You must be logged in as an admin to access this page.', 'warning')
        return redirect(url_for('login'))
    
    logs = Log.query.all()
    return render_template('admin_logs.html', logs=logs)


# Run the Flask app
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
