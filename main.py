"""Rank Clip Studio — python main.py, porta 80."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import shutil
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parent / 'static'
RENDER_LOCK = threading.BoundedSemaphore(1)
MAX_BYTES = 180 * 1024 * 1024


def ffmpeg_path():
    binary = shutil.which('ffmpeg')
    if binary:
        return binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def reply_json(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/health':
            return self.reply_json(200, {'ok': True, 'mp4': bool(ffmpeg_path())})
        if path.startswith('/api/'):
            return self.reply_json(404, {'error': 'Endpoint inexistente.'})
        if path.startswith('/static/'):
            self.path = self.path[len('/static'):]
        return super().do_GET()

    def list_directory(self, path):
        self.send_error(404)
        return None

    def do_POST(self):
        if urlsplit(self.path).path != '/api/mp4':
            return self.reply_json(404, {'error': 'Endpoint inexistente.'})
        binary = ffmpeg_path()
        if not binary:
            return self.reply_json(503, {'error': 'Instala requirements.txt para ativar a conversão MP4.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_BYTES:
            return self.reply_json(413, {'error': 'Vídeo vazio ou maior que 180 MB.'})
        if not RENDER_LOCK.acquire(blocking=False):
            return self.reply_json(429, {'error': 'Existe outra conversão em curso. Tenta novamente.'})
        try:
            with tempfile.TemporaryDirectory(prefix='rank-clip-') as folder:
                source, output = Path(folder) / 'input.video', Path(folder) / 'clip.mp4'
                remaining = length
                self.connection.settimeout(120)
                with source.open('wb') as file:
                    while remaining:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError('Upload incompleto.')
                        file.write(chunk)
                        remaining -= len(chunk)
                result = subprocess.run([
                    binary, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
                    '-map', '0:v:0', '-map', '0:a?', '-vf', 'fps=30,scale=trunc(iw/2)*2:trunc(ih/2)*2',
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-threads', '2', str(output)
                ], capture_output=True, timeout=240)
                if result.returncode or not output.exists():
                    return self.reply_json(422, {'error': 'O vídeo não pôde ser convertido. O original continua disponível.'})
                self.send_response(200)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Content-Length', str(output.stat().st_size))
                self.send_header('Content-Disposition', 'attachment; filename="rank-clip.mp4"')
                self.end_headers()
                with output.open('rb') as file:
                    shutil.copyfileobj(file, self.wfile)
        except (ValueError, TimeoutError, subprocess.TimeoutExpired) as exc:
            self.reply_json(422, {'error': str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            RENDER_LOCK.release()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '80'))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'Rank Clip Studio: 0.0.0.0:{port} | MP4: {bool(ffmpeg_path())}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
