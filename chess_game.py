import chess
import chess.pgn
import random
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일에서 환경 변수 로드

# Gemini API 키 설정
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

def initialize_chess_game():
    """체스 게임 초기화"""
    board = chess.Board()
    
    # Gemini 모델 초기화
    model = genai.GenerativeModel("gemini-2.0-flash-lite")
    chat = model.start_chat(history=[])
    
    # 체스 게임 시스템 프롬프트
    system_prompt = """
당신은 체스 AI입니다. 사용자와 체스 게임을 진행합니다.
당신은 체스 규칙을 완벽하게 이해하고 있으며, PGN 표기법으로 수를 표현합니다.

게임 진행 방식:
1. 사용자가 백(White)을 맡고, 당신은 흑(Black)을 맡습니다.
2. 사용자가 수를 두면, 당신은 현재 보드 상태를 분석하고 최선의 응답 수를 둡니다.
3. 당신은 항상 합법적인 수만 둡니다.
4. 당신은 수를 둘 때 간단한 설명을 추가할 수 있습니다.

응답 형식:
- 당신의 수만 PGN 표기법으로 응답하세요 (예: "e5", "Nf6").
- 추가 설명이나 분석은 하지 마세요.
- 오직 한 수만 응답하세요.
"""
    
    # 시스템 프롬프트 설정
    chat.send_message(system_prompt, stream=False)
    
    return {
        "board": board,
        "moves": [],
        "pgn": "",
        "game_over": False,
        "winner": None,
        "chat": chat
    }

def process_chess_move(game_state, move_pgn):
    """PGN 형식의 체스 수를 처리"""
    board = game_state["board"]
    
    # 게임이 이미 끝났는지 확인
    if game_state["game_over"]:
        return {
            "message": "게임이 이미 종료되었습니다.",
            "board": board.fen(),
            "game_over": True,
            "winner": game_state["winner"],
            "pgn": get_pgn(game_state)
        }
    
    # 플레이어의 수 처리
    try:
        # PGN 표기법을 UCI 이동으로 변환
        move = board.parse_san(move_pgn)
        board.push(move)
        game_state["moves"].append(move_pgn)
    except ValueError:
        return {
            "message": f"잘못된 수입니다: {move_pgn}",
            "board": board.fen(),
            "valid_moves": [board.san(m) for m in board.legal_moves],
            "pgn": get_pgn(game_state)
        }
    
    # 게임 종료 확인
    if board.is_checkmate():
        game_state["game_over"] = True
        game_state["winner"] = "player"
        return {
            "message": "체크메이트! 당신이 이겼습니다!",
            "board": board.fen(),
            "game_over": True,
            "winner": "player",
            "pgn": get_pgn(game_state)
        }
    
    if board.is_stalemate() or board.is_insufficient_material() or board.is_fifty_moves() or board.is_repetition():
        game_state["game_over"] = True
        game_state["winner"] = "draw"
        return {
            "message": "무승부입니다.",
            "board": board.fen(),
            "game_over": True,
            "winner": "draw",
            "pgn": get_pgn(game_state)
        }
    
    # Gemini에게 현재 보드 상태 전송하고 응답 수 받기
    try:
        # 현재까지의 게임 기보 생성
        current_pgn = get_pgn(game_state)
        
        # Gemini에게 현재 보드 상태와 기보 전송
        prompt = f"""
현재 체스 게임 상태:
FEN: {board.fen()}

현재까지의 기보:
{current_pgn}

당신은 흑(Black)입니다. 다음 수를 PGN 표기법으로 응답하세요.
응답은 오직 수만 포함해야 합니다 (예: "e5", "Nf6").
"""
        
        response = game_state["chat"].send_message(prompt, stream=False)
        ai_move_san = response.text.strip()
        
        # 응답에서 불필요한 텍스트 제거 (따옴표, 마침표 등)
        ai_move_san = ai_move_san.strip('"\'.,\n ')
        
        # 여러 줄이 있을 경우 첫 번째 줄만 사용
        if "\n" in ai_move_san:
            ai_move_san = ai_move_san.split("\n")[0].strip()
        
        # 응답이 여러 단어를 포함할 경우 첫 번째 단어만 사용
        if " " in ai_move_san:
            ai_move_san = ai_move_san.split(" ")[0].strip()
        
        # AI의 수가 유효한지 확인
        try:
            ai_move = board.parse_san(ai_move_san)
            board.push(ai_move)
            game_state["moves"].append(ai_move_san)
        except ValueError:
            # AI가 잘못된 수를 두었을 경우 랜덤 수 선택
            legal_moves = list(board.legal_moves)
            if legal_moves:
                ai_move = random.choice(legal_moves)
                ai_move_san = board.san(ai_move)
                board.push(ai_move)
                game_state["moves"].append(ai_move_san)
                ai_move_san = f"{ai_move_san} (AI가 잘못된 수를 두어 랜덤 수로 대체)"
        
        # 게임 종료 확인 (AI 수 이후)
        if board.is_checkmate():
            game_state["game_over"] = True
            game_state["winner"] = "ai"
            return {
                "message": f"AI의 수: {ai_move_san}. 체크메이트! AI가 이겼습니다.",
                "ai_move": ai_move_san,
                "board": board.fen(),
                "game_over": True,
                "winner": "ai",
                "pgn": get_pgn(game_state)
            }
        
        if board.is_stalemate() or board.is_insufficient_material() or board.is_fifty_moves() or board.is_repetition():
            game_state["game_over"] = True
            game_state["winner"] = "draw"
            return {
                "message": f"AI의 수: {ai_move_san}. 무승부입니다.",
                "ai_move": ai_move_san,
                "board": board.fen(),
                "game_over": True,
                "winner": "draw",
                "pgn": get_pgn(game_state)
            }
        
        # 체크 상태 확인
        if board.is_check():
            return {
                "message": f"AI의 수: {ai_move_san}. 체크!",
                "ai_move": ai_move_san,
                "board": board.fen(),
                "check": True,
                "pgn": get_pgn(game_state)
            }
        
        return {
            "message": f"AI의 수: {ai_move_san}",
            "ai_move": ai_move_san,
            "board": board.fen(),
            "pgn": get_pgn(game_state)
        }
        
    except Exception as e:
        # AI 응답 오류 시 랜덤 수 선택
        legal_moves = list(board.legal_moves)
        if legal_moves:
            ai_move = random.choice(legal_moves)
            ai_move_san = board.san(ai_move)
            board.push(ai_move)
            game_state["moves"].append(ai_move_san)
            
            return {
                "message": f"AI의 수: {ai_move_san} (AI 응답 오류로 랜덤 수 선택)",
                "ai_move": ai_move_san,
                "board": board.fen(),
                "pgn": get_pgn(game_state),
                "error": str(e)
            }
    
    # 이 부분에 도달하면 오류 상황
    return {
        "message": "오류가 발생했습니다.",
        "board": board.fen(),
        "pgn": get_pgn(game_state)
    }

def get_pgn(game_state):
    """현재 게임 상태의 PGN 표기법 반환"""
    game = chess.pgn.Game()
    
    # 게임 메타데이터 설정
    game.headers["Event"] = "AI Chess Challenge"
    game.headers["White"] = "Player"
    game.headers["Black"] = "AI"
    
    # 이동 기록 추가
    node = game
    board = chess.Board()
    
    for i, move_san in enumerate(game_state["moves"]):
        try:
            move = board.parse_san(move_san)
            node = node.add_variation(move)
            board.push(move)
        except ValueError:
            # 잘못된 수가 있을 경우 무시
            pass
    
    # PGN 문자열 반환
    return str(game) 