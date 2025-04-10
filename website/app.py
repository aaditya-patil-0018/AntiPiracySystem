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
from deepwater import PremiumWatermarker
from watermark_detector import WatermarkDetector

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Configure admin credentials
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin"

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Admin credentials (in production, use environment variables)
ADMIN_USERNAME = "admin"

# Initialize user manager
user_manager = User()

# Initialize watermarker with the existing systems
watermarker = VideoWatermarker(
    font_scale=1.2,
    alpha=0.3,
    watermark_interval_sec=5
)

# Initialize premium watermarker (deepwater)
premium_watermarker = PremiumWatermarker(
    secret_key="corporate_secure_key_2024"
)

# Initialize watermark detector
watermark_detector = WatermarkDetector()

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

@app.route('/admin-login', methods=["GET", "POST"])
def admin_login():
    """Admin login page with dedicated credentials."""
    # Check if admin is already logged in
    if 'admin' in session:
        return redirect(url_for('admin'))
        
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            # Create admin session
            session['admin'] = {
                'email': email,
                'is_admin': True
            }
            flash('Admin login successful', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid admin credentials', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin-logout')
def admin_logout():
    """Admin logout function."""
    session.pop('admin', None)
    flash('Admin logged out successfully', 'info')
    return redirect(url_for('admin_login'))

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
    # Check if admin is logged in with dedicated admin session
    if 'admin' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))

    if request.method == "POST":
        action = request.form.get('action')
        username = request.form.get('username')
        
        if not action or not username:
            flash('Invalid request parameters', 'error')
            return redirect(url_for('admin'))
            
        if action == 'delete':
            result = user_manager.delete_user(username)
            flash(result['message'], 'success' if result['success'] else 'error')
        elif action == 'toggle_active':
            user = user_manager.get_user_by_username(username)
            if user:
                new_status = not user['is_active']
                result = user_manager.update_user(username, is_active=new_status)
                flash(result['message'], 'success' if result['success'] else 'error')

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
            deepwater_name = f"deepwater_{video_id}{file_extension}"
            encrypted_name = f"encrypted_{video_id}{file_extension}.enc"
            key_name = f"key_{video_id}.key"
            
            # Setup paths
            temp_path = os.path.join('uploads/original', temp_original)
            processed_path = os.path.join('uploads/processed', processed_name)
            deepwater_path = os.path.join('uploads/processed', deepwater_name)
            encrypted_path = os.path.join('uploads/processed', encrypted_name)
            key_path = os.path.join('uploads/processed', key_name)
            
            try:
                # Save original file temporarily
                file.save(temp_path)
                
                # Generate fingerprint
                fingerprint_result = fingerprint_system.store_video(temp_path)
                if not fingerprint_result['success']:
                    raise Exception(fingerprint_result['message'])
                
                # Apply visible watermark
                watermark_result = watermarker.apply_watermark(
                    input_path=temp_path,
                    output_path=processed_path,
                    watermark_text=f"Protected - {session['user']['id']}.{session['user']['created_at'].replace('-','').replace(' ', '').replace(':', '')}"
                )
                if not watermark_result['success']:
                    raise Exception(watermark_result['message'])
                
                # Apply deep watermark with user ID
                user_id = session['user']['id']
                premium_watermarker.user_id = user_id
                try:
                    premium_watermarker.embed_video(
                        input_path=processed_path,
                        output_path=deepwater_path
                    )
                    actual_deepwater_path = deepwater_path
                except Exception as dw_error:
                    # If deepwater fails, use the regular watermarked file instead
                    actual_deepwater_path = processed_path
                    print(f"Deepwater watermarking failed: {str(dw_error)}")
                
                # Encrypt the watermarked video
                encryption_result = encryptor.encrypt_file(
                    input_path=actual_deepwater_path,
                    output_path=encrypted_path
                )
                if not encryption_result['success']:
                    raise Exception(encryption_result['message'])
                
                # Save encryption key
                key_result = encryptor.save_key(key_path)
                if not key_result['success']:
                    raise Exception(key_result['message'])
                
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
                        actual_deepwater_path, encrypted_path, key_path,
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
                for path in [temp_path, processed_path, deepwater_path, encrypted_path, key_path]:
                    if os.path.exists(path):
                        os.remove(path)
                raise Exception(f"Processing error: {str(process_error)}")
            
        except Exception as e:
            # Clean up any files that might have been created
            for path in [temp_path, processed_path, deepwater_path, encrypted_path, key_path]:
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
                WHERE video_id = ?
            """, (video_id,))
            
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

                    # Apply visible watermark if needed - keeping this for compatibility
                    if not os.path.exists(processed_path):
                        watermark_result = watermarker.apply_watermark(
                            input_path=temp_path,
                            output_path=f"uploads/processed/processed_{video_id}.mp4",
                            watermark_text=f"Protected - {session['user']['id']}.{session['user']['created_at'].replace('-','').replace(' ', '').replace(':', '')}"
                        )
                        if not watermark_result['success']:
                            raise Exception(watermark_result['message'])
                        send_path = f"uploads/processed/processed_{video_id}.mp4"
                    else:
                        send_path = temp_path

                    # Send the decrypted file
                    response = send_file(
                        send_path,
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

@app.route('/my-videos')
def my_videos():
    """Show all videos uploaded by the current user."""
    if 'user' not in session:
        flash('Please log in to access your videos.', 'error')
        return redirect(url_for('getin'))
        
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get all videos for this user
            cursor.execute("""
                SELECT 
                    video_id, original_filename, upload_date,
                    fingerprint, size_bytes, duration_seconds,
                    status
                FROM user_videos 
                WHERE user_email = ? 
                ORDER BY upload_date DESC
            """, (session['user']['email'],))
            
            videos_data = cursor.fetchall()
            
            videos = [{
                'video_id': row[0],
                'filename': row[1],
                'upload_date': row[2],
                'fingerprint': row[3],
                'size_mb': round(row[4] / (1024 * 1024), 2),
                'duration': round(row[5], 2),
                'status': row[6]
            } for row in videos_data]
            
            # Calculate stats
            stats = {
                'total_videos': len(videos),
                'total_size': round(sum(v['size_mb'] for v in videos), 2),
                'total_duration': round(sum(v['duration'] for v in videos) / 60, 2),  # Convert to minutes
                'latest_upload_date': videos[0]['upload_date'] if videos else "No uploads yet"
            }
            
            return render_template('my_videos.html', videos=videos, stats=stats)
            
    except Exception as e:
        flash(f'Error loading videos: {str(e)}', 'error')
        return redirect(url_for('userdashboard'))

@app.route('/delete-video/<video_id>', methods=['POST'])
def delete_video(video_id):
    """Delete a video and all associated files."""
    if 'user' not in session:
        return {'success': False, 'message': 'User not authenticated'}, 401
        
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First check if video exists and belongs to user
            cursor.execute("""
                SELECT processed_path, encrypted_path, encryption_key_path 
                FROM user_videos 
                WHERE video_id = ? AND user_email = ?
            """, (video_id, session['user']['email']))
            
            result = cursor.fetchone()
            
            if not result:
                return {'success': False, 'message': 'Video not found or permission denied'}, 404
                
            processed_path, encrypted_path, key_path = result
            
            # Delete files
            for path in [processed_path, encrypted_path, key_path]:
                if path and os.path.exists(path):
                    os.remove(path)
            
            # Delete from database
            cursor.execute("DELETE FROM user_videos WHERE video_id = ?", (video_id,))
            
            return {'success': True, 'message': 'Video deleted successfully'}
            
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/video-info/<video_id>')
def get_video_info(video_id):
    """API endpoint to get information about a video by its ID."""
    if 'user' not in session:
        return {'success': False, 'message': 'User not authenticated'}, 401
        
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
                return {'success': False, 'message': 'Video not found'}, 404
                
            video = {
                'video_id': result[0],
                'filename': result[1],
                'upload_date': result[2],
                'fingerprint': result[3],
                'size_mb': round(result[4] / (1024 * 1024), 2),
                'duration': round(result[5], 2),
                'status': result[6]
            }
            
            return {'success': True, 'video': video}
            
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/admin/detect-watermark', methods=['GET', 'POST'])
def admin_detect_watermark():
    """Admin function to detect watermarks in uploaded videos."""
    # Check if admin is logged in
    if 'admin' not in session:
        flash('Admin access required.', 'error')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        # Process the uploaded video for watermark detection
        if 'video' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['video']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            try:
                # Save the file temporarily
                temp_filename = secure_filename(file.filename)
                temp_path = os.path.join('uploads/original', f"detect_{temp_filename}")
                file.save(temp_path)
                
                # Get list of users for detection
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    # Get user IDs from the user_videos table instead of users table
                    cursor.execute("SELECT DISTINCT user_email FROM user_videos")
                    user_emails = [row[0] for row in cursor.fetchall()]
                    
                    # Map emails to IDs for watermark detection
                    user_ids = []
                    for email in user_emails:
                        cursor.execute("SELECT video_id FROM user_videos WHERE user_email = ? LIMIT 1", (email,))
                        id_row = cursor.fetchone()
                        if id_row:
                            user_ids.append(str(id_row[0]))
                
                # Detect watermarks
                detection_results = {}
                
                # Check for deepwater watermark
                try:
                    # Detect master watermark (corporate)
                    corporate_detector = PremiumWatermarker(
                        secret_key="corporate_secure_key_2024"
                    )
                    deepwater_result = corporate_detector.detect_watermarks(temp_path)
                    detection_results['premium'] = deepwater_result
                    
                    # For each user, try detecting their watermark
                    best_user_match = None
                    best_confidence = 0
                    
                    for user_id in user_ids:
                        user_detector = PremiumWatermarker(
                            secret_key="corporate_secure_key_2024",
                            user_id=user_id
                        )
                        user_result = user_detector.detect_watermarks(temp_path)
                        if user_result['user']['detected'] and user_result['user']['confidence'] > best_confidence:
                            best_user_match = user_id
                            best_confidence = user_result['user']['confidence']
                    
                    if best_user_match:
                        detection_results['premium']['user']['id'] = best_user_match
                        detection_results['premium']['user']['detected'] = True
                        detection_results['premium']['user']['confidence'] = best_confidence
                    
                except Exception as e:
                    detection_results['premium'] = {
                        'error': str(e),
                        'master': {'detected': False, 'confidence': 0.0},
                        'user': {'detected': False, 'confidence': 0.0, 'id': None}
                    }
                
                # Check for standard watermark using detector
                try:
                    detector = WatermarkDetector()
                    standard_result = detector.detect_user(temp_path, user_ids)
                    detection_results['standard'] = standard_result
                except Exception as e:
                    detection_results['standard'] = {
                        'error': str(e),
                        'detected': False, 
                        'user_id': None, 
                        'confidence': 0.0
                    }
                
                # Clean up
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                # If user identified, get their details
                identified_user = None
                user_id = None
                
                if detection_results['premium']['user']['detected']:
                    user_id = detection_results['premium']['user']['id']
                elif detection_results['standard']['detected']:
                    user_id = detection_results['standard']['user_id']
                
                if user_id:
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        # Query user_videos by video_id
                        cursor.execute("SELECT user_email, video_id, upload_date FROM user_videos WHERE video_id = ?", (user_id,))
                        user_data = cursor.fetchone()
                        if not user_data:
                            # Try as partial match in case we only have a prefix
                            cursor.execute("SELECT user_email, video_id, upload_date FROM user_videos WHERE video_id LIKE ?", (f"{user_id}%",))
                            user_data = cursor.fetchone()
                            
                        if user_data:
                            identified_user = {
                                'id': user_id,
                                'email': user_data[0],
                                'video_id': user_data[1],
                                'upload_date': user_data[2]
                            }
                
                return render_template(
                    'watermark_detection.html', 
                    results=detection_results,
                    identified_user=identified_user
                )
                
            except Exception as e:
                flash(f'Error during detection: {str(e)}', 'error')
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
    
    # GET request - show the upload form
    return render_template('watermark_detection.html')

if __name__ == '__main__':
    app.run(debug=True)