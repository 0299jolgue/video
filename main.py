"""Rank Clip Studio: standard-library HTTP server on 0.0.0.0:80."""
from email import policy
from email.parser import BytesParser
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import hmac
import html
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time

BASE = Path(__file__).resolve().parent
STATIC = BASE / 'static'
RENDER_LOCK = threading.BoundedSemaphore(1)
SESSIONS = {}
MAX_UPLOAD = 250 * 1024 * 1024
RANKS = [
    {'name': 'Bronze', 'min': 0}, {'name': 'Silver', 'min': 750},
    {'name': 'Gold', 'min': 1500}, {'name': 'Diamond', 'min': 3000},
    {'name': 'Mythic', 'min': 4500}, {'name': 'Legendary', 'min': 6000},
    {'name': 'Masters', 'min': 8500}, {'name': 'Pro', 'min': 11250},
]


def ffmpeg_exe():
    found = shutil.which('ffmpeg')
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None


def media_details(binary, path):
    probe = subprocess.run([binary, '-hide_banner', '-i', str(path)], capture_output=True, timeout=15)
    details = probe.stderr.decode('utf-8', errors='replace')
    match = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', details)
    if not match or 'Video:' not in details:
        raise ValueError('The uploaded final video could not be read.')
    seconds = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
    return min(60.0, seconds), 'Audio:' in details


def render_video(manifest, uploads):
    binary = ffmpeg_exe()
    if not binary:
        raise RuntimeError('FFmpeg is unavailable. Install requirements.txt.')
    lengths = manifest.get('durations', [])
    if not isinstance(lengths, list) or not 1 <= len(lengths) <= 12 or any(type(n) is not int or n < 1 or n > 5 for n in lengths):
        raise ValueError('Choose 1–12 scenes lasting 1–5 seconds each.')
    width, height = manifest.get('size', [])
    if (width, height) not in [(720, 1280), (1080, 1920), (1080, 720), (1620, 1080)]:
        raise ValueError('Invalid video size.')
    if any(f'scene{i}' not in uploads for i in range(len(lengths))):
        raise ValueError('One or more scene images are missing.')
    with tempfile.TemporaryDirectory(prefix='rank-studio-') as folder:
        work = Path(folder)
        arguments = [binary, '-hide_banner', '-loglevel', 'error', '-y']
        filters, labels = [], []
        seconds = sum(lengths)
        for i, length in enumerate(lengths):
            data = uploads[f'scene{i}']
            if len(data) > 20 * 1024 * 1024:
                raise ValueError('Scene image exceeds 20 MB.')
            path = work / f'scene-{i}.png'
            path.write_bytes(data)
            arguments.extend(['-loop', '1', '-framerate', f'1/{length}', '-t', str(length), '-i', str(path)])
            frames = length * 30
            filters.append(f"[{i}:v]zoompan=z='min(zoom+0.0018,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps=30,setsar=1,format=yuv420p[v{i}]")
            labels.append(f'[v{i}]')
        finale_index = None
        finale_audio = False
        finale_length = 0
        if uploads.get('final'):
            final_path = work / 'final.input'
            final_path.write_bytes(uploads['final'])
            finale_length, finale_audio = media_details(binary, final_path)
            finale_index = len(lengths)
            arguments.extend(['-i', str(final_path)])
            filters.append(f'[{finale_index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps=30,trim=duration={finale_length:.3f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v{finale_index}]')
            labels.append(f'[v{finale_index}]')
            seconds += finale_length
        elif manifest.get('celebration') in ('masters', 'pro'):
            if not uploads.get('endcard'):
                raise ValueError('The celebration image is missing.')
            final_path = work / 'endcard.png'
            final_path.write_bytes(uploads['endcard'])
            finale_index = len(lengths)
            finale_length = 3
            arguments.extend(['-loop', '1', '-framerate', '1/3', '-t', '3', '-i', str(final_path)])
            filters.append(f"[{finale_index}:v]zoompan=z='min(zoom+0.0018,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=90:s={width}x{height}:fps=30,format=yuv420p[v{finale_index}]")
            labels.append(f'[v{finale_index}]')
            seconds += 3
        filters.append(''.join(labels) + f'concat=n={len(labels)}:v=1:a=0[outv]')
        music_index = len(lengths) + (1 if finale_index is not None else 0)
        if uploads.get('music'):
            music_path = work / 'music.input'
            music_path.write_bytes(uploads['music'])
            arguments.extend(['-stream_loop', '-1', '-i', str(music_path)])
            filters.append(f'[{music_index}:a]atrim=duration={seconds:.3f},asetpts=PTS-STARTPTS,volume=0.55[bg]')
        if finale_audio:
            filters.append(f'[{finale_index}:a]atrim=duration={finale_length:.3f},asetpts=PTS-STARTPTS,adelay={sum(lengths)*1000}:all=1,atrim=duration={seconds:.3f}[fa]')
        if uploads.get('music') and finale_audio:
            filters.append('[bg][fa]amix=inputs=2:duration=first:dropout_transition=0[outa]')
            audio_label = '[outa]'
        elif uploads.get('music'):
            audio_label = '[bg]'
        elif finale_audio:
            audio_label = '[fa]'
        else:
            audio_label = None
        output = work / 'rank-clip.mp4'
        arguments.extend(['-filter_complex', ';'.join(filters), '-map', '[outv]'])
        if audio_label:
            arguments.extend(['-map', audio_label, '-c:a', 'aac', '-b:a', '160k'])
        arguments.extend(['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-threads', '2', '-t', f'{seconds:.3f}', str(output)])
        result = subprocess.run(arguments, capture_output=True, timeout=300)
        if result.returncode or not output.exists():
            raise ValueError('Video rendering failed: ' + result.stderr.decode('utf-8', errors='replace')[-700:])
        return output.read_bytes()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def reply(self, code, data, content_type='text/html; charset=utf-8', extra=None):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def reply_json(self, code, data):
        self.reply(code, json.dumps(data), 'application/json; charset=utf-8')

    def token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return None
        item = cookie.get('rank_session')
        if item and SESSIONS.get(item.value, 0) > time.time():
            return item.value
        return None

    def authorized(self, path):
        if self.token():
            return True
        if path.startswith('/api/'):
            self.reply_json(401, {'error': 'Please sign in.'})
        else:
            self.send_response(302)
            self.send_header('Location', '/login')
            self.end_headers()
        return False

    def page(self, name, error=''):
        markup = (BASE / 'templates' / name).read_text(encoding='utf-8')
        if name == 'index.html':
            markup = markup.replace('{{ asset_version }}', str(int((STATIC / 'app.js').stat().st_mtime)))
        if name == 'login.html':
            markup = markup.replace('<!--LOGIN_ERROR-->', f'<p class="login-error" role="alert">{html.escape(error)}</p>' if error else '')
        self.reply(401 if error else 200, markup)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/health':
            return self.reply_json(200, {'ok': True, 'mp4': bool(ffmpeg_exe())})
        if path == '/login':
            return self.page('login.html')
        if path == '/style.css':
            return super().do_GET()
        if not self.authorized(path):
            return
        if path == '/':
            return self.page('index.html')
        if path == '/api/ranks':
            return self.reply_json(200, {'ranks': RANKS, 'note': 'Rank Score limits from Supercell. Win gains vary by opponent score; there is no published average per rank.'})
        if path.startswith('/api/'):
            return self.reply_json(404, {'error': 'Unknown endpoint.'})
        if path in ('/app.js', '/template.png', '/game.ttf', '/FONT-LICENSE.txt'):
            return super().do_GET()
        self.send_error(404)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == '/login':
            return self.login()
        if not self.authorized(path):
            return
        if path == '/logout':
            SESSIONS.pop(self.token(), None)
            self.send_response(302)
            self.send_header('Location', '/login')
            self.send_header('Set-Cookie', 'rank_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax')
            self.end_headers()
            return
        if path == '/api/render':
            return self.render()
        self.reply_json(404, {'error': 'Unknown endpoint.'})

    def login(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size < 4096:
                raise ValueError('Invalid login form.')
            fields = parse_qs(self.rfile.read(size).decode('utf-8'))
            user = fields.get('username', [''])[0]
            password = fields.get('password', [''])[0]
            if hmac.compare_digest(user, os.getenv('ADMIN_USER', 'admin')) and hmac.compare_digest(password, os.getenv('ADMIN_PASSWORD', 'admin123')):
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = time.time() + 86400
                self.send_response(302)
                self.send_header('Location', '/')
                self.send_header('Set-Cookie', f'rank_session={token}; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax')
                self.end_headers()
            else:
                self.page('login.html', 'Incorrect username or password.')
        except ValueError as exc:
            self.page('login.html', str(exc))

    def render(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_UPLOAD:
                return self.reply_json(413, {'error': 'Upload is empty or exceeds 250 MB.'})
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data;'):
                return self.reply_json(415, {'error': 'Expected multipart form data.'})
        except ValueError:
            return self.reply_json(400, {'error': 'Invalid Content-Length.'})
        if not RENDER_LOCK.acquire(blocking=False):
            return self.reply_json(429, {'error': 'Another render is running. Please try again.'})
        try:
            self.connection.settimeout(120)
            payload = self.rfile.read(size)
            if len(payload) != size:
                raise ValueError('Incomplete upload.')
            head = ('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode('utf-8')
            message = BytesParser(policy=policy.default).parsebytes(head + payload)
            if not message.is_multipart():
                raise ValueError('Invalid multipart upload.')
            files = {}
            manifest = None
            for part in message.iter_parts():
                name = part.get_param('name', header='Content-Disposition')
                if name == 'manifest':
                    manifest = json.loads(part.get_content())
                elif name:
                    files[name] = part.get_payload(decode=True)
            if not isinstance(manifest, dict):
                raise ValueError('Missing video settings.')
            result = render_video(manifest, files)
            self.reply(200, result, 'video/mp4', {'Content-Disposition': 'attachment; filename="rank-clip.mp4"'})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.reply_json(422, {'error': str(exc)})
        except (TimeoutError, subprocess.TimeoutExpired):
            self.reply_json(504, {'error': 'Rendering timed out. Try 720p or fewer scenes.'})
        except RuntimeError as exc:
            self.reply_json(503, {'error': str(exc)})
        finally:
            RENDER_LOCK.release()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '80'))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'Rank Clip Studio ready on 0.0.0.0:{port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
