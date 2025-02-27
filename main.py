import os
import random
from string import ascii_uppercase
from flask import Flask, redirect, render_template, request, session, url_for, jsonify
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import json
import datetime

# Initialize Flask
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "supersecretkey")
socketio = SocketIO(app, async_mode="gevent")

rooms = {}

def generate_unique_code(length=4):
    while True:
        code = "".join(random.choice(ascii_uppercase) for _ in range(length))
        if code not in rooms:
            return code

@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error="Please provide a name.", code=code, name=name)
        if join and not code:
            return render_template("home.html", error="Please enter the room code.", code=code, name=name)
        
        room = code
        if create:
            room = generate_unique_code()
            rooms[room] = {"members": 0, "messages": [], "users": []}
        elif room not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)

        session["room"] = room
        session["name"] = name
        rooms[room]["members"] += 1
        rooms[room]["users"].append(name)
        return redirect(url_for("room"))

    return render_template("home.html")

@app.route("/room")
def room():
    room = session.get("room")
    if not room or not session.get("name") or room not in rooms:
        return redirect(url_for("home"))
    return render_template("room.html", code=room, messages=rooms[room]["messages"], users=rooms[room]["users"], username=session.get("name"))

@socketio.on("message")
def message(data):
    room = session.get("room")
    if not room or room not in rooms:
        return
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = {"name": session.get("name"), "message": data["data"], "timestamp": timestamp}
    rooms[room]["messages"].append(content)
    send(content, to=room)

@socketio.on("typing")
def typing(data):
    emit("typing", {"name": session.get("name"), "typing": data["typing"]}, to=session.get("room"), broadcast=True)

@socketio.on("connect")
def connect():
    room = session.get("room")
    name = session.get("name")
    if not room or not name or room not in rooms:
        return
    
    join_room(room)
    emit("user_joined", {"name": name}, to=room)
    emit("update_users", {"users": rooms[room]["users"]}, to=room)

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)
    if room in rooms:
        rooms[room]["members"] -= 1
        if name in rooms[room]["users"]:
            rooms[room]["users"].remove(name)
        if rooms[room]["members"] <= 0:
            del rooms[room]
    emit("user_left", {"name": name}, to=room)
    emit("update_users", {"users": rooms[room]["users"]}, to=room)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

