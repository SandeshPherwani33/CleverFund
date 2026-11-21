import pandas as pd
import os

data_dir = 'data'
for file in os.listdir(data_dir):
    if file.endswith(('.xlsx', '.xls')):
        path = os.path.join(data_dir, file)
        print(f'Loading {file}...')
        df = pd.read_excel(path)
        print(f'Shape: {df.shape}')
        print(f'Columns: {df.columns.tolist()}')
        
        # Normalize column names
        print(f'\nStartup_Status unique values: {df["Startup_Status"].unique()}')
        print(f'Status unique values: {df["Status"].unique()}')
        
        print(f'\nValue counts for Startup_Status:')
        print(df['Startup_Status'].value_counts())
        print(f'\nValue counts for Status:')
        print(df['Status'].value_counts())
        break
