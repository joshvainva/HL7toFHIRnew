import imageio_ffmpeg
import subprocess
import sys

def convert():
    if len(sys.argv) < 3:
        print("Usage: convert_to_mp4.py <in> <out>")
        return
        
    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # Get the bundled ffmpeg binary from the imageio-ffmpeg wheel
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    # ffmpeg parameters for standard mp4 web playback
    cmd = [
        ffmpeg_exe,
        "-y",                             # overwrite existing
        "-i", input_file,                 # input webp
        "-c:v", "libx264",                # robust codec
        "-crf", "23",                     # high quality
        "-preset", "fast",                
        "-pix_fmt", "yuv420p",            # universally supported pixel format
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", # ensure dimensions are even
        output_file
    ]
    
    print("Executing internal FFmpeg:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("FFmpeg error:", result.stderr)
    else:
        print("Success! Wrote MP4 to:", output_file)

if __name__ == "__main__":
    convert()
