"""
카드 명세서 분석 프로그램
Flask 메인 애플리케이션 (로그인 시스템 포함)
"""
import os
import secrets
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import database as db
import parser as excel_parser
from auth import User, init_auth_db, set_auth_db_path, get_user_db_path

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))

# 기본 경로 설정
BASE_PATH = Path(__file__).parent

# 업로드 폴더 생성
app.config['UPLOAD_FOLDER'] = BASE_PATH / 'uploads'
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)

# Flask-Login 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))


@app.before_request
def before_request():
    """요청 전 사용자별 DB 경로 설정"""
    if current_user.is_authenticated:
        user_db_path = get_user_db_path(str(BASE_PATH), current_user.id)
        db.DB_PATH = user_db_path
        # 테이블 초기화 확인
        if not os.path.exists(user_db_path):
            db.init_db()


# ============ 인증 라우트 ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    """로그인/회원가입 페이지"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        action = request.form.get('action')
        
        if not username or not password:
            error = '사용자명과 비밀번호를 입력하세요'
        elif action == 'register':
            # 회원가입
            if len(password) < 4:
                error = '비밀번호는 4자 이상이어야 합니다'
            else:
                user_id = User.create(username, password)
                if user_id:
                    user = User.get(user_id)
                    login_user(user)
                    # 새 사용자 DB 초기화
                    user_db_path = get_user_db_path(str(BASE_PATH), user_id)
                    db.DB_PATH = user_db_path
                    db.init_db()
                    return redirect(url_for('index'))
                else:
                    error = '이미 존재하는 사용자명입니다'
        else:
            # 로그인
            user_data = User.get_by_username(username)
            if user_data and User.verify_password(user_data['password_hash'], password):
                user = User(user_data['id'], user_data['username'])
                login_user(user)
                return redirect(url_for('index'))
            else:
                error = '사용자명 또는 비밀번호가 올바르지 않습니다'
    
    return render_template('login.html', error=error)


@app.route('/logout')
@login_required
def logout():
    """로그아웃"""
    logout_user()
    return redirect(url_for('login'))


# ============ 대시보드 ============

@app.route('/')
@login_required
def index():
    """대시보드 - 기간 선택 지원"""
    now = datetime.now()
    
    start_year = request.args.get('start_year', now.year, type=int)
    start_month = request.args.get('start_month', now.month, type=int)
    end_year = request.args.get('end_year', now.year, type=int)
    end_month = request.args.get('end_month', now.month, type=int)
    
    summary = db.get_summary_by_date_range(start_year, start_month, end_year, end_month)
    total = sum(s['total'] or 0 for s in summary)
    recent_txs = db.get_transactions_by_date_range(start_year, start_month, end_year, end_month)[:10]
    categories = db.get_categories()
    years = list(range(2025, now.year + 1))
    
    return render_template('index.html',
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
        summary=summary,
        total=total,
        recent_txs=recent_txs,
        categories=categories,
        years=years,
        username=current_user.username
    )


# ============ 거래 내역 ============

@app.route('/transactions')
@login_required
def transactions():
    """거래 내역 페이지"""
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    category_id = request.args.get('category', type=int)
    tag_id = request.args.get('tag', type=int)
    search = request.args.get('search', '')
    
    filters = {}
    if year:
        filters['year'] = year
    if month:
        filters['month'] = month
    if category_id:
        filters['category_id'] = category_id
    if tag_id:
        filters['tag_id'] = tag_id
    if search:
        filters['search'] = search
    
    txs = db.get_transactions(filters if filters else None)
    categories = db.get_categories()
    tags = db.get_tags()
    
    all_txs = db.get_transactions()
    years = sorted(set(int(t['date'][:4]) for t in all_txs if t['date']), reverse=True)
    
    # 전체 금액 합계
    total_amount = sum(tx['billed_amount'] or 0 for tx in txs)
    
    return render_template('transactions.html',
        transactions=txs,
        categories=categories,
        tags=tags,
        years=years,
        current_year=year,
        current_month=month,
        current_category=category_id,
        current_tag=tag_id,
        search=search,
        total_amount=total_amount
    )


# ============ 파일 업로드 ============

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """파일 업로드"""
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': '파일이 없습니다'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '파일이 선택되지 않았습니다'}), 400
        
        filename = file.filename
        file_path = app.config['UPLOAD_FOLDER'] / filename
        file.save(file_path)
        
        try:
            count = excel_parser.import_file(file_path)
            return jsonify({
                'success': True,
                'message': f'{count}건의 거래가 추가되었습니다'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return render_template('upload.html')


# ============ 카테고리 API ============

@app.route('/categories')
@login_required
def categories_page():
    """카테고리 관리 페이지"""
    categories = db.get_categories()
    uncategorized_merchants = db.get_uncategorized_merchants()
    merchant_rules = db.get_merchant_rules()
    return render_template('categories.html', 
        categories=categories,
        uncategorized_merchants=uncategorized_merchants,
        merchant_rules=merchant_rules
    )


@app.route('/api/categories', methods=['GET', 'POST'])
@login_required
def api_categories():
    """카테고리 API"""
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name', '').strip()
        color = data.get('color', '#6366f1')
        
        if not name:
            return jsonify({'error': '카테고리 이름을 입력하세요'}), 400
        
        cat_id = db.create_category(name, color)
        if cat_id:
            return jsonify({'id': cat_id, 'name': name, 'color': color})
        return jsonify({'error': '이미 존재하는 카테고리입니다'}), 400
    
    return jsonify(db.get_categories())


@app.route('/api/categories/<int:cat_id>', methods=['PUT', 'DELETE'])
@login_required
def api_category_detail(cat_id):
    """단일 카테고리 수정/삭제"""
    if request.method == 'PUT':
        data = request.get_json()
        db.update_category(cat_id, data.get('name'), data.get('color'))
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        db.delete_category(cat_id)
        return jsonify({'success': True})


@app.route('/api/merchants/rule', methods=['POST', 'DELETE'])
@login_required
def api_merchant_rule():
    """가맹점 분류 규칙 API"""
    data = request.get_json()
    merchant = data.get('merchant', '').strip()
    
    if request.method == 'POST':
        category_id = data.get('category_id')
        if not merchant or not category_id:
            return jsonify({'error': '가맹점과 카테고리를 선택하세요'}), 400
        
        affected = db.apply_category_to_all_transactions_by_merchant(merchant, category_id)
        return jsonify({'success': True, 'affected': affected})
    
    elif request.method == 'DELETE':
        if not merchant:
            return jsonify({'error': '가맹점을 선택하세요'}), 400
        db.delete_merchant_rule(merchant)
        return jsonify({'success': True})


# ============ 거래 API ============

@app.route('/api/transactions/<int:tx_id>/category', methods=['PUT'])
@login_required
def update_tx_category(tx_id):
    """거래 카테고리 수정"""
    data = request.get_json()
    category_id = data.get('category_id')
    
    db.update_transaction_category(tx_id, category_id)
    
    if data.get('save_rule') and data.get('merchant'):
        db.set_merchant_category_rule(data['merchant'], category_id)
    
    return jsonify({'success': True})


@app.route('/api/transactions/<int:tx_id>/memo', methods=['PUT'])
@login_required
def update_tx_memo(tx_id):
    """거래 메모 수정"""
    data = request.get_json()
    content = data.get('content', '')
    db.set_memo(tx_id, content)
    return jsonify({'success': True})


@app.route('/api/transactions/<int:tx_id>/tags', methods=['POST', 'DELETE'])
@login_required
def manage_tx_tags(tx_id):
    """거래 태그 관리"""
    data = request.get_json()
    
    if request.method == 'POST':
        tag_name = data.get('name', '').strip()
        if tag_name:
            tag_id = db.create_tag(tag_name)
            if tag_id:
                db.add_tag_to_transaction(tx_id, tag_id)
                return jsonify({'success': True, 'tag_id': tag_id})
        return jsonify({'error': '태그 이름을 입력하세요'}), 400
    
    elif request.method == 'DELETE':
        tag_id = data.get('tag_id')
        if tag_id:
            db.remove_tag_from_transaction(tx_id, tag_id)
        return jsonify({'success': True})


@app.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
@login_required
def delete_tx(tx_id):
    """거래 삭제"""
    db.delete_transaction(tx_id)
    return jsonify({'success': True})


@app.route('/api/transactions/bulk/category', methods=['PUT'])
@login_required
def bulk_update_category():
    """일괄 카테고리 변경"""
    data = request.get_json()
    transaction_ids = data.get('transaction_ids', [])
    category_id = data.get('category_id')
    
    if not transaction_ids:
        return jsonify({'error': '거래를 선택하세요'}), 400
    
    for tx_id in transaction_ids:
        db.update_transaction_category(tx_id, category_id)
    
    return jsonify({'success': True, 'count': len(transaction_ids)})


@app.route('/api/transactions/bulk', methods=['DELETE'])
@login_required
def bulk_delete_transactions():
    """일괄 거래 삭제"""
    data = request.get_json()
    transaction_ids = data.get('transaction_ids', [])
    
    if not transaction_ids:
        return jsonify({'error': '거래를 선택하세요'}), 400
    
    for tx_id in transaction_ids:
        db.delete_transaction(tx_id)
    
    return jsonify({'success': True, 'count': len(transaction_ids)})


# ============ 태그 API ============

@app.route('/api/tags')
@login_required
def api_tags():
    """모든 태그 조회"""
    return jsonify(db.get_tags())


@app.route('/api/tags/autocomplete')
@login_required
def api_tags_autocomplete():
    """태그 자동완성"""
    query = request.args.get('q', '')
    tags = db.search_tags(query)
    return jsonify(tags)


# ============ 리포트 ============

@app.route('/reports')
@login_required
def reports():
    """분석 리포트 페이지"""
    now = datetime.now()
    year = request.args.get('year', now.year, type=int)
    month = request.args.get('month', now.month, type=int)
    
    # 이번달 카테고리별 요약
    current_summary = db.get_monthly_summary(year, month)
    current_total = sum(s['total'] or 0 for s in current_summary)
    
    # 전달 계산
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    
    # 전달 카테고리별 요약
    prev_summary = db.get_monthly_summary(prev_year, prev_month)
    prev_total = sum(s['total'] or 0 for s in prev_summary)
    
    # 비교 데이터 생성
    comparison_data = []
    all_categories = {}
    
    for s in current_summary:
        cat_id = s['id']
        all_categories[cat_id] = {
            'id': cat_id,
            'name': s['name'] or '미분류',
            'color': s['color'] or '#64748b',
            'current': s['total'] or 0,
            'prev': 0
        }
    
    for s in prev_summary:
        cat_id = s['id']
        if cat_id in all_categories:
            all_categories[cat_id]['prev'] = s['total'] or 0
        else:
            all_categories[cat_id] = {
                'id': cat_id,
                'name': s['name'] or '미분류',
                'color': s['color'] or '#64748b',
                'current': 0,
                'prev': s['total'] or 0
            }
    
    comparison_data = list(all_categories.values())
    comparison_data.sort(key=lambda x: x['current'], reverse=True)
    
    # 총 지출 비교
    total_diff = current_total - prev_total
    total_diff_percent = ((current_total - prev_total) / prev_total * 100) if prev_total > 0 else 0
    
    # 연간 월별 추이
    yearly = db.get_yearly_summary(year)
    
    # 연도 목록
    all_txs = db.get_transactions()
    years = sorted(set(int(t['date'][:4]) for t in all_txs if t['date']), reverse=True)
    if not years:
        years = [now.year]
    
    return render_template('reports.html',
        year=year,
        month=month,
        prev_year=prev_year,
        prev_month=prev_month,
        category_summary=current_summary,
        comparison_data=comparison_data,
        current_total=current_total,
        prev_total=prev_total,
        total_diff=total_diff,
        total_diff_percent=total_diff_percent,
        yearly=yearly,
        years=years
    )


@app.route('/api/reports/monthly')
@login_required
def api_monthly_report():
    """월별 리포트 API"""
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    summary = db.get_monthly_summary(year, month)
    return jsonify(summary)


@app.route('/api/reports/yearly')
@login_required
def api_yearly_report():
    """연간 리포트 API"""
    year = request.args.get('year', datetime.now().year, type=int)
    
    monthly = db.get_yearly_summary(year)
    return jsonify(monthly)


if __name__ == '__main__':
    db.init_db()
    
    print("=" * 50)
    print("카드 명세서 분석 프로그램")
    print("브라우저에서 http://127.0.0.1:5000 접속")
    print("=" * 50)
    
    app.run(debug=True, port=5000)
