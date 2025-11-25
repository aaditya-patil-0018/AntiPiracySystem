import cv2
import hashlib
import sqlite3
import os

class VideoFingerprint:
    def __init__(self, db_path="fingerprints.db"):
        """Initialize VideoFingerprint with database path."""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database and create table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
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
        
        conn.commit()
        conn.close()

    def generate_fingerprint(self, video_path):
        """Generates a unique fingerprint for a video file using SHA-256 hashing."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

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

    def store_video(self, video_path):
        """Stores the video and its fingerprint in the database."""
        try:
            fingerprint = self.generate_fingerprint(video_path)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            with open(video_path, 'rb') as file:
                video_data = file.read()
            
            cursor.execute(
                """INSERT INTO video_fingerprints 
                   (video_name, fingerprint, video, video_path) 
                   VALUES (?, ?, ?, ?)""", 
                (os.path.basename(video_path), fingerprint, video_data, video_path)
            )
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'message': f"Fingerprint and video for '{os.path.basename(video_path)}' stored successfully!",
                'fingerprint': fingerprint
            }
            
        except sqlite3.IntegrityError:
            return {
                'success': False,
                'message': "Error: This fingerprint already exists in the database.",
                'fingerprint': fingerprint
            }
        except Exception as e:
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'fingerprint': None
            }

    def check_fingerprint(self, video_path):
        """Check if a video's fingerprint exists in the database."""
        try:
            fingerprint = self.generate_fingerprint(video_path)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT video_name, video_path FROM video_fingerprints WHERE fingerprint = ?", 
                         (fingerprint,))
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                return {
                    'exists': True,
                    'original_name': result[0],
                    'original_path': result[1],
                    'fingerprint': fingerprint
                }
            return {
                'exists': False,
                'fingerprint': fingerprint
            }
            
        except Exception as e:
            return {
                'exists': False,
                'error': str(e),
                'fingerprint': None
            }

    def get_all_fingerprints(self):
        """Retrieve all stored fingerprints and their associated video names."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT video_name, fingerprint, video_path FROM video_fingerprints")
        results = cursor.fetchall()
        
        conn.close()
        
        return [
            {
                'video_name': row[0],
                'fingerprint': row[1],
                'video_path': row[2]
            }
            for row in results
        ]

    def delete_fingerprint(self, fingerprint):
        """Delete a fingerprint and its associated video from the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM video_fingerprints WHERE fingerprint = ?", (fingerprint,))
            
            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                return {
                    'success': True,
                    'message': f"Fingerprint {fingerprint} deleted successfully!"
                }
            else:
                conn.close()
                return {
                    'success': False,
                    'message': f"Fingerprint {fingerprint} not found in database."
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Error deleting fingerprint: {str(e)}"
            }

def main():
    video_path = input("Enter the path of the video file: ")
    if not os.path.exists(video_path):
        print("Error: File does not exist.")
        return
    
    fingerprint = generate_video_fingerprint(video_path)
    store_video_and_fingerprint(video_path, fingerprint)

if __name__ == "__main__":
    main()
