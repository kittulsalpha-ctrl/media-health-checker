import os
import json
import subprocess
import shutil
from flask import (
    Flask,
    render_template_string,
    send_from_directory,
    request,
    redirect
)

app = Flask(__name__)

REPORTS_FOLDER = "reports"
FRAMES_FOLDER = "frames"
WATCH_FOLDER = "watch-folder"
PASSED_FOLDER = "passed"
WARNING_FOLDER = "warning"
FAILED_FOLDER = "failed"
PROXIES_FOLDER = "proxies"

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mxf", ".avi", ".mkv"}

for folder in [
    REPORTS_FOLDER,
    FRAMES_FOLDER,
    WATCH_FOLDER,
    PASSED_FOLDER,
    WARNING_FOLDER,
    FAILED_FOLDER,
    PROXIES_FOLDER
]:
    os.makedirs(folder, exist_ok=True)


HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Media Operations Dashboard</title>
    <meta http-equiv="refresh" content="30">

    <style>
        body { font-family: Arial; background: #f4f4f4; margin: 30px; }
        h1 { color: #222; }
        .upload-box, .table-container {
            background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;
        }
        .stats { display: flex; gap: 20px; margin-bottom: 30px; }
        .card {
            background: white; padding: 20px; border-radius: 10px; width: 180px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        table { width: 100%; border-collapse: collapse; }
        th { background: #222; color: white; padding: 12px; }
        td { padding: 12px; border-bottom: 1px solid #ddd; }
        .pass { color: green; font-weight: bold; }
        .warning { color: orange; font-weight: bold; }
        .fail { color: red; font-weight: bold; }
        img { width: 160px; border-radius: 8px; }
        input, select {
            padding: 10px; border-radius: 5px; border: 1px solid #ccc; margin-right: 10px;
        }
        button {
            padding: 10px 20px; background: black; color: white;
            border: none; border-radius: 5px; cursor: pointer;
        }
    </style>
</head>

<body>

<h1>Media Operations Dashboard</h1>

<div class="upload-box">
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".mp4,.mov,.mxf,.avi,.mkv" required>
        <button type="submit">Upload Media</button>
    </form>
</div>

<div class="stats">
    <div class="card"><h3>Total Files</h3><h2>{{ total_files }}</h2></div>
    <div class="card"><h3>PASS</h3><h2 class="pass">{{ pass_count }}</h2></div>
    <div class="card"><h3>WARNING</h3><h2 class="warning">{{ warning_count }}</h2></div>
    <div class="card"><h3>FAIL</h3><h2 class="fail">{{ fail_count }}</h2></div>
</div>

<div style="margin-bottom: 20px;">
    <input type="text" id="searchInput" placeholder="Search filename...">
    <select id="statusFilter">
        <option value="ALL">All Status</option>
        <option value="PASS">PASS</option>
        <option value="WARNING">WARNING</option>
        <option value="FAIL">FAIL</option>
    </select>
</div>

<div class="table-container">
<table>
    <tr>
        <th>Frame</th>
        <th>Filename</th>
        <th>Status</th>
        <th>Codec</th>
        <th>Resolution</th>
        <th>AI Tags</th>
        <th>Validation Notes</th>
        <th>Proxy Reduction</th>
    </tr>

    {% for item in reports %}
    <tr class="report-row" data-status="{{ item.status }}">
        <td><img src="/frames/{{ item.filename }}.jpg"></td>
        <td>{{ item.filename }}</td>

        <td>
            {% if item.status == "PASS" %}
                <span class="pass">PASS</span>
            {% elif item.status == "WARNING" %}
                <span class="warning">WARNING</span>
            {% else %}
                <span class="fail">FAIL</span>
            {% endif %}
        </td>

        <td>{{ item.video_codec }}</td>
        <td>{{ item.resolution }}</td>
        <td>{{ item.ai_tags | join(", ") }}</td>
        <td>{{ item.validation_messages | join(", ") }}</td>
        <td>{{ item.size_reduction_percent }}%</td>
    </tr>
    {% endfor %}
</table>
</div>

<script>
const searchInput = document.getElementById("searchInput");
const statusFilter = document.getElementById("statusFilter");
const rows = document.querySelectorAll(".report-row");

function filterRows() {
    const searchValue = searchInput.value.toLowerCase();
    const selectedStatus = statusFilter.value;

    rows.forEach(row => {
        const filename = row.children[1].innerText.toLowerCase();
        const status = row.dataset.status;

        const matchesSearch = filename.includes(searchValue);
        const matchesStatus = selectedStatus === "ALL" || status === selectedStatus;

        row.style.display = matchesSearch && matchesStatus ? "" : "none";
    });
}

searchInput.addEventListener("input", filterRows);
statusFilter.addEventListener("change", filterRows);
</script>

</body>
</html>
"""


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


def process_media(file_path):
    filename = os.path.basename(file_path)

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
        return

    metadata = json.loads(result.stdout)

    video_stream = None
    audio_stream = None

    for stream in metadata.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        if stream.get("codec_type") == "audio" and audio_stream is None:
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
        validation_messages.append("Media passed all validation checks")

    if status == "PASS":
        destination = os.path.join(PASSED_FOLDER, filename)
    elif status == "WARNING":
        destination = os.path.join(WARNING_FOLDER, filename)
    else:
        destination = os.path.join(FAILED_FOLDER, filename)

    shutil.move(file_path, destination)

    frame_path = os.path.join(FRAMES_FOLDER, filename + ".jpg")

    frame_command = [
        "ffmpeg",
        "-i", destination,
        "-ss", "00:00:01",
        "-vframes", "1",
        frame_path,
        "-y"
    ]

    subprocess.run(frame_command, capture_output=True, text=True)

    proxy_filename = "proxy_" + os.path.splitext(filename)[0] + ".mp4"
    proxy_path = os.path.join(PROXIES_FOLDER, proxy_filename)

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

    subprocess.run(proxy_command, capture_output=True, text=True)

    original_size = os.path.getsize(destination)
    proxy_size = os.path.getsize(proxy_path) if os.path.exists(proxy_path) else 0

    if original_size > 0 and proxy_size > 0:
        size_reduction_percent = round(
            ((original_size - proxy_size) / original_size) * 100,
            2
        )
    else:
        size_reduction_percent = 0

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

    report_path = os.path.join(REPORTS_FOLDER, filename + ".json")

    with open(report_path, "w") as report_file:
        json.dump(report, report_file, indent=4)


@app.route("/frames/<path:filename>")
def serve_frame(filename):
    return send_from_directory(FRAMES_FOLDER, filename)


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect("/")

    file = request.files["file"]

    if file.filename == "":
        return redirect("/")

    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return redirect("/")

    save_path = os.path.join(WATCH_FOLDER, file.filename)
    file.save(save_path)

    process_media(save_path)

    return redirect("/")


@app.route("/")
def dashboard():
    reports = []

    pass_count = 0
    warning_count = 0
    fail_count = 0

    for file in os.listdir(REPORTS_FOLDER):
        if file.endswith(".json"):
            report_path = os.path.join(REPORTS_FOLDER, file)

            with open(report_path) as report_file:
                data = json.load(report_file)
                reports.append(data)

                if data["status"] == "PASS":
                    pass_count += 1
                elif data["status"] == "WARNING":
                    warning_count += 1
                else:
                    fail_count += 1

    total_files = len(reports)

    return render_template_string(
        HTML_PAGE,
        reports=reports,
        total_files=total_files,
        pass_count=pass_count,
        warning_count=warning_count,
        fail_count=fail_count
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)