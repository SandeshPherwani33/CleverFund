import pandas as pd
import sys
p = r"d:\capstone front\data\ekdum_final_industry_fixed (1).xlsx"
try:
    xls = pd.ExcelFile(p)
except Exception as e:
    print('ERROR opening file:', e)
    sys.exit(1)
print('SHEETS:', xls.sheet_names)
for s in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=s)
    print('\n--- Sheet:', s, '---')
    print('shape:', df.shape)
    print('columns:', df.columns.tolist())
    print('dtypes counts:')
    print(df.dtypes.value_counts().to_dict())
    print('\nmissing per column (top 10):')
    print(df.isna().sum().sort_values(ascending=False).head(10).to_dict())
    print('\nsample rows (3):')
    print(df.head(3).to_dict())
