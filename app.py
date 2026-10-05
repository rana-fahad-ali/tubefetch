#!/usr/bin/env python3
"""
TubeFetch - YouTube Video Downloader
Paste a YouTube link, see a preview, pick a quality, download as MP4.

Run:  python app.py   ->  open http://127.0.0.1:5000
"""
import os
import re
import glob
import tempfile
import shutil

from flask import Flask, request, jsonify, send_file, render_template, after_this_request
import yt_dlp
from yt_dlp.utils import sanitize_filename

app = Flask(__name__)

# Accept the common YouTube URL shapes
URL_RE = re.compile(
    r'^(https?://)?(www\.|m\.|music\.|gaming\.)?(youtube\.com/(watch|shorts|embed|live|v/)|youtu\.be/)',
    re.IGNORECASE,
)

# yt-dlp format selector chars we allow from the client
FORMAT_RE = re.compile(r'^[\w\[\]\(\)\*\+\/=<>!\-,\.\s]+$')


def ydl_opts(extra=None):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 25,
        'retries': 2,
    }
    if extra:
        opts.update(extra)
    return opts


def human_size(num):
    if not num:
        return '—'
    for unit in ('B', 'KB', 'MB', 'GB'):
        if num < 1024:
            return f'{num:.1f} {unit}'
        num /= 1024
    return f'{num:.1f} TB'


def fmt_duration(secs):
    if not secs:
        return ''
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def clean_error(msg):
    """Shorten yt-dlp errors into something a human can read."""
    msg = str(msg)
    if 'Private video' in msg:
        return 'This video is private.'
    if 'age' in msg.lower() and 'sign in' in msg.lower():
        return 'This video is age-restricted and cannot be fetched.'
    if 'not available' in msg.lower():
        return 'This video is not available.'
    if 'HTTP Error 403' in msg:
        return 'YouTube refused the request (403). Try updating yt-dlp: pip install -U yt-dlp'
    # keep only the first meaningful line
    line = next((l for l in msg.splitlines() if l.strip()), msg)
    return line[:220]


def extract_info(url):
    """Extract video info, falling back to an alternate YouTube client
    when YouTube throws its 'not a bot' check at datacenter IPs."""
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if 'not a bot' in msg or 'confirm you' in msg or 'HTTP Error 403' in msg:
            opts = ydl_opts({'extractor_args': {'youtube': {'player_client': ['android']}}})
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        raise


def download_with_fallback(url, opts):
    """Download, retrying with the alternate client if YouTube bot-checks us."""
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if 'not a bot' in msg or 'confirm you' in msg or 'HTTP Error 403' in msg:
            opts = dict(opts)
            opts['extractor_args'] = {'youtube': {'player_client': ['android']}}
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=True)
        raise


def build_options(info):
    """Return download options: [{key, label, ext, size, size_h, note, height, audio_only}]"""
    all_fmts = info.get('formats') or []
    videos = [f for f in all_fmts if f.get('vcodec') not in (None, 'none') and f.get('url')]
    audios = [f for f in all_fmts if f.get('acodec') not in (None, 'none')
              and f.get('vcodec') in (None, 'none') and f.get('url')]

    best_audio = max(audios, key=lambda f: (f.get('abr') or 0,
                                           f.get('filesize') or f.get('filesize_approx') or 0)
                     ) if audios else None
    audio_id = best_audio['format_id'] if best_audio else 'bestaudio'
    audio_size = (best_audio.get('filesize') or best_audio.get('filesize_approx') or 0) if best_audio else 0

    by_height = {}
    for f in videos:
        if f.get('height'):
            by_height.setdefault(f['height'], []).append(f)

    options = []
    for h in sorted(by_height, reverse=True):
        group = by_height[h]
        v = max(group, key=lambda f: (f.get('ext') == 'mp4',
                                      f.get('acodec') not in (None, 'none'),
                                      f.get('tbr') or 0))
        vsize = v.get('filesize') or v.get('filesize_approx') or 0
        if v.get('acodec') not in (None, 'none'):
            sel, size = v['format_id'], vsize
            note = 'Single file, ready to play'
        else:
            sel = f"{v['format_id']}+{audio_id}"
            size = vsize + audio_size
            note = 'HD video merged with audio'
        options.append({
            'key': sel, 'label': f'{h}p MP4', 'ext': 'mp4',
            'size': size, 'size_h': human_size(size),
            'note': note, 'height': h, 'audio_only': False,
        })

    options.append({
        'key': 'bestaudio', 'label': 'MP3 audio', 'ext': 'mp3',
        'size': audio_size, 'size_h': human_size(audio_size),
        'note': 'Audio only', 'height': 0, 'audio_only': True,
    })
    return options


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/info', methods=['POST'])
def api_info():
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or '').strip()
    if not url:
        return jsonify({'ok': False, 'error': 'Paste a YouTube link first.'}), 400
    if not URL_RE.match(url):
        return jsonify({'ok': False, 'error': 'That does not look like a YouTube link.'}), 400
    try:
        info = extract_info(url)
    except Exception as e:  # noqa: BLE001 - surface any fetch failure cleanly
        return jsonify({'ok': False, 'error': clean_error(e)}), 422

    thumbs = info.get('thumbnails') or []
    thumb = (max(thumbs, key=lambda t: t.get('width') or 0).get('url')
             if thumbs else info.get('thumbnail'))
    return jsonify({
        'ok': True,
        'title': info.get('title') or 'Untitled',
        'channel': info.get('uploader') or info.get('channel') or '',
        'duration': fmt_duration(info.get('duration')),
        'views': info.get('view_count'),
        'thumbnail': thumb,
        'page_url': info.get('webpage_url') or url,
        'options': build_options(info),
    })


@app.route('/api/download')
def api_download():
    url = (request.args.get('url') or '').strip()
    fmt = (request.args.get('format') or '').strip()
    label = (request.args.get('label') or 'video').strip()
    if not url or not URL_RE.match(url):
        return 'Invalid YouTube URL.', 400
    if not fmt or not FORMAT_RE.match(fmt):
        return 'Invalid format selection.', 400

    tmpdir = tempfile.mkdtemp(prefix='tubefetch_')

    @after_this_request
    def cleanup(response):
        shutil.rmtree(tmpdir, ignore_errors=True)
        return response

    audio_only = (label or '').lower().startswith('mp3')
    outtmpl = os.path.join(tmpdir, 'video.%(ext)s')
    opts = ydl_opts({
        'format': fmt,
        'merge_output_format': 'mp4',
        'outtmpl': outtmpl,
        'noplaylist': True,
    })
    if audio_only:
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        info = download_with_fallback(url, opts)
    except Exception as e:  # noqa: BLE001
        return f'Download failed: {clean_error(e)}', 422

    files = glob.glob(os.path.join(tmpdir, '*'))
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        return 'Download failed: no file was produced.', 500
    path = max(files, key=os.path.getsize)
    ext = os.path.splitext(path)[1].lstrip('.') or ('mp3' if audio_only else 'mp4')

    title = sanitize_filename(info.get('title') or 'youtube_video', restricted=False)
    download_name = f'{title[:90]}.{ext}'
    mimetype = 'audio/mpeg' if ext == 'mp3' else 'video/mp4'
    return send_file(path, as_attachment=True, download_name=download_name, mimetype=mimetype)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
