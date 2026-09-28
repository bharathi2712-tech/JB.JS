from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import threading
from datetime import datetime

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = os.path.expanduser('~/YouTube Downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

download_progress = {}

class ProgressHook:
    def __init__(self, video_id):
        self.video_id = video_id
    
    def __call__(self, d):
        if d['status'] == 'downloading':
            percent = d['_percent_str'].strip()
            speed = d['_speed_str'].strip()
            eta = d['_eta_str'].strip()
            
            download_progress[self.video_id] = {
                'status': 'downloading',
                'percent': percent,
                'speed': speed,
                'eta': eta,
                'filename': d.get('filename', 'Unknown')
            }
        elif d['status'] == 'finished':
            download_progress[self.video_id] = {
                'status': 'finished',
                'filename': d.get('filename', 'Unknown'),
                'message': 'Download completed!'
            }

@app.route('/')
def index():
    return render_template('index1.html')

@app.route('/api/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    format_type = data.get('format', 'mp4')
    quality = data.get('quality', 'best')
    max_filesize = data.get('maxFilesize')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    video_id = datetime.now().strftime('%Y%m%d%H%M%S')
    download_progress[video_id] = {'status': 'initializing'}
    
    thread = threading.Thread(target=_download_video, args=(url, format_type, quality, max_filesize, video_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({'video_id': video_id, 'message': 'Download started'})

def _download_video(url, format_type, quality, max_filesize, video_id):
    try:
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
        
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'progress_hooks': [ProgressHook(video_id)],
            'quiet': False,
        }
        
        # Add file size limit if provided
        if max_filesize and max_filesize.isdigit():
            ydl_opts['max_filesize'] = int(max_filesize) * 1024 * 1024
        
        # Configure options based on format
        if format_type == 'mp3':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:  # mp4
            if quality == 'best':
                ydl_opts['format'] = 'bestvideo+bestaudio/best'
            else:
                # For specific quality (1080, 720, 480, etc.)
                ydl_opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            download_progress[video_id] = {
                'status': 'completed',
                'filename': os.path.basename(filename),
                'message': 'Download completed successfully!'
            }
    
    except Exception as e:
        download_progress[video_id] = {
            'status': 'error',
            'error': str(e)
        }

@app.route('/api/progress/<video_id>')
def get_progress(video_id):
    if video_id in download_progress:
        return jsonify(download_progress[video_id])
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/files')
def list_files():
    files = []
    if os.path.exists(DOWNLOAD_FOLDER):
        for file in os.listdir(DOWNLOAD_FOLDER):
            filepath = os.path.join(DOWNLOAD_FOLDER, file)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                size_mb = round(size / (1024 * 1024), 2)
                files.append({
                    'name': file,
                    'size': f'{size_mb} MB',
                    'date': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M')
                })
    return jsonify(sorted(files, key=lambda x: x['date'], reverse=True))

@app.route('/api/download-file/<filename>')
def download_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    if not os.path.abspath(filepath).startswith(os.path.abspath(DOWNLOAD_FOLDER)):
        return jsonify({'error': 'Invalid file'}), 403
    
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    if not os.path.abspath(filepath).startswith(os.path.abspath(DOWNLOAD_FOLDER)):
        return jsonify({'error': 'Invalid file'}), 403
    
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'message': 'File deleted'})
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🎥 Advanced YouTube Downloader")
    print("📱 Open http://localhost:5000 in your browser")
    print("💾 Downloads:", os.path.abspath(DOWNLOAD_FOLDER))
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
