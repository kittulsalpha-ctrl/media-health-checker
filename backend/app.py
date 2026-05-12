import os
import json
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

os.makedirs(REPORTS_FOLDER, exist_ok=True)
os.makedirs(FRAMES_FOLDER, exist_ok=True)
os.makedirs(WATCH_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mxf", ".avi", ".mkv"}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>

    <title>Media Operations Dashboard</title>
    <meta http-equiv="refresh" content="40">

    <style>
        body {
            font-family: Arial;
            background: #f4f4f4;
            margin: 30px;
        }

        h1 {
            color: #222;
        }

        .upload-box {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }

        .stats {
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            width: 180px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        .table-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th {
            background: #222;
            color: white;
            padding: 12px;
        }

        td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }

        .pass {
            color: green;
            font-weight: bold;
        }

        .warning {
            color: orange;
            font-weight: bold;
        }

        .fail {
            color: red;
            font-weight: bold;
        }

        img {
            width: 160px;
            border-radius: 8px;
        }

        input, select {
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #ccc;
            margin-right: 10px;
        }

        button {
            padding: 10px 20px;
            background: black;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
    </style>

</head>

<body>

    <h1>Media Operations Dashboard</h1>

    <div class="upload-box">
        <form
            action="/upload"
            method="post"
            enctype="multipart/form-data"
        >
            <input
                type="file"
                name="file"
                accept=".mp4,.mov,.mxf,.avi,.mkv"
                required
            >

            <button type="submit">Upload Media</button>
        </form>
    </div>

    <div class="stats">

        <div class="card">
            <h3>Total Files</h3>
            <h2>{{ total_files }}</h2>
        </div>

        <div class="card">
            <h3>PASS</h3>
            <h2 class="pass">{{ pass_count }}</h2>
        </div>

        <div class="card">
            <h3>WARNING</h3>
            <h2 class="warning">{{ warning_count }}</h2>
        </div>

        <div class="card">
            <h3>FAIL</h3>
            <h2 class="fail">{{ fail_count }}</h2>
        </div>

    </div>

    <div style="margin-bottom: 20px;">

        <input
            type="text"
            id="searchInput"
            placeholder="Search filename..."
        >

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
            </tr>

            {% for item in reports %}

            <tr class="report-row" data-status="{{ item.status }}">

                <td>
                    <img src="/frames/{{ item.filename }}.jpg">
                </td>

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
        const matchesStatus =
            selectedStatus === "ALL" || status === selectedStatus;

        row.style.display =
            matchesSearch && matchesStatus ? "" : "none";
    });
}

searchInput.addEventListener("input", filterRows);
statusFilter.addEventListener("change", filterRows);
</script>

</body>
</html>
"""

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
        print("Rejected unsupported file type:", file.filename)
        return redirect("/")

    save_path = os.path.join(WATCH_FOLDER, file.filename)
    file.save(save_path)

    print(f"Uploaded file: {file.filename}")

    return redirect("/")

@app.route("/")
def dashboard():
    reports = []

    pass_count = 0
    warning_count = 0
    fail_count = 0

    if os.path.exists(REPORTS_FOLDER):
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
    app.run(host="0.0.0.0", port=5001)