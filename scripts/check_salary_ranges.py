import pandas as pd

df = pd.read_csv("csv/salary_structures.csv", parse_dates=["effective_from", "effective_to"])
df = df.sort_values(["employee_id", "component_id", "effective_from"])
df["prev_end"] = df.groupby(["employee_id", "component_id"]).effective_to.shift()
nxt = df[df.prev_end.notna()]
overlaps = nxt[nxt.effective_from <= nxt.prev_end]
gaps = nxt[nxt.effective_from > nxt.prev_end + pd.Timedelta(days=1)]
print(f"overlaps: {len(overlaps)}, gaps: {len(gaps)}")