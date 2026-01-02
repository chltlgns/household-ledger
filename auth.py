"""
사용자 인증 모듈
Flask-Login 기반 로그인 시스템
"""
import sqlite3
import os
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin


# 사용자 데이터베이스 경로
AUTH_DB_PATH = None


def set_auth_db_path(base_path):
    """인증 DB 경로 설정"""
    global AUTH_DB_PATH
    AUTH_DB_PATH = os.path.join(base_path, 'users.db')


def get_auth_connection():
    """인증 DB 연결"""
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    """사용자 테이블 생성"""
    conn = get_auth_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"Auth database initialized at {AUTH_DB_PATH}")


class User(UserMixin):
    """사용자 모델"""
    def __init__(self, id, username):
        self.id = id
        self.username = username
    
    @staticmethod
    def get(user_id):
        """ID로 사용자 조회"""
        conn = get_auth_connection()
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        conn.close()
        
        if row:
            return User(row['id'], row['username'])
        return None
    
    @staticmethod
    def get_by_username(username):
        """사용자명으로 조회"""
        conn = get_auth_connection()
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    @staticmethod
    def create(username, password):
        """새 사용자 생성"""
        conn = get_auth_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            conn.close()
            return None  # 이미 존재하는 사용자
    
    @staticmethod
    def verify_password(stored_hash, password):
        """비밀번호 검증"""
        return check_password_hash(stored_hash, password)


def get_user_db_path(base_path, user_id):
    """사용자별 데이터베이스 경로 반환"""
    return os.path.join(base_path, f'data_{user_id}.db')
