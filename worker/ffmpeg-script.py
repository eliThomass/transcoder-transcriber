import subprocess

def run_ffmpeg(input_file, output_file):
    command = [
        "ffmpeg",
        "-i", input_file,
        "-vf", "scale=854:480",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        output_file
    ]

    subprocess.run(command, check=True)



run_ffmpeg("input.mp4", "output_480p.mp4")
    