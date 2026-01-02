# 💰 카드 명세서 분석 프로그램 (가계부)

삼성카드 명세서를 분석하고 지출을 관리하는 로컬 웹 애플리케이션입니다.

## ✨ 주요 기능

- **명세서 업로드**: Excel 파일(.xlsx) 업로드로 거래 내역 자동 파싱
- **카테고리 관리**: 지출 카테고리 분류 및 가맹점별 자동 분류 규칙
- **기간별 조회**: 시작~종료 기간을 선택하여 지출 현황 확인
- **태그 & 메모**: 거래별 태그와 메모 추가
- **시각화**: 카테고리별 지출 차트로 시각화

## 🚀 설치 및 실행

### 요구사항
- Python 3.9+

### 설치
```bash
# 의존성 설치
pip install -r requirements.txt
```

### 실행
```bash
python run.py
```
브라우저가 자동으로 열립니다.

### EXE 빌드 (선택)
```bash
pip install pyinstaller
pyinstaller 가계부.spec
```
`dist/가계부.exe` 파일이 생성됩니다.

## 📁 프로젝트 구조

```
가계부/
├── app.py           # Flask 메인 애플리케이션
├── run.py           # 앱 런처 (브라우저 자동 열기)
├── database.py      # SQLite 데이터베이스 관리
├── parser.py        # Excel 파일 파싱
├── templates/       # HTML 템플릿
├── static/          # CSS, JS 파일
├── .env.example     # 환경변수 예시
└── requirements.txt # 의존성 목록
```

## ⚙️ 환경 설정 (선택)

`.env.example`을 복사하여 `.env`로 이름을 변경하고 설정:

```env
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=False
```

## 📊 지원 파일 형식

- 삼성카드 명세서 Excel 파일 (.xlsx)
  - 일시불 시트
  - 할부 시트
  - ~~해외이용 시트~~ (제외됨)

## 🔒 보안

- 모든 데이터는 로컬 SQLite 데이터베이스(`data.db`)에 저장됩니다
- 외부 서버로 데이터가 전송되지 않습니다
- 개인정보가 포함된 `data.db` 파일은 Git에 업로드되지 않습니다

## 📝 라이선스

MIT License
