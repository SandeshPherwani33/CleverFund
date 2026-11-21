"""
Generate a sample startup dataset with balanced classes for training
"""
import pandas as pd
import numpy as np
from pathlib import Path

# Set random seed for reproducibility
np.random.seed(42)

def generate_sample_dataset(n_samples=5000):
    """Generate a balanced startup dataset with success/failure labels"""
    
    # Generate target variable (50/50 split for simplicity, or match original)
    # But let's use the actual pattern from the problem description: ~67% success, ~33% failure
    n_success = int(n_samples * 0.67)
    n_failure = n_samples - n_success
    
    # Helper to build synthetic but realistic-sounding company names
    def _make_company_names(n):
        prefixes = [
            'Velocity', 'Nova', 'Apex', 'Bright', 'Quantum', 'Nimbus', 'Atlas', 'Vertex', 'Pioneer', 'Summit',
            'Pulse', 'Echo', 'Launch', 'Catalyst', 'Fusion', 'Blue', 'Green', 'Silver', 'Iron', 'Oak'
        ]
        suffixes = [
            'AI', 'Labs', 'Systems', 'Analytics', 'Works', 'Dynamics', 'Solutions', 'Ventures', 'Networks', 'Tech',
            'Capital', 'Studios', 'Concepts', 'Global', 'Innovations', 'Partners', 'Holdings', 'Insight', 'Cloud', 'Market'
        ]
        names = []
        for i in range(n):
            p = prefixes[i % len(prefixes)]
            s = suffixes[(i * 7) % len(suffixes)]
            # Add a small numeric suffix occasionally to reduce collisions
            if i % 37 == 0:
                name = f"{p} {s} {i}"
            else:
                name = f"{p} {s}"
            names.append(name)
        return names

    data = {
        'Number_of_Founders': np.random.randint(1, 10, n_samples),
        'Marketing_Expense': np.random.randint(10000, 1000000, n_samples),
        'Employees_Count': np.random.randint(1, 500, n_samples),
        'Customer_Retention_Rate': np.random.uniform(0, 100, n_samples),
        # Use a `startup` column (aliases map to canonical `name` later)
        'startup': _make_company_names(n_samples),
        'Startup_Status': np.concatenate([np.ones(n_success), np.zeros(n_failure)]).astype(int),
        'Founder_Experience': np.random.randint(0, 30, n_samples),
        'Funding_Amount': np.random.randint(50000, 10000000, n_samples),
        'Business_Model': np.random.choice(['SaaS', 'B2C', 'B2B'], n_samples),
        'Revenue': np.random.randint(0, 5000000, n_samples),
        'Startup_Age': np.random.randint(1, 15, n_samples),
        'Burn_Rate': np.random.randint(10000, 500000, n_samples),
        'InvestmentType': np.random.choice(['Seed', 'Series A', 'Series B', 'Series C', 'Venture', 'Angel', 'Equity', 'Debt', 'Grant', 'Bootstrap', 'Incubator', 'Accelerator'], n_samples),
        'Market_Size': np.random.choice(['Small', 'Medium', 'Large', 'Very Large'], n_samples),
        'City': np.random.choice(['San Francisco', 'New York', 'Los Angeles', 'Boston', 'Seattle', 'Austin', 'Denver', 'Chicago', 'Toronto', 'London'], n_samples),
        'Product_Uniqueness_Score': np.random.uniform(0, 100, n_samples),
        'Industry': np.random.choice(['Technology', 'Healthcare', 'Finance', 'Retail', 'Education', 'E-Commerce', 'SaaS'], n_samples),
        'InvestmentAmount_USD': np.random.randint(50000, 10000000, n_samples),
        'Status': np.concatenate([['Success'] * n_success, ['Failure'] * n_failure]),
        'Investor': [f'Investor_{np.random.randint(1, 100)}' for _ in range(n_samples)],
        'Date': pd.date_range('2020-01-01', periods=n_samples, freq='h'),
    }
    
    df = pd.DataFrame(data)
    
    # Shuffle the dataframe
    df = df.sample(frac=1).reset_index(drop=True)
    
    return df

# Generate dataset
print("Generating sample dataset...")
df = generate_sample_dataset(5000)

# Save to CSV
output_path = Path('data') / 'combined_dataset.csv'
output_path.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(output_path, index=False)
print(f"Dataset saved to {output_path}")
print(f"\nDataset info:")
print(f"Shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")
print(f"\nClass distribution:")
print(df['Startup_Status'].value_counts())
print(f"\nStatus distribution:")
print(df['Status'].value_counts())
