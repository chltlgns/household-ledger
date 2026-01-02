"""
카드 명세서 분석 프로그램
Flask 메인 애플리케이션
"""
import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for
import database as db
import parser as excel_parser

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['UPLOAD_FOLDER'] = Path(__file__).parent / 'uploads'

# 업로드 폴더 생성
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)


@app.route('/')
def index():
    """대시보드 - 기간 선택 지원"""
    # 현재 연/월
    now = datetime.now()
    
    # 시작/종료 연월 파라미터 (기본값: 현재 월)
    start_year = request.args.get('start_year', now.year, type=int)
    start_month = request.args.get('start_month', now.month, type=int)
    end_year = request.args.get('end_year', now.year, type=int)
    end_month = request.args.get('end_month', now.month, type=int)
    
    # 기간별 요약
    summary = db.get_summary_by_date_range(start_year, start_month, end_year, end_month)
    
    # 총 지출
    total = sum(s['total'] or 0 for s in summary)
    
    # 최근 거래 (기간 내)
    recent_txs = db.get_transactions_by_date_range(start_year, start_month, end_year, end_month)[:10]
    
    # 카테고리 목록
    categories = db.get_categories()
    
    # 연도 목록 (2025년부터 현재년까지)
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
        years=years
    )


@app.route('/transactions')
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
    
    # 연도/월 목록 생성
    all_txs = db.get_transactions()
    years = sorted(set(int(t['date'][:4]) for t in all_txs if t['date']), reverse=True)
    
    return render_template('transactions.html',
        transactions=txs,
        categories=categories,
        tags=tags,
        years=years,
        current_year=year,
        current_month=month,
        current_category=category_id,
        current_tag=tag_id,
        search=search
    )


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """파일 업로드"""
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': '파일이 없습니다'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '파일이 선택되지 않았습니다'}), 400
        
        # 파일 저장
        filename = file.filename
        file_path = app.config['UPLOAD_FOLDER'] / filename
        file.save(file_path)
        
        try:
            # 파싱 및 DB 저장
            count = excel_parser.import_file(file_path)
            return jsonify({
                'success': True,
                'message': f'{count}건의 거래가 추가되었습니다'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            # 업로드된 파일 삭제 (선택적)
            # file_path.unlink(missing_ok=True)
            pass
    
    return render_template('upload.html')


# ============ 카테고리 API ============

@app.route('/categories')
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
def api_merchant_rule():
    """가맹점 분류 규칙 API"""
    data = request.get_json()
    merchant = data.get('merchant', '').strip()
    
    if request.method == 'POST':
        category_id = data.get('category_id')
        if not merchant or not category_id:
            return jsonify({'error': '가맹점과 카테고리를 선택하세요'}), 400
        
        # 규칙 저장 및 기존 거래에 일괄 적용
        affected = db.apply_category_to_all_transactions_by_merchant(merchant, category_id)
        return jsonify({'success': True, 'affected': affected})
    
    elif request.method == 'DELETE':
        if not merchant:
            return jsonify({'error': '가맹점을 선택하세요'}), 400
        db.delete_merchant_rule(merchant)
        return jsonify({'success': True})


# ============ 거래 API ============

@app.route('/api/transactions/<int:tx_id>/category', methods=['PUT'])
def update_tx_category(tx_id):
    """거래 카테고리 수정"""
    data = request.get_json()
    category_id = data.get('category_id')
    
    db.update_transaction_category(tx_id, category_id)
    
    # 가맹점 규칙 저장 (체크박스 선택 시)
    if data.get('save_rule') and data.get('merchant'):
        db.set_merchant_category_rule(data['merchant'], category_id)
    
    return jsonify({'success': True})


@app.route('/api/transactions/<int:tx_id>/memo', methods=['PUT'])
def update_tx_memo(tx_id):
    """거래 메모 수정"""
    data = request.get_json()
    content = data.get('content', '')
    db.set_memo(tx_id, content)
    return jsonify({'success': True})


@app.route('/api/transactions/<int:tx_id>/tags', methods=['POST', 'DELETE'])
def manage_tx_tags(tx_id):
    """거래 태그 관리"""
    data = request.get_json()
    
    if request.method == 'POST':
        tag_name = data.get('name', '').strip()
        if tag_name:
            # 태그 생성 또는 기존 태그 ID 반환
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
def delete_tx(tx_id):
    """거래 삭제"""
    db.delete_transaction(tx_id)
    return jsonify({'success': True})


# ============ 태그 API ============

@app.route('/api/tags')
def api_tags():
    """모든 태그 조회"""
    return jsonify(db.get_tags())


@app.route('/api/tags/autocomplete')
def api_tags_autocomplete():
    """태그 자동완성"""
    query = request.args.get('q', '')
    tags = db.search_tags(query)
    return jsonify(tags)


# ============ 리포트 ============

@app.route('/reports')
def reports():
    """분석 리포트 페이지"""
    now = datetime.now()
    year = request.args.get('year', now.year, type=int)
    month = request.args.get('month', type=int)
    
    # 월별 요약 (카테고리별)
    if month:
        category_summary = db.get_monthly_summary(year, month)
    else:
        # 연간 전체
        category_summary = []
        for m in range(1, 13):
            monthly = db.get_monthly_summary(year, m)
            # 합산
            for ms in monthly:
                found = False
                for cs in category_summary:
                    if cs['id'] == ms['id']:
                        cs['count'] = (cs.get('count') or 0) + (ms.get('count') or 0)
                        cs['total'] = (cs.get('total') or 0) + (ms.get('total') or 0)
                        found = True
                        break
                if not found:
                    category_summary.append(dict(ms))
    
    # 연간 월별 추이
    yearly = db.get_yearly_summary(year)
    
    # 태그별 요약
    tag_summary = db.get_tag_summary(year, month)
    
    # 연도 목록
    all_txs = db.get_transactions()
    years = sorted(set(int(t['date'][:4]) for t in all_txs if t['date']), reverse=True)
    if not years:
        years = [now.year]
    
    return render_template('reports.html',
        year=year,
        month=month,
        category_summary=category_summary,
        yearly=yearly,
        tag_summary=tag_summary,
        years=years
    )


@app.route('/api/reports/monthly')
def api_monthly_report():
    """월별 리포트 API"""
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    summary = db.get_monthly_summary(year, month)
    return jsonify(summary)


@app.route('/api/reports/yearly')
def api_yearly_report():
    """연간 리포트 API"""
    year = request.args.get('year', datetime.now().year, type=int)
    
    monthly = db.get_yearly_summary(year)
    return jsonify(monthly)


if __name__ == '__main__':
    # 데이터베이스 초기화
    db.init_db()
    
    print("=" * 50)
    print("카드 명세서 분석 프로그램")
    print("브라우저에서 http://127.0.0.1:5000 접속")
    print("=" * 50)
    
    app.run(debug=True, port=5000)
