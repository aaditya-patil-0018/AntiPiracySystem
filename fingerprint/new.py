import cv2
import hashlib
import sqlite3
import os

def generate_video_fingerprint(video_path):
    """Generates a unique fingerprint for a video file using SHA-256 hashing."""
    hash_sha256 = hashlib.sha256()
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % 30 == 0:  # Sample every 30th frame for hashing
            frame_bytes = cv2.imencode('.jpg', frame)[1].tobytes()
            hash_sha256.update(frame_bytes)
        
        frame_count += 1
    
    cap.release()
    return hash_sha256.hexdigest()

def store_video_and_fingerprint(video_path, fingerprint):
    """Stores the video and its fingerprint in an SQLite database."""
    conn = sqlite3.connect("fingerprints.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_name TEXT,
            fingerprint TEXT UNIQUE,
            video BLOB,
            video_path TEXT
        )
    """)
    
    with open(video_path, 'rb') as file:
        video_data = file.read()
    
    try:
        cursor.execute("INSERT INTO video_fingerprints (video_name, fingerprint, video, video_path) VALUES (?, ?, ?, ?)", 
                       (os.path.basename(video_path), fingerprint, video_data, video_path))
        conn.commit()
        print(f"Fingerprint and video for '{os.path.basename(video_path)}' stored successfully!")
    except sqlite3.IntegrityError:
        print("Error: This fingerprint already exists in the database.")
    
    conn.close()

def main():
    video_path = input("Enter the path of the video file: ")
    if not os.path.exists(video_path):
        print("Error: File does not exist.")
        return
    
    fingerprint = generate_video_fingerprint(video_path)
    store_video_and_fingerprint(video_path, fingerprint)

if __name__ == "__main__":
    main()