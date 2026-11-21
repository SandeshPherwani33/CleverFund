import dataset

p = dataset._resolve_dataset_path()
print('path used:', p)
df = dataset.load_startup_dataset()
print('columns:', df.columns.tolist())
print(df[['name','funding_amount','num_employees','revenue']].head(5).to_dict())
