import os
import uuid
import json
import time
import threading
import subprocess
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

jobs = {}

def run_job(job_id, args_list, log_path):
    with open(log_path, 'w', encoding='utf-8') as f:
        cmd = ["python", "-u", "run.py"] + args_list
        proc = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding='utf-8',
            bufsize=1
        )
        
        for line in proc.stdout:
            f.write(line)
            f.flush()
            
        proc.wait()
        
    if proc.returncode == 0:
        jobs[job_id]["status"] = "done"
    else:
        jobs[job_id]["status"] = "error"

@app.route("/")
def index():
    return render_template("index.html")

import run

@app.route("/api/analyze")
def analyze():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
        
    try:
        video_id = run.extract_video_id(url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL"}), 400
            
        heatmap = run.fetch_heatmap_segments(video_id)
        
        cmd = ["yt-dlp", "--print", "%(title)s|%(duration)s|%(thumbnail)s"]
        if os.path.exists("cookies.txt"):
            cmd.extend(["--cookies", "cookies.txt"])
        cmd.append(url)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        parts = result.stdout.strip().split('|', 2)
        
        title = parts[0] if len(parts) > 0 else "Unknown Video"
        duration = float(parts[1]) if len(parts) > 1 and parts[1].isdigit() else run.get_video_duration(video_id)
        thumbnail = parts[2] if len(parts) > 2 else f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
                    
        return jsonify({
            "video_id": video_id,
            "title": title,
            "duration": duration,
            "thumbnail": thumbnail,
            "heatmap": heatmap
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/start", methods=["POST"])
def start_job():
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
        
    job_id = str(uuid.uuid4())
    log_path = os.path.join(LOGS_DIR, f"{job_id}.log")
    
    # Extract parameters with defaults
    crop = data.get('crop', 1)
    subtitle = data.get('subtitle', 0)
    model = data.get('model', '')
    font = data.get('font', '')
    manual_segments = data.get('manual_segments', '')
    max_clips = data.get('max_clips', 10)
    padding = data.get('padding', 10)
    font_size = data.get('font_size', 13)
    font_color = data.get('font_color', 'FFFFFF')

    # Construct command
    args = [
        "--url", url,
        "--crop", str(crop),
        "--subtitle", str(subtitle),
        "--max-clips", str(max_clips),
        "--padding", str(padding),
        "--font-size", str(font_size),
        "--font-color", str(font_color)
    ]
    if model:
        args.extend(["--model", model])
    if font:
        args.extend(["--font", font])
    if manual_segments:
        args.extend(["--manual", manual_segments])
        
    jobs[job_id] = {"status": "running"}
    
    thread = threading.Thread(target=run_job, args=(job_id, args, log_path))
    thread.daemon = True
    thread.start()
    
    return jsonify({"job_id": job_id})

@app.route("/api/stream/<job_id>")
def stream(job_id):
    def generate():
        log_path = os.path.join(LOGS_DIR, f"{job_id}.log")
        for _ in range(20):
            if os.path.exists(log_path):
                break
            time.sleep(0.5)
            
        if not os.path.exists(log_path):
            yield f"data: Error: Log file not found\n\n"
            return
            
        with open(log_path, 'r', encoding='utf-8') as f:
            while True:
                lines = f.readlines(8192)
                if not lines:
                    if job_id in jobs and jobs[job_id]["status"] != "running":
                        break
                    time.sleep(0.05)
                    continue
                for line in lines:
                    yield f"data: {line.strip()}\n\n"
                
        final_status = jobs.get(job_id, {}).get("status", "unknown")
        yield f"data: [PROCESS_{final_status.upper()}]\n\n"
        
    return Response(generate(), mimetype="text/event-stream")

if __name__ == "__main__":
    try:
        from waitress import serve
        print("=" * 50)
        print("  Skydash.NET Dashboard")
        print("  http://localhost:5000")
        print("=" * 50)
        serve(app, host="0.0.0.0", port=5000, threads=8)
    except ImportError:
        print("[WARN] Waitress not installed, using Flask dev server.")
        print("[WARN] Web UI may freeze during heavy processing.")
        print("[TIP]  Run: pip install waitress")
        app.run(debug=True, port=5000, threaded=True)
