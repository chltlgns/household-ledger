import pandas as pd

xls = pd.ExcelFile('samsungcard_20251213.xlsx')

# 할부 시트 구조 확인
print("=" * 80)
print("할부 시트 구조:")
print("=" * 80)
df_halbu = pd.read_excel(xls, sheet_name='할부', header=None)
print(df_halbu.head(10).to_string())

# 해외이용 시트 - FC* FREEPIK PREMIUM+ 중복 확인
print("\n" + "=" * 80)
print("해외이용 시트 - FREEPIK 거래:")
print("=" * 80)
df_overseas = pd.read_excel(xls, sheet_name='해외이용', header=None)
for i, row in df_overseas.iterrows():
    if 'FREEPIK' in str(row.values):
        print(f"Row {i}: {row.tolist()}")
