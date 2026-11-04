"""Prints (and saves to docs/role_table.md) which role may use each route of YOUR real app, and flags routes with no rule.
Run:  python -m scripts.print_role_table"""
from fastapi.routing import APIRoute
from app.main import app
from app.permissions import role_table_markdown

routes = [(m, r.path) for r in app.routes if isinstance(r, APIRoute) for m in sorted(r.methods - {"HEAD", "OPTIONS"})]
table = role_table_markdown(routes)
print(table)
open("docs/role_table.md", "w", encoding="utf-8").write(table + "\n")
missing = table.count("NO RULE") // 3
print(f"\n{len(routes)} routes; {missing} without a rule (denied by default until you add them to app/permissions.py RULES)")
