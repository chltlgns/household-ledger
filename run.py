"""
가계부 앱 런처
시작 시 브라우저 자동으로 열기
"""
import webbrowser
import threading
import time
import sys
import os

# EXE로 패키징된 경우를 위한 경로 설정
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
    os.chdir(base_path)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# 환경변수 로드 (.env 파일이 있으면)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(base_path, '.env'))
except ImportError:
    pass  # python-dotenv가 없으면 무시

# 환경변수에서 설정 읽기 (기본값 제공)
FLASK_HOST = os.getenv('FLASK_HOST', '127.0.0.1')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# 인증 DB 초기화
from auth import set_auth_db_path, init_auth_db
set_auth_db_path(base_path)
init_auth_db()

# app 모듈에 BASE_PATH 설정
import app as flask_app
flask_app.BASE_PATH = base_path

# Flask 앱 가져오기
from app import app

def open_browser():
    """서버 시작 후 브라우저 열기"""
    time.sleep(1.5)  # 서버 시작 대기
    webbrowser.open(f'http://{FLASK_HOST}:{FLASK_PORT}/')

if __name__ == '__main__':
    # 브라우저 열기 스레드 시작
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Flask 서버 시작
    app.run(debug=FLASK_DEBUG, host=FLASK_HOST, port=FLASK_PORT, use_reloader=False)


