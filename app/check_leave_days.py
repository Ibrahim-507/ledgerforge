import pandas as pd
from app.leave_days import count_leave_days

LONG_LEAVE = "ML"
holidays = set(pd.to_datetime(pd.read_csv("csv/holidays.csv").holiday_date).dt.date)
req = pd.read_csv("csv/leave_requests.csv", parse_dates=["start_date", "end_date"])
req["mine"] = [
    count_leave_days(s.date(), e.date(), holidays, skip_holidays=(str(code).strip() != LONG_LEAVE))
    for s, e, code in zip(req.start_date, req.end_date, req.leave_type_code)
]

bad = req[req.mine != req.days]
print("requests:", len(req), " mismatches:", len(bad))
print(bad[["leave_request_id", "leave_type_code", "start_date", "end_date", "days", "mine", "status"]].head(10).to_string())
