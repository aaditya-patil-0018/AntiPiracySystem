import cv2
import numpy as np
import random

# === CONFIG ===
video_path = 'test1.mp4'         # Input video file
output_path = 'output_watermarked.mp4' # Output video file
watermark_text = "MyWatermark"         # Watermark text
font = cv2.FONT_HERSHEY_SIMPLEX
font_scale = 1
font_thickness = 2
alpha = 0.2                            # More transparent
min_duration = 10                      # Min frames for watermark appearance
max_duration = 30                      # Max frames for watermark appearance
watermark_interval_sec = 6             # One watermark every 6 seconds

# === Load video ===
cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    print("❌ Error: Cannot open video file.")
    exit()

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
video_duration_sec = total_frames / fps

# === Dynamic watermark spots based on video duration ===
num_watermark_spots = max(1, int(video_duration_sec / watermark_interval_sec))
print(f"📌 Video Duration: {video_duration_sec:.2f}s → {num_watermark_spots} watermarks will be added.")

# === Output writer ===
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

# === Generate watermark appearance ranges ===
watermark_frames = []
for _ in range(num_watermark_spots):
    if total_frames <= max_duration:
        start = 0
        duration = total_frames
    else:
        start = random.randint(0, total_frames - max_duration)
        duration = random.randint(min_duration, max_duration)

    end = min(start + duration, total_frames)

    # Position
    text_size = cv2.getTextSize(watermark_text, font, font_scale, font_thickness)[0]
    text_width, text_height = text_size
    x = random.randint(0, max(0, width - text_width - 1))
    y = random.randint(text_height + 1, max(0, height - 1))

    watermark_frames.append({'start': start, 'end': end, 'pos': (x, y)})

# === Process video frames ===
frame_idx = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    for wf in watermark_frames:
        if wf['start'] <= frame_idx < wf['end']:
            overlay = frame.copy()
            cv2.putText(overlay, watermark_text, wf['pos'], font, font_scale,
                        (255, 255, 255), font_thickness, cv2.LINE_AA)
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
            break

    out.write(frame)
    frame_idx += 1


cap.release()
out.release()
print("✅ Watermarked video saved to:", output_path)

