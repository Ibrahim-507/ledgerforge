import pandas as pd

for name in ["attendance", "leave_types", "leave_requests", "leave_balances", "holidays"]:
    df = pd.read_csv(f"data/{name}.csv")
    print("=====", name, df.shape)
    print(df.head(3).to_string())
    missing = df.isna().sum()
    print("missing values:", missing[missing > 0].to_dict())