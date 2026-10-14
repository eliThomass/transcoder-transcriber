import json
import subprocess
from pathlib import Path

# Limits for uploads, which are untrusted input.
MAX_DURATION_SECONDS = 2 * 3600
MAX_DIMENSION = 4096
FFMPEG_TIMEOUT_SECONDS = 3 * 3600

# Only read local MP4 files, so crafted inputs (e.g. HLS playlists) can't pull in other files or URLs.
SAFE_INPUT = ["-protocol_whitelist", "file", "-f", "mp4"]


# The upload isn't a usable MP4 (the API shows the user a bad-file error).
class InvalidInput(Exception):
    pass


# Checks the upload with ffprobe before encoding; returns True if it has an audio track.
def probeVideo(inputFile):
    result = subprocess.run(
        ["ffprobe", "-v", "error", *SAFE_INPUT, "-print_format", "json", "-show_format", "-show_streams", str(inputFile)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise InvalidInput(f"ffprobe failed: {result.stderr.strip()[:500]}")
    info = json.loads(result.stdout)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    duration = float(info.get("format", {}).get("duration") or 0)
    if video is None:
        raise InvalidInput("no video stream")
    if not 0 < duration <= MAX_DURATION_SECONDS:
        raise InvalidInput(f"duration {duration}s out of range")
    if max(video.get("width", 0), video.get("height", 0)) > MAX_DIMENSION:
        raise InvalidInput("frame size too large")
    return any(s.get("codec_type") == "audio" for s in streams)


#Only thing is that resolutuion is for 16:9 videos (laptop and PC) if we want  to support other ratios we need to tweak the frontend
# fps=None keeps the original frame rate; outputFile=None uses the videos_un -> videos_pro test folders.
def runFfmpeg(inputFile, subtitleFile,  resolution, fps, videoCodec, encodingSpeed, quality, audioCodec,audioBitrate, outputFile=None, brightness="0"):

    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    if outputFile is None:
        inputFile = PROJECT_ROOT / "videos_un" / Path(inputFile).name

        outputName = f"{inputFile.stem}_{resolution}p.mp4"
        outputFile = PROJECT_ROOT / "videos_pro" / outputName

    # Video filters: scale keeps the aspect ratio, then optional brightness and burned-in subtitles.
    filters = f"scale=-2:{resolution}"
    if brightness != "0":
        filters += f",eq=brightness={brightness}"
    if(subtitleFile != None):
        filters += f",subtitles={subtitleFile}"  # only pass server-generated paths; filter syntax isn't escaped

    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        *SAFE_INPUT,
        "-i", str(inputFile),
        "-t", str(MAX_DURATION_SECONDS),  # hard stop even if the file lies about its length
        "-map", "0:v:0", "-map", "0:a:0?",  # first video and audio track only
        "-map_metadata", "-1",  # strip metadata such as GPS location
        "-vf", filters,
    ]
    if fps is not None:
        command += ["-r", fps]
    command += [
        "-c:v", videoCodec,
        "-preset", encodingSpeed,
        "-crf", quality,
        "-pix_fmt", "yuv420p",  # plays in every browser and player
        "-c:a", audioCodec,
        "-b:a", audioBitrate,
        "-movflags", "+faststart",  # lets playback start before the whole file downloads
        str(outputFile)
    ]

    subprocess.run(command, check=True, timeout=FFMPEG_TIMEOUT_SECONDS)


# TEST (runs only with `python worker/Ffmpeg_script.py`, not when the API imports this file)
if __name__ == "__main__":
    runFfmpeg("input.mp4", None, "720", "30", "libx264", "fast", "23", "aac", "128k")
    #runFfmpegSub("input.mp4", "subtitle.srt", "720", "30", "libx264", "fast", "23", "aac", "128k", "output_with_subs.mp4")
