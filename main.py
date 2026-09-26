"""Rank Clip Studio — start with python main.py; listens on port 80."""
from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from pathlib import Path
import hmac
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading

BASE = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(BASE / 'templates'), static_folder=str(BASE / 'static'), static_url_path='')
app.secret_key = os.getenv('SESSION_SECRET') or secrets.token_hex(32)
app.config.update(MAX_CONTENT_LENGTH=250 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
RENDER_LOCK = threading.BoundedSemaphore(1)
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


@app.before_request
def require_login():
    if request.path == '/login' or request.path == '/api/health':
        return None
    if session.get('user') == 'admin':
        return None
    if request.path.startswith('/api/'):
        return jsonify(error='Please sign in.'), 401
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username', '')
        password = request.form.get('password', '')
        if hmac.compare_digest(user, os.getenv('ADMIN_USER', 'admin')) and hmac.compare_digest(password, os.getenv('ADMIN_PASSWORD', 'admin123')):
            session.clear()
            session['user'] = 'admin'
            return redirect('/')
        return render_template('login.html', error='Incorrect username or password.'), 401
    return render_template('login.html', error=None)


@app.post('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/api/health')
def health():
    return jsonify(ok=True, mp4=bool(ffmpeg_exe()))


@app.get('/api/ranks')
def ranks():
    return jsonify(ranks=RANKS, note='Rank Score limits from Supercell. Win gains vary by opponent score; there is no published average per rank.')


@app.post('/api/render')
def render_video():
    binary = ffmpeg_exe()
    if not binary:
        return jsonify(error='FFmpeg is not installed. Install requirements.txt.'), 503
    if not RENDER_LOCK.acquire(blocking=False):
        return jsonify(error='Another render is running. Please try again.'), 429
    try:
        manifest = json.loads(request.form.get('manifest', '{}'))
        lengths = manifest.get('durations', [])
        if not isinstance(lengths, list) or not 1 <= len(lengths) <= 12 or any(type(n) is not int or n < 1 or n > 5 for n in lengths):
            raise ValueError('Choose 1–12 scenes lasting 1–5 seconds each.')
        width, height = manifest.get('size', [])
        if (width, height) not in [(720, 1280), (1080, 1920), (1080, 720), (1620, 1080)]:
            raise ValueError('Invalid video size.')
        if any(f'scene{i}' not in request.files for i in range(len(lengths))):
            raise ValueError('One or more scene images are missing.')
        with tempfile.TemporaryDirectory(prefix='rank-studio-') as folder:
            work = Path(folder)
            arguments = [binary, '-hide_banner', '-loglevel', 'error', '-y']
            filters, labels = [], []
            seconds = sum(lengths)
            for i, length in enumerate(lengths):
                path = work / f'scene-{i}.png'
                request.files[f'scene{i}'].save(path)
                if path.stat().st_size > 20 * 1024 * 1024:
                    raise ValueError('Scene image exceeds 20 MB.')
                arguments.extend(['-loop', '1', '-framerate', f'1/{length}', '-t', str(length), '-i', str(path)])
                frames = length * 30
                filters.append(f"[{i}:v]zoompan=z='min(zoom+0.0018,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps=30,setsar=1,format=yuv420p[v{i}]")
                labels.append(f'[v{i}]')
            finale_index = None
            finale_audio = False
            finale_length = 0
            finale = request.files.get('final')
            if finale and finale.filename:
                final_path = work / 'final.input'
                finale.save(final_path)
                finale_length, finale_audio = media_details(binary, final_path)
                finale_index = len(lengths)
                arguments.extend(['-i', str(final_path)])
                filters.append(f'[{finale_index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps=30,trim=duration={finale_length:.3f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v{finale_index}]')
                labels.append(f'[v{finale_index}]')
                seconds += finale_length
            elif manifest.get('celebration') in ('masters', 'pro'):
                # The optional generated celebration is a final PNG supplied by the browser.
                final = request.files.get('endcard')
                if not final:
                    raise ValueError('The celebration image is missing.')
                final_path = work / 'endcard.png'
                final.save(final_path)
                finale_index = len(lengths)
                finale_length = 3
                arguments.extend(['-loop', '1', '-framerate', '1/3', '-t', '3', '-i', str(final_path)])
                filters.append(f"[{finale_index}:v]zoompan=z='min(zoom+0.0018,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=90:s={width}x{height}:fps=30,format=yuv420p[v{finale_index}]")
                labels.append(f'[v{finale_index}]')
                seconds += 3
            filters.append(''.join(labels) + f'concat=n={len(labels)}:v=1:a=0[outv]')
            music = request.files.get('music')
            music_index = len(lengths) + (1 if finale_index is not None else 0)
            if music and music.filename:
                music_path = work / 'music.input'
                music.save(music_path)
                arguments.extend(['-stream_loop', '-1', '-i', str(music_path)])
                filters.append(f'[{music_index}:a]atrim=duration={seconds:.3f},asetpts=PTS-STARTPTS,volume=0.55[bg]')
            if finale_audio:
                filters.append(f'[{finale_index}:a]atrim=duration={finale_length:.3f},asetpts=PTS-STARTPTS,adelay={sum(lengths)*1000}:all=1,atrim=duration={seconds:.3f}[fa]')
            if music and music.filename and finale_audio:
                filters.append('[bg][fa]amix=inputs=2:duration=first:dropout_transition=0[outa]')
                audio_label = '[outa]'
            elif music and music.filename:
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
            return send_file(io.BytesIO(output.read_bytes()), mimetype='video/mp4', as_attachment=True, download_name='rank-clip.mp4')
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return jsonify(error=str(exc)), 422
    except subprocess.TimeoutExpired:
        return jsonify(error='Rendering timed out. Try 720p or fewer scenes.'), 504
    finally:
        RENDER_LOCK.release()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '80')), threaded=True)
