import os
from flask import Flask, request, redirect, url_for, send_from_directory, render_template_string, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dropflow-secret-key-123')

# Configuração da pasta de uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'mp4', 'mp3', 'doc', 'docx'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite máximo de 16MB por ficheiro

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Interface HTML (Embutida para facilitar o deploy no Render)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DropFlow</title>
    <style>
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .container { max-width: 600px; width: 100%; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        h1 { text-align: center; color: #38bdf8; margin-top: 0; }
        .upload-box { border: 2px dashed #38bdf8; padding: 25px; text-align: center; border-radius: 8px; margin-bottom: 20px; background: #0f172a; }
        input[type="file"] { margin-bottom: 15px; width: 100%; color: #94a3b8; }
        button { background: #0284c7; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; width: 100%; font-size: 16px; font-weight: bold; }
        button:hover { background: #0369a1; }
        .file-list { list-style: none; padding: 0; margin-top: 20px; }
        .file-item { display: flex; justify-content: space-between; align-items: center; background: #334155; padding: 10px 15px; border-radius: 6px; margin-bottom: 8px; }
        .file-item a { color: #38bdf8; text-decoration: none; word-break: break-all; }
        .file-item a:hover { text-decoration: underline; }
        .flash { padding: 10px; background: #f59e0b; color: #000; border-radius: 6px; margin-bottom: 15px; text-align: center; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌊 DropFlow</h1>

        {% with messages = get_flashed_messages() %}
          {% if messages %}
            {% for message in messages %}
              <div class="flash">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <div class="upload-box">
            <form method="post" action="/upload" enctype="multipart/form-data">
                <input type="file" name="file" required>
                <button type="submit">Enviar Ficheiro</button>
            </form>
        </div>

        <h2>Ficheiros Guardados</h2>
        <ul class="file-list">
            {% for file in files %}
                <li class="file-item">
                    <a href="{{ url_for('download_file', name=file) }}" target="_blank">{{ file }}</a>
                </li>
            {% else %}
                <p style="color: #94a3b8; text-align: center;">Nenhum ficheiro enviado ainda.</p>
            {% endfor %}
        </ul>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    files = os.listdir(app.config['UPLOAD_FOLDER']) if os.path.exists(app.config['UPLOAD_FOLDER']) else []
    return render_template_string(HTML_TEMPLATE, files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('Nenhum ficheiro selecionado.')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum ficheiro selecionado.')
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash('Ficheiro enviado com sucesso!')
        return redirect(url_for('index'))
    else:
        flash('Tipo de ficheiro não suportado.')
        return redirect(url_for('index'))

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config['UPLOAD_FOLDER'], name)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
