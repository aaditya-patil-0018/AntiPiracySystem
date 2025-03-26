import cv2
import numpy as np
import random

class VideoWatermarker:
    def __init__(self, font=cv2.FONT_HERSHEY_SIMPLEX, font_scale=1, font_thickness=2, 
                 alpha=0.2, min_duration=10, max_duration=30, watermark_interval_sec=6):
        """Initialize VideoWatermarker with customizable parameters."""
        self.font = font
        self.font_scale = font_scale
        self.font_thickness = font_thickness
        self.alpha = alpha  # Transparency
        self.min_duration = min_duration  # Min frames for watermark appearance
        self.max_duration = max_duration  # Max frames for watermark appearance
        self.watermark_interval_sec = watermark_interval_sec  # One watermark every X seconds

    def _get_video_properties(self, cap):
        """Get video properties from capture object."""
        return {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        }

    def _generate_watermark_spots(self, video_props, watermark_text):
        """Generate random positions and durations for watermarks."""
        video_duration_sec = video_props['total_frames'] / video_props['fps']
        num_watermark_spots = max(1, int(video_duration_sec / self.watermark_interval_sec))
        
        watermark_frames = []
        for _ in range(num_watermark_spots):
            if video_props['total_frames'] <= self.max_duration:
                start = 0
                duration = video_props['total_frames']
            else:
                start = random.randint(0, video_props['total_frames'] - self.max_duration)
                duration = random.randint(self.min_duration, self.max_duration)

            end = min(start + duration, video_props['total_frames'])

            # Calculate random position for watermark
            text_size = cv2.getTextSize(watermark_text, self.font, self.font_scale, 
                                      self.font_thickness)[0]
            text_width, text_height = text_size
            x = random.randint(0, max(0, video_props['width'] - text_width - 1))
            y = random.randint(text_height + 1, max(0, video_props['height'] - 1))

            watermark_frames.append({'start': start, 'end': end, 'pos': (x, y)})
            
        return watermark_frames, num_watermark_spots

    def apply_watermark(self, input_path, output_path, watermark_text):
        """Apply watermark to video."""
        try:
            # Open video file
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                return {
                    'success': False,
                    'message': "Error: Cannot open video file."
                }

            # Get video properties
            video_props = self._get_video_properties(cap)
            
            # Generate watermark positions
            watermark_frames, num_spots = self._generate_watermark_spots(video_props, watermark_text)
            
            # Initialize video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(
                output_path, 
                fourcc, 
                video_props['fps'], 
                (video_props['width'], video_props['height'])
            )

            # Process frames
            frame_idx = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                # Apply watermark if frame is in watermark range
                for wf in watermark_frames:
                    if wf['start'] <= frame_idx < wf['end']:
                        overlay = frame.copy()
                        cv2.putText(
                            overlay, 
                            watermark_text, 
                            wf['pos'], 
                            self.font, 
                            self.font_scale,
                            (255, 255, 255), 
                            self.font_thickness, 
                            cv2.LINE_AA
                        )
                        cv2.addWeighted(
                            overlay, 
                            self.alpha, 
                            frame, 
                            1 - self.alpha, 
                            0, 
                            frame
                        )
                        break

                out.write(frame)
                frame_idx += 1

            # Cleanup
            cap.release()
            out.release()

            return {
                'success': True,
                'message': f"Watermarked video saved to: {output_path}",
                'details': {
                    'num_watermarks': num_spots,
                    'video_duration': video_props['total_frames'] / video_props['fps'],
                    'fps': video_props['fps'],
                    'resolution': f"{video_props['width']}x{video_props['height']}"
                }
            }

        except Exception as e:
            return {
                'success': False,
                'message': f"Error processing video: {str(e)}"
            }

    def set_watermark_style(self, **kwargs):
        """Update watermark style parameters."""
        valid_params = {
            'font_scale': float,
            'font_thickness': int,
            'alpha': float,
            'min_duration': int,
            'max_duration': int,
            'watermark_interval_sec': int
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
            'message': "Watermark style updated successfully"
        }
