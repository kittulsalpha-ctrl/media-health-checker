import os
import json
import subprocess
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Media Health Checker</title>
    <style>
        body {
            font-family: Arial;
            margin: 40px;
            background: #f4f4f4;
        }

        .container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            max-width: 700px;
            margin: auto;
        }

        h1 {
            color: #333;
        }

        button {
            padding: 10px 20px;
            background: black;
            color: white;
            border: none;
            cursor: pointer;
        }

        pre {
            background: #eee;
            padding: 15px;
            overflow-x: auto;
        }
    </style>
</head>
<body>

<div class="container">
    <h1>Media Health Checker</h1>

    <form action="/check" method="post" enctype="multipart/form-data">
        <input type="file" name="file" required>
        <br><br>
        <button type="submit">Analyze File</button>
    </form>

    {% if report %}
    <h2>Analysis Result</h2>

    <pre>{{ report }}</pre>
    {% endif %}
</div>

</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/check", methods=["POST"])
def check_media():

    if "file" not in request.files:
        return "No file uploaded"

    file = request.files["file"]

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    file.save(file_path)

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

    report = {
        "filename": file.filename,
        "duration_seconds": metadata.get("format", {}).get("duration"),
        "video_codec": video_stream.get("codec_name") if video_stream else None,
        "resolution": f"{video_stream.get('width')}x{video_stream.get('height')}" if video_stream else None,
        "frame_rate": video_stream.get("avg_frame_rate") if video_stream else None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "audio_channels": audio_stream.get("channels") if audio_stream else None,
        "status": "PASS"
    }

    return render_template_string(
        HTML_PAGE,
        report=json.dumps(report, indent=4)
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
import json
import subprocess
from flask import Flask, jsonify, request

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/")
def home():
    return jsonify({
        "app": "Media Health Checker",
        "status": "running"
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/check", methods=["POST"])
def check_media():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    command = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        return jsonify({
            "status": "FAIL",
            "error": "ffprobe failed to read the file"
        }), 500

    metadata = json.loads(result.stdout)

    video_stream = None
    audio_stream = None

    for stream in metadata.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        if stream.get("codec_type") == "audio" and audio_stream is None:
            audio_stream = stream

    report = {
        "filename": file.filename,
        "duration_seconds": metadata.get("format", {}).get("duration"),
        "file_size_bytes": metadata.get("format", {}).get("size"),
        "overall_bitrate": metadata.get("format", {}).get("bit_rate"),
        "video_codec": video_stream.get("codec_name") if video_stream else None,
        "resolution": f"{video_stream.get('width')}x{video_stream.get('height')}" if video_stream else None,
        "frame_rate": video_stream.get("avg_frame_rate") if video_stream else None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "audio_channels": audio_stream.get("channels") if audio_stream else None,
        "audio_sample_rate": audio_stream.get("sample_rate") if audio_stream else None,
        "status": "PASS" if video_stream and audio_stream else "WARNING"
    }

    return jsonify(report)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
