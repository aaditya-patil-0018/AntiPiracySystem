from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
import os
from users import User
import json
import uuid
from fingerprint import VideoFingerprint
import hashlib
import time
import sqlite3
from watermark import VideoWatermarker
import shutil
import cv2
from contextlib import contextmanager
from encryption.video_encryption import VideoEncryption

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

# Initialize watermarker with the existing systems
watermarker = VideoWatermarker(
    font_scale=1.2,
    alpha=0.3,
    watermark_interval_sec=5
)

# Initialize encryption system with the other initializations
encryptor = VideoEncryption()

# Add this database connection manager
@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = sqlite3.connect('videos.db', timeout=20)  # Add timeout
        yield conn
    finally:
        if conn:
            conn.commit()
            conn.close()

# Modify the database initialization to include both original and processed videos
def init_video_database():
    conn = sqlite3.connect('videos.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_videos (
            video_id TEXT PRIMARY KEY,
            user_email TEXT,
            original_filename TEXT,
            processed_path TEXT,
            encrypted_path TEXT,
            encryption_key_path TEXT,
            upload_date TIMESTAMP,
            fingerprint TEXT,
            size_bytes INTEGER,
            duration_seconds FLOAT,
            status TEXT,
            FOREIGN KEY (user_email) REFERENCES users (email)
        )
    """)
    conn.commit()
    conn.close()

# Create necessary directories
def init_directories():
    dirs = ['uploads/original', 'uploads/processed']
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)

# Initialize everything at startup
init_directories()
init_video_database()
fingerprint_system = VideoFingerprint()
watermarker = VideoWatermarker(
    font_scale=1.2,
    alpha=0.3,
    watermark_interval_sec=5
)

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
        
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('getin.html')
            
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
        
        if not action or not username:
            flash('Invalid request parameters', 'error')
            return redirect(url_for('admin'))
            
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
        try:
            # Generate unique video ID
            timestamp = str(int(time.time()))
            random_uuid = str(uuid.uuid4())
            video_id = hashlib.sha256(f"{timestamp}{random_uuid}".encode()).hexdigest()
            print("1")

            # Setup filenames and paths
            original_filename = secure_filename(file.filename)
            file_extension = os.path.splitext(original_filename)[1]
            
            # Create unique filenames
            temp_original = f"temp_{video_id}{file_extension}"
            processed_name = f"processed_{video_id}{file_extension}"
            encrypted_name = f"encrypted_{video_id}{file_extension}.enc"
            key_name = f"key_{video_id}.key"
            
            # Setup paths
            temp_path = os.path.join('uploads/original', temp_original)
            processed_path = os.path.join('uploads/processed', processed_name)
            encrypted_path = os.path.join('uploads/processed', encrypted_name)
            key_path = os.path.join('uploads/processed', key_name)
            
            try:
                # Save original file temporarily
                file.save(temp_path)
                
                # Generate fingerprint
                fingerprint_result = fingerprint_system.store_video(temp_path)
                if not fingerprint_result['success']:
                    raise Exception(fingerprint_result['message'])
                
                # Apply watermark
                watermark_result = watermarker.apply_watermark(
                    input_path=temp_path,
                    output_path=processed_path,
                    watermark_text=f"Protected - {video_id[:8]}"
                )
                if not watermark_result['success']:
                    raise Exception(watermark_result['message'])
                
                # Encrypt the watermarked video
                encryption_result = encryptor.encrypt_file(
                    input_path=processed_path,
                    output_path=encrypted_path
                )
                if not encryption_result['success']:
                    raise Exception(encryption_result['message'])
                
                # Save encryption key
                key_result = encryptor.save_key(key_path)
                if not key_result['success']:
                    raise Exception(key_result['message'])
                print("11")
                # Get video metadata
                cap = cv2.VideoCapture(temp_path)
                size_bytes = os.path.getsize(temp_path)
                duration_seconds = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
                cap.release()
                
                # Store video information in database
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO user_videos (
                            video_id, user_email, original_filename,
                            processed_path, encrypted_path, encryption_key_path,
                            upload_date, fingerprint, size_bytes,
                            duration_seconds, status
                        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
                    """, (
                        video_id, session['user']['email'], original_filename,
                        processed_path, encrypted_path, key_path,
                        fingerprint_result['fingerprint'], size_bytes,
                        duration_seconds, 'completed'
                    ))
                
                # Delete temporary original file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                return {
                    'success': True,
                    'message': 'File uploaded, processed, and encrypted successfully',
                    'video_id': video_id,
                    'fingerprint': fingerprint_result['fingerprint']
                }
                
            except Exception as process_error:
                # Clean up all files on error
                for path in [temp_path, processed_path, encrypted_path, key_path]:
                    if os.path.exists(path):
                        os.remove(path)
                raise Exception(f"Processing error: {str(process_error)}")
            
        except Exception as e:
            # Clean up any files that might have been created
            for path in [temp_path, processed_path, encrypted_path, key_path]:
                if 'path' in locals() and os.path.exists(path):
                    os.remove(path)
            return {'success': False, 'message': f'Error: {str(e)}'}, 500
    
    return {'success': False, 'message': 'File type not allowed'}, 400

@app.route('/videos')
def get_user_videos():
    if 'user' not in session:
        return {'success': False, 'message': 'User not authenticated'}, 401
        
    try:
        conn = sqlite3.connect('videos.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT video_id, original_filename, upload_date, fingerprint 
            FROM user_videos 
            WHERE user_email = ? 
            ORDER BY upload_date DESC
        """, (session['user']['email'],))
        
        videos = [{
            'video_id': row[0],
            'filename': row[1],
            'upload_date': row[2],
            'fingerprint': row[3]
        } for row in cursor.fetchall()]
        
        conn.close()
        return {'success': True, 'videos': videos}
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return {'success': False, 'message': str(e)}, 500

@app.route('/download/<video_id>/<version>')
def download_video(video_id, version):
    if 'user' not in session:
        return redirect(url_for('getin'))
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT processed_path, encrypted_path, encryption_key_path, original_filename
                FROM user_videos 
                WHERE video_id = ? AND user_email = ?
            """, (video_id, session['user']['email']))
            
            result = cursor.fetchone()
            
            if not result:
                return {'success': False, 'message': 'Video not found or access denied'}, 404
            
            processed_path, encrypted_path, key_path, original_filename = result
            
            if version == 'processed':
                # For processed version, decrypt the encrypted file
                try:
                    # Initialize encryptor with the saved key
                    temp_encryptor = VideoEncryption(key_path=key_path)
                    
                    # Create temporary file for decryption
                    temp_path = f"uploads/processed/temp_download_{video_id}.mp4"
                    
                    # Decrypt the file
                    decrypt_result = temp_encryptor.decrypt_file(
                        input_path=encrypted_path,
                        output_path=temp_path
                    )
                    
                    if not decrypt_result['success']:
                        raise Exception(decrypt_result['message'])
                    
                    # Send the decrypted file
                    response = send_file(
                        temp_path,
                        as_attachment=True,
                        download_name=f"protected_{original_filename}"
                    )
                    
                    # Delete temporary file after sending
                    os.remove(temp_path)
                    return response
                    
                except Exception as e:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    raise Exception(f"Decryption error: {str(e)}")
                    
            else:
                return {'success': False, 'message': 'Invalid version specified'}, 400
            
    except Exception as e:
        return {'success': False, 'message': f'Error downloading file: {str(e)}'}, 500

@app.route('/video/<video_id>')
def view_video(video_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    video_id, original_filename, upload_date,
                    fingerprint, size_bytes, duration_seconds,
                    status
                FROM user_videos 
                WHERE video_id = ?
            """, (video_id,))
            
            result = cursor.fetchone()
            
            if not result:
                flash('Video not found', 'error')
                return redirect(url_for('index'))
                
            video = {
                'video_id': result[0],
                'filename': result[1],
                'upload_date': result[2],
                'fingerprint': result[3],
                'size_mb': round(result[4] / (1024 * 1024), 2),
                'duration': round(result[5], 2),
                'status': result[6]
            }
            
            return render_template('video_share.html', video=video)
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)