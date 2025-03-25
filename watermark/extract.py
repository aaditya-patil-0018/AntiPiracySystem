import cv2
import numpy as np
import hashlib
import json

# Paths to files
suspect_video = 'test1.mp4'  # The video to check for tampering
original_hash_file = 'watermark_hashes.json'  # Hash file saved from watermarking

# Load original watermark hash data
with open(original_hash_file, 'r') as f:
    original_hashes = json.load(f)

# Open the suspect video
cap = cv2.VideoCapture(suspect_video)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# Watermark position settings (Must match the original placement)
font = cv2.FONT_HERSHEY_SIMPLEX
font_scale = 1
font_thickness = 2
(text_width, text_height), _ = cv2.getTextSize('YourBrandName', font, font_scale, font_thickness)
x = width - text_width - 10  # Bottom-right corner
y = height - text_height - 10

# Track tampered frames
tampered_frames = []
frame_index = 0

while True:
    ret, frame = cap.read()
    if not ret or frame_index >= len(original_hashes):
        break

    # Extract the watermark region from the suspect frame
    watermark_region = frame[y:y + text_height + 10, x:x + text_width + 10]

    # Compute hash of the extracted watermark region
    crop_bytes = watermark_region.tobytes()
    hash_value = hashlib.md5(crop_bytes).hexdigest()  # Use SHA-256 for better security

    # Compare with original hash
    if hash_value != original_hashes.get(str(frame_index)):
        tampered_frames.append(frame_index)

    frame_index += 1

cap.release()
cv2.destroyAllWindows()

# Print results
if tampered_frames:
    print("⚠️ Tampering detected in frames:", tampered_frames[:10], "..." if len(tampered_frames) > 10 else "")
    print(f"🔍 Total tampered frames: {len(tampered_frames)}")
else:
    print("✅ No tampering detected. Watermark is intact.")
