"""
Excel 파서 모듈
삼성카드 명세서 Excel/CSV 파일 파싱
"""
import pandas as pd
from pathlib import Path
import re
import database as db


def clean_amount(value):
    """금액 문자열을 숫자로 변환"""
    if pd.isna(value):
        return 0
    if isinstance(value, (int, float)):
        return float(value)
    # 콤마 제거 후 숫자 변환
    cleaned = str(value).replace(',', '').replace(' ', '')
    try:
        return float(cleaned)
    except ValueError:
        return 0


def parse_date(value):
    """날짜 문자열 정규화 (YYYYMMDD 형식)"""
    if pd.isna(value):
        return None
    date_str = str(value).replace('-', '').replace('/', '').replace('.', '')
    # 숫자만 추출
    digits = re.sub(r'\D', '', date_str)
    if len(digits) >= 8:
        return digits[:8]
    return None


def detect_sheet_type(df, sheet_name=''):
    """시트 유형 감지 (해외/국내/요약)"""
    # 시트 이름으로 먼저 판단
    sheet_name_lower = sheet_name.lower() if sheet_name else ''
    if '해외' in sheet_name:
        return 'overseas'
    if '일시불' in sheet_name or '할부' in sheet_name:
        return 'domestic'
    if '청구요약' in sheet_name or '요약' in sheet_name:
        return 'summary'
    
    # 첫 10행 내에서 키워드 검색
    for i in range(min(10, len(df))):
        row_text = ' '.join([str(x) for x in df.iloc[i].tolist() if pd.notna(x)])
        if '해외이용' in row_text or '해외매출' in row_text:
            return 'overseas'
        if '국내이용' in row_text or '국내매출' in row_text or '일시불' in row_text:
            return 'domestic'
        if '청구요약' in row_text or '결제예정' in row_text:
            return 'summary'
    return 'unknown'


def find_header_row(df, keywords):
    """헤더 행 찾기"""
    for i in range(min(20, len(df))):
        row_text = ' '.join([str(x) for x in df.iloc[i].tolist() if pd.notna(x)])
        if any(kw in row_text for kw in keywords):
            return i
    return None


def is_installment_sheet(df):
    """할부 시트인지 확인"""
    for i in range(min(5, len(df))):
        row_text = ' '.join([str(x) for x in df.iloc[i].tolist() if pd.notna(x)])
        if '할부' in row_text:
            return True
    return False


def parse_overseas_sheet(df):
    """해외이용 시트 파싱"""
    transactions = []
    
    # 헤더 행 찾기
    header_row = find_header_row(df, ['이용일', '가맹점', '접수일'])
    if header_row is None:
        print("해외이용 헤더를 찾을 수 없습니다.")
        return transactions
    
    # 헤더 설정
    headers = df.iloc[header_row].tolist()
    
    # 컬럼 인덱스 매핑
    col_map = {}
    for idx, h in enumerate(headers):
        h_str = str(h).strip() if pd.notna(h) else ''
        if '이용일' in h_str:
            col_map['date'] = idx
        elif '접수일' in h_str:
            col_map['receipt_date'] = idx
        elif '가맹점' in h_str:
            col_map['merchant'] = idx
        elif '업종' in h_str:
            col_map['business_type'] = idx
        elif '국가' in h_str:
            col_map['country'] = idx
        elif '현지' in h_str and '금액' in h_str:
            col_map['local_amount'] = idx
        elif '화폐' in h_str or 'USD' in h_str.upper():
            col_map['currency'] = idx
        elif '접수금액' in h_str or 'US$' in h_str:
            col_map['usd_amount'] = idx
        elif '환율' in h_str:
            col_map['exchange_rate'] = idx
        elif '원화' in h_str:
            col_map['krw_amount'] = idx
        elif '수수료' in h_str:
            col_map['fee'] = idx
        elif '청구금액' in h_str or '청구' in h_str:
            col_map['billed_amount'] = idx
    
    # 데이터 행 파싱
    for i in range(header_row + 1, len(df)):
        row = df.iloc[i].tolist()
        
        # 빈 행이나 합계 행 스킵
        date_val = row[col_map.get('date', 0)] if 'date' in col_map else None
        merchant_val = row[col_map.get('merchant', 2)] if 'merchant' in col_map else None
        
        if pd.isna(date_val) or not parse_date(date_val):
            # 합계 행인지 확인
            if pd.notna(merchant_val) and '합계' in str(merchant_val):
                continue
            continue
        
        tx = {
            'date': parse_date(row[col_map.get('date', 0)]),
            'receipt_date': parse_date(row[col_map.get('receipt_date', 1)]),
            'merchant': str(row[col_map.get('merchant', 2)]).strip() if pd.notna(row[col_map.get('merchant', 2)]) else '',
            'business_type': str(row[col_map.get('business_type', 3)]).strip() if 'business_type' in col_map and pd.notna(row[col_map['business_type']]) else None,
            'country': str(row[col_map.get('country', 4)]).strip() if 'country' in col_map and pd.notna(row[col_map['country']]) else None,
            'local_amount': clean_amount(row[col_map['local_amount']]) if 'local_amount' in col_map else None,
            'currency': str(row[col_map['currency']]).strip() if 'currency' in col_map and pd.notna(row[col_map['currency']]) else 'USD',
            'usd_amount': clean_amount(row[col_map['usd_amount']]) if 'usd_amount' in col_map else None,
            'exchange_rate': clean_amount(row[col_map['exchange_rate']]) if 'exchange_rate' in col_map else None,
            'krw_amount': int(clean_amount(row[col_map['krw_amount']])) if 'krw_amount' in col_map else 0,
            'fee': int(clean_amount(row[col_map['fee']])) if 'fee' in col_map else 0,
            'billed_amount': 0,  # 아래에서 설정
            'is_overseas': 1,
            'category_id': None,
        }
        
        # 해외거래는 원화환산 금액을 사용 (청구금액 대신)
        tx['billed_amount'] = tx['krw_amount']
        
        # 유효한 거래만 추가
        if tx['merchant'] and tx['billed_amount'] > 0:
            # 가맹점 기반 자동 카테고리 지정
            auto_cat = db.get_category_by_merchant(tx['merchant'])
            if auto_cat:
                tx['category_id'] = auto_cat['id']
            
            transactions.append(tx)
    
    return transactions


def parse_domestic_sheet(df, sheet_name=''):
    """국내이용/일시불/할부 시트 파싱"""
    transactions = []
    is_halbu = is_installment_sheet(df) or '할부' in sheet_name
    
    # 헤더 행 찾기 - 다양한 키워드 지원
    header_row = find_header_row(df, ['이용일', '가맹점', '이용금액', '원금'])
    if header_row is None:
        print("국내이용 헤더를 찾을 수 없습니다.")
        return transactions
    
    headers = df.iloc[header_row].tolist()
    print(f"  발견된 헤더: {headers}")
    print(f"  할부 시트: {is_halbu}")
    
    col_map = {}
    for idx, h in enumerate(headers):
        h_str = str(h).strip() if pd.notna(h) else ''
        if '이용일' in h_str and 'date' not in col_map:
            col_map['date'] = idx
        elif '가맹점' in h_str and 'merchant' not in col_map:
            col_map['merchant'] = idx
        elif '업종' in h_str and 'business_type' not in col_map:
            col_map['business_type'] = idx
        elif h_str == '원금':  # 정확히 '원금'만
            col_map['principal'] = idx
        elif '이용금액' in h_str and 'amount' not in col_map:
            col_map['amount'] = idx
        elif '할부' in h_str and '개월' in h_str:
            col_map['installment'] = idx
    
    print(f"  컬럼 매핑: {col_map}")
    
    for i in range(header_row + 1, len(df)):
        row = df.iloc[i].tolist()
        
        date_val = row[col_map.get('date', 0)] if 'date' in col_map else None
        if pd.isna(date_val) or not parse_date(date_val):
            continue
        
        # 금액 파싱 - 할부는 원금, 일시불은 이용금액
        if is_halbu and 'principal' in col_map:
            raw_amount = row[col_map['principal']]
        elif 'amount' in col_map:
            raw_amount = row[col_map['amount']]
        else:
            raw_amount = 0
        
        amount = int(clean_amount(raw_amount))
        
        # 가맹점명 파싱 - 여러 컬럼 위치 시도
        merchant = ''
        if 'merchant' in col_map and pd.notna(row[col_map['merchant']]):
            merchant = str(row[col_map['merchant']]).strip()
        
        # 업종 파싱
        business_type = None
        if 'business_type' in col_map and pd.notna(row[col_map['business_type']]):
            business_type = str(row[col_map['business_type']]).strip()
        
        tx = {
            'date': parse_date(date_val),
            'receipt_date': None,
            'merchant': merchant,
            'business_type': business_type,
            'country': None,
            'local_amount': None,
            'currency': 'KRW',
            'usd_amount': None,
            'exchange_rate': None,
            'krw_amount': amount,
            'fee': 0,
            'billed_amount': amount,
            'is_overseas': 0,
            'category_id': None,
        }
        
        # 가맹점명이 있고 금액이 있는 거래만 (취소거래는 음수도 허용)
        if tx['merchant'] and tx['billed_amount'] != 0:
            auto_cat = db.get_category_by_merchant(tx['merchant'])
            if auto_cat:
                tx['category_id'] = auto_cat['id']
            transactions.append(tx)
    
    return transactions


def parse_excel_file(file_path):
    """Excel 파일 전체 파싱"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
    
    all_transactions = []
    
    # Excel 파일의 모든 시트 읽기
    xls = pd.ExcelFile(file_path)
    
    for sheet_name in xls.sheet_names:
        print(f"시트 파싱 중: {sheet_name}")
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        
        sheet_type = detect_sheet_type(df, sheet_name)
        print(f"  시트 유형: {sheet_type}")
        
        # 해외이용 시트는 제외
        if sheet_type == 'overseas':
            print(f"  스킵 (해외결제 제외)")
            continue
        elif sheet_type == 'domestic':
            txs = parse_domestic_sheet(df, sheet_name)
            all_transactions.extend(txs)
            print(f"  국내 거래 {len(txs)}건 파싱됨")
        else:
            print(f"  스킵 (요약 또는 미지원 시트)")
    
    return all_transactions


def parse_csv_file(file_path):
    """CSV 파일 파싱 (단일 시트)"""
    df = pd.read_csv(file_path, header=None, encoding='utf-8')
    
    sheet_type = detect_sheet_type(df)
    
    if sheet_type == 'overseas':
        return parse_overseas_sheet(df)
    elif sheet_type == 'domestic':
        return parse_domestic_sheet(df)
    else:
        return []


def import_file(file_path):
    """파일 import 및 DB 저장 (동일 월 기존 데이터 삭제 후 저장)"""
    file_path = Path(file_path)
    
    if file_path.suffix.lower() in ['.xlsx', '.xls']:
        transactions = parse_excel_file(file_path)
    elif file_path.suffix.lower() == '.csv':
        transactions = parse_csv_file(file_path)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {file_path.suffix}")
    
    # 파싱된 거래에서 연도+월 추출 (중복 제거)
    months_in_file = set()
    for tx in transactions:
        if tx.get('date') and len(tx['date']) >= 6:
            year = int(tx['date'][:4])
            month = int(tx['date'][4:6])
            months_in_file.add((year, month))
    
    # 해당 월의 기존 거래 삭제
    deleted_total = 0
    for year, month in months_in_file:
        deleted = db.delete_transactions_by_month(year, month)
        deleted_total += deleted
    
    if deleted_total > 0:
        print(f"기존 {deleted_total}건 삭제됨")
    
    # DB에 저장
    imported_count = 0
    for tx in transactions:
        try:
            db.add_transaction(tx)
            imported_count += 1
        except Exception as e:
            print(f"거래 저장 실패: {e}")
    
    print(f"총 {imported_count}건 저장됨")
    return imported_count


if __name__ == "__main__":
    # 테스트
    import sys
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        db.init_db()
        count = import_file(file_path)
        print(f"Import 완료: {count}건")
