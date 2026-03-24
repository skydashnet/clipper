# Skydash.NET // Heatmap Clip Extractor

Tools otomatis modern yang dapat mengekstrak bagian paling viral / paling sering diulang dari video YouTube (berdasarkan grafik *Most Replayed* / Heatmap), dan memprosesnya menjadi klip video vertikal (9:16) yang siap di-upload ke YouTube Shorts, TikTok, atau Instagram Reels. Tools ini juga ditenagai oleh AI untuk _generate_ dan me-_render_ *hard-subtitle* langsung ke dalam videonya.

## Fitur Utama

- **Deteksi Viral Otomatis**: Menggunakan data grafik "Most Replayed" dari YouTube untuk langsung melompat ke bagian yang paling banyak ditonton audiens.
- **Remux Vertikal (Crop)**: Memotong rasio video horizontal dan otomatis menjadikannya vertikal (9:16).
- **Auto Subtitles**: Ditenagai oleh AI *Faster-Whisper*. Transkripsi bahasa Indonesia (atau bahasa apapun) dengan super cepat lewat CPU/GPU.
- **Bisa Bebas Kustomisasi**:
  - Dukungan potong *Center* (di tengah) atau *Split-Screen* (kamera atas, *gameplay* bawah).
  - Bisa _custom_ Padding, nama Font, ukuran Font, sampai warna Font hex.
  - Preview interaktif via Web Dashboard modern gaya *Cyber-Tokyo*.
- **Anti Lemot / Anti Blok**: Menggunakan *yt-dlp multi-threading* native untuk _bypass_ masalah _download throttling_ YouTube. Otomatis nge-detect file `cookies.txt` untuk memastikan hasil download selalu **Kualitas Resolusi Tinggi (HD / 1080p)**, serta bisa mendownload **Batas Umur (18+)** maupun **Video Khusus Member (Members-Only)**!

## Persyaratan Sistem

- **Python 3.10+**
- **FFmpeg**: Wajib ter-install dan ada di `PATH` sistem operasi kamu.
- **Node.js**: Diperlukan untuk dekripsi beberapa _cipher_ kode pada plugin download.


## Cara Instalasi

Hanya untuk pengguna Windows, langsung klik 2x script ini:
```cmd
install.bat
```
Script ini akan otomatis mengecek kelengkapan komputer kamu (seperti Python, FFmpeg, aria2), lalu membuat *Virtual Environment* Python agar *library*-nya tidak bentrok, dan meng-install semua *library* pendukung (seperti Flask, faster-whisper, dan yt-dlp).

### Instalasi Manual 
```cmd
# Buat virtual environment
python -m venv venv
venv\Scripts\activate

# Install module yg diperlukan
pip install -r requirements.txt
# (atau jika file txt tidak ada)
pip install flask yt-dlp faster-whisper requests
```

## 🍪 Setup `cookies.txt` (PENTING Untuk Download Kualitas HD & Dilewati Batasan Akun)
Jika kamu ingin mendownload video secara kencang dengan **Kualitas Tertinggi (1080p HD)** atau mendownload video yang dibatasi umur (Age-Restricted) dan privasi khusus member, kamu sangat membutuhkan file `cookies.txt`! (Karena YouTube seringkali menyembunyikan kualitas HD untuk lalu lintas yang terdeteksi sebagai robot/anonymous).
1. Install Ekstensi Browser seperti **"Get cookies.txt LOCALLY"** (tersedia di Chrome/Edge/Firefox).
2. Buka Youtube.com di browsermu dan pastikan kamu sudah Login.
3. Klik Icon Ekstensi-nya lalu klik tombol **Export** cookies.
4. Rename / Ubah nama hasil file yang terdownload menjadi tepat bernama `cookies.txt` dan letakkan di **dalam folder project ini** (satu folder dengan `app.py`).
5. Skydash.NET sekarang akan secara otomatis membaca file tersebut setiap kali kamu memproses video!

## Cara Menggunakan

### 1. Web UI Dashboard (Paling Gampang & Direkomendasikan)
Jalankan dashboard aplikasi melalui file `start.bat` yang ada di folder ini (atau jalankan script dibawah ini di cmd):
```cmd
venv\Scripts\activate
python app.py
```
Lalu buka alamat `http://127.0.0.1:5000` di web browser mu. Pasang link YouTube-mu, klik Fetch untuk melihat hasil deteksi Heatmap, centang klip mana yang kamu mau, tonton *preview* dari klip tersebut, seting warna & font, lalu klik Ekstrak!

### 2. Command Line Interface / Headless (Bagi Developer)
Bisa juga dijalankan di latar belakang lewat *Command Prompt* atau Terminal langsung:
```cmd
venv\Scripts\activate
python run.py --url https://youtu.be/CONTOH --crop 1 --subtitle 1 --font Arial --padding 10 --font-color FFFF00 --font-size 15
```
Ketik perintah `python run.py --help` untuk melihat seluruh input manual yang tersedia.

---
**Author**: Skydash.NET
**License**: MIT
