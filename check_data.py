import sqlite3

conn = sqlite3.connect('data.db')

# 2025년 11월 거래내역 확인
print("=" * 80)
print("2025년 11월 거래내역")
print("=" * 80)

cursor = conn.execute('''
    SELECT date, merchant, billed_amount, is_overseas 
    FROM transactions 
    WHERE date LIKE '202511%' 
    ORDER BY billed_amount DESC
    LIMIT 20
''')

for row in cursor:
    date_str = f"{row[0][:4]}.{row[0][4:6]}.{row[0][6:8]}"
    overseas = "해외" if row[3] else "국내"
    print(f"{date_str} | {row[1][:30]:30} | ₩{row[2]:>10,} | {overseas}")

# 통계
cursor = conn.execute('SELECT COUNT(*) FROM transactions WHERE date LIKE "202511%"')
count = cursor.fetchone()[0]
print(f"\n총 {count}건")

# 해외거래 체크
print("\n" + "=" * 80)
print("해외거래 청구금액 확인 (FC* FREEPIK PREMIUM+)")
print("=" * 80)
cursor = conn.execute('''
    SELECT date, merchant, billed_amount 
    FROM transactions 
    WHERE merchant LIKE '%FREEPIK%' AND is_overseas = 1
''')
for row in cursor:
    print(f"{row[0]} | {row[1]} | ₩{row[2]:,}")

conn.close()
