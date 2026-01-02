"""
데이터베이스 관리 모듈
SQLite를 사용한 로컬 데이터 저장
"""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"


def get_connection():
    """데이터베이스 연결 반환"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """데이터베이스 초기화 및 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 카테고리 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#6366f1',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 거래 내역 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            receipt_date TEXT,
            merchant TEXT NOT NULL,
            business_type TEXT,
            country TEXT,
            local_amount REAL,
            currency TEXT,
            usd_amount REAL,
            exchange_rate REAL,
            krw_amount INTEGER NOT NULL,
            fee INTEGER DEFAULT 0,
            billed_amount INTEGER NOT NULL,
            category_id INTEGER,
            card_number TEXT,
            is_overseas INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)
    
    # 메모 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL UNIQUE,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
        )
    """)
    
    # 태그 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#10b981'
        )
    """)
    
    # 거래-태그 연결 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaction_tags (
            transaction_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (transaction_id, tag_id),
            FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    """)
    
    # 가맹점-카테고리 매핑 테이블 (자동분류용)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS merchant_category_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_pattern TEXT NOT NULL UNIQUE,
            category_id INTEGER NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)
    
    # 기본 카테고리 생성
    default_categories = [
        ('소프트웨어/구독', '#8b5cf6'),
        ('광고', '#f59e0b'),
        ('쇼핑', '#ec4899'),
        ('식비', '#10b981'),
        ('교통', '#3b82f6'),
        ('통신', '#6366f1'),
        ('기타', '#64748b'),
    ]
    
    for name, color in default_categories:
        try:
            cursor.execute(
                "INSERT INTO categories (name, color) VALUES (?, ?)",
                (name, color)
            )
        except sqlite3.IntegrityError:
            pass  # 이미 존재함
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


# ============ 카테고리 CRUD ============

def get_categories():
    """모든 카테고리 조회"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_category(name, color='#6366f1'):
    """새 카테고리 생성"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO categories (name, color) VALUES (?, ?)",
            (name, color)
        )
        conn.commit()
        cat_id = cursor.lastrowid
        conn.close()
        return cat_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def update_category(cat_id, name=None, color=None):
    """카테고리 수정"""
    conn = get_connection()
    if name:
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, cat_id))
    if color:
        conn.execute("UPDATE categories SET color = ? WHERE id = ?", (color, cat_id))
    conn.commit()
    conn.close()


def delete_category(cat_id):
    """카테고리 삭제"""
    conn = get_connection()
    # 해당 카테고리의 거래들은 NULL로 설정
    conn.execute("UPDATE transactions SET category_id = NULL WHERE category_id = ?", (cat_id,))
    conn.execute("DELETE FROM merchant_category_rules WHERE category_id = ?", (cat_id,))
    conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()


# ============ 거래 내역 CRUD ============

def add_transaction(data):
    """거래 내역 추가"""
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO transactions 
        (date, receipt_date, merchant, business_type, country, 
         local_amount, currency, usd_amount, exchange_rate, 
         krw_amount, fee, billed_amount, category_id, card_number, is_overseas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('date'),
        data.get('receipt_date'),
        data.get('merchant'),
        data.get('business_type'),
        data.get('country'),
        data.get('local_amount'),
        data.get('currency'),
        data.get('usd_amount'),
        data.get('exchange_rate'),
        data.get('krw_amount', 0),
        data.get('fee', 0),
        data.get('billed_amount', 0),
        data.get('category_id'),
        data.get('card_number'),
        data.get('is_overseas', 0)
    ))
    conn.commit()
    tx_id = cursor.lastrowid
    conn.close()
    return tx_id


def get_transactions(filters=None):
    """거래 내역 조회 (필터링 지원)"""
    conn = get_connection()
    query = """
        SELECT t.*, c.name as category_name, c.color as category_color,
               m.content as memo
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN memos m ON t.id = m.transaction_id
        WHERE 1=1
    """
    params = []
    
    if filters:
        if filters.get('year'):
            query += " AND substr(t.date, 1, 4) = ?"
            params.append(str(filters['year']))
        if filters.get('month'):
            query += " AND substr(t.date, 5, 2) = ?"
            params.append(str(filters['month']).zfill(2))
        if filters.get('category_id'):
            query += " AND t.category_id = ?"
            params.append(filters['category_id'])
        if filters.get('tag_id'):
            query += " AND t.id IN (SELECT transaction_id FROM transaction_tags WHERE tag_id = ?)"
            params.append(filters['tag_id'])
        if filters.get('search'):
            query += " AND (t.merchant LIKE ? OR t.business_type LIKE ?)"
            search = f"%{filters['search']}%"
            params.extend([search, search])
    
    query += " ORDER BY t.date DESC, t.id DESC"
    
    rows = conn.execute(query, params).fetchall()
    transactions = []
    
    for row in rows:
        tx = dict(row)
        # 해당 거래의 태그들 조회
        tags = conn.execute("""
            SELECT t.* FROM tags t
            JOIN transaction_tags tt ON t.id = tt.tag_id
            WHERE tt.transaction_id = ?
        """, (tx['id'],)).fetchall()
        tx['tags'] = [dict(tag) for tag in tags]
        transactions.append(tx)
    
    conn.close()
    return transactions


def update_transaction_category(tx_id, category_id):
    """거래의 카테고리 수정"""
    conn = get_connection()
    conn.execute(
        "UPDATE transactions SET category_id = ? WHERE id = ?",
        (category_id, tx_id)
    )
    conn.commit()
    conn.close()


def delete_transaction(tx_id):
    """거래 삭제"""
    conn = get_connection()
    conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()


# ============ 메모 CRUD ============

def set_memo(tx_id, content):
    """거래에 메모 설정 (upsert)"""
    conn = get_connection()
    if content and content.strip():
        conn.execute("""
            INSERT INTO memos (transaction_id, content) VALUES (?, ?)
            ON CONFLICT(transaction_id) DO UPDATE SET 
                content = excluded.content,
                updated_at = CURRENT_TIMESTAMP
        """, (tx_id, content.strip()))
    else:
        conn.execute("DELETE FROM memos WHERE transaction_id = ?", (tx_id,))
    conn.commit()
    conn.close()


# ============ 태그 CRUD ============

def get_tags():
    """모든 태그 조회"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_tag(name, color='#10b981'):
    """새 태그 생성"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO tags (name, color) VALUES (?, ?)",
            (name.strip(), color)
        )
        conn.commit()
        tag_id = cursor.lastrowid
        conn.close()
        return tag_id
    except sqlite3.IntegrityError:
        # 이미 존재하면 기존 ID 반환
        row = conn.execute("SELECT id FROM tags WHERE name = ?", (name.strip(),)).fetchone()
        conn.close()
        return row['id'] if row else None


def add_tag_to_transaction(tx_id, tag_id):
    """거래에 태그 추가"""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO transaction_tags (transaction_id, tag_id) VALUES (?, ?)",
            (tx_id, tag_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # 이미 연결됨
    conn.close()


def remove_tag_from_transaction(tx_id, tag_id):
    """거래에서 태그 제거"""
    conn = get_connection()
    conn.execute(
        "DELETE FROM transaction_tags WHERE transaction_id = ? AND tag_id = ?",
        (tx_id, tag_id)
    )
    conn.commit()
    conn.close()


def search_tags(query):
    """태그 자동완성 검색"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tags WHERE name LIKE ? ORDER BY name LIMIT 10",
        (f"%{query}%",)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============ 가맹점 분류 규칙 ============

def get_category_by_merchant(merchant):
    """가맹점명으로 카테고리 자동 조회"""
    conn = get_connection()
    row = conn.execute("""
        SELECT c.id, c.name, c.color FROM merchant_category_rules mcr
        JOIN categories c ON mcr.category_id = c.id
        WHERE ? LIKE '%' || mcr.merchant_pattern || '%'
        ORDER BY LENGTH(mcr.merchant_pattern) DESC
        LIMIT 1
    """, (merchant,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_merchant_category_rule(merchant_pattern, category_id):
    """가맹점 분류 규칙 설정"""
    conn = get_connection()
    conn.execute("""
        INSERT INTO merchant_category_rules (merchant_pattern, category_id)
        VALUES (?, ?)
        ON CONFLICT(merchant_pattern) DO UPDATE SET category_id = excluded.category_id
    """, (merchant_pattern, category_id))
    conn.commit()
    conn.close()


def get_all_merchants():
    """전체 가맹점 목록 조회 (중복 제거)"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT DISTINCT merchant, 
               MAX(business_type) as business_type,
               COUNT(*) as tx_count,
               SUM(billed_amount) as total_amount
        FROM transactions
        GROUP BY merchant
        ORDER BY merchant
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_merchant_rules():
    """가맹점 분류 규칙 목록 조회"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT mcr.id, mcr.merchant_pattern, mcr.category_id,
               c.name as category_name, c.color as category_color
        FROM merchant_category_rules mcr
        JOIN categories c ON mcr.category_id = c.id
        ORDER BY mcr.merchant_pattern
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_uncategorized_merchants():
    """카테고리 규칙이 없는 가맹점 목록"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT DISTINCT t.merchant,
               MAX(t.business_type) as business_type,
               COUNT(*) as tx_count,
               SUM(t.billed_amount) as total_amount
        FROM transactions t
        WHERE NOT EXISTS (
            SELECT 1 FROM merchant_category_rules mcr
            WHERE t.merchant LIKE '%' || mcr.merchant_pattern || '%'
        )
        GROUP BY t.merchant
        ORDER BY t.merchant
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def apply_category_to_all_transactions_by_merchant(merchant_pattern, category_id):
    """특정 가맹점의 모든 거래에 카테고리 일괄 적용"""
    conn = get_connection()
    # 규칙 저장
    conn.execute("""
        INSERT INTO merchant_category_rules (merchant_pattern, category_id)
        VALUES (?, ?)
        ON CONFLICT(merchant_pattern) DO UPDATE SET category_id = excluded.category_id
    """, (merchant_pattern, category_id))
    
    # 기존 거래들에도 적용
    conn.execute("""
        UPDATE transactions 
        SET category_id = ?
        WHERE merchant LIKE '%' || ? || '%'
    """, (category_id, merchant_pattern))
    
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return affected


def delete_merchant_rule(merchant_pattern):
    """가맹점 분류 규칙 삭제"""
    conn = get_connection()
    conn.execute("DELETE FROM merchant_category_rules WHERE merchant_pattern = ?", (merchant_pattern,))
    conn.commit()
    conn.close()


# ============ 기존 거래 삭제 (중복 방지) ============

def delete_transactions_by_month(year, month):
    """특정 연도+월의 모든 거래 삭제"""
    conn = get_connection()
    month_str = f"{year}{str(month).zfill(2)}"
    cursor = conn.execute(
        "DELETE FROM transactions WHERE substr(date, 1, 6) = ?",
        (month_str,)
    )
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"Deleted {deleted_count} transactions for {year}-{month}")
    return deleted_count


def get_all_months_in_data():
    """데이터에 존재하는 모든 연도+월 조합 반환"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT DISTINCT substr(date, 1, 4) as year, substr(date, 5, 2) as month
        FROM transactions
        ORDER BY year DESC, month DESC
    """).fetchall()
    conn.close()
    return [(int(row['year']), int(row['month'])) for row in rows]


def get_summary_by_date_range(start_year, start_month, end_year, end_month):
    """기간별 카테고리별 지출 요약"""
    conn = get_connection()
    start_str = f"{start_year}{str(start_month).zfill(2)}"
    end_str = f"{end_year}{str(end_month).zfill(2)}"
    
    rows = conn.execute("""
        SELECT c.id, c.name, c.color, 
               COUNT(t.id) as count,
               SUM(t.billed_amount) as total
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE substr(t.date, 1, 6) >= ? AND substr(t.date, 1, 6) <= ?
        GROUP BY c.id
        ORDER BY total DESC
    """, (start_str, end_str)).fetchall()
    
    conn.close()
    return [dict(row) for row in rows]


def get_transactions_by_date_range(start_year, start_month, end_year, end_month):
    """기간별 거래 내역 조회"""
    conn = get_connection()
    start_str = f"{start_year}{str(start_month).zfill(2)}"
    end_str = f"{end_year}{str(end_month).zfill(2)}"
    
    query = """
        SELECT t.*, c.name as category_name, c.color as category_color,
               m.content as memo
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN memos m ON t.id = m.transaction_id
        WHERE substr(t.date, 1, 6) >= ? AND substr(t.date, 1, 6) <= ?
        ORDER BY t.date DESC, t.id DESC
    """
    
    rows = conn.execute(query, (start_str, end_str)).fetchall()
    transactions = []
    
    for row in rows:
        tx = dict(row)
        tags = conn.execute("""
            SELECT t.* FROM tags t
            JOIN transaction_tags tt ON t.id = tt.tag_id
            WHERE tt.transaction_id = ?
        """, (tx['id'],)).fetchall()
        tx['tags'] = [dict(tag) for tag in tags]
        transactions.append(tx)
    
    conn.close()
    return transactions


# ============ 리포트/분석 ============

def get_monthly_summary(year, month):
    """월별 카테고리별 지출 요약"""
    conn = get_connection()
    month_str = f"{year}{str(month).zfill(2)}"
    
    rows = conn.execute("""
        SELECT c.id, c.name, c.color, 
               COUNT(t.id) as count,
               SUM(t.billed_amount) as total
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE substr(t.date, 1, 6) = ?
        GROUP BY c.id
        ORDER BY total DESC
    """, (month_str,)).fetchall()
    
    conn.close()
    return [dict(row) for row in rows]


def get_yearly_summary(year):
    """연도별 월별 지출 요약"""
    conn = get_connection()
    
    rows = conn.execute("""
        SELECT substr(date, 5, 2) as month,
               SUM(billed_amount) as total
        FROM transactions
        WHERE substr(date, 1, 4) = ?
        GROUP BY month
        ORDER BY month
    """, (str(year),)).fetchall()
    
    conn.close()
    return [dict(row) for row in rows]


def get_tag_summary(year=None, month=None):
    """태그별 지출 요약"""
    conn = get_connection()
    query = """
        SELECT tg.id, tg.name, tg.color,
               COUNT(DISTINCT t.id) as count,
               SUM(t.billed_amount) as total
        FROM transaction_tags tt
        JOIN tags tg ON tt.tag_id = tg.id
        JOIN transactions t ON tt.transaction_id = t.id
        WHERE 1=1
    """
    params = []
    
    if year:
        query += " AND substr(t.date, 1, 4) = ?"
        params.append(str(year))
    if month:
        query += " AND substr(t.date, 5, 2) = ?"
        params.append(str(month).zfill(2))
    
    query += " GROUP BY tg.id ORDER BY total DESC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()
    print("Database tables created successfully!")
