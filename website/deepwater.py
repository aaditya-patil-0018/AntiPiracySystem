import numpy as np
import cv2
from scipy.fftpack import dct, idct
import hashlib
import sys
from tqdm import tqdm
from typing import Dict, Optional, Tuple

class PremiumWatermarker:
    def __init__(self, secret_key: str, user_id: str = None):
        self.secret_key = secret_key
        self.user_id = user_id
        
        self.master_wm = self._generate_watermark(secret_key, 64)
        self.user_wm = self._generate_watermark(user_id, 32) if user_id else None
        
        self.block_size = 16
        self.master_bands = [(3,2), (2,3), (4,1), (1,4)]
        self.user_bands = [(3,3), (2,4), (4,2), (1,5)]
        
        self.base_master_strength = 0.06
        self.base_user_strength = 0.07
        self.frame_skip = 2
        
        self.master_threshold = 0.02
        self.user_threshold = 0.01
        self.user_roi = (0.25, 0.25, 0.75, 0.75)

    def _generate_watermark(self, data: str, size: int) -> Optional[np.ndarray]:
        if not data:
            return None
        try:
            seed = int(hashlib.sha256(data.encode()).hexdigest(), 16) % (2**32 - 1)
            np.random.seed(seed)
            pattern = np.random.randn(size, size)
            return pattern / np.linalg.norm(pattern) * 0.12
        except Exception as e:
            print(f"Watermark generation error: {str(e)}", file=sys.stderr)
            return None

    def _get_embedding_strength(self, block: np.ndarray) -> Tuple[float, float]:
        if block is None:
            return (0, 0)
        variance = np.var(block)
        brightness = np.mean(block)
        texture_factor = np.log1p(variance) * 0.6
        brightness_factor = 1.25 - (brightness / 255)
        master_str = self.base_master_strength * texture_factor * brightness_factor
        user_str = self.base_user_strength * texture_factor * brightness_factor
        return (master_str, user_str)

    def _process_block(self, block: np.ndarray) -> np.ndarray:
        if block is None:
            return block
        try:
            block_float = block.astype(np.float32)
            dct_block = dct(dct(block_float.T, norm='ortho').T, norm='ortho')
            master_str, user_str = self._get_embedding_strength(block_float)
            
            if self.master_wm is not None:
                for (x,y) in self.master_bands:
                    if x < self.master_wm.shape[0] and y < self.master_wm.shape[1]:
                        dct_block[x,y] += master_str * self.master_wm[x,y] * dct_block[0,0] * 0.85
            if self.user_wm is not None:
                for (x,y) in self.user_bands:
                    if x < self.user_wm.shape[0] and y < self.user_wm.shape[1]:
                        dct_block[x,y] += user_str * self.user_wm[x,y] * dct_block[0,0] * 0.8
            
            watermarked_block = idct(idct(dct_block.T, norm='ortho').T, norm='ortho')
            return np.clip(watermarked_block, 0, 255).astype(np.uint8)
        except Exception:
            return block

    def embed_video(self, input_path: str, output_path: str) -> None:
        try:
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                raise IOError(f"Cannot open video: {input_path}")
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            frame_count = 0
            with tqdm(total=total_frames, desc="Embedding") as pbar:
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if frame_count % self.frame_skip == 0:
                        try:
                            yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
                            y_channel = yuv[:,:,0]
                            for i in range(0, height - self.block_size, self.block_size):
                                for j in range(0, width - self.block_size, self.block_size):
                                    block = y_channel[i:i+self.block_size, j:j+self.block_size]
                                    if np.var(block) < 10:
                                        continue
                                    in_roi = (self.user_roi[0]*height <= i < self.user_roi[2]*height and
                                              self.user_roi[1]*width <= j < self.user_roi[3]*width)
                                    if in_roi or self.user_wm is None:
                                        watermarked_block = self._process_block(block)
                                        y_channel[i:i+self.block_size, j:j+self.block_size] = watermarked_block
                            yuv[:,:,0] = y_channel
                            frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
                        except Exception as e:
                            print(f"Frame error: {str(e)}", file=sys.stderr)
                    out.write(frame)
                    frame_count += 1
                    pbar.update(1)
            cap.release()
            out.release()
        except Exception as e:
            print(f"Embedding failed: {str(e)}", file=sys.stderr)
            raise

    def detect_watermarks(self, video_path: str) -> Dict:
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise IOError(f"Cannot open video: {video_path}")
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            master_accum = np.zeros_like(self.master_wm) if self.master_wm is not None else None
            user_accum = np.zeros_like(self.user_wm) if self.user_wm is not None else None
            master_count = user_count = 0
            frame_count = 0
            with tqdm(desc="Detecting") as pbar:
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
                                    block = y_channel[i:i+self.block_size, j:j+self.block_size]
                                    dct_block = dct(dct(block.T, norm='ortho').T, norm='ortho')
                                    in_roi = (self.user_roi[0]*height <= i < self.user_roi[2]*height and
                                              self.user_roi[1]*width <= j < self.user_roi[3]*width)
                                    if self.master_wm is not None:
                                        for (x,y) in self.master_bands:
                                            if dct_block[0,0] != 0:
                                                master_accum[x,y] += dct_block[x,y] / (dct_block[0,0] + 1e-10)
                                                master_count += 1
                                    if in_roi and self.user_wm is not None:
                                        for (x,y) in self.user_bands:
                                            if dct_block[0,0] != 0:
                                                user_accum[x,y] += dct_block[x,y] / (dct_block[0,0] + 1e-10)
                                                user_count += 1
                        except Exception as e:
                            print(f"Detection error: {str(e)}", file=sys.stderr)
                    frame_count += 1
                    pbar.update(1)
            cap.release()
            results = {
                'master': {'detected': False, 'confidence': 0.0},
                'user': {'detected': False, 'confidence': 0.0, 'id': self.user_id}
            }
            if self.master_wm is not None and master_count > 0:
                master_wm = master_accum / master_count
                master_norm = np.linalg.norm(master_wm) * np.linalg.norm(self.master_wm)
                if master_norm > 1e-10:
                    master_corr = np.sum(master_wm * self.master_wm) / master_norm
                    results['master'] = {
                        'detected': master_corr > self.master_threshold,
                        'confidence': float(master_corr)
                    }
            if self.user_wm is not None and user_count > 0:
                user_wm = user_accum / user_count
                user_norm = np.linalg.norm(user_wm) * np.linalg.norm(self.user_wm)
                if user_norm > 1e-10:
                    user_corr = np.sum(user_wm * self.user_wm) / user_norm
                    results['user'] = {
                        'detected': user_corr > self.user_threshold,
                        'confidence': float(user_corr),
                        'id': self.user_id
                    }
            return results
        except Exception as e:
            print(f"Detection failed: {str(e)}", file=sys.stderr)
            return {
                'master': {'detected': False, 'confidence': 0.0},
                'user': {'detected': False, 'confidence': 0.0, 'id': self.user_id}
            }

if __name__ == "__main__":
    try:
        print("=== PREMIUM WATERMARKING SYSTEM ===")
        watermarker = PremiumWatermarker(
            secret_key="corporate_secure_key_2024",
            user_id="user_aditya"
        )
        print("\nEmbedding watermarks into video...")
        watermarker.embed_video("testtest.mp4", "testtestwatermark2.mp4")
    except Exception as e:
        print(f"Execution failed: {e}", file=sys.stderr)