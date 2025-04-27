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
            return redirect(url_for('dashboard'))
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
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", 'danger')

    return render_template('register.html')

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
                if not File.query.filter_by(filename=new_name).first() and \
                   not os.path.exists(os.path.join('shared_treasures', new_name)):
                    filename = new_name
                    break
                version += 1
            print(f"🆕 Created new version: {filename}")
    else:
        pass

    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    new_file = File(filename=filename, size=file_size, upload_time=datetime.utcnow())
    db.session.add(new_file)
    db.session.commit()

    flash('File uploaded successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/download/<filename>')
def download_file(filename):
    if 'user_id' not in session:
        flash('You must be logged in to download files.', 'warning')
        return redirect(url_for('login'))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Connect to the server
        s.connect(('localhost', 5559))  # Use the server's IP and port

        # Send the custom protocol command
        s.send(f"REVEAL {filename}".encode())

        # Wait for the server's response (file details or error)
        response = s.recv(1024).decode()

        if response.startswith("READY"):
            # The server is ready to send the file
            file_size, file_hash = response.split()[1:3]
            file_data = b"" 
            while True:
                chunk = s.recv(1024)
                if not chunk:
                    break
                file_data += chunk

            # Save the file to a location on the Flask server
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(file_path, 'wb') as f:
                f.write(file_data)

            # After downloading, save to database and serve the file
            file_size = os.path.getsize(file_path)
            new_file = File(
                filename=filename,
                size=file_size,
                upload_time=datetime.now()
            )
            db.session.add(new_file)
            db.session.commit()

            # Log the download action
            log = Log(username=session['username'], action=f"downloaded {filename}", timestamp=datetime.utcnow())
            db.session.add(log)
            db.session.commit()

            # After downloading, send the file to the client (browser)
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
        else:
            flash('File not found or error during download', 'danger')
            return redirect(url_for('dashboard'))

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Run the Flask app
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
