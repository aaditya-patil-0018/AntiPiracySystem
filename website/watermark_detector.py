import numpy as np
import cv2
from scipy.fftpack import dct
import hashlib
from tqdm import tqdm
from typing import List, Dict, Optional, Tuple

class WatermarkDetector:
    def __init__(self, block_size: int = 16, 
                 user_bands: List[Tuple[int, int]] = [(3,3), (2,4), (4,2), (1,5)],
                 user_threshold: float = 0.02,
                 user_roi: Tuple[float, float, float, float] = (0.25, 0.25, 0.75, 0.75),
                 frame_skip: int = 2):
        """Initialize the watermark detector with configurable parameters.
        
        Args:
            block_size: Size of DCT blocks for processing
            user_bands: DCT frequency bands used for watermarking
            user_threshold: Correlation threshold for positive watermark detection
            user_roi: Region of interest (top_y, top_x, bottom_y, bottom_x) as fractions of frame
            frame_skip: Process every nth frame
        """
        self.block_size = block_size
        self.user_bands = user_bands
        self.user_threshold = user_threshold
        self.user_roi = user_roi
        self.frame_skip = frame_skip
    
    def _generate_user_watermark(self, user_id: str, size: int = 32) -> np.ndarray:
        """Generate the expected watermark pattern for a given user ID.
        
        Args:
            user_id: Unique identifier for the user
            size: Size of the watermark pattern
            
        Returns:
            Normalized watermark pattern as numpy array
        """
        if not user_id:
            return None
            
        seed = int(hashlib.sha256(user_id.encode()).hexdigest(), 16) % (2**32 - 1)
        np.random.seed(seed)
        wm = np.random.randn(size, size)
        return wm / np.linalg.norm(wm) * 0.12

    def _extract_watermark_signature(self, video_path: str) -> Tuple[np.ndarray, int]:
        """Extract the watermark signature from a video.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Tuple of (extracted watermark signature, number of blocks processed)
        """
        # Read video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise IOError(f"Cannot open video: {video_path}")
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        user_accum = np.zeros((32, 32))
        user_count = 0
        frame_count = 0

        print("Extracting watermark signature from video...")
        with tqdm(desc="Scanning frames") as pbar:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_count % self.frame_skip == 0:
                    try:
                        yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
                        y_channel = yuv[:,:,0].astype(np.float32)

                        for i in range(0, height - self.block_size, self.block_size):
                            for j in range(0, width - self.block_size, self.block_size):
                                in_roi = (self.user_roi[0]*height <= i < self.user_roi[2]*height and
                                          self.user_roi[1]*width <= j < self.user_roi[3]*width)
                                if not in_roi:
                                    continue
                                    
                                block = y_channel[i:i+self.block_size, j:j+self.block_size]
                                dct_block = dct(dct(block.T, norm='ortho').T, norm='ortho')
                                
                                if dct_block[0,0] != 0:
                                    for (x, y) in self.user_bands:
                                        user_accum[x,y] += dct_block[x,y] / (dct_block[0,0] + 1e-10)
                                    user_count += 1
                    except Exception as e:
                        print(f"Error processing frame {frame_count}: {str(e)}")
                        continue
                frame_count += 1
                pbar.update(1)
        cap.release()

        if user_count == 0:
            raise ValueError("No watermarkable content found in video.")
            
        return user_accum, user_count

    def detect_user(self, video_path: str, user_ids: List[str]) -> Dict:
        """Detect which user watermark is present in the video.
        
        Args:
            video_path: Path to the video file
            user_ids: List of user IDs to check against
            
        Returns:
            Dictionary with detection results
        """
        # Extract watermark signature from video
        try:
            user_accum, user_count = self._extract_watermark_signature(video_path)
            
            # Normalize extracted watermark signature
            extracted_wm = user_accum / user_count

            # Compare with all user watermarks
            print("\nMatching extracted signature with database of users...")
            best_match = {'user_id': None, 'confidence': 0.0}
            
            for user_id in user_ids:
                expected_wm = self._generate_user_watermark(user_id)
                dot = np.sum(expected_wm * extracted_wm)
                norm = np.linalg.norm(expected_wm) * np.linalg.norm(extracted_wm)
                
                if norm < 1e-10:
                    continue
                    
                correlation = dot / norm
                if correlation > best_match['confidence']:
                    best_match = {'user_id': user_id, 'confidence': float(correlation)}
            
            # Check if best match passes threshold
            best_match['detected'] = best_match['confidence'] > self.user_threshold
            return best_match
            
        except Exception as e:
            print(f"Detection failed: {str(e)}")
            return {'user_id': None, 'confidence': 0.0, 'detected': False, 'error': str(e)}
    
    def set_detection_parameters(self, **kwargs):
        """Update detector parameters.
        
        Args:
            **kwargs: Parameters to update (block_size, user_bands, user_threshold, 
                      user_roi, frame_skip)
        
        Returns:
            Dictionary with update status
        """
        valid_params = {
            'block_size': int,
            'user_bands': list,
            'user_threshold': float,
            'user_roi': tuple,
            'frame_skip': int
        }

        for param, value in kwargs.items():
            if param in valid_params:
                try:
                    setattr(self, param, valid_params[param](value))
                except ValueError:
                    return {
                        'success': False,
                        'message': f"Invalid value for {param}: {value}"
                    }

        return {
            'success': True,
            'message': "Detection parameters updated successfully"
        }
        
if __name__ == "__main__":
    # List of all user IDs who were issued watermarked videos
    all_users = ["user004", "user_aditya", "user003", "user_sachin", "user008"]
    
    # Create detector with default parameters
    detector = WatermarkDetector()
    
    # Detect watermark
    result = detector.detect_user("/Users/aadi/Downloads/protected_classroom.mp4", all_users)
    
    print("\n=== USER WATERMARK RESULT ===")
    if result['detected']:
        print(f"User Watermark DETECTED!")
        print(f"User ID: {result['user_id']}")
        print(f"Confidence: {result['confidence']:.4f}")
    else:
        print("No matching user watermark detected.")
