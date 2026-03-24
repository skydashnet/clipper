"""
Skydash.NET - YouTube Heatmap Clip Extractor
=============================================
Automatically extracts the most-replayed segments from YouTube videos
and converts them into vertical short-form clips (9:16) with optional
AI-generated subtitles using Faster-Whisper.

Author  : Skydash.NET
License : MIT
"""

import os
import re
import json
import sys
import subprocess
import shutil
import threading
import itertools
import time
import requests
import warnings
import argparse
from urllib.parse import urlparse, parse_qs

# ── Encoding fix for Windows terminal ────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════════════════════════════════════
#  USER CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

OUTPUT_DIR      = "clips"   # Folder to save final clips
MAX_CLIP_SECS   = 60        # Maximum length of each clip (seconds)
MIN_HEAT_SCORE  = 0.40      # Minimum heatmap intensity (0.0 - 1.0)
MAX_CLIPS       = 10        # Maximum number of clips to export per video
CLIP_PADDING    = 10        # Seconds to pad before and after each segment
SPLIT_TOP_H     = 960       # Top section height in split crop mode (px)
SPLIT_BOT_H     = 320       # Bottom section height in split crop mode (px)
WHISPER_MODEL   = "small"   # Whisper model: tiny / base / small / medium / large-v3

# Video format priority — prefer H.264 to avoid AV1/VP9 decoding issues.
# Falls back gracefully if 1080p H.264 is unavailable.
VIDEO_FORMAT = (
    "bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a]"
    "/bestvideo[height>=720][ext=mp4]+bestaudio[ext=m4a]"
    "/bestvideo[ext=mp4]+bestaudio[ext=m4a]"
    "/bestvideo+bestaudio"
    "/best"
)

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

BANNER = r"""
 ___    _                 _               _         _   _  ___   _____ 
(  _`\ ( )               ( )             ( )       ( ) ( )(  _`\(_   _)
| (_(_)| |/')  _   _    _| |   _ _   ___ | |__     | `\| || (_(_) | |  
`\__ \ | , <  ( ) ( ) /'_` | /'_` )/',__)|  _ `\   | , ` ||  _)_  | |  
( )_) || |\`\ | (_) |( (_| |( (_| |\__, \| | | | _ | |`\ || (_( ) | |  
`\____)(_) (_)`\__, |`\__,_)`\__,_)(____/(_) (_)(_)(_) (_)(____/' (_)  
              ( )_| |                                                  
              `\___/'                                                  
          Skydash.NET  →  Viral Shorts  |  Auto Clip Extractor
"""

WHISPER_SIZES = {
    "tiny":     "75 MB",
    "base":     "142 MB",
    "small":    "466 MB",
    "medium":   "1.5 GB",
    "large-v3": "2.9 GB",
}

DIVIDER = "─" * 54


# ══════════════════════════════════════════════════════════════════════════════
#  TERMINAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def info(msg):   print(f"  ℹ  {msg}")
def ok(msg):     print(f"  ✅  {msg}")
def warn(msg):   print(f"  ⚠️   {msg}")
def fail(msg):   print(f"  ❌  {msg}")
def step(msg):   print(f"\n  ▶  {msg}")
def section(title):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


class Spinner:
    """Animated spinner for long-running subprocess tasks."""

    def __init__(self, label):
        self.label   = label
        self._done   = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        for ch in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            if self._done.is_set():
                break
            print(f"\r  {ch}  {self.label}...", end="", flush=True)
            time.sleep(0.1)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, *_):
        self._done.set()
        self._thread.join()
        status = "✅" if exc_type is None else "❌"
        suffix = "selesai." if exc_type is None else "gagal."
        print(f"\r  {status}  {self.label} {suffix}          ")


def run_silent(cmd, **kwargs):
    """Run a subprocess silently, raise CalledProcessError on failure."""
    return subprocess.run(
        cmd, check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True, **kwargs
    )


def run_visible(cmd, **kwargs):
    """Run a subprocess with output visible in terminal."""
    return subprocess.run(cmd, text=True, **kwargs)

def run_ffmpeg_progress(cmd: list, label: str):
    """Run FFmpeg and stream its progress to stdout so the UI can grab it."""
    print(f"  🎬 Memulai {label}...")
    
    if "-progress" not in cmd:
        cmd = cmd[:1] + ["-v", "warning", "-stats"] + cmd[1:]
        
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace"
    )
    
    for line in process.stdout:
        lineStr = line.strip()
        if "frame=" in lineStr or "size=" in lineStr or "time=" in lineStr:
            print(f"  [FFMPEG] {lineStr}", flush=True)

    process.wait()
    if process.returncode != 0:
        fail(f"{label} gagal!")
        raise subprocess.CalledProcessError(process.returncode, cmd)
    ok(f"{label} selesai.")


# ══════════════════════════════════════════════════════════════════════════════
#  DEPENDENCY CHECK
# ══════════════════════════════════════════════════════════════════════════════

def check_dependencies(need_whisper: bool):
    """Verify all required tools and packages are available."""
    section("🔧 Dependency Check")

    # FFmpeg
    if not shutil.which("ffmpeg"):
        fail("FFmpeg not found in PATH.")
        info("Please run run.bat to auto-install, or download from https://ffmpeg.org")
        sys.exit(1)
    ok("FFmpeg found.")

    # Node.js
    if not shutil.which("node"):
        warn("Node.js not found — YouTube n-challenge may fail for some videos.")
        info("Download from https://nodejs.org (LTS recommended)")
    else:
        try:
            ver = subprocess.check_output(["node", "--version"], text=True).strip()
            ok(f"Node.js {ver} found.")
        except Exception:
            warn("Node.js check failed.")

    aria2_path = shutil.which("aria2c")
    if not aria2_path:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            possible_path = os.path.join(local_appdata, "Microsoft", "WinGet", "Packages")
            if os.path.exists(possible_path):
                for root, _, files in os.walk(possible_path):
                    if "aria2c.exe" in files:
                        aria2_path = os.path.join(root, "aria2c.exe")
                        break

    if not aria2_path:
        fail("aria2c not found. This is required to bypass YouTube download throttling (stuck at 0bps).")
        info("Please install aria2 (e.g., 'winget install aria2' on Windows).")
        info("If you just installed it, RESTART YOUR TERMINAL.")
        sys.exit(1)
    
    os.environ["PATH"] += os.pathsep + os.path.dirname(aria2_path)
    ok("aria2c found.")
    info("Updating yt-dlp...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "yt-dlp", "-q"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    ok("yt-dlp is up to date.")

    if need_whisper:
        try:
            import faster_whisper
            ok("faster-whisper found.")
            _check_whisper_model()
        except ImportError:
            info("Installing faster-whisper...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper", "-q"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            ok("faster-whisper installed.")
            _check_whisper_model()


def _check_whisper_model():
    cache_dir  = os.path.expanduser("~/.cache/huggingface/hub")
    model_key  = f"faster-whisper-{WHISPER_MODEL}"
    cached     = False

    if os.path.exists(cache_dir):
        try:
            cached = any(model_key in d.lower() for d in os.listdir(cache_dir))
        except Exception:
            pass

    if cached:
        ok(f"Whisper model '{WHISPER_MODEL}' is cached and ready.")
    else:
        warn(f"Whisper model '{WHISPER_MODEL}' not cached.")
        info(f"Will auto-download ~{WHISPER_SIZES.get(WHISPER_MODEL, '?')} on first use.")


# ══════════════════════════════════════════════════════════════════════════════
#  URL / VIDEO UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def extract_video_id(url: str) -> str | None:
    """Parse a YouTube URL and return the video ID, or None if invalid."""
    parsed = urlparse(url.strip())

    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/").split("?")[0] or None

    if parsed.hostname in ("youtube.com", "www.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            parts = parsed.path.split("/")
            return parts[2] if len(parts) > 2 else None
        if parsed.path.startswith("/live/"):
            parts = parsed.path.split("/")
            return parts[2] if len(parts) > 2 else None

    return None


def get_video_duration(video_id: str) -> int:
    """Return video duration in seconds using yt-dlp."""
    cmd = [sys.executable, "-m", "yt_dlp", "--get-duration",
           "--no-warnings", f"https://youtu.be/{video_id}"]
    try:
        out   = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        parts = out.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except Exception:
        pass
    return 7200


# ══════════════════════════════════════════════════════════════════════════════
#  HEATMAP PARSER
# ══════════════════════════════════════════════════════════════════════════════

def fetch_heatmap_segments(video_id: str) -> list[dict]:
    """
    Scrape YouTube watch page and extract 'Most Replayed' heatmap markers.
    Returns a list of dicts sorted by score descending.
    """
    url     = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        html = requests.get(url, headers=headers, timeout=20).text
    except Exception as e:
        fail(f"Failed to fetch YouTube page: {e}")
        return []

    _HEATMAP_PATTERNS = [
        r'"markers":\s*(\[.*?\])\s*,\s*"?markersMetadata"?',
        r'"heatMarkers":\s*(\[.*?\])',
        r'"markers":\s*(\[.*?\])(?:\s*[,}])',
    ]
    raw_markers = None
    for pattern in _HEATMAP_PATTERNS:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                raw_markers = json.loads(match.group(1).replace('\\"', '"'))
                if raw_markers:
                    break
            except Exception:
                continue
    if not raw_markers:
        return []

    segments = []
    for marker in raw_markers:
        if "heatMarkerRenderer" in marker:
            marker = marker["heatMarkerRenderer"]
        try:
            score = float(marker.get("intensityScoreNormalized", 0))
            if score < MIN_HEAT_SCORE:
                continue
            segments.append({
                "start":    float(marker["startMillis"]) / 1000,
                "duration": min(float(marker["durationMillis"]) / 1000, MAX_CLIP_SECS),
                "score":    score,
            })
        except Exception:
            continue

    segments.sort(key=lambda x: x["score"], reverse=True)
    return segments


# ══════════════════════════════════════════════════════════════════════════════
#  DOWNLOADER
# ══════════════════════════════════════════════════════════════════════════════

def _probe_resolution(filepath: str) -> int:
    """Use ffprobe to get the video height (resolution) of a file."""
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=height",
            "-of", "csv=p=0",
            filepath,
        ], text=True, stderr=subprocess.DEVNULL).strip()
        return int(out)
    except Exception:
        return 0

def download_full_video(video_id: str, out_path: str, cookies_source: str | None = None) -> bool:
    """
    Download the entire YouTube video using yt-dlp and aria2c.
    By downloading the full video locally first, we bypass YouTube's zero-byte
    throttling that plagues ffmpeg range-requests for DASH segments.
    """
    step("Downloading full video (using aria2c to bypass throttle)...")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--js-runtimes",       "node",
        "--remote-components", "ejs:github",
        "-S",                  "res:1080,ext:mp4:m4a,codec:h264",
        "--downloader",        "m3u8:native",
        "--downloader",        "dash,m3u8:aria2c",
        "--downloader-args",   "aria2c:-x 8 -s 8 -j 8 -k 5M --summary-interval=0",
        "--concurrent-fragments", "5",
        "--retries",           "10",
        "--fragment-retries",  "10",
        "--socket-timeout",    "30",
        "-f",                  VIDEO_FORMAT,
        "--merge-output-format", "mp4",
        "-o",                  out_path,
    ]

    if cookies_source and os.path.isfile(cookies_source):
        cmd += ["--cookies", cookies_source]

    cmd.append(f"https://youtu.be/{video_id}")

    proc = subprocess.Popen(cmd)
    proc.wait()

    if proc.returncode != 0:
        fail("yt-dlp exited with errors.")
        return False
    if not os.path.exists(out_path):
        fail("Output file not found after download.")
        return False
        
    height = _probe_resolution(out_path)
    if height > 0:
        ok(f"Downloaded in {height}p.")
    return True

def extract_clip_segment(full_video: str, t_start: float, t_end: float, out_path: str) -> bool:
    """
    Extract a clip from the downloaded full video locally using ffmpeg.
    This is extremely fast compared to downloading ranges over the internet.
    """
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", str(t_start),
        "-to", str(t_end),
        "-i", full_video,
        "-c", "copy",
        out_path
    ]
    try:
        run_silent(cmd)
        return True
    except subprocess.CalledProcessError as e:
        fail(f"Local extraction failed: {e.stderr[:120]}")
        return False

    return True


# ══════════════════════════════════════════════════════════════════════════════
#  VIDEO PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def remux_to_faststart(src: str, dst: str) -> bool:
    """
    Re-mux video to fix fragmented MP4 (moov atom) issues
    and move moov atom to the front for fast seeking.
    Also converts any non-H.264 codec (AV1, VP9) to H.264.
    """
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", src,
        "-c:v", "libx264", "-preset", "fast", "-crf", "17",
        "-c:a", "copy",
        "-movflags", "+faststart",
        dst,
    ]
    try:
        run_ffmpeg_progress(cmd, "Optimasi Video (Remux)")
        return True
    except subprocess.CalledProcessError as e:
        fail(f"Remux failed: {e}")
        return False


def crop_to_vertical(src: str, dst: str, mode: int) -> bool:
    """
    Crop and scale a horizontal video into 720x1280 (9:16) vertical format.
    Supports three modes: 1=default, 2=split_left, 3=split_right.
    """
    if mode == 1:
        vf = "scale=-2:1280,crop=720:1280:(iw-720)/2:(ih-1280)/2"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", src,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-c:a", "aac", "-b:a", "128k",
            dst,
        ]
    else:
        cam_x = "0" if mode == 2 else f"iw-720"
        vf = (
            f"scale=-2:1280[sc];"
            f"[sc]split=2[a][b];"
            f"[a]crop=720:{SPLIT_TOP_H}:(iw-720)/2:(ih-1280)/2[top];"
            f"[b]crop=720:{SPLIT_BOT_H}:{cam_x}:ih-{SPLIT_BOT_H}[bot];"
            f"[top][bot]vstack=inputs=2[out]"
        )
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", src,
            "-filter_complex", vf,
            "-map", "[out]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-c:a", "aac", "-b:a", "128k",
            dst,
        ]

    try:
        run_ffmpeg_progress(cmd, "Potong Video (Crop to vertical)")
        return True
    except subprocess.CalledProcessError as e:
        fail(f"Crop failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  SUBTITLE GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def secs_to_ass_ts(secs: float) -> str:
    """Convert float seconds to ASS timestamp: H:MM:SS.cs"""
    h  = int(secs // 3600)
    m  = int((secs % 3600) // 60)
    s  = int(secs % 60)
    cs = int((secs % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def transcribe_and_write_ass(video_file: str, ass_file: str, font: str, font_size: int, font_color: str) -> bool:
    """
    Transcribe audio using Faster-Whisper and write a Karaoke ASS subtitle file.
    """
    try:
        from faster_whisper import WhisperModel
        step(f"Loading Whisper model '{WHISPER_MODEL}'...")
        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        ok("Model loaded. Transcribing audio with word timestamps...")

        segments, _ = model.transcribe(video_file, language="id", word_timestamps=True)

        if font_color.startswith("#"):
            font_color = font_color[1:]
        if len(font_color) == 6:
            high_color = f"&H{font_color[4:6]}{font_color[2:4]}{font_color[0:2]}&"
        else:
            high_color = "&H00FFFF&"

        base_color = "&HFFFFFF&"

        with open(ass_file, "w", encoding="utf-8") as f:
            f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 720\nPlayResY: 1280\n\n")
            f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write(f"Style: Default,{font},{font_size},{base_color},&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,100,1\n\n")
            f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            
            lines_written = 0
            for seg in segments:
                if not seg.words:
                    start_ts = secs_to_ass_ts(seg.start)
                    end_ts = secs_to_ass_ts(seg.end)
                    text = seg.text.strip()
                    if text:
                        f.write(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}\n")
                        lines_written += 1
                    continue
                    
                for i, active_word in enumerate(seg.words):
                    start_ts = secs_to_ass_ts(active_word.start)
                    end_ts = secs_to_ass_ts(seg.words[i+1].start) if i + 1 < len(seg.words) else secs_to_ass_ts(seg.end)
                    
                    text_parts = []
                    for j, w in enumerate(seg.words):
                        word_str = w.word.strip()
                        if j == i:
                            text_parts.append(f"{{\\c{high_color}}}{word_str}{{\\c{base_color}}}")
                        else:
                            text_parts.append(word_str)
                    
                    dialogue_text = " ".join(text_parts)
                    f.write(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{dialogue_text}\n")
                    lines_written += 1

        ok(f"Karaoke Subtitle written ({lines_written} lines).")
        return True

    except Exception as e:
        fail(f"Transcription error: {e}")
        return False

def burn_subtitles(src: str, ass_file: str, dst: str) -> bool:
    abs_ass  = os.path.abspath(ass_file)
    safe_ass = abs_ass.replace("\\", "/").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-i", src,
        "-vf", f"subtitles='{safe_ass}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "copy",
        dst,
    ]

    try:
        run_ffmpeg_progress(cmd, "Membakar Subtitle (Hardsub)")
        return True
    except subprocess.CalledProcessError:
        fail("Subtitle burn failed.")
        return False

# ══════════════════════════════════════════════════════════════════════════════
#  CLIP PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def process_clip(full_video: str, segment: dict, clip_num: int,
                 total_dur: int, crop_mode: str,
                 use_subtitle: bool, font: str = "Arial",
                 padding: int = 10, font_size: int = 13, font_color: str = "FFFFFF") -> bool:
    """
    Full pipeline for a single clip:
      1. Extract segment  →  2. Remux  →  3. Crop  →  4. Subtitle  →  5. Save
    """
    pad_start = max(0, segment["start"] - padding)
    pad_end   = min(segment["start"] + segment["duration"] + padding, total_dur)
    duration  = int(pad_end - pad_start)

    if duration < 3:
        return False

    raw_file  = f"_tmp_raw_{clip_num}.mp4"
    fix_file  = f"_tmp_fix_{clip_num}.mp4"
    crop_file = f"_tmp_crop_{clip_num}.mp4"
    ass_file  = f"_tmp_sub_{clip_num}.ass"
    out_file  = os.path.join(OUTPUT_DIR, f"clip_{clip_num}.mp4")

    temp_files = [raw_file, fix_file, crop_file, ass_file]

    print(f"\n{'═' * 54}")
    print(
        f"  🎬  Clip {clip_num}  |  "
        f"{int(pad_start)}s → {int(pad_end)}s  |  "
        f"{duration}s  |  score {segment['score']:.2f}"
    )
    print(f"{'═' * 54}")

    def cleanup(*files):
        for f in files:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

    try:
        # ── Step 1: Extract ──────────────────────────────────────────────────
        step("Extracting segment from full video...")
        ok_ext = extract_clip_segment(
            full_video, pad_start, pad_end, raw_file
        )
        if not ok_ext:
            cleanup(*temp_files)
            return False

        # ── Step 2: Remux / convert to H.264 ────────────────────────────────
        if not remux_to_faststart(raw_file, fix_file):
            warn("Remux failed — trying to continue with raw file...")
            os.rename(raw_file, fix_file)
        else:
            cleanup(raw_file)

        # ── Step 3: Crop to vertical ─────────────────────────────────────────
        if not crop_to_vertical(fix_file, crop_file, crop_mode):
            cleanup(*temp_files)
            return False
        cleanup(fix_file)

        # ── Step 4: Subtitle (optional) ──────────────────────────────────────
        if use_subtitle:
            transcribed = transcribe_and_write_ass(crop_file, ass_file, font, font_size, font_color)
            if transcribed and os.path.exists(ass_file):
                ok_sub = burn_subtitles(crop_file, ass_file, out_file)
                cleanup(ass_file)
                if not ok_sub:
                    warn("Subtitle burn failed — saving without subtitle.")
                    if os.path.exists(crop_file):
                        os.rename(crop_file, out_file)
                    else:
                        fail("Crop file missing, cannot save fallback clip.")
                        return False
                else:
                    cleanup(crop_file)
            else:
                warn("Transcription failed — saving without subtitle.")
                os.rename(crop_file, out_file)
        else:
            os.rename(crop_file, out_file)

        # ── Done ──────────────────────────────────────────────────────────────
        if not os.path.exists(out_file):
            fail(f"Output file missing after processing clip {clip_num}.")
            return False
        size_mb = os.path.getsize(out_file) / (1024 * 1024)
        ok(f"Clip {clip_num} saved → {out_file}  ({size_mb:.1f} MB)")
        return True

    except Exception as e:
        fail(f"Unexpected error on clip {clip_num}: {e}")
        cleanup(*temp_files)
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  INTERACTIVE MENUS
# ══════════════════════════════════════════════════════════════════════════════

def ask_crop_mode() -> tuple[str, str]:
    section("🖼  Crop Mode")
    options = [
        ("default",     "Default      — center crop (best for vlogs, podcasts)"),
        ("split_left",  "Split Left   — top: gameplay | bottom: left facecam"),
        ("split_right", "Split Right  — top: gameplay | bottom: right facecam"),
    ]
    for i, (_, label) in enumerate(options, 1):
        print(f"  {i}. {label}")

    while True:
        choice = input("\n  Select (1-3): ").strip()
        if choice in ("1", "2", "3"):
            mode, label = options[int(choice) - 1]
            ok(f"Selected: {label}")
            return mode, label
        warn("Invalid choice — please enter 1, 2, or 3.")


def ask_subtitle() -> bool:
    section("🎙  Auto Subtitle (Faster-Whisper)")
    size = WHISPER_SIZES.get(WHISPER_MODEL, "?")
    print(f"  Model  : {WHISPER_MODEL}  (~{size})")
    print(f"  Language : Bahasa Indonesia")
    print(f"  Device   : CPU (int8)")
    choice = input("\n  Enable auto subtitle? (y/n): ").strip().lower()
    enabled = choice in ("y", "yes")
    if enabled:
        ok("Auto subtitle enabled.")
    else:
        info("Subtitle disabled.")
    return enabled


def find_cookies_source() -> str | None:
    """Look for cookies.txt in the script directory."""
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    cookies_path = os.path.join(script_dir, "cookies.txt")
    if os.path.isfile(cookies_path):
        ok("cookies.txt found — using for authenticated download.")
        return cookies_path
    warn("cookies.txt not found — HD may not be available.")
    info("Export cookies via 'Get cookies.txt LOCALLY' Chrome extension")
    info("and place cookies.txt in the same folder as run.py.")
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    global WHISPER_MODEL

    parser = argparse.ArgumentParser(description="Skydash.NET Heatmap Clipper")
    parser.add_argument("--url", help="YouTube URL to process (skips interactive prompts)")
    parser.add_argument("--crop", type=int, choices=[1, 2, 3], default=1, help="Crop Mode (1=Default, 2=SplitLeft, 3=SplitRight)")
    parser.add_argument("--subtitle", type=int, choices=[0, 1], default=0, help="Enable Subtitles (0=No, 1=Yes)")
    parser.add_argument("--model", type=str, default="small", help="Whisper model size (tiny, base, small, medium, large)")
    parser.add_argument("--font", type=str, default="Arial", help="Font name for subtitles")
    parser.add_argument("--font-size", type=int, default=13, help="Subtitle font size inside ffmpeg")
    parser.add_argument("--font-color", type=str, default="FFFFFF", help="Subtitle Hex Color (e.g. FFFFFF)")
    parser.add_argument("--manual", type=str, help="Comma-separated manual segments, e.g. '10-20,30-45'")
    parser.add_argument("--max-clips", type=int, default=10, help="Maximum number of clips to generate")
    parser.add_argument("--padding", type=int, default=10, help="Padding in seconds around segment")
    args = parser.parse_args()

    print(BANNER)

    global MAX_CLIPS, CLIP_PADDING
    MAX_CLIPS = args.max_clips
    CLIP_PADDING = args.padding

    if args.url:
        crop_mode    = args.crop
        use_subtitle = args.subtitle == 1
        crop_label   = "Default (Center)" if crop_mode == 1 else "Split"
        WHISPER_MODEL = args.model
        url = args.url
        font = args.font
        font_size = args.font_size
        font_color = args.font_color
    else:
        # ── User selections ───────────────────────────────────────────────────────
        crop_mode, crop_label = ask_crop_mode()
        use_subtitle          = ask_subtitle()
        font = "Arial"
        font_size = 13
        font_color = "FFFFFF"
        section("🔗  YouTube URL")
        url = input("  Paste YouTube link: ").strip()

    # ── Dependency check ──────────────────────────────────────────────────────
    check_dependencies(need_whisper=use_subtitle)

    # ── Cookies ───────────────────────────────────────────────────────────────
    cookies_source = find_cookies_source()

    video_id = extract_video_id(url)

    if not video_id:
        fail("Could not parse a valid YouTube video ID from that URL.")
        return

    ok(f"Video ID: {video_id}")

    # ── Heatmap / Manual Segments ─────────────────────────────────────────────
    if args.url and args.manual:
        section("🌡  Using Manual Segments")
        segments = []
        for part in args.manual.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    s, e = map(float, part.split("-"))
                    segments.append({
                        "start": s,
                        "duration": e - s,
                        "score": 1.0
                    })
                except:
                    pass
    else:
        section("🌡  Fetching Heatmap Data")
        segments = fetch_heatmap_segments(video_id)

    if not segments:
        fail("No valid segments found for this video.")
        info("The video may not have 'Most Replayed' data yet.")
        info(f"Try lowering MIN_HEAT_SCORE (currently {MIN_HEAT_SCORE}) in run.py.")
        return

    ok(f"Found {len(segments)} high-engagement segment(s).")

    # ── Summary ───────────────────────────────────────────────────────────────
    section("⚙  Processing Plan")
    print(f"  Segments found : {len(segments)}")
    print(f"  Max clips      : {MAX_CLIPS}")
    print(f"  Padding        : {CLIP_PADDING}s each side")
    print(f"  Crop mode      : {crop_label}")
    print(f"  Subtitle       : {'Yes (' + WHISPER_MODEL + ')' if use_subtitle else 'No'}")
    print(f"  Output folder  : {OUTPUT_DIR}/")

    total_duration = get_video_duration(video_id)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Download Full Video ONCE ──────────────────────────────────────────────
    full_video_path = f"_tmp_full_{video_id}.mp4"
    if not os.path.exists(full_video_path):
        ok_full = download_full_video(video_id, full_video_path, cookies_source)
        if not ok_full:
            fail("Failed to download the full video. Aborting.")
            return
    else:
        ok(f"Using previously downloaded full video: {full_video_path}")

    total_duration = get_video_duration(video_id)

    # ── Process clips ─────────────────────────────────────────────────────────
    saved = 0
    for seg in segments:
        if saved >= MAX_CLIPS:
            break
        if process_clip(
            full_video_path, seg,
            saved + 1,
            total_duration,
            crop_mode,
            use_subtitle,
            font,
            CLIP_PADDING,
            font_size,
            font_color
        ):
            saved += 1

    try:
        if os.path.exists(full_video_path):
            os.remove(full_video_path)
    except: pass

    # ── Final summary ─────────────────────────────────────────────────────────
    print(f"\n{'═' * 54}")
    if saved > 0:
        ok(f"Done! {saved} clip(s) saved to '{OUTPUT_DIR}/'.")
    else:
        fail("No clips were saved successfully.")
    print(f"{'═' * 54}\n")


if __name__ == "__main__":
    main()