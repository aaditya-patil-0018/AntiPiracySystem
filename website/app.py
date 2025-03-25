from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
import os
from users import User
import json
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Admin credentials (in production, use environment variables)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Initialize user manager
user_manager = User()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/getin', methods=["GET", "POST"])
def getin():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        
        # First check if user exists by email
        user = user_manager.get_user_by_email(email)
        
        if user:
            # User exists, attempt login
            result = user_manager.login(user['username'], password)
            if result['success']:
                session['user'] = result['user']
                # flash('Login successful!', 'success')
                return redirect(url_for('userdashboard'))
            else:
                flash(result['message'], 'error')
        else:
            # User doesn't exist, attempt registration
            # Generate username from email
            username = email.split('@')[0]
            result = user_manager.register(username, email, password)
            if result['success']:
                # Auto login after registration
                login_result = user_manager.login(username, password)
                if login_result['success']:
                    session['user'] = login_result['user']
                    # flash('Registration and login successful!', 'success')
                    return redirect(url_for('userdashboard'))
            else:
                flash(result['message'], 'error')
                
    return render_template('getin.html')

@app.route("/userdashboard")
def userdashboard():
    if 'user' not in session:
        # flash('Please log in to access your dashboard.', 'error')
        return redirect(url_for('getin'))
    return render_template('userdashboard.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    # flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin', methods=["GET", "POST"])
def admin():
    # Check if user is logged in as admin
    if 'user' not in session or session['user']['username'] != ADMIN_USERNAME:
        # flash('Admin access required.', 'error')
        return redirect(url_for('getin'))

    if request.method == "POST":
        action = request.form.get('action')
        username = request.form.get('username')
        
        if action == 'delete':
            result = user_manager.delete_user(username)
            # flash(result['message'], 'success' if result['success'] else 'error')
        elif action == 'toggle_active':
            user = user_manager.get_user_by_username(username)
            if user:
                new_status = not user['is_active']
                result = user_manager.update_user(username, is_active=new_status)
                # flash(result['message'], 'success' if result['success'] else 'error')

    # Get all users for display
    users = user_manager.get_all_users()
    return render_template('admin.html', users=users)

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'user' not in session:
        return {'success': False, 'message': 'User not authenticated'}, 401
    
    if 'video' not in request.files:
        return {'success': False, 'message': 'No file part'}, 400
    
    file = request.files['video']
    if file.filename == '':
        return {'success': False, 'message': 'No selected file'}, 400
    
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        try:
            file.save(filepath)
            # Here you would typically process the video (encryption, watermarking, etc.)
            return {
                'success': True,
                'message': 'File uploaded successfully',
                'filename': filename,
                'filepath': filepath
            }
        except Exception as e:
            return {'success': False, 'message': f'Error saving file: {str(e)}'}, 500
    
    return {'success': False, 'message': 'File type not allowed'}, 400

@app.route('/download/<filename>')
def download_video(filename):
    if 'user' not in session:
        # flash('Please login to download files.', 'error')
        return redirect(url_for('getin'))
    
    try:
        return send_file(
            os.path.join(app.config['UPLOAD_FOLDER'], filename),
            as_attachment=True
        )
    except Exception as e:
        # flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('userdashboard'))

if __name__ == '__main__':
    app.run(debug=True)