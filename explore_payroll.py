"""Look at the data for Task 11 (vendors and expense bills). Prints a lot: send it all.

    python explore_task11.py
"""
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", 50)


def load(name):
    return pd.read_csv(f"csv/{name}.csv")


print("===== vendors")
vendors = load("vendors")
print(vendors.shape)
print(vendors.head(3).to_string())

print("\n===== expenses")
expenses = load("expenses")
print(expenses.shape)
print(list(expenses.columns))
print(expenses.head(3).to_string())
print("\nvalues of columns with 12 or fewer different values:")
for column in expenses.columns:
    if expenses[column].nunique(dropna=False) <= 12:
        print(f"--- {column}")
        print(expenses[column].value_counts(dropna=False).to_string())

print("\n===== chart_of_accounts: liability and expense accounts")
chart = load("chart_of_accounts")
print(chart[chart.account_type.isin(["LIABILITY", "EXPENSE"])][
    ["account_code", "account_name", "account_type", "normal_balance", "is_group"]].to_string())

print("\n===== journal_entries: what kinds of entries exist")
entries = load("journal_entries")
print(entries.source_type.value_counts().to_string())

print("\n===== how an expense bill and its payment were posted in the official books")
lines = load("journal_lines")
for source_type in ["EXPENSE", "EXPENSE_PAYMENT", "BILL_PAYMENT", "VENDOR_PAYMENT"]:
    sample = entries[entries.source_type == source_type].head(2)
    for _, entry in sample.iterrows():
        print(f"\n-- {entry.entry_id} {entry.source_type} {entry.source_id} {entry.description} "
              f"status={entry.status} debit={entry.total_debit}")
        print(lines[lines.entry_id == entry.entry_id][
            ["line_no", "account_code", "debit", "credit", "cost_center_department_id",
             "line_description"]].to_string(index=False))