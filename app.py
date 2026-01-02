from flask import (
    Flask, request, jsonify, send_from_directory,
    session
)
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import subprocess
import threading
import os
import datetime
import json
import time
import sys  # <-- added
from chatbox import generate_chat_reply

# ---- Paths & command file shared with control_service.py ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMMAND_FILE = os.path.join(BASE_DIR, "control_command.json")

app = Flask(__name__, static_folder='Frontend', static_url_path='')

app.config['SECRET_KEY'] = 'change-this-to-a-strong-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=7)

db = SQLAlchemy(app)
CORS(app, supports_credentials=True)

# ---- Controller process (control_service.py) ----
controller_proc = None
controller_started = False

@app.before_request
def start_controller_once():
    global controller_started
    if not controller_started:
        start_controller()
        controller_started = True


def start_controller():
    """
    Start control_service.py as a background process if not already running.
    """
    global controller_proc

    # If already started and still running, do nothing
    if controller_proc is not None and controller_proc.poll() is None:
        return

    controller_script = os.path.join(BASE_DIR, "control_service.py")

    try:
        controller_proc = subprocess.Popen(
            [sys.executable, controller_script]
        )
        print("Control service started with PID:", controller_proc.pid)
    except Exception as e:
        print("Failed to start control service:", e)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_message = db.Column(db.Text, nullable=False)
    bot_reply = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    user = db.relationship('User', backref=db.backref('messages', lazy=True))


with app.app_context():
    db.create_all()


@app.route("/")
def home():
    if "user_id" not in session:
        return app.send_static_file("login.html")
    return app.send_static_file("index.html")


@app.route("/run", methods=["POST"])
def run_mode():
    # ensure controller is running (extra safety)
    start_controller()

    data = request.get_json() or {}
    script = data.get("script", "").lower()

    # Map old script names / labels to logical modes
    if "aimouse" in script or "handgesture" in script or "hand" in script:
        mode = "hand"
    elif "eye" in script:
        mode = "eye"
    elif "voice" in script:
        mode = "voice"
    elif "keyboard" in script:
        mode = "keyboard"
    elif "stop" in script:
        mode = "none"
    else:
        return jsonify({"error": f"Unknown mode for script: {script}"}), 400

    # Write desired mode into command file
    cmd = {"mode": mode, "time": time.time()}
    try:
        with open(COMMAND_FILE, "w", encoding="utf-8") as f:
            json.dump(cmd, f)
    except Exception as e:
        print("Error writing command file:", e)
        return jsonify({"error": "Failed to send command to controller"}), 500

    if mode == "none":
        msg = "All control modes stopped."
    else:
        msg = f"{mode.upper()} mode requested. Previous mode will stop automatically."

    return jsonify({"message": msg})


@app.route('/3d_model/<path:filename>')
def serve_3d_model(filename):
    return send_from_directory('3d_model', filename)


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({"error": "Username and password required."}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists."}), 400

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User registered successfully."})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password."}), 401

    session['user_id'] = user.id
    session['username'] = user.username
    session.permanent = True 
    
    return jsonify({"message": "Logged in successfully.", "username": user.username})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@app.route('/api/me', methods=['GET'])
def me():
    if 'user_id' not in session:
        return jsonify({"authenticated": False})
    return jsonify({
        "authenticated": True,
        "username": session.get('username')
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated."}), 401

    data = request.get_json() or {}
    user_message = (data.get('message') or '').strip()
    if not user_message:
        return jsonify({"error": "Empty message."}), 400

    user_id = session['user_id']

    last_msgs = ChatMessage.query.filter_by(user_id=user_id) \
        .order_by(ChatMessage.created_at.desc()) \
        .limit(10).all()
    history = []
    for m in reversed(last_msgs):
        history.append({"role": "user", "content": m.user_message})
        history.append({"role": "assistant", "content": m.bot_reply})

    try:
        reply = generate_chat_reply(user_message, history=history)
    except Exception as e:
        print("Chat error:", e)
        return jsonify({"error": f"AI error: {e}"}), 500

    chat_msg = ChatMessage(
        user_id=user_id,
        user_message=user_message,
        bot_reply=reply,
    )
    db.session.add(chat_msg)
    db.session.commit()

    return jsonify({"reply": reply})


@app.route('/api/chat/history', methods=['GET'])
def chat_history():
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated."}), 401

    user_id = session['user_id']
    msgs = ChatMessage.query.filter_by(user_id=user_id) \
        .order_by(ChatMessage.created_at.asc()) \
        .all()

    data = []
    for m in msgs:
        data.append({
            "id": m.id,
            "user_message": m.user_message,
            "bot_reply": m.bot_reply,
            "created_at": m.created_at.isoformat() + "Z",
        })
    return jsonify({"messages": data})


if __name__ == "__main__":
    app.run(debug=True)
