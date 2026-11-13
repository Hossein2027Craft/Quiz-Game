from ai_questions import generate_question
from database import initialize_db, save_player, get_players
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import secrets
import string
import threading
from time import time

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# اتاق‌ها در حافظه موقت نگهداری می‌شوند
rooms = {}
rooms_lock = threading.Lock()

game_settings = {
    "question_count": 10,
    "question_time": 30,
    "difficulty": "medium",
    "sound": True
}


def generate_room_code():
    characters = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(characters) for _ in range(6))
        if code not in rooms:
            return code


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/create-match", methods=["GET", "POST"])
def create_match():
    if request.method == "POST":
        player_name = request.form.get("player_name", "").strip()

        if not player_name:
            return render_template(
                "create_match.html",
                error="لطفاً نام بازیکن را وارد کن."
            )

        room_code = generate_room_code()

        rooms[room_code] = {
            "host": player_name,
            "players": [player_name],
            "started": False,
            "loading": False,
            "loading_start": None,
            "questions_ready": False,
            "loading_error": False,
            "questions": [],
            "scores": {},
            "progress": {},
            "answers": {}
        }

        session["room_code"] = room_code
        session["player_name"] = player_name
        session["is_host"] = True

        save_player(room_code, player_name, "host")

        return redirect(url_for("lobby", room_code=room_code))

    return render_template("create_match.html")


@app.route("/join-match", methods=["GET", "POST"])
def join_match():
    if request.method == "POST":
        player_name = request.form.get("player_name", "").strip()
        room_code = request.form.get("room_code", "").strip().upper()

        if not player_name or not room_code:
            return render_template(
                "join_match.html",
                error="تمام فیلدها را پر کن."
            )

        room = rooms.get(room_code)

        if room is None:
            return render_template(
                "join_match.html",
                error="کد مسابقه اشتباه است."
            )

        if room["started"] or room["loading"]:
            return render_template(
                "join_match.html",
                error="این مسابقه شروع شده است."
            )

        if len(room["players"]) >= 4:
            return render_template(
                "join_match.html",
                error="ظرفیت مسابقه تکمیل است."
            )

        if player_name in room["players"]:
            return render_template(
                "join_match.html",
                error="این نام قبلاً وارد مسابقه شده است."
            )

        saved = save_player(room_code, player_name, "player")

        if not saved:
            return render_template(
                "join_match.html",
                error="این نام قبلاً در مسابقه ثبت شده است."
            )

        room["players"].append(player_name)

        session["room_code"] = room_code
        session["player_name"] = player_name
        session["is_host"] = False

        return redirect(url_for("lobby", room_code=room_code))

    return render_template("join_match.html")


@app.route("/lobby/<room_code>")
def lobby(room_code):
    room = rooms.get(room_code)

    if room is None:
        return "اتاق مسابقه پیدا نشد!", 404

    if session.get("room_code") != room_code:
        return "ابتدا وارد مسابقه شو!", 403

    if session.get("player_name") not in room["players"]:
        return "شما عضو این مسابقه نیستید!", 403

    if room["started"]:
        return redirect(url_for("game", room_code=room_code))

    return render_template(
        "lobby.html",
        room_code=room_code,
        room=room
    )


def load_game_questions(room_code):
    room = rooms.get(room_code)

    if room is None:
        return

    try:
        questions = []

        # تولید سؤال‌ها در پس‌زمینه
        for _ in range(game_settings["question_count"]):
            question = generate_question(game_settings["difficulty"])
            questions.append(question)

        # فقط پس از تولید کامل سؤال‌ها، بازی آماده می‌شود
        with rooms_lock:
            room["questions"] = questions
            room["scores"] = {
                player: 0 for player in room["players"]
            }
            room["progress"] = {
                player: 0 for player in room["players"]
            }
            room["answers"] = {}
            room["questions_ready"] = True
            room["started"] = True
            room["loading"] = False
            room["loading_error"] = False

    except Exception:
        app.logger.exception("Question generation failed")

        with rooms_lock:
            room["loading"] = False
            room["questions_ready"] = False
            room["loading_error"] = True
            room["started"] = False


@app.route("/start-match/<room_code>", methods=["POST"])
def start_match(room_code):
    room = rooms.get(room_code)

    if room is None:
        return "اتاق مسابقه پیدا نشد!", 404

    if (
        session.get("room_code") != room_code
        or not session.get("is_host")
    ):
        return "فقط میزبان می‌تواند مسابقه را شروع کند.", 403

    if len(room["players"]) < 2:
        return "برای شروع مسابقه حداقل دو بازیکن لازم است."

    if room.get("loading") or room.get("started"):
        return redirect(url_for("lobby", room_code=room_code))

    with rooms_lock:
        room["loading"] = True
        room["loading_start"] = time()
        room["questions_ready"] = False
        room["loading_error"] = False

    thread = threading.Thread(
        target=load_game_questions,
        args=(room_code,),
        daemon=True
    )
    thread.start()

    return redirect(url_for("lobby", room_code=room_code))


@app.route("/game-status/<room_code>")
def game_status(room_code):
    room = rooms.get(room_code)

    if room is None:
        return jsonify({"error": "اتاق پیدا نشد"}), 404

    if session.get("room_code") != room_code:
        return jsonify({"error": "عضو مسابقه نیستی"}), 403

    start_time = room.get("loading_start")

    elapsed = (
        round(time() - start_time)
        if start_time is not None
        else 0
    )

    return jsonify({
        "loading": room.get("loading", False),
        "ready": room.get("questions_ready", False),
        "started": room.get("started", False),
        "error": room.get("loading_error", False),
        "elapsed": elapsed
    })


@app.route("/game/<room_code>")
def game(room_code):
    room = rooms.get(room_code)

    if room is None:
        return "اتاق مسابقه پیدا نشد!", 404

    player = session.get("player_name")

    if player not in room["players"]:
        return "شما عضو این مسابقه نیستید!", 403

    if not room["started"] or not room["questions_ready"]:
        return redirect(url_for("lobby", room_code=room_code))

    index = room["progress"][player]

    if index >= len(room["questions"]):
        return render_template(
            "game.html",
            finished=True,
            score=room["scores"][player],
            total=len(room["questions"])
        )

    question = room["questions"][index]
    feedback = session.pop("feedback", None)

    return render_template(
        "game.html",
        finished=False,
        question=question,
        index=index,
        total=len(room["questions"]),
        score=room["scores"][player],
        feedback=feedback,
        answered=player in room["answers"].get(index, {})
    )


@app.route("/answer/<room_code>", methods=["POST"])
def answer(room_code):
    room = rooms.get(room_code)

    if room is None:
        return "اتاق پیدا نشد!", 404

    player = session.get("player_name")

    if player not in room["players"]:
        return "بازیکن معتبر نیست!", 403

    if not room["started"]:
        return redirect(url_for("lobby", room_code=room_code))

    index = room["progress"][player]

    if index >= len(room["questions"]):
        return redirect(url_for("game", room_code=room_code))

    room["answers"].setdefault(index, {})

    if player in room["answers"][index]:
        return redirect(url_for("game", room_code=room_code))

    selected = request.form.get("answer")
    question = room["questions"][index]
    correct = selected == question["correct_answer"]

    # پاسخ درست و غلط هر دو ثبت می‌شوند تا بازیکن
    # بتواند به سؤال بعدی برود و دوباره پاسخ ندهد.
    room["answers"][index][player] = selected

    if correct:
        room["scores"][player] += 1

    session["feedback"] = {
        "correct": correct,
        "selected": selected
    }

    return redirect(url_for("game", room_code=room_code))


@app.route("/next-question/<room_code>", methods=["POST"])
def next_question(room_code):
    room = rooms.get(room_code)

    if room is None:
        return "اتاق پیدا نشد!", 404

    player = session.get("player_name")

    if player not in room["players"]:
        return "بازیکن معتبر نیست!", 403

    index = room["progress"][player]

    if player not in room["answers"].get(index, {}):
        return redirect(url_for("game", room_code=room_code))

    room["progress"][player] += 1
    session.pop("feedback", None)

    return redirect(url_for("game", room_code=room_code))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        try:
            question_count = int(
                request.form.get("question_count", 10)
            )
            question_time = int(
                request.form.get("question_time", 30)
            )

            if not 1 <= question_count <= 50:
                raise ValueError

            if not 5 <= question_time <= 300:
                raise ValueError

            game_settings["question_count"] = question_count
            game_settings["question_time"] = question_time
            game_settings["difficulty"] = request.form.get(
                "difficulty", "medium"
            )
            game_settings["sound"] = (
                request.form.get("sound") == "on"
            )

        except ValueError:
            return render_template(
                "settings.html",
                settings=game_settings,
                error="تعداد سؤال یا زمان نامعتبر است."
            )

        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        settings=game_settings
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True
    )
