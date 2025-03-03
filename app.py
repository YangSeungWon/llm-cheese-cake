from flask import Flask, request, jsonify, session, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import timedelta
import uuid
import os
from dotenv import load_dotenv

# 모듈 임포트
from gemini_chat import initialize_gemini_chat
from chess_game import process_chess_move

load_dotenv()  # .env 파일에서 환경 변수 로드

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")  # 세션 관리용 시크릿 키
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

# 실제 FLAG 값 (이것을 참가자들이 추출해야 함)
FLAG1 = os.getenv("FLAG1", "flag{pr0mpt_1nj3ct10n_m4st3r-level1}")
FLAG2 = os.getenv("FLAG2", "flag{pr0mpt_1nj3ct10n_m4st3r-level2}")
FLAG3 = os.getenv("FLAG3", "flag{pr0mpt_1nj3ct10n_m4st3r-level3}")
CHESS_FLAG = os.getenv("CHESS_FLAG", "flag{ch3ss_m4st3r_w1ns}")

limiter = Limiter(
    get_remote_address, app=app, default_limits=["200 per day", "50 per hour"]
)

# 채팅 세션을 저장할 딕셔너리
chat_sessions = {}
# 체스 게임 세션을 저장할 딕셔너리
chess_sessions = {}

@app.route("/start_challenge", methods=["POST"])
def start_challenge():
    # 난이도 레벨 가져오기 (기본값: level1)
    level = request.json.get("level", "level1")
    if level not in ["level1", "level2", "level3"]:
        level = "level1"
    
    # 새로운 세션 ID 생성
    session_id = str(uuid.uuid4())

    # 레벨에 따른 FLAG 선택
    if level == "level1":
        flag = FLAG1
    elif level == "level2":
        flag = FLAG2
    else:  # level3
        flag = FLAG3

    # 새로운 챌린지 세션 시작
    chat_sessions[session_id] = initialize_gemini_chat(flag, level)

    # 세션 ID와 레벨 저장
    session["chat_id"] = session_id
    session["level"] = level
    session["challenge_type"] = "prompt_injection"

    return jsonify(
        {
            "status": "success",
            "message": f"챌린지 레벨 {level}이 시작되었습니다. AI와 대화를 시작하세요.",
        }
    )

@app.route("/start_chess", methods=["POST"])
def start_chess():
    # 새로운 세션 ID 생성
    session_id = str(uuid.uuid4())
    
    # 새로운 체스 게임 세션 시작
    from chess_game import initialize_chess_game
    chess_sessions[session_id] = initialize_chess_game()
    
    # 세션 ID 저장
    session["chess_id"] = session_id
    session["challenge_type"] = "chess"
    
    return jsonify({
        "status": "success",
        "message": "체스 게임이 시작되었습니다. 첫 번째 수를 두세요.",
        "board": chess_sessions[session_id]["board"].fen()
    })

@app.route("/chat", methods=["POST"])
def chat():
    if "chat_id" not in session:
        return jsonify({"status": "error", "message": "먼저 챌린지를 시작해주세요."})

    session_id = session["chat_id"]

    if session_id not in chat_sessions:
        return jsonify(
            {"status": "error", "message": "세션이 만료되었습니다. 다시 시작해주세요."}
        )

    user_input = request.json.get("message", "")

    try:
        # 사용자 메시지를 Gemini에 전송
        response = chat_sessions[session_id].send_message(user_input, stream=False)
        return jsonify({"status": "success", "response": response.text})
    except Exception as e:
        error_message = str(e)
        if "429" in error_message:
            return jsonify({
                "status": "error", 
                "message": "Gemini API 할당량을 초과했습니다. 잠시 후 다시 시도해주세요."
            })
        else:
            return jsonify({"status": "error", "message": f"오류가 발생했습니다: {error_message}"})

@app.route("/chess_move", methods=["POST"])
def chess_move():
    if "chess_id" not in session:
        return jsonify({"status": "error", "message": "먼저 체스 게임을 시작해주세요."})
    
    session_id = session["chess_id"]
    
    if session_id not in chess_sessions:
        return jsonify({"status": "error", "message": "세션이 만료되었습니다. 다시 시작해주세요."})
    
    move = request.json.get("move", "")
    
    try:
        result = process_chess_move(chess_sessions[session_id], move)
        
        # 게임이 끝났고 플레이어가 이겼다면 FLAG 제공
        if result.get("game_over") and result.get("winner") == "player":
            result["flag"] = CHESS_FLAG
            
        return jsonify({"status": "success", **result})
    except Exception as e:
        return jsonify({"status": "error", "message": f"오류가 발생했습니다: {str(e)}"})

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/chess", methods=["GET"])
def chess_page():
    return render_template("chess.html")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8670) 