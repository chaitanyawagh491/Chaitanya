from flask import Flask, request, jsonify, g
import sqlite3
import os
import hashlib
import hmac
import base64
import json
import bcrypt
from datetime import datetime
from pathlib import Path
from typing import Optional

app = Flask(__name__)

DB_PATH = Path(__file__).parent / "auth.db"
JWT_SECRET = os.environ.get("JWT_SECRET", "DEFAULT_JWT_SIGNING_KEY_visual_analyzer_dev")

DEFAULT_USER_CREDITS = 15

def get_db() -> sqlite3.Connection:
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(str(DB_PATH))
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_local_db():
    os.makedirs(Path(DB_PATH).parent, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    cursor = db.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        hwid TEXT DEFAULT NULL,
        is_banned INTEGER DEFAULT 0,
        credits INTEGER DEFAULT 15,
        credits_unlimited INTEGER DEFAULT 0,
        lifetime_requests INTEGER DEFAULT 0,
        last_request_at TEXT DEFAULT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_login TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS login_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        ip_address TEXT,
        hwid TEXT,
        status TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT,
        ip_address TEXT,
        details TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invite_keys (
        key TEXT PRIMARY KEY,
        is_used INTEGER DEFAULT 0,
        used_by TEXT DEFAULT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 15")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN credits_unlimited INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN lifetime_requests INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_request_at TEXT DEFAULT NULL")
    except Exception:
        pass
    cursor.execute(
        "UPDATE users SET credits = 15 WHERE credits IS NULL AND credits_unlimited = 0"
    )
    configs = {
        "latest_version": "3.0.0",
        "changelog": "V3 Local Development Release.",
        "download_url": "",
        "announcements": "Welcome to local development server."
    }
    for key, value in configs.items():
        cursor.execute("SELECT key FROM system_config WHERE key = ?", (key,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO system_config (key, value) VALUES (?, ?)", (key, value)
            )
    cursor.execute("SELECT username FROM users WHERE username = ?", ("admin",))
    if not cursor.fetchone():
        admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
        hashed = hash_password(admin_pass)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, credits, credits_unlimited) VALUES (?, ?, ?, ?, ?)",
            ("admin", hashed, "admin", 15, 1)
        )
        print("[DB] Seeded administrator account: admin")
    db.commit()
    db.close()
    print("[DB] Local database initialized.")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")

def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def sign_jwt(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    token_input = f"{header_b64}.{payload_b64}"
    sig = hmac.new(JWT_SECRET.encode(), token_input.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{token_input}.{sig_b64}"

def verify_jwt(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        token_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(JWT_SECRET.encode(), token_input.encode(), hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        if not hmac.compare_digest(sig_b64, expected_b64):
            return None
        padded = payload_b64 + "=" * ((4 - len(payload_b64) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if payload.get("exp") and datetime.now().timestamp() > payload["exp"]:
            return None
        return payload
    except Exception:
        return None

def check_admin_session() -> Optional[dict]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    payload = verify_jwt(token)
    if payload and payload.get("role") in ["admin", "moderator"]:
        return payload
    return None

def check_user_session() -> Optional[dict]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    return verify_jwt(token)

def log_audit(actor: str, action: str, target: str, ip: str, details: str):
    try:
        db = get_db()
        db.execute(
            "INSERT INTO audit_log (actor, action, target, ip_address, details) VALUES (?, ?, ?, ?, ?)",
            (actor, action, target, ip, details)
        )
        db.commit()
    except Exception as e:
        print(f"[AUDIT] Failed to write audit log: {e}")

def is_primary_owner(username: str, db: sqlite3.Connection) -> bool:
    primary_owner = os.environ.get("PRIMARY_OWNER", "admin")
    if username == primary_owner:
        return True
    try:
        row = db.execute("SELECT username FROM users ORDER BY created_at ASC LIMIT 1").fetchone()
        return row and row["username"] == username
    except Exception:
        return False

@app.route("/api/ping", methods=["GET"])
def ping():
    db_status = "connected"
    try:
        get_db().execute("SELECT 1").fetchone()
    except Exception:
        db_status = "error"
    return jsonify({"status": "online", "database": db_status, "timestamp": datetime.now().isoformat()})

@app.route("/api/announcements", methods=["GET"])
def announcements():
    row = get_db().execute("SELECT value FROM system_config WHERE key = 'announcements'").fetchone()
    return jsonify({"announcements": row["value"] if row else ""})

@app.route("/api/update", methods=["GET"])
def update():
    client_ver = request.args.get("version", "")
    db = get_db()
    rows = db.execute("SELECT key, value FROM system_config").fetchall()
    config_map = {r["key"]: r["value"] for r in rows}
    latest = config_map.get("latest_version", "3.0.0")
    return jsonify({
        "latest_version": latest,
        "changelog": config_map.get("changelog", ""),
        "download_url": config_map.get("download_url", ""),
        "update_available": latest != client_ver
    })

@app.route("/api/changelog", methods=["GET"])
def changelog():
    row = get_db().execute("SELECT value FROM system_config WHERE key = 'changelog'").fetchone()
    return row["value"] if row else ""

@app.route("/api/local-session", methods=["POST"])
def local_session():
    if request.remote_addr not in ("127.0.0.1", "localhost", "::1"):
        return jsonify({"success": False, "message": "Local sessions only available on localhost."}), 403

    data = request.get_json() or {}
    hwid = data.get("hwid", "").strip()
    db = get_db()

    username = "local_user"
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        default_pass = hashlib.sha256(f"local_{hwid}".encode()).hexdigest()[:16]
        hashed = hash_password(default_pass)
        db.execute(
            "INSERT INTO users (username, password_hash, role, credits, credits_unlimited, hwid) VALUES (?, ?, ?, ?, ?, ?)",
            (username, hashed, "user", 9999, 1, hwid or None)
        )
        db.commit()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    elif hwid and not user["hwid"]:
        db.execute("UPDATE users SET hwid = ? WHERE username = ?", (hwid, username))
        db.commit()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("UPDATE users SET last_login = ? WHERE username = ?", (now_str, username))
    db.commit()

    exp = datetime.now().timestamp() + (30 * 86400)
    token = sign_jwt({"username": user["username"], "role": user["role"], "exp": exp})
    credits_val = user["credits"] if user["credits"] is not None else 9999
    credits_unlimited = bool(user["credits_unlimited"])

    return jsonify({
        "success": True,
        "token": token,
        "user_data": {
            "username": user["username"],
            "ip": request.remote_addr,
            "hwid": user["hwid"] or hwid,
            "role": user["role"],
            "expires": "Never (Lifetime)",
            "createdate": user["created_at"],
            "lastlogin": now_str,
            "subscription": "Local Edition",
            "credits": credits_val,
            "credits_unlimited": credits_unlimited,
            "lifetime_requests": user["lifetime_requests"] or 0
        }
    })

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    hwid = data.get("hwid", "").strip()
    ip_addr = request.remote_addr
    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not check_password(password, user["password_hash"]):
        db.execute(
            "INSERT INTO login_history (username, ip_address, hwid, status) VALUES (?, ?, ?, ?)",
            (username, ip_addr, hwid, "FAILED_PASSWORD")
        )
        db.commit()
        return jsonify({"success": False, "message": "Invalid username or password"}), 401
    if user["is_banned"] == 1:
        db.execute(
            "INSERT INTO login_history (username, ip_address, hwid, status) VALUES (?, ?, ?, ?)",
            (username, ip_addr, hwid, "BANNED")
        )
        db.commit()
        return jsonify({"success": False, "message": "Account has been banned"}), 403
    user_hwid = user["hwid"]
    if not user_hwid:
        db.execute("UPDATE users SET hwid = ? WHERE username = ?", (hwid, username))
        db.commit()
        user_hwid = hwid
    elif user_hwid != hwid:
        db.execute(
            "INSERT INTO login_history (username, ip_address, hwid, status) VALUES (?, ?, ?, ?)",
            (username, ip_addr, hwid, "DEVICE_MISMATCH")
        )
        db.commit()
        return jsonify({"success": False, "message": "Device mismatch."}), 403
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("UPDATE users SET last_login = ? WHERE username = ?", (now_str, username))
    db.execute(
        "INSERT INTO login_history (username, ip_address, hwid, status) VALUES (?, ?, ?, ?)",
        (username, ip_addr, hwid, "SUCCESS")
    )
    db.commit()
    exp = datetime.now().timestamp() + (24 * 3600)
    token = sign_jwt({"username": user["username"], "role": user["role"], "exp": exp})
    credits_val = user["credits"] if user["credits"] is not None else DEFAULT_USER_CREDITS
    credits_unlimited = bool(user["credits_unlimited"])
    return jsonify({
        "success": True,
        "token": token,
        "user_data": {
            "username": user["username"],
            "ip": ip_addr,
            "hwid": user_hwid,
            "role": user["role"],
            "expires": "Never (Lifetime)",
            "createdate": user["created_at"],
            "lastlogin": now_str,
            "subscription": (
                "Developer Admin" if user["role"] == "admin"
                else "Moderator" if user["role"] == "moderator"
                else "Standard Client"
            ),
            "credits": credits_val,
            "credits_unlimited": credits_unlimited,
            "lifetime_requests": user["lifetime_requests"] or 0
        }
    })

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    hwid = data.get("hwid", "").strip()
    requested_role = data.get("role", "user").strip()
    invite_key = data.get("invite_key", "").strip()
    ip_addr = request.remote_addr
    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400
    db = get_db()
    if db.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone():
        return jsonify({"success": False, "message": "Username already exists"}), 409
    count = db.execute("SELECT count(*) as count FROM users").fetchone()["count"]
    final_role = "user"
    is_bootstrap = False
    if count == 0:
        final_role = "admin"
        is_bootstrap = True
    else:
        init_secret = request.headers.get("X-Init-Secret")
        env_secret = os.environ.get("INIT_SECRET", "visual_analyzer_init")
        if init_secret and init_secret == env_secret:
            if requested_role in ["admin", "moderator"]:
                final_role = requested_role
                is_bootstrap = True
    if not is_bootstrap:
        if not invite_key:
            return jsonify({"success": False, "message": "A valid access key is required for registration."}), 400
        inv = db.execute("SELECT * FROM invite_keys WHERE key = ? AND is_used = 0", (invite_key,)).fetchone()
        if not inv:
            return jsonify({"success": False, "message": "Invalid or already used access key."}), 403
        db.execute("UPDATE invite_keys SET is_used = 1, used_by = ? WHERE key = ?", (username, invite_key))
    hashed = hash_password(password)
    is_admin_role = final_role in ["admin"]
    initial_credits = 15
    initial_unlimited = 1 if is_admin_role else 0
    db.execute(
        "INSERT INTO users (username, password_hash, hwid, role, credits, credits_unlimited) VALUES (?, ?, ?, ?, ?, ?)",
        (username, hashed, hwid if hwid else None, final_role, initial_credits, initial_unlimited)
    )
    db.commit()
    if is_bootstrap and final_role != "user":
        log_audit("SYSTEM_INIT", "INITIALIZE_PRIVILEGED_ROLE", username, ip_addr, f"Role: {final_role}")
    else:
        log_audit("SYSTEM", "REGISTER_USER_WITH_KEY", username, ip_addr, f"Key: {invite_key}")
    return jsonify({"success": True, "message": f"Registration successful. Role: {final_role}"}), 201

@app.route("/api/user/credits", methods=["GET"])
def get_user_credits():
    session = check_user_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    username = session["username"]
    db = get_db()
    user = db.execute(
        "SELECT credits, credits_unlimited, lifetime_requests, last_request_at FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    if not user:
        return jsonify({"message": "User not found"}), 404
    return jsonify({
        "username": username,
        "credits": user["credits"] if user["credits"] is not None else 0,
        "credits_unlimited": bool(user["credits_unlimited"]),
        "lifetime_requests": user["lifetime_requests"] or 0,
        "last_request_at": user["last_request_at"]
    })

@app.route("/api/user/consume-credit", methods=["POST"])
def consume_credit():
    session = check_user_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    username = session["username"]
    db = get_db()
    user = db.execute(
        "SELECT credits, credits_unlimited FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    if not user:
        return jsonify({"message": "User not found"}), 404
    if user["credits_unlimited"]:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE users SET lifetime_requests = lifetime_requests + 1, last_request_at = ? WHERE username = ?",
            (now_str, username)
        )
        db.commit()
        return jsonify({"success": True, "credits": -1, "unlimited": True, "message": "Request processed."})
    if not user["credits"] or user["credits"] <= 0:
        return jsonify({
            "success": False,
            "credits": 0,
            "unlimited": False,
            "message": "No credits available. Contact administrator."
        }), 402
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """UPDATE users
           SET credits = credits - 1,
               lifetime_requests = lifetime_requests + 1,
               last_request_at = ?
           WHERE username = ?""",
        (now_str, username)
    )
    db.commit()
    updated = db.execute("SELECT credits FROM users WHERE username = ?", (username,)).fetchone()
    remaining = updated["credits"] if updated else 0
    return jsonify({"success": True, "credits": remaining, "unlimited": False, "message": "Credit consumed."})

@app.route("/api/admin/invites", methods=["GET"])
def admin_invites():
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    db = get_db()
    rows = db.execute("SELECT key, is_used, used_by, created_at FROM invite_keys ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/admin/invites", methods=["POST"])
def admin_create_invite():
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    import uuid
    key = f"PORTAL-{uuid.uuid4().hex[:12].upper()}"
    db = get_db()
    db.execute("INSERT INTO invite_keys (key, is_used) VALUES (?, 0)", (key,))
    db.commit()
    log_audit(session["username"], "GENERATE_INVITE_KEY", key, request.remote_addr, "Generated invite key.")
    return jsonify({"message": "Access key generated successfully", "key": key})

@app.route("/api/admin/invites/<key>", methods=["DELETE"])
def admin_delete_invite(key):
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    db = get_db()
    db.execute("DELETE FROM invite_keys WHERE key = ?", (key,))
    db.commit()
    log_audit(session["username"], "DELETE_INVITE_KEY", key, request.remote_addr, "Deleted access key.")
    return jsonify({"message": "Access key deleted successfully"})

@app.route("/api/admin/users", methods=["GET"])
def admin_users():
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    db = get_db()
    oldest = db.execute("SELECT username FROM users ORDER BY created_at ASC LIMIT 1").fetchone()
    oldest_username = oldest["username"] if oldest else None
    rows = db.execute(
        """SELECT username, role, hwid, is_banned, credits, credits_unlimited,
                  lifetime_requests, last_request_at, created_at, last_login
           FROM users"""
    ).fetchall()
    result = []
    primary_owner = os.environ.get("PRIMARY_OWNER", "admin")
    for row in rows:
        d = dict(row)
        d["is_owner"] = (
            d["username"] == oldest_username or
            d["username"] == primary_owner
        )
        result.append(d)
    return jsonify(result)

@app.route("/api/admin/users", methods=["POST"])
def admin_create():
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "user").strip()
    if not username or not password:
        return jsonify({"message": "Username and password required"}), 400
    if session["role"] == "moderator" and role != "user":
        return jsonify({"message": "Moderators cannot create privileged profiles."}), 403
    db = get_db()
    if db.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone():
        return jsonify({"message": "Username already exists"}), 409
    hashed = hash_password(password)
    is_admin_role = role == "admin"
    db.execute(
        "INSERT INTO users (username, password_hash, role, credits, credits_unlimited) VALUES (?, ?, ?, ?, ?)",
        (username, hashed, role, DEFAULT_USER_CREDITS, 1 if is_admin_role else 0)
    )
    db.commit()
    log_audit(session["username"], "CREATE_USER", username, request.remote_addr, f"Role: {role}")
    return jsonify({"message": f"User '{username}' created successfully"})

@app.route("/api/admin/users/<username>", methods=["DELETE"])
def admin_delete(username):
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    if session["username"] == username:
        return jsonify({"message": "Cannot delete your own account"}), 400
    db = get_db()
    if is_primary_owner(username, db):
        return jsonify({"message": "Cannot delete the protected primary owner account."}), 403
    if session["role"] == "moderator":
        return jsonify({"message": "Moderators are not authorized to delete profiles."}), 403
    db.execute("DELETE FROM users WHERE username = ?", (username,))
    db.commit()
    log_audit(session["username"], "DELETE_USER", username, request.remote_addr, "Deleted user.")
    return jsonify({"message": f"User '{username}' deleted successfully"})

@app.route("/api/admin/reset-password", methods=["POST"])
def admin_reset_pass():
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    data = request.get_json() or {}
    target = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not target or not password:
        return jsonify({"message": "Username and password required"}), 400
    db = get_db()
    if is_primary_owner(target, db) and session["username"] != target:
        return jsonify({"message": "Cannot reset password for the primary owner account."}), 403
    user = db.execute("SELECT role FROM users WHERE username = ?", (target,)).fetchone()
    if not user:
        return jsonify({"message": "User not found"}), 404
    if session["role"] == "moderator" and user["role"] == "admin":
        return jsonify({"message": "Moderators cannot reset administrator passwords."}), 403
    hashed = hash_password(password)
    db.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hashed, target))
    db.commit()
    log_audit(session["username"], "RESET_PASSWORD", target, request.remote_addr, "Password reset.")
    return jsonify({"message": "Password reset successfully."})

@app.route("/api/admin/reset-hwid", methods=["POST"])
def admin_reset_hwid():
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    data = request.get_json() or {}
    target = data.get("username", "").strip()
    if not target:
        return jsonify({"message": "Username required"}), 400
    db = get_db()
    if is_primary_owner(target, db) and session["username"] != target:
        return jsonify({"message": "Cannot reset HWID for the primary owner account."}), 403
    db.execute("UPDATE users SET hwid = NULL WHERE username = ?", (target,))
    db.commit()
    log_audit(session["username"], "RESET_HWID", target, request.remote_addr, "HWID reset.")
    return jsonify({"message": "Device binding reset successfully."})

@app.route("/api/admin/ban", methods=["POST"])
def admin_ban():
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    data = request.get_json() or {}
    target = data.get("username", "").strip()
    banned = int(data.get("banned", 1))
    if not target:
        return jsonify({"message": "Username required"}), 400
    if session["username"] == target:
        return jsonify({"message": "Cannot ban your own account"}), 400
    db = get_db()
    if is_primary_owner(target, db):
        return jsonify({"message": "Cannot ban the primary owner account."}), 403
    user = db.execute("SELECT role FROM users WHERE username = ?", (target,)).fetchone()
    if not user:
        return jsonify({"message": "User not found"}), 404
    if session["role"] == "moderator" and user["role"] == "admin":
        return jsonify({"message": "Moderators cannot ban admin profiles."}), 403
    db.execute("UPDATE users SET is_banned = ? WHERE username = ?", (banned, target))
    db.commit()
    action = "BANNED" if banned == 1 else "UNBANNED"
    log_audit(session["username"], action, target, request.remote_addr, f"Status: {banned}")
    return jsonify({"message": f"User '{target}' has been {action.lower()}."})

@app.route("/api/admin/users/<username>/credits", methods=["GET"])
def admin_get_credits(username):
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    db = get_db()
    user = db.execute(
        "SELECT credits, credits_unlimited, lifetime_requests, last_request_at FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    if not user:
        return jsonify({"message": "User not found"}), 404
    return jsonify({
        "username": username,
        "credits": user["credits"] if user["credits"] is not None else 0,
        "credits_unlimited": bool(user["credits_unlimited"]),
        "lifetime_requests": user["lifetime_requests"] or 0,
        "last_request_at": user["last_request_at"]
    })

@app.route("/api/admin/users/<username>/credits", methods=["POST"])
def admin_set_credits(username):
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    data = request.get_json() or {}
    action = data.get("action", "set")
    amount = data.get("amount", 0)
    unlimited = data.get("unlimited", None)
    db = get_db()
    user = db.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        return jsonify({"message": "User not found"}), 404
    if unlimited is not None:
        db.execute("UPDATE users SET credits_unlimited = ? WHERE username = ?", (1 if unlimited else 0, username))
        db.commit()
        state = "enabled" if unlimited else "disabled"
        log_audit(session["username"], "SET_CREDITS_UNLIMITED", username, request.remote_addr, f"Unlimited {state}")
        return jsonify({"message": f"Unlimited credits {state} for '{username}'."})
    if action == "set":
        db.execute("UPDATE users SET credits = ? WHERE username = ?", (int(amount), username))
        msg = f"Credits set to {amount}"
    elif action == "add":
        db.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (int(amount), username))
        msg = f"Added {amount} credits"
    else:
        return jsonify({"message": "Invalid action."}), 400
    db.commit()
    updated = db.execute("SELECT credits FROM users WHERE username = ?", (username,)).fetchone()
    log_audit(session["username"], f"ADMIN_CREDITS_{action.upper()}", username, request.remote_addr, msg)
    return jsonify({"message": f"{msg} for '{username}'.", "credits": updated["credits"]})

@app.route("/api/admin/version", methods=["POST"])
def admin_version():
    session = check_admin_session()
    if not session or session["role"] != "admin":
        return jsonify({"message": "Admin role required."}), 403
    data = request.get_json() or {}
    db = get_db()
    updates = {
        "latest_version": data.get("version", "").strip(),
        "changelog": data.get("changelog", "").strip(),
        "download_url": data.get("download_url", "").strip(),
        "announcements": data.get("announcements", "").strip()
    }
    for key, value in updates.items():
        if value:
            db.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (key, value))
    db.commit()
    log_audit(session["username"], "UPDATE_SYSTEM_CONFIG", None, request.remote_addr, "Updated config.")
    return jsonify({"message": "System configuration updated successfully."})

@app.route("/api/admin/audit-logs", methods=["GET"])
def admin_audit_logs():
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    rows = get_db().execute(
        "SELECT id, actor, action, target, ip_address, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 150"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/admin/login-history", methods=["GET"])
def admin_login_history():
    session = check_admin_session()
    if not session:
        return jsonify({"message": "Unauthorized"}), 401
    rows = get_db().execute(
        "SELECT id, username, ip_address, hwid, status, timestamp FROM login_history ORDER BY id DESC LIMIT 150"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    init_local_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
