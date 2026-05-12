import os
import time
import json
import shutil
import subprocess

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_FOLDER = "watch-folder"
PASSED_FOLDER = "passed"
FAILED_FOLDER = "failed"
WARNING_FOLDER = "warning"
REPORTS_FOLDER = "reports"
FRAMES_FOLDER = "frames"


def generate_ai_tags(filename, video_codec, resolution, audio_stream):

    tags = ["media", "video"]

    lower_name = filename.lower()

    if "car" in lower_name or "race" in lower_name:
        tags.extend(["car", "racing", "sports"])

    if "football" in lower_name or "soccer" in lower_name:
        tags.extend(["football", "sports"])

    if video_codec == "h264":
        tags.append("h264")

    if resolution == "1920x1080":
        tags.append("full-hd")

    if audio_stream:
        tags.append("audio-present")

        audio_codec = audio_stream.get("codec_name")
        channels = audio_stream.get("channels")

        if audio_codec:
            tags.append(audio_codec)

        if channels == 2:
            tags.append("stereo")

        elif channels == 1:
            tags.append("mono")

    else:
        tags.append("no-audio")

    return list(set(tags))


class MediaHandler(FileSystemEventHandler):

    def on_created(self, event):

        if event.is_directory:
            return

        file_path = event.src_path

        print(f"\nNew file detected: {file_path}")

        time.sleep(2)

        command = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        metadata = json.loads(result.stdout)

        video_stream = None
        audio_stream = None

        for stream in metadata.get("streams", []):

            if stream.get("codec_type") == "video":
                video_stream = stream

            if stream.get("codec_type") == "audio":
                audio_stream = stream

        status = "PASS"

        validation_messages = []

        video_codec = video_stream.get("codec_name") if video_stream else None

        width = video_stream.get("width") if video_stream else 0
        height = video_stream.get("height") if video_stream else 0

        resolution = f"{width}x{height}"

        bitrate = int(metadata.get("format", {}).get("bit_rate", 0))

        if not audio_stream:
            status = "FAIL"
            validation_messages.append("No audio detected")

        if width < 1920 or height < 1080:
            status = "FAIL"
            validation_messages.append("Resolution below 1080p")

        if video_codec != "h264":

            if status != "FAIL":
                status = "WARNING"

            validation_messages.append("Non-H264 codec detected")

        if bitrate < 5000000:

            if status == "PASS":
                status = "WARNING"

            validation_messages.append("Bitrate below recommended threshold")

        if not validation_messages:
            validation_messages.append(
                "Media passed all validation checks"
            )

        filename = os.path.basename(file_path)

        if status == "PASS":
            destination = os.path.join(
                PASSED_FOLDER,
                filename
            )

        elif status == "WARNING":
            destination = os.path.join(
                WARNING_FOLDER,
                filename
            )

        else:
            destination = os.path.join(
                FAILED_FOLDER,
                filename
            )

        shutil.move(file_path, destination)

        frame_filename = filename + ".jpg"

        frame_path = os.path.join(
            FRAMES_FOLDER,
            frame_filename
        )

        frame_command = [
            "ffmpeg",
            "-i", destination,
            "-ss", "00:00:01",
            "-vframes", "1",
            frame_path,
            "-y"
        ]

        subprocess.run(
            frame_command,
            capture_output=True,
            text=True
        )

        print(f"\nFrame extracted: {frame_path}")
        proxy_filename = "proxy_" + os.path.splitext(filename)[0] + ".mp4"

        proxy_path = os.path.join(
            "proxies",
            proxy_filename
        )

        proxy_command = [
            "ffmpeg",
            "-i", destination,
            "-c:v", "libx264",
            "-crf", "28",
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "96k",
            proxy_path,
            "-y"
        ]

        subprocess.run(
            proxy_command,
            capture_output=True,
            text=True
        )

        original_size = os.path.getsize(destination)
        proxy_size = os.path.getsize(proxy_path)

        size_reduction_percent = round(
            ((original_size - proxy_size) / original_size) * 100,
            2
        )

        print(f"\nProxy generated: {proxy_path}")
        ai_tags = generate_ai_tags(
            filename,
            video_codec,
            resolution,
            audio_stream
        )

        report = {
            "filename": filename,
            "status": status,
            "video_codec": video_codec,
            "resolution": resolution,
            "bitrate": bitrate,
            "validation_messages": validation_messages,
            "ai_tags": ai_tags,
            "extracted_frame": frame_path,
            "proxy_file": proxy_path,
            "original_size_bytes": original_size,
            "proxy_size_bytes": proxy_size,
            "size_reduction_percent": size_reduction_percent
        }

        report_filename = filename + ".json"

        report_path = os.path.join(
            REPORTS_FOLDER,
            report_filename
        )

        with open(report_path, "w") as report_file:
            json.dump(report, report_file, indent=4)

        print("\nValidation Report:")
        print(json.dumps(report, indent=4))

        print(f"\nMetadata report saved: {report_path}")


if __name__ == "__main__":

    print("Watching folder for new media files...")

    os.makedirs(WATCH_FOLDER, exist_ok=True)
    os.makedirs(PASSED_FOLDER, exist_ok=True)
    os.makedirs(FAILED_FOLDER, exist_ok=True)
    os.makedirs(WARNING_FOLDER, exist_ok=True)
    os.makedirs(REPORTS_FOLDER, exist_ok=True)
    os.makedirs(FRAMES_FOLDER, exist_ok=True)

    event_handler = MediaHandler()

    observer = Observer()

    observer.schedule(
        event_handler,
        WATCH_FOLDER,
        recursive=False
    )

    observer.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        observer.stop()

    observer.join()