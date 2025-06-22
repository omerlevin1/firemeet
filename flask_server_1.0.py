# === flask_server.py ===
from flask import Flask, request, jsonify
from Firebase_auth import FirebaseAuthClient
import uuid
from firebase_admin import auth as admin_auth
from flask_cors import CORS
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime

app = Flask(__name__)
CORS(app)
auth_client = FirebaseAuthClient()

import socket


def get_client_ip(req):
    ip = req.remote_addr
    if ip == "127.0.0.1" or ip == "::1":
        # Get the actual local IP address of the server
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
    return ip


# Firebase setup (once at the top of flask_server.py)
cred = credentials.Certificate(
    r"C:\Users\omerl\PycharmProjects\firemeet 3.0\server\json.json")  # path to your service account key
initialize_app(cred)
db = firestore.client()

auth_client = FirebaseAuthClient()


def parse_firebase_error(raw_error):
    try:
        error_message = str(raw_error)
        if "EMAIL_EXISTS" in error_message:
            return "This email is already registered."
        elif "INVALID_PASSWORD" in error_message:
            return "Incorrect password."
        elif "EMAIL_NOT_FOUND" in error_message:
            return "This email does not exist."
        elif "WEAK_PASSWORD" in error_message:
            return "Password must be at least 6 characters."
        else:
            return "Something went wrong. Please try again."
    except Exception:
        return "An unknown error occurred."


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    ip = get_client_ip(request)
    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required."}), 400

    success, result = auth_client.login_user(email, password)
    if success:
        db.collection("online_users").document(email).set({
            "email": email,
            "status": "online",
            "ip": ip,
            "last_updated": datetime.utcnow().isoformat()
        }, merge=True)
        # Update status to online

        return jsonify({"success": True, "data": result}), 200

    else:
        friendly = parse_firebase_error(result)
        return jsonify({"success": False, "message": friendly}), 401


@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")
    ip = get_client_ip(request)

    if not all([email, password, name, ip]):
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    success, result = auth_client.signup_user(email, password)
    if not success:
        friendly = parse_firebase_error(result)
        return jsonify({"success": False, "message": friendly}), 400

    # Pull UID from Pyrebase response
    uid = result["localId"]

    # Store extra user data in Firestore
    user_doc = {
        "name": name,
        "email": email,
        "ip_address": ip,
        "signup_time": datetime.utcnow().isoformat(),
        "role": "user"
    }

    db.collection("users").document(uid).set(user_doc)

    # Log them in after signup
    login_success, login_result = auth_client.login_user(email, password)
    if login_success:
        # Mark user as online after signup
        db.collection("online_users").document(email).set({
            "email": email,
            "status": "online",
            "ip": ip,
            "last_updated": datetime.utcnow().isoformat()
        }, merge=True)

        return jsonify({"success": True, "data": login_result}), 200
    else:
        return jsonify({"success": True, "data": {"email": email}, "message": "User created, but login failed."}), 200


@app.route("/start_meeting", methods=["POST"])
def start_meeting():
    data = request.get_json()
    token = data.get("token")
    meeting_id = data.get("meeting_id") or str(uuid.uuid4())[:6]  # optional: use provided or generate 6-char ID

    # Verify token
    try:
        decoded = admin_auth.verify_id_token(token)
        email = decoded["email"]
        uid = decoded["uid"]
    except Exception as e:
        return jsonify({"success": False, "message": "Invalid token"}), 401

    # Create meeting document
    doc = {
        "host": email,
        "uid": uid,
        "start_time": datetime.utcnow().isoformat(),
        "pending_requests": {},
        "accepted_users": [email]
    }

    db.collection("meetings").document(meeting_id).set(doc)
    db.collection("online_users").document(email).set({
        "email": email,
        "status": "in_meeting",
        "last_updated": datetime.utcnow().isoformat()
    }, merge=True)

    return jsonify({"success": True, "meeting_id": meeting_id})


from datetime import datetime

from datetime import datetime


@app.route("/update_status", methods=["POST"])
def update_status():
    data = request.json
    email = data.get("email")
    status = data.get("status")

    if not email or status not in ["online", "offline", "in_meeting"]:
        return jsonify({"success": False, "message": "Invalid input"}), 400

    db.collection("online_users").document(email).set({
        "email": email,
        "status": status,
        "last_updated": datetime.utcnow().isoformat()
    }, merge=True)

    return jsonify({"success": True})


@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.json
    sender = data.get("sender")
    message = data.get("message")
    meeting_id = data.get("meeting_id")

    if not sender or not message or not meeting_id:
        return jsonify({"error": "Missing sender, message, or meeting_id"}), 400

    timestamp = datetime.utcnow().isoformat()
    msg_data = {
        "sender": sender,
        "message": message,
        "timestamp": timestamp
    }

    # Store under /meetings/{meeting_id}/messages/
    db.collection("meetings").document(meeting_id).collection("messages").document(timestamp).set(msg_data)

    return jsonify({"status": "ok", "id": timestamp})


@app.route("/get_messages", methods=["GET"])
def get_messages():
    meeting_id = request.args.get("meeting_id")
    after_id = request.args.get("after_id")

    if not meeting_id:
        return jsonify({"error": "Missing meeting_id"}), 400

    try:
        messages_ref = db.collection("meetings").document(meeting_id).collection("messages").order_by("timestamp")

        if after_id:
            after_doc = db.collection("meetings").document(meeting_id).collection("messages").document(after_id).get()
            if after_doc.exists:
                messages_ref = messages_ref.start_after(after_doc)

        query = messages_ref.limit(50).stream()

        messages = []
        for doc in query:
            msg = doc.to_dict()
            msg["id"] = doc.id
            messages.append(msg)

        return jsonify(messages)

    except Exception as e:
        print(f"[ERROR] Failed to retrieve messages: {e}")
        return jsonify([]), 500


@app.route("/end_meeting", methods=["POST"])
def end_meeting():
    data = request.json
    meeting_id = data.get("meeting_id")

    if not meeting_id:
        return jsonify({"error": "Missing meeting_id"}), 400

    try:
        db.collection("meetings").document(meeting_id).update({
            "status": "ended"
        })
        return jsonify({"success": True})
    except Exception as e:
        print(f"[ERROR] Could not end meeting: {e}")
        return jsonify({"success": False}), 500


from flask import jsonify


@app.route("/online_users", methods=["GET"])
def get_online_users():
    try:
        docs = db.collection("online_users").stream()
        users = [doc.to_dict() for doc in docs]
        return jsonify(users)
    except Exception as e:
        print(f"[ERROR] Fetching online users failed: {e}")
        return jsonify([]), 500


@app.route("/request_join", methods=["POST"])
def request_join():
    data = request.get_json()
    meeting_id = data.get("meeting_id")
    target_email = data.get("email")  # the person to invite
    requester = data.get("requester")

    if not meeting_id or not target_email or not requester:
        return jsonify({"success": False, "message": "Missing data"}), 400

    ref = db.collection("meetings").document(meeting_id)
    ref.set({
        "pending_requests": {
            target_email: requester
        }
    }, merge=True)

    return jsonify({"success": True})


@app.route("/respond_join_request", methods=["POST"])
def respond_join_request():
    data = request.get_json()
    meeting_id = data.get("meeting_id")
    email = data.get("email")  # user responding
    response = data.get("response")  # "accept" or "decline"

    if not meeting_id or not email or response not in ["accept", "decline"]:
        return jsonify({"success": False, "message": "Invalid data"}), 400

    meeting_ref = db.collection("meetings").document(meeting_id)
    meeting = meeting_ref.get()
    if not meeting.exists:
        return jsonify({"success": False, "message": "Meeting not found"}), 404

    meeting_data = meeting.to_dict()
    pending = meeting_data.get("pending_requests", {})

    # Remove from pending_requests
    pending.pop(email, None)
    updates = {"pending_requests": pending}

    if response == "accept":
        accepted = meeting_data.get("accepted_users", [])
        if email not in accepted:
            accepted.append(email)
        updates["accepted_users"] = accepted
        # Set status
        db.collection("online_users").document(email).set({
            "status": "in_meeting",
            "last_updated": datetime.utcnow().isoformat()
        }, merge=True)

        host_email = meeting_data["host"]
        host_doc = db.collection("online_users").document(host_email).get()
        host_ip = host_doc.to_dict().get("ip", "127.0.0.1")

    meeting_ref.update(updates)
    # Optional: write system message to messages collection
    msg_text = f"{email} {'accepted' if response == 'accept' else 'declined'} your invite"
    msg_data = {
        "sender": "system",  # you can filter this client-side if needed
        "message": f"🔴 {msg_text}",
        "timestamp": datetime.utcnow().isoformat()
    }

    db.collection("meetings").document(meeting_id).collection("messages").add(msg_data)

    return jsonify({"success": True, "host_ip": host_ip})


@app.route("/get_pending_requests", methods=["GET"])
def get_pending_requests():
    email = request.args.get("email")
    if not email:
        return jsonify({"pending": False}), 400

    try:
        meetings = db.collection("meetings").stream()
        for doc in meetings:
            data = doc.to_dict()
            pending = data.get("pending_requests", {})
            if email in pending:
                return jsonify({
                    "pending": True,
                    "requester": pending[email],
                    "meeting_id": doc.id  # send back the actual ID
                })
    except Exception as e:
        print(f"[ERROR] get_pending_requests: {e}")

    return jsonify({"pending": False})


@app.route("/request_join_by_id", methods=["POST"])
def request_join_by_id():
    data = request.get_json()
    meeting_id = data.get("meeting_id")
    requester_email = data.get("email")

    if not meeting_id or not requester_email:
        return jsonify({"success": False, "message": "Missing meeting_id or email"}), 400

    meeting_ref = db.collection("meetings").document(meeting_id)
    meeting_doc = meeting_ref.get()

    if not meeting_doc.exists:
        return jsonify({"success": False, "message": "Meeting not found"}), 404

    meeting_data = meeting_doc.to_dict()
    host_email = meeting_data.get("host")

    # Add to pending_requests
    pending = meeting_data.get("pending_requests", {})
    pending[requester_email] = requester_email
    meeting_ref.update({"pending_requests": pending})

    print(f"[SERVER] Join request from {requester_email} for meeting {meeting_id}")
    return jsonify({"success": True, "host_email": host_email})


@app.route("/get_meeting_info", methods=["GET"])
def get_meeting_info():
    meeting_id = request.args.get("meeting_id")
    if not meeting_id:
        return jsonify({}), 400
    doc = db.collection("meetings").document(meeting_id).get()
    if not doc.exists:
        return jsonify({}), 404
    return jsonify(doc.to_dict())


@app.route("/get_accepted_users", methods=["GET"])
def get_accepted_users():
    meeting_id = request.args.get("meeting_id")
    if not meeting_id:
        return jsonify({"error": "Missing meeting_id"}), 400

    doc = db.collection("meetings").document(meeting_id).get()
    if not doc.exists:
        return jsonify({"error": "Meeting not found"}), 404

    data = doc.to_dict()
    accepted_emails = data.get("accepted_users", [])
    accepted_users = []

    for email in accepted_emails:
        user_doc = db.collection("online_users").document(email).get()
        if user_doc.exists:
            accepted_users.append(user_doc.to_dict())

    return jsonify({"accepted_users": accepted_users})


if __name__ == "__main__":
    print("🔥 flask_server_1.0.py has started and is running!")
    app.run(host="0.0.0.0", port=5000)
