from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

# Initialize Flask app and configurations
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///file_sharing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app.secret_key = os.urandom(24)

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

# Initialize the database
with app.app_context():
    db.create_all()

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
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials, please try again.', 'danger')

    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('You must be logged in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    files = File.query.all()

    # Fetch logs if the user is an admin
    logs = []
    if session.get('role') == 'admin':
        logs = Log.query.all()  # Get all logs for admin

    return render_template('dashboard.html', files=files, logs=logs)

# File upload route
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        flash('You must be logged in to upload files.', 'warning')
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['file']

    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('dashboard'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        new_file = File(
            filename=filename,
            size=os.path.getsize(filepath),
            upload_time=datetime.now()
        )
        db.session.add(new_file)
        db.session.commit()

        # Log the upload action
        log = Log(username=session['username'], action=f"uploaded {filename}", timestamp=datetime.utcnow())
        db.session.add(log)
        db.session.commit()

        flash('File uploaded successfully', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('File type not allowed. Please upload a valid file.', 'danger')
        return redirect(url_for('dashboard'))

# Download file route
@app.route('/download/<filename>')
def download_file(filename):
    if 'user_id' not in session:
        flash('You must be logged in to download files.', 'warning')
        return redirect(url_for('login'))
    
    try:
        # Use absolute path and force download
        upload_folder = os.path.abspath(app.config['UPLOAD_FOLDER'])
        return send_from_directory(upload_folder, filename, as_attachment=True)
    except FileNotFoundError:
        flash(f'File "{filename}" not found.', 'danger')
        return redirect(url_for('dashboard'))

# Delete file route (for admin only)
@app.route('/delete/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    if 'role' not in session or session['role'] != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('dashboard'))

    file = File.query.get_or_404(file_id)

    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    except FileNotFoundError:
        pass  # File already deleted

    db.session.delete(file)
    db.session.commit()

    # Log the delete action
    log = Log(username=session['username'], action=f"deleted {file.filename}", timestamp=datetime.utcnow())
    db.session.add(log)
    db.session.commit()

    flash('File deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists, please choose another.', 'danger')
        else:
            role = 'user'
            if 'role' in session and session['role'] == 'admin':
                role = request.form['role']

            new_user = User(username=username, password=hashed_password, role=role)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Run the Flask app
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
