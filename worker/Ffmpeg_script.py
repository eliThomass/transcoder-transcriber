import subprocess


#Only thing is that resolutuion is for 16:9 videos (laptop and PC) if we want  to support other ratios we need to tweak the frontend
def runFfmpeg(inputFile, resolution, fps, videoCodec, encodingSpeed, quality, audioCodec,audioBitrate, outputFile):
    command = [
        "ffmpeg",
        "-i", inputFile,
        "-vf", f"scale=-2:{resolution}",
        "-r", fps,
        "-c:v", videoCodec,
        "-preset", encodingSpeed,
        "-crf", quality,
        "-c:a", audioCodec,
        "-b:a", audioBitrate,
        outputFile
    ]

    subprocess.run(command, check=True)

# TEST
runFfmpeg("input.mp4", "720", "30", "libx264", "fast", "23", "aac", "128k", "output.mp4")