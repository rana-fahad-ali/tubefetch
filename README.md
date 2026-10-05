# TubeFetch — YouTube Video Downloader

Paste a YouTube link, see a preview (thumbnail, title, channel, duration),
pick a quality, and download it as an **MP4** (or MP3 audio-only).

Runs entirely on your own computer — no accounts, no queues, no watermarks.

## Deploy it live (no install on your PC)

The project is ready to deploy as-is. Two free options:

### Option A — Render (recommended, ~5 minutes)
1. Put this folder on GitHub (create a repo, upload the files).
2. Go to https://dashboard.render.com → **New +** → **Web Service** → connect your GitHub repo.
3. Render detects the `Dockerfile` automatically. Keep the **Free** plan, click **Create Web Service**.
4. Wait ~3–5 minutes for the build. You get a live URL like `https://tubefetch.onrender.com` — open it, paste a link, download. Done.
5. Note: the free plan sleeps after 15 min of inactivity, so the first visit after a while takes ~30–60 s to wake up.

### Option B — Hugging Face Spaces (Docker)
1. Go to https://huggingface.co/new-space → name it `tubefetch`, pick the **Docker** SDK, create.
2. Upload all files (or push via git). The Space builds the `Dockerfile` and gives you a live URL like `https://huggingface.co/spaces/YOURNAME/tubefetch`.

### One honest caveat
YouTube sometimes shows a "confirm you're not a bot" check to cloud/server IPs. The app automatically retries with an alternate YouTube client when that happens (this worked in testing from a cloud server). If one host gets blocked anyway, try the other option above.

## Quick start (run on your own computer)

You need **Python 3.9+** and **ffmpeg** (for HD merging / MP3).

```bash
cd youtube-downloader-tool
chmod +x run.sh
./run.sh
```

Then open **http://127.0.0.1:5000** in your browser.

Manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## How it works

- `GET /` — the downloader page
- `POST /api/info` `{ "url": "..." }` — fetches title, thumbnail, duration
  and builds the quality list (144p → 4K MP4 + MP3 audio)
- `GET /api/download?url=…&format=…&label=…` — downloads, merges
  video+audio into one MP4, and sends the file to your browser

Downloads are streamed to a temp folder and deleted right after the
file is sent, so nothing piles up on disk.

## Troubleshooting

- **"YouTube refused the request (403)"** — YouTube sometimes shows a
  "sign in to confirm you're not a bot" check to cloud/VPN IPs. The app
  automatically retries with an alternate YouTube client when that happens.
  If it still fails, run the tool on your home computer (not a VPS) and
  update the downloader engine: `pip install -U yt-dlp`
- **No 1080p/4K option listed** — the video simply has no higher
  resolution on YouTube
- **ffmpeg missing** — HD merging and MP3 need it:
  `sudo apt install ffmpeg` (Ubuntu/Debian) or download it from
  https://ffmpeg.org for Windows/Mac

## Please use responsibly

Only download videos you own, that are Creative Commons licensed,
or where you have the creator's permission.
