import cv2
import numpy as np
import hashlib
import json

input_video = 'test1.mp4'
output_video = 'output_watermarked.mp4'
watermark_text = 'YourBrandName'
hash_data_file = 'watermark_hashes.json'


cap = cv2.VideoCapture(input_video)
fps = int(cap.get(cv2.CAP_PROP_FPS))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

font = cv2.FONT_HERSHEY_SIMPLEX
font_scale = 1
font_thickness = 2
color = (255, 255, 255)
alpha = 0.15

(text_width, text_height), _ = cv2.getTextSize(watermark_text, font, font_scale, font_thickness)
position = (width - text_width - 10, height - text_height - 10)

hash_data = {}

frame_index = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Create overlay and blend
    overlay = frame.copy()
    cv2.putText(overlay, watermark_text, position, font, font_scale, color, font_thickness, cv2.LINE_AA)
    watermarked_frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

    # Crop watermark region from the frame
    x, y = position
    crop = watermarked_frame[y:y + text_height + 10, x:x + text_width + 10]

    # Compute hash of the watermark area
    crop_bytes = crop.tobytes()
    hash_value = hashlib.md5(crop_bytes).hexdigest()
    hash_data[frame_index] = hash_value

    # Write frame
    out.write(watermarked_frame)
    frame_index += 1

# Save hashes to file
with open(hash_data_file, 'w') as f:
    json.dump(hash_data, f)

cap.release()
out.release()
cv2.destroyAllWindows()

print("✅ Watermarked video saved as:", output_video)
print("🔐 Watermark region hashes saved as:", hash_data_file)
