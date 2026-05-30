# """
# Expense Tracker — Bootstrap Frontend
# Mounts directly onto your existing FastAPI app (main.py / app).

# HOW TO USE:
#     In your main.py, at the bottom, add:
#         from frontend import mount_frontend
#         mount_frontend(app)
#     Then run: uvicorn main:app --reload --port 8000

# Auth flow (no popups, no Gradio):
#     /app          → dashboard (requires cookie)
#     /app/login    → login page  (redirects to OAuth)
#     /app/callback → exchanges code, sets cookie, redirects to /app
# """

# from fastapi import Request, Cookie
# from fastapi.responses import HTMLResponse, RedirectResponse
# import httpx, json, os, secrets, base64, hashlib, urllib.parse
# from fastapi import Form  # add this import at the top

# SELF_URL     = os.getenv("SELF_URL", "http://localhost:8001")
# REDIRECT_URI = f"{SELF_URL}/app/callback"
# API_BASE     = SELF_URL   # same server

# # ── PKCE ──────────────────────────────────────────────────────────────────────
# def _pkce():
#     v = secrets.token_urlsafe(64)
#     c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
#     return v, c

# # ── Token cache (in-memory; swap for Redis/DB in prod) ────────────────────────
# _VERIFIERS: dict[str, dict] = {}   # state → {verifier, client_id}

# # ── HTML shell ────────────────────────────────────────────────────────────────
# def _page(title: str, body: str, extra_head: str = "") -> HTMLResponse:
#     html = f"""<!DOCTYPE html>
# <html lang="en">
# <head>
# <meta charset="UTF-8">
# <meta name="viewport" content="width=device-width, initial-scale=1">
# <title>{title} · Expense Tracker</title>
# <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
# <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
# <link rel="preconnect" href="https://fonts.googleapis.com">
# <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
# {extra_head}
# <style>
# :root {{
#   --accent: #6366f1;
#   --accent-soft: #eef2ff;
#   --surface: #f8f9fb;
#   --border: #e5e7eb;
#   --text: #111827;
#   --muted: #6b7280;
#   --danger: #ef4444;
#   --success: #22c55e;
# }}
# *, *::before, *::after {{ box-sizing: border-box; }}
# body {{
#   font-family: 'DM Sans', sans-serif;
#   background: var(--surface);
#   color: var(--text);
#   min-height: 100vh;
# }}
# .navbar {{
#   background: #fff !important;
#   border-bottom: 1px solid var(--border);
#   padding: 0 1.5rem;
#   height: 58px;
# }}
# .navbar-brand {{
#   font-weight: 600;
#   font-size: 1.05rem;
#   color: var(--text) !important;
#   gap: 8px;
# }}
# .nav-link {{
#   color: var(--muted) !important;
#   font-size: 0.9rem;
#   font-weight: 500;
#   padding: 0.35rem 0.75rem !important;
#   border-radius: 6px;
#   transition: background 0.15s, color 0.15s;
# }}
# .nav-link:hover, .nav-link.active {{
#   background: var(--accent-soft);
#   color: var(--accent) !important;
# }}
# .nav-link .bi {{ margin-right: 5px; }}
# .card {{
#   border: 1px solid var(--border);
#   border-radius: 12px;
#   box-shadow: none;
#   background: #fff;
# }}
# .metric-card {{
#   border: 1px solid var(--border);
#   border-radius: 12px;
#   background: #fff;
#   padding: 1.25rem 1.5rem;
# }}
# .metric-card .val {{
#   font-size: 1.75rem;
#   font-weight: 600;
#   color: var(--text);
#   font-family: 'DM Mono', monospace;
#   letter-spacing: -1px;
# }}
# .metric-card .lbl {{
#   font-size: 0.78rem;
#   color: var(--muted);
#   text-transform: uppercase;
#   letter-spacing: 0.6px;
#   margin-top: 2px;
# }}
# .metric-card .icon-wrap {{
#   width: 40px; height: 40px;
#   border-radius: 10px;
#   display: flex; align-items: center; justify-content: center;
#   font-size: 1.1rem;
# }}
# .btn-accent {{
#   background: var(--accent);
#   color: #fff;
#   border: none;
#   border-radius: 8px;
#   font-weight: 500;
#   font-size: 0.9rem;
#   padding: 0.45rem 1rem;
#   transition: opacity 0.15s;
# }}
# .btn-accent:hover {{ opacity: 0.88; color: #fff; }}
# .btn-outline-accent {{
#   border: 1.5px solid var(--accent);
#   color: var(--accent);
#   background: transparent;
#   border-radius: 8px;
#   font-weight: 500;
#   font-size: 0.9rem;
#   padding: 0.45rem 1rem;
#   transition: background 0.15s, color 0.15s;
# }}
# .btn-outline-accent:hover {{
#   background: var(--accent-soft);
#   color: var(--accent);
# }}
# .form-control, .form-select {{
#   border: 1.5px solid var(--border);
#   border-radius: 8px;
#   font-size: 0.9rem;
#   padding: 0.5rem 0.85rem;
#   background: #fff;
#   color: var(--text);
#   transition: border-color 0.15s;
# }}
# .form-control:focus, .form-select:focus {{
#   border-color: var(--accent);
#   box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
# }}
# .form-label {{
#   font-size: 0.8rem;
#   font-weight: 600;
#   color: var(--muted);
#   text-transform: uppercase;
#   letter-spacing: 0.5px;
#   margin-bottom: 5px;
# }}
# .table {{ font-size: 0.875rem; }}
# .table thead th {{
#   font-size: 0.72rem;
#   text-transform: uppercase;
#   letter-spacing: 0.6px;
#   color: var(--muted);
#   border-bottom: 1px solid var(--border);
#   background: var(--surface);
#   font-weight: 600;
#   padding: 0.6rem 1rem;
# }}
# .table td {{ padding: 0.7rem 1rem; vertical-align: middle; border-color: var(--border); }}
# .table tbody tr:hover {{ background: var(--surface); }}
# .badge-cat {{
#   font-size: 0.72rem;
#   font-weight: 500;
#   padding: 3px 9px;
#   border-radius: 20px;
#   background: var(--accent-soft);
#   color: var(--accent);
# }}
# .badge-pay {{
#   font-size: 0.72rem;
#   font-weight: 500;
#   padding: 3px 9px;
#   border-radius: 20px;
#   background: #f0fdf4;
#   color: #15803d;
# }}
# .page-content {{ padding: 1.75rem 1.5rem; max-width: 1200px; margin: 0 auto; }}
# .section-title {{
#   font-size: 1rem;
#   font-weight: 600;
#   color: var(--text);
#   margin-bottom: 1rem;
# }}
# .tab-btn {{
#   border: none;
#   background: none;
#   color: var(--muted);
#   font-weight: 500;
#   font-size: 0.9rem;
#   padding: 0.5rem 1rem;
#   border-bottom: 2px solid transparent;
#   cursor: pointer;
#   transition: color 0.15s, border-color 0.15s;
# }}
# .tab-btn.active {{
#   color: var(--accent);
#   border-bottom-color: var(--accent);
# }}
# .tab-pane {{ display: none; }}
# .tab-pane.active {{ display: block; }}
# .alert-success-custom {{
#   background: #f0fdf4; color: #15803d;
#   border: 1px solid #bbf7d0;
#   border-radius: 8px;
#   padding: 0.6rem 1rem;
#   font-size: 0.875rem;
# }}
# .alert-danger-custom {{
#   background: #fef2f2; color: #b91c1c;
#   border: 1px solid #fecaca;
#   border-radius: 8px;
#   padding: 0.6rem 1rem;
#   font-size: 0.875rem;
# }}
# /* Bar chart */
# .bar-chart {{ display: flex; flex-direction: column; gap: 8px; }}
# .bar-row {{ display: flex; align-items: center; gap: 10px; font-size: 0.8rem; }}
# .bar-label {{ width: 100px; color: var(--muted); text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
# .bar-track {{ flex: 1; background: var(--accent-soft); border-radius: 4px; height: 20px; }}
# .bar-fill {{ height: 100%; border-radius: 4px; background: var(--accent); transition: width 0.5s ease; }}
# .bar-val {{ width: 70px; font-family: 'DM Mono', monospace; font-size: 0.78rem; color: var(--text); }}
# </style>
# </head>
# <body>
# {body}
# <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
# </body>
# </html>"""
#     return HTMLResponse(html)


# # ── Navbar ─────────────────────────────────────────────────────────────────────
# def _navbar(user_name: str = "") -> str:
#     return f"""
# <nav class="navbar navbar-expand-lg d-flex align-items-center">
#   <a class="navbar-brand d-flex align-items-center gap-2" href="/app">
#     <span style="font-size:1.3rem">💸</span> Expense Tracker
#   </a>
#   <div class="ms-auto d-flex align-items-center gap-1">
#     <a href="/app"          class="nav-link"><i class="bi bi-grid-1x2"></i>Dashboard</a>
#     <a href="/app/expenses" class="nav-link"><i class="bi bi-list-ul"></i>Expenses</a>
#     <a href="/app/add"      class="nav-link"><i class="bi bi-plus-circle"></i>Add</a>
#     <a href="/app/profile"  class="nav-link"><i class="bi bi-person"></i>Profile</a>
#     <span class="ms-3 me-1" style="font-size:0.82rem;color:var(--muted)">
#       <i class="bi bi-person-circle"></i> {user_name}
#     </span>
#     <a href="/app/logout" class="btn btn-sm" style="border:1.5px solid var(--border);border-radius:8px;font-size:0.82rem;color:var(--muted);padding:0.3rem 0.7rem">
#       <i class="bi bi-box-arrow-right"></i> Sign out
#     </a>
#   </div>
# </nav>"""


# # ── Helper: call MCP tool via internal POST ───────────────────────────────────
# async def _mcp(token: str, tool: str, arguments: dict) -> dict | None:
#     async with httpx.AsyncClient() as client:
#         r = await client.post(
#             f"{API_BASE}/",
#             headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
#             json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
#                   "params": {"name": tool, "arguments": arguments}},
#             timeout=10,
#         )
#     if not r.is_success:
#         return None
#     data = r.json()
#     if "error" in data:
#         return None
#     try:
#         return json.loads(data["result"]["content"][0]["text"])
#     except Exception:
#         return None


# # ── Register OAuth client once ────────────────────────────────────────────────
# _CLIENT_ID: str | None = None

# async def _get_client_id() -> str:
#     global _CLIENT_ID
#     if _CLIENT_ID:
#         return _CLIENT_ID
#     async with httpx.AsyncClient() as client:
#         r = await client.post(f"{API_BASE}/register",
#                               json={"redirect_uris": [REDIRECT_URI]})
#         _CLIENT_ID = r.json()["client_id"]
#     return _CLIENT_ID


# # ── Bar chart HTML helper ─────────────────────────────────────────────────────
# def _bar_chart(data: dict, prefix: str = "₹") -> str:
#     if not data:
#         return '<p class="text-muted small">No data yet.</p>'
#     mx = max(data.values()) or 1
#     rows = ""
#     for k, v in sorted(data.items(), key=lambda x: -x[1]):
#     	pct = v / mx * 100
#     	rows += f"""
#       <div class="bar-row">
#         <div class="bar-label" title="{k}">{k}</div>
#         <div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>
#         <div class="bar-val">{prefix}{v:,.0f}</div>
#       </div>"""
#     return f'<div class="bar-chart">{rows}</div>'


# # ══════════════════════════════════════════════════════════════════════════════
# # ROUTES
# # ══════════════════════════════════════════════════════════════════════════════

# def mount_frontend(app):
#     """Call this in your main.py: from frontend import mount_frontend; mount_frontend(app)"""

#     # ── /app/login ────────────────────────────────────────────────────────────
#     @app.get("/app/login")
#     async def app_login(request: Request):
#         client_id        = await _get_client_id()
#         verifier, challenge = _pkce()
#         state            = secrets.token_urlsafe(16)
#         _VERIFIERS[state] = {"verifier": verifier, "client_id": client_id}

#         auth_url = (
#             f"{API_BASE}/oauth/authorize"
#             f"?client_id={urllib.parse.quote(client_id)}"
#             f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
#             f"&response_type=code"
#             f"&code_challenge={urllib.parse.quote(challenge)}"
#             f"&code_challenge_method=S256"
#             f"&scope=mcp"
#             f"&state={urllib.parse.quote(state)}"
#         )
#         return RedirectResponse(auth_url, status_code=302)

#     # ── /app/callback ─────────────────────────────────────────────────────────
#     @app.get("/app/callback")
#     async def app_callback(request: Request, code: str = "", state: str = "", error: str = ""):
#         if error or not code:
#             return RedirectResponse("/app/login", status_code=302)

#         stored = _VERIFIERS.pop(state, None)
#         if not stored:
#             return _page("Error", '<div class="page-content"><div class="alert-danger-custom">Invalid state. <a href="/app/login">Try again</a>.</div></div>')

#         async with httpx.AsyncClient() as client:
#             r = await client.post(f"{API_BASE}/oauth/token", data={
#                 "grant_type":    "authorization_code",
#                 "code":          code,
#                 "redirect_uri":  REDIRECT_URI,
#                 "client_id":     stored["client_id"],
#                 "code_verifier": stored["verifier"],
#             })

#         token = r.json().get("access_token") if r.is_success else None
#         if not token:
#             return _page("Error", '<div class="page-content"><div class="alert-danger-custom">Token exchange failed. <a href="/app/login">Try again</a>.</div></div>')

#         resp = RedirectResponse("/app", status_code=302)
#         resp.set_cookie("exp_token", token, httponly=True, samesite="lax", max_age=86400)
#         return resp

#     # ── /app/logout ───────────────────────────────────────────────────────────
#     @app.get("/app/logout")
#     async def app_logout():
#         resp = RedirectResponse("/app/login", status_code=302)
#         resp.delete_cookie("exp_token")
#         return resp

#     # ── helper: get token from cookie or redirect ─────────────────────────────
#     def _tok(exp_token: str | None) -> str | None:
#         return exp_token if exp_token else None

#     # ── /app — Dashboard ──────────────────────────────────────────────────────
#     @app.get("/app")
#     async def app_dashboard(request: Request, exp_token: str | None = Cookie(default=None)):
#         token = _tok(exp_token)
#         if not token:
#             return RedirectResponse("/app/login", status_code=302)

#         summary = await _mcp(token, "get_summary",  {}) or {}
#         profile = await _mcp(token, "get_profile",  {}) or {}

#         total   = summary.get("total", 0)
#         count   = summary.get("count", 0)
#         by_cat  = summary.get("by_category", {})
#         by_pay  = summary.get("by_payment_method", {})
#         top_cat = max(by_cat.items(), key=lambda x: x[1], default=("—", 0))
#         avg     = (total / count) if count else 0
#         uname   = profile.get("nickname") or profile.get("name") or "User"

#         cat_chart = _bar_chart(by_cat)
#         pay_chart = _bar_chart(by_pay)

#         body = f"""
# {_navbar(uname)}
# <div class="page-content">
#   <div class="d-flex align-items-center justify-content-between mb-4">
#     <div>
#       <h5 class="mb-0 fw-semibold">Dashboard</h5>
#       <p class="mb-0 text-muted" style="font-size:0.82rem">Welcome back, {uname} 👋</p>
#     </div>
#     <a href="/app/add" class="btn-accent"><i class="bi bi-plus-lg me-1"></i>Add Expense</a>
#   </div>

#   <!-- Metrics -->
#   <div class="row g-3 mb-4">
#     <div class="col-sm-6 col-lg-3">
#       <div class="metric-card d-flex align-items-center gap-3">
#         <div class="icon-wrap" style="background:#eef2ff;color:#6366f1"><i class="bi bi-currency-rupee"></i></div>
#         <div><div class="val">₹{total:,.0f}</div><div class="lbl">Total Spent</div></div>
#       </div>
#     </div>
#     <div class="col-sm-6 col-lg-3">
#       <div class="metric-card d-flex align-items-center gap-3">
#         <div class="icon-wrap" style="background:#f0fdf4;color:#16a34a"><i class="bi bi-receipt"></i></div>
#         <div><div class="val">{count}</div><div class="lbl">Transactions</div></div>
#       </div>
#     </div>
#     <div class="col-sm-6 col-lg-3">
#       <div class="metric-card d-flex align-items-center gap-3">
#         <div class="icon-wrap" style="background:#fff7ed;color:#ea580c"><i class="bi bi-tag"></i></div>
#         <div><div class="val">{top_cat[0]}</div><div class="lbl">Top Category</div></div>
#       </div>
#     </div>
#     <div class="col-sm-6 col-lg-3">
#       <div class="metric-card d-flex align-items-center gap-3">
#         <div class="icon-wrap" style="background:#fdf4ff;color:#9333ea"><i class="bi bi-calculator"></i></div>
#         <div><div class="val">₹{avg:,.0f}</div><div class="lbl">Avg per Transaction</div></div>
#       </div>
#     </div>
#   </div>

#   <!-- Charts -->
#   <div class="row g-3">
#     <div class="col-lg-6">
#       <div class="card p-4">
#         <div class="section-title"><i class="bi bi-bar-chart me-2" style="color:var(--accent)"></i>Spend by Category</div>
#         {cat_chart}
#       </div>
#     </div>
#     <div class="col-lg-6">
#       <div class="card p-4">
#         <div class="section-title"><i class="bi bi-credit-card me-2" style="color:#16a34a"></i>Spend by Payment Method</div>
#         {pay_chart}
#       </div>
#     </div>
#   </div>
# </div>"""
#         return _page("Dashboard", body)

#     # ── /app/expenses — List + Edit/Delete ────────────────────────────────────
#     @app.get("/app/expenses")
#     async def app_expenses(
#         request: Request,
#         exp_token: str | None = Cookie(default=None),
#         category: str = "", payment: str = "",
#         month: str = "", year: str = "",
#         msg: str = "",
#     ):
#         token = _tok(exp_token)
#         if not token:
#             return RedirectResponse("/app/login", status_code=302)

#         profile = await _mcp(token, "get_profile", {}) or {}
#         uname   = profile.get("nickname") or profile.get("name") or "User"

#         args = {}
#         if category: args["category"]       = category
#         if payment:  args["payment_method"] = payment
#         if month:    args["month"]           = int(month)
#         if year:     args["year"]            = int(year)

#         data     = await _mcp(token, "list_expenses", args) or {}
#         expenses = data.get("expenses", [])

#         CATEGORIES = ["Food","Transport","Shopping","Health","Utilities","Entertainment","Other"]
#         PAYMENTS   = ["Cash","Credit Card","Debit Card","UPI","Net Banking","Other"]

#         cat_opts = "".join(f'<option value="{c}" {"selected" if c==category else ""}>{c}</option>' for c in CATEGORIES)
#         pay_opts = "".join(f'<option value="{p}" {"selected" if p==payment else ""}>{p}</option>' for p in PAYMENTS)
#         month_opts = "".join(f'<option value="{m}" {"selected" if str(m)==month else ""}>{m:02d}</option>' for m in range(1,13))
#         year_opts  = "".join(f'<option value="{y}" {"selected" if str(y)==year else ""}>{y}</option>' for y in range(2022, 2027))

#         rows = ""
#         for e in expenses:
#             rec = "🔁" if e.get("is_recurring") else ""
#             rows += f"""
#             <tr>
#               <td><span class="text-muted" style="font-family:'DM Mono',monospace;font-size:0.78rem">#{e['id']}</span></td>
#               <td>{e['date']}</td>
#               <td><span class="badge-cat">{e.get('category','')}</span></td>
#               <td style="font-family:'DM Mono',monospace;font-weight:500">₹{e['amount']:,.2f}</td>
#               <td><span class="badge-pay">{e.get('payment_method','')}</span></td>
#               <td style="font-size:0.8rem;color:var(--muted)">{e.get('tags','') or ''}</td>
#               <td style="text-align:center">{rec}</td>
#               <td style="font-size:0.82rem;color:var(--muted)">{e.get('description','') or ''}</td>
#               <td>
#                 <a href="/app/expenses/edit/{e['id']}" class="btn btn-sm btn-outline-accent me-1" style="font-size:0.78rem;padding:2px 8px">
#                   <i class="bi bi-pencil"></i>
#                 </a>
#                 <a href="/app/expenses/delete/{e['id']}" class="btn btn-sm" style="border:1.5px solid #fee2e2;color:#ef4444;font-size:0.78rem;padding:2px 8px;border-radius:7px"
#                    onclick="return confirm('Delete this expense?')">
#                   <i class="bi bi-trash"></i>
#                 </a>
#               </td>
#             </tr>"""

#         if not rows:
#             rows = '<tr><td colspan="9" class="text-center text-muted py-4">No expenses found.</td></tr>'

#         alert = ""
#         if msg == "deleted":
#             alert = '<div class="alert-danger-custom mb-3"><i class="bi bi-check-circle me-1"></i>Expense deleted.</div>'
#         elif msg == "saved":
#             alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Expense updated.</div>'

#         body = f"""
# {_navbar(uname)}
# <div class="page-content">
#   <div class="d-flex align-items-center justify-content-between mb-3">
#     <h5 class="mb-0 fw-semibold">All Expenses</h5>
#     <a href="/app/add" class="btn-accent"><i class="bi bi-plus-lg me-1"></i>Add Expense</a>
#   </div>
#   {alert}
#   <!-- Filters -->
#   <form method="get" action="/app/expenses" class="card p-3 mb-3">
#     <div class="row g-2 align-items-end">
#       <div class="col-sm-3">
#         <label class="form-label">Category</label>
#         <select name="category" class="form-select">
#           <option value="">All</option>{cat_opts}
#         </select>
#       </div>
#       <div class="col-sm-3">
#         <label class="form-label">Payment</label>
#         <select name="payment" class="form-select">
#           <option value="">All</option>{pay_opts}
#         </select>
#       </div>
#       <div class="col-sm-2">
#         <label class="form-label">Month</label>
#         <select name="month" class="form-select">
#           <option value="">All</option>{month_opts}
#         </select>
#       </div>
#       <div class="col-sm-2">
#         <label class="form-label">Year</label>
#         <select name="year" class="form-select">
#           <option value="">All</option>{year_opts}
#         </select>
#       </div>
#       <div class="col-sm-2">
#         <button type="submit" class="btn-accent w-100" style="height:38px">
#           <i class="bi bi-funnel me-1"></i>Filter
#         </button>
#       </div>
#     </div>
#   </form>

#   <!-- Table -->
#   <div class="card" style="overflow:hidden">
#     <div style="overflow-x:auto">
#       <table class="table mb-0">
#         <thead>
#           <tr>
#             <th>ID</th><th>Date</th><th>Category</th><th>Amount</th>
#             <th>Payment</th><th>Tags</th><th>Rec.</th><th>Description</th><th>Actions</th>
#           </tr>
#         </thead>
#         <tbody>{rows}</tbody>
#       </table>
#     </div>
#   </div>
#   <p class="text-muted mt-2" style="font-size:0.8rem">{len(expenses)} record(s)</p>
# </div>"""
#         return _page("Expenses", body)

#     # ── /app/expenses/edit/{id} ───────────────────────────────────────────────
#     @app.get("/app/expenses/edit/{expense_id}")
#     async def app_edit_expense(expense_id: int, request: Request,
#                                exp_token: str | None = Cookie(default=None)):
#         token = _tok(exp_token)
#         if not token: return RedirectResponse("/app/login", status_code=302)

#         profile = await _mcp(token, "get_profile", {}) or {}
#         uname   = profile.get("nickname") or profile.get("name") or "User"
#         e       = await _mcp(token, "get_expense", {"expense_id": expense_id})
#         if not e or "error" in e:
#             return RedirectResponse("/app/expenses", status_code=302)

#         CATEGORIES = ["Food","Transport","Shopping","Health","Utilities","Entertainment","Other"]
#         PAYMENTS   = ["Cash","Credit Card","Debit Card","UPI","Net Banking","Other"]
#         cat_opts = "".join(f'<option {"selected" if c==e.get("category") else ""}>{c}</option>' for c in CATEGORIES)
#         pay_opts = "".join(f'<option {"selected" if p==e.get("payment_method") else ""}>{p}</option>' for p in PAYMENTS)
#         chk      = "checked" if e.get("is_recurring") else ""

#         body = f"""
# {_navbar(uname)}
# <div class="page-content" style="max-width:680px">
#   <div class="d-flex align-items-center gap-2 mb-4">
#     <a href="/app/expenses" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
#     <span class="text-muted">/</span>
#     <h5 class="mb-0 fw-semibold">Edit Expense #{expense_id}</h5>
#   </div>
#   <div class="card p-4">
#     <form method="post" action="/app/expenses/edit/{expense_id}">
#       <div class="row g-3">
#         <div class="col-sm-6">
#           <label class="form-label">Amount (₹)</label>
#           <input class="form-control" type="number" step="0.01" name="amount" value="{e.get('amount','')}" required>
#         </div>
#         <div class="col-sm-6">
#           <label class="form-label">Date</label>
#           <input class="form-control" type="date" name="date" value="{e.get('date','')}" required>
#         </div>
#         <div class="col-sm-6">
#           <label class="form-label">Category</label>
#           <select class="form-select" name="category">{cat_opts}</select>
#         </div>
#         <div class="col-sm-6">
#           <label class="form-label">Payment Method</label>
#           <select class="form-select" name="payment_method">{pay_opts}</select>
#         </div>
#         <div class="col-12">
#           <label class="form-label">Description</label>
#           <input class="form-control" type="text" name="description" value="{e.get('description','') or ''}">
#         </div>
#         <div class="col-sm-8">
#           <label class="form-label">Tags</label>
#           <input class="form-control" type="text" name="tags" value="{e.get('tags','') or ''}">
#         </div>
#         <div class="col-sm-4 d-flex align-items-end pb-1">
#           <div class="form-check">
#             <input class="form-check-input" type="checkbox" name="is_recurring" id="rec" {chk}>
#             <label class="form-check-label" for="rec" style="font-size:0.85rem">Recurring</label>
#           </div>
#         </div>
#         <div class="col-12 d-flex gap-2 mt-2">
#           <button type="submit" class="btn-accent px-4">
#             <i class="bi bi-floppy me-1"></i>Save Changes
#           </button>
#           <a href="/app/expenses" class="btn-outline-accent px-4">Cancel</a>
#         </div>
#       </div>
#     </form>
#   </div>
# </div>"""
#         return _page(f"Edit #{expense_id}", body)

#     @app.post("/app/expenses/edit/{expense_id}")
#     async def app_edit_expense_post(
#         expense_id: int,
#         request: Request,
#         exp_token: str | None = Cookie(default=None),
#         amount: float = Form(0),
#         date: str = Form(""),
#         category: str = Form(""),
#         payment_method: str = Form(""),
#         description: str = Form(""),
#         tags: str = Form(""),
#         is_recurring: str = Form(""),
#     ):
#         token = _tok(exp_token)
#         if not token:
#             return RedirectResponse("/app/login", status_code=302)
#         await _mcp(token, "update_expense", {
#             "expense_id": expense_id, "amount": amount, "date": date,
#             "category": category, "payment_method": payment_method,
#             "description": description or None, "tags": tags or None,
#             "is_recurring": is_recurring == "on",
#         })
#         return RedirectResponse("/app/expenses?msg=saved", status_code=302)

#     # ── /app/expenses/delete/{id} ─────────────────────────────────────────────
#     @app.get("/app/expenses/delete/{expense_id}")
#     async def app_delete_expense(expense_id: int, exp_token: str | None = Cookie(default=None)):
#         token = _tok(exp_token)
#         if not token: return RedirectResponse("/app/login", status_code=302)
#         await _mcp(token, "delete_expense", {"expense_id": expense_id})
#         return RedirectResponse("/app/expenses?msg=deleted", status_code=302)

#     # ── /app/add — Add Expense ─────────────────────────────────────────────────
#     @app.get("/app/add")
#     async def app_add(request: Request, exp_token: str | None = Cookie(default=None), msg: str = ""):
#         token = _tok(exp_token)
#         if not token: return RedirectResponse("/app/login", status_code=302)

#         profile = await _mcp(token, "get_profile", {}) or {}
#         uname   = profile.get("nickname") or profile.get("name") or "User"

#         from datetime import date as _date
#         today = str(_date.today())

#         CATEGORIES = ["Food","Transport","Shopping","Health","Utilities","Entertainment","Other"]
#         PAYMENTS   = ["Cash","Credit Card","Debit Card","UPI","Net Banking","Other"]
#         cat_opts = "".join(f'<option {"selected" if c=="Food" else ""}>{c}</option>' for c in CATEGORIES)
#         pay_opts = "".join(f'<option {"selected" if p=="UPI" else ""}>{p}</option>' for p in PAYMENTS)

#         alert = ""
#         if msg == "added":
#             alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Expense added successfully!</div>'

#         body = f"""
# {_navbar(uname)}
# <div class="page-content" style="max-width:680px">
#   <h5 class="mb-4 fw-semibold">Add Expense</h5>
#   {alert}
#   <div class="card p-4">
#     <form method="post" action="/app/add">
#       <div class="row g-3">
#         <div class="col-sm-6">
#           <label class="form-label">Amount (₹) *</label>
#           <input class="form-control" type="number" step="0.01" name="amount" placeholder="0.00" required autofocus>
#         </div>
#         <div class="col-sm-6">
#           <label class="form-label">Date *</label>
#           <input class="form-control" type="date" name="date" value="{today}" required>
#         </div>
#         <div class="col-sm-6">
#           <label class="form-label">Category *</label>
#           <select class="form-select" name="category">{cat_opts}</select>
#         </div>
#         <div class="col-sm-6">
#           <label class="form-label">Payment Method</label>
#           <select class="form-select" name="payment_method">{pay_opts}</select>
#         </div>
#         <div class="col-12">
#           <label class="form-label">Description</label>
#           <input class="form-control" type="text" name="description" placeholder="What was this for?">
#         </div>
#         <div class="col-sm-8">
#           <label class="form-label">Tags <span style="font-size:0.75rem;color:var(--muted)">(comma-separated)</span></label>
#           <input class="form-control" type="text" name="tags" placeholder="food, work, weekend">
#         </div>
#         <div class="col-sm-4 d-flex align-items-end pb-1">
#           <div class="form-check">
#             <input class="form-check-input" type="checkbox" name="is_recurring" id="rec2">
#             <label class="form-check-label" for="rec2" style="font-size:0.85rem">Recurring expense</label>
#           </div>
#         </div>
#         <div class="col-12 mt-2">
#           <button type="submit" class="btn-accent px-5" style="height:42px;font-size:0.95rem">
#             <i class="bi bi-plus-lg me-1"></i>Add Expense
#           </button>
#         </div>
#       </div>
#     </form>
#   </div>
# </div>"""
#         return _page("Add Expense", body)

#     @app.post("/app/add")
#     async def app_add_post(
#         request: Request,
#         exp_token: str | None = Cookie(default=None),
#         amount: float = Form(0),
#         date: str = Form(""),
#         category: str = Form(""),
#         payment_method: str = Form(""),
#         description: str = Form(""),
#         tags: str = Form(""),
#         is_recurring: str = Form(""),
#     ):
#         token = _tok(exp_token)
#         if not token:
#             return RedirectResponse("/app/login", status_code=302)
#         await _mcp(token, "create_expense", {
#             "amount": amount, "category": category, "date": date,
#             "payment_method": payment_method,
#             "description": description or None,
#             "tags": tags or None,
#             "is_recurring": is_recurring == "on",
#         })
#         return RedirectResponse("/app/add?msg=added", status_code=302)

#     # ── /app/profile ──────────────────────────────────────────────────────────
#     @app.get("/app/profile")
#     async def app_profile(request: Request, exp_token: str | None = Cookie(default=None)):
#         token = _tok(exp_token)
#         if not token: return RedirectResponse("/app/login", status_code=302)

#         profile = await _mcp(token, "get_profile", {}) or {}
#         uname   = profile.get("nickname") or profile.get("name") or "User"
#         summary = await _mcp(token, "get_summary", {}) or {}

#         initials = "".join(w[0].upper() for w in profile.get("name", "U").split()[:2])

#         body = f"""
# {_navbar(uname)}
# <div class="page-content" style="max-width:560px">
#   <h5 class="mb-4 fw-semibold">Profile</h5>
#   <div class="card p-4 mb-3">
#     <div class="d-flex align-items-center gap-3 mb-4">
#       <div style="width:56px;height:56px;border-radius:50%;background:var(--accent-soft);
#                   color:var(--accent);font-size:1.2rem;font-weight:600;
#                   display:flex;align-items:center;justify-content:center">{initials}</div>
#       <div>
#         <div style="font-weight:600;font-size:1rem">{profile.get('name','')}</div>
#         <div style="font-size:0.85rem;color:var(--muted)">{profile.get('email','')}</div>
#       </div>
#     </div>
#     <table style="width:100%;font-size:0.875rem">
#       <tr><td style="color:var(--muted);padding:6px 0;width:140px">Nickname</td>
#           <td style="font-weight:500">{profile.get('nickname') or '—'}</td></tr>
#       <tr><td style="color:var(--muted);padding:6px 0">Phone</td>
#           <td style="font-weight:500">{profile.get('phone') or '—'}</td></tr>
#       <tr><td style="color:var(--muted);padding:6px 0">Total Spent</td>
#           <td style="font-weight:500;font-family:'DM Mono',monospace">₹{summary.get('total',0):,.2f}</td></tr>
#       <tr><td style="color:var(--muted);padding:6px 0">Transactions</td>
#           <td style="font-weight:500">{summary.get('count',0)}</td></tr>
#     </table>
#   </div>
#   <a href="/app/logout" class="btn-outline-accent">
#     <i class="bi bi-box-arrow-right me-1"></i>Sign Out
#   </a>
# </div>"""
#         return _page("Profile", body)

#     # ── /app redirect ─────────────────────────────────────────────────────────
#     @app.get("/app/")
#     async def app_root_slash(exp_token: str | None = Cookie(default=None)):
#         if not exp_token:
#             return RedirectResponse("/app/login", status_code=302)
#         return RedirectResponse("/app", status_code=302)


"""
Expense Tracker — Bootstrap Frontend v3
Adds: Invite Code System, Join Approval Workflow, Privacy Controls,
      Multi-Admin Management, Role Management, Audit Logs.

New routes:
    /app/groups/join                         → enter invite code
    /app/groups/join/{code}                  → preview & submit join request
    /app/groups/{id}/invite                  → admin: view/regenerate invite code
    /app/groups/{id}/requests                → admin: manage join requests
    /app/groups/{id}/roles                   → admin: manage roles
    /app/groups/{id}/audit                   → admin: audit log
"""

from fastapi import Request, Cookie, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx, json, os, secrets, base64, hashlib, urllib.parse
from datetime import date as _date

SELF_URL     = os.getenv("SELF_URL", "http://localhost:8001")
REDIRECT_URI = f"{SELF_URL}/app/callback"
API_BASE     = SELF_URL

# ── PKCE ──────────────────────────────────────────────────────────────────────
def _pkce():
    v = secrets.token_urlsafe(64)
    c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    return v, c

_VERIFIERS: dict[str, dict] = {}

# ── HTML shell ────────────────────────────────────────────────────────────────
def _page(title: str, body: str, extra_head: str = "") -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Expense Tracker</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
{extra_head}
<style>
:root {{
  --accent: #6366f1;
  --accent-soft: #eef2ff;
  --surface: #f8f9fb;
  --border: #e5e7eb;
  --text: #111827;
  --muted: #6b7280;
  --danger: #ef4444;
  --success: #22c55e;
  --warn: #f59e0b;
}}
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  font-family: 'DM Sans', sans-serif;
  background: var(--surface);
  color: var(--text);
  min-height: 100vh;
}}
.navbar {{
  background: #fff !important;
  border-bottom: 1px solid var(--border);
  padding: 0 1.5rem;
  height: 58px;
}}
.navbar-brand {{
  font-weight: 600;
  font-size: 1.05rem;
  color: var(--text) !important;
}}
.nav-link {{
  color: var(--muted) !important;
  font-size: 0.9rem;
  font-weight: 500;
  padding: 0.35rem 0.75rem !important;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}}
.nav-link:hover, .nav-link.active {{
  background: var(--accent-soft);
  color: var(--accent) !important;
}}
.nav-link .bi {{ margin-right: 5px; }}
.card {{
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: none;
  background: #fff;
}}
.metric-card {{
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
  padding: 1.25rem 1.5rem;
}}
.metric-card .val {{
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text);
  font-family: 'DM Mono', monospace;
  letter-spacing: -1px;
}}
.metric-card .lbl {{
  font-size: 0.78rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-top: 2px;
}}
.metric-card .icon-wrap {{
  width: 40px; height: 40px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
}}
.btn-accent {{
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.9rem;
  padding: 0.45rem 1rem;
  transition: opacity 0.15s;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}}
.btn-accent:hover {{ opacity: 0.88; color: #fff; }}
.btn-outline-accent {{
  border: 1.5px solid var(--accent);
  color: var(--accent);
  background: transparent;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.9rem;
  padding: 0.45rem 1rem;
  transition: background 0.15s, color 0.15s;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}}
.btn-outline-accent:hover {{
  background: var(--accent-soft);
  color: var(--accent);
}}
.form-control, .form-select {{
  border: 1.5px solid var(--border);
  border-radius: 8px;
  font-size: 0.9rem;
  padding: 0.5rem 0.85rem;
  background: #fff;
  color: var(--text);
  transition: border-color 0.15s;
}}
.form-control:focus, .form-select:focus {{
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
}}
.form-label {{
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 5px;
}}
.table {{ font-size: 0.875rem; }}
.table thead th {{
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  font-weight: 600;
  padding: 0.6rem 1rem;
}}
.table td {{ padding: 0.7rem 1rem; vertical-align: middle; border-color: var(--border); }}
.table tbody tr:hover {{ background: var(--surface); }}
.badge-cat {{
  font-size: 0.72rem; font-weight: 500; padding: 3px 9px;
  border-radius: 20px; background: var(--accent-soft); color: var(--accent);
}}
.badge-pay {{
  font-size: 0.72rem; font-weight: 500; padding: 3px 9px;
  border-radius: 20px; background: #f0fdf4; color: #15803d;
}}
.badge-type {{
  font-size: 0.72rem; font-weight: 500; padding: 3px 9px;
  border-radius: 20px; background: #fff7ed; color: #c2410c;
}}
.badge-archived {{
  font-size: 0.72rem; font-weight: 500; padding: 3px 9px;
  border-radius: 20px; background: #f3f4f6; color: #6b7280;
}}
.badge-active {{
  font-size: 0.72rem; font-weight: 500; padding: 3px 9px;
  border-radius: 20px; background: #f0fdf4; color: #15803d;
}}
.badge-pending {{
  font-size: 0.72rem; font-weight: 500; padding: 3px 9px;
  border-radius: 20px; background: #fffbeb; color: #92400e;
}}
.badge-owner {{
  font-size: 0.72rem; font-weight: 500; padding: 3px 9px;
  border-radius: 20px; background: #eef2ff; color: #6366f1;
}}
.badge-admin {{
  font-size: 0.72rem; font-weight: 500; padding: 3px 9px;
  border-radius: 20px; background: #fdf4ff; color: #9333ea;
}}
.badge-member {{
  font-size: 0.72rem; font-weight: 500; padding: 3px 9px;
  border-radius: 20px; background: #f8fafc; color: #64748b;
}}
.page-content {{ padding: 1.75rem 1.5rem; max-width: 1200px; margin: 0 auto; }}
.section-title {{
  font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 1rem;
}}
.alert-success-custom {{
  background: #f0fdf4; color: #15803d;
  border: 1px solid #bbf7d0; border-radius: 8px;
  padding: 0.6rem 1rem; font-size: 0.875rem;
}}
.alert-danger-custom {{
  background: #fef2f2; color: #b91c1c;
  border: 1px solid #fecaca; border-radius: 8px;
  padding: 0.6rem 1rem; font-size: 0.875rem;
}}
.alert-warn-custom {{
  background: #fffbeb; color: #92400e;
  border: 1px solid #fde68a; border-radius: 8px;
  padding: 0.6rem 1rem; font-size: 0.875rem;
}}
.balance-positive {{ color: #15803d; font-weight: 600; font-family: 'DM Mono', monospace; }}
.balance-negative {{ color: #b91c1c; font-weight: 600; font-family: 'DM Mono', monospace; }}
.balance-zero     {{ color: var(--muted); font-family: 'DM Mono', monospace; }}
.group-card {{
  border: 1px solid var(--border); border-radius: 12px; background: #fff;
  padding: 1.25rem 1.5rem; transition: box-shadow 0.15s, border-color 0.15s;
  text-decoration: none; color: inherit; display: block;
}}
.group-card:hover {{
  box-shadow: 0 4px 16px rgba(99,102,241,0.08);
  border-color: var(--accent);
  color: inherit;
}}
.debt-row {{
  display: flex; align-items: center; gap: 12px;
  padding: 0.85rem 1rem; border-bottom: 1px solid var(--border);
  font-size: 0.875rem;
}}
.debt-row:last-child {{ border-bottom: none; }}
.debt-arrow {{
  width: 32px; height: 32px; border-radius: 50%;
  background: #fef2f2; color: #ef4444;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.85rem; flex-shrink: 0;
}}
.bar-chart {{ display: flex; flex-direction: column; gap: 8px; }}
.bar-row {{ display: flex; align-items: center; gap: 10px; font-size: 0.8rem; }}
.bar-label {{ width: 100px; color: var(--muted); text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.bar-track {{ flex: 1; background: var(--accent-soft); border-radius: 4px; height: 20px; }}
.bar-fill  {{ height: 100%; border-radius: 4px; background: var(--accent); transition: width 0.5s ease; }}
.bar-val   {{ width: 70px; font-family: 'DM Mono', monospace; font-size: 0.78rem; color: var(--text); }}
#participant-rows .prow {{
  display: flex; gap: 8px; align-items: center; margin-bottom: 6px;
}}
/* invite code display */
.invite-code-box {{
  font-family: 'DM Mono', monospace;
  font-size: 1.6rem;
  font-weight: 600;
  letter-spacing: 6px;
  color: var(--accent);
  background: var(--accent-soft);
  border: 2px dashed var(--accent);
  border-radius: 10px;
  padding: 1rem 2rem;
  text-align: center;
  cursor: pointer;
  transition: background 0.15s;
  user-select: all;
}}
.invite-code-box:hover {{ background: #e0e7ff; }}
/* request status badges */
.badge-req-pending  {{ background: #fffbeb; color: #92400e; font-size: 0.72rem; padding: 3px 9px; border-radius: 20px; font-weight: 500; }}
.badge-req-approved {{ background: #f0fdf4; color: #15803d; font-size: 0.72rem; padding: 3px 9px; border-radius: 20px; font-weight: 500; }}
.badge-req-rejected {{ background: #fef2f2; color: #b91c1c; font-size: 0.72rem; padding: 3px 9px; border-radius: 20px; font-weight: 500; }}
/* audit log */
.audit-row {{
  display: flex; gap: 12px; align-items: flex-start;
  padding: 0.75rem 1rem; border-bottom: 1px solid var(--border);
  font-size: 0.82rem;
}}
.audit-row:last-child {{ border-bottom: none; }}
.audit-dot {{
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent); flex-shrink: 0; margin-top: 5px;
}}
/* admin panel tab strip */
.admin-tabs {{
  display: flex; gap: 2px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 10px;
  padding: 3px; margin-bottom: 1.5rem;
}}
.admin-tab {{
  flex: 1; text-align: center; padding: 0.4rem 0.75rem;
  border-radius: 7px; font-size: 0.82rem; font-weight: 500;
  color: var(--muted); text-decoration: none;
  transition: background 0.15s, color 0.15s;
}}
.admin-tab.active, .admin-tab:hover {{
  background: #fff; color: var(--accent);
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}}
/* join preview card */
.join-preview {{
  border: 2px solid var(--accent);
  border-radius: 14px;
  background: var(--accent-soft);
  padding: 2rem;
  text-align: center;
}}
</style>
</head>
<body>
{body}
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    return HTMLResponse(html)


# ── Navbar ─────────────────────────────────────────────────────────────────────
def _navbar(user_name: str = "") -> str:
    return f"""
<nav class="navbar navbar-expand-lg d-flex align-items-center">
  <a class="navbar-brand d-flex align-items-center gap-2" href="/app">
    <span style="font-size:1.3rem">💸</span> Expense Tracker
  </a>
  <div class="ms-auto d-flex align-items-center gap-1 flex-wrap">
    <a href="/app"          class="nav-link"><i class="bi bi-grid-1x2"></i>Dashboard</a>
    <a href="/app/expenses" class="nav-link"><i class="bi bi-list-ul"></i>Expenses</a>
    <a href="/app/add"      class="nav-link"><i class="bi bi-plus-circle"></i>Add</a>
    <a href="/app/groups"   class="nav-link"><i class="bi bi-people"></i>Groups</a>
    <a href="/app/groups/join" class="nav-link"><i class="bi bi-key"></i>Join</a>
    <a href="/app/profile"  class="nav-link"><i class="bi bi-person"></i>Profile</a>
    <span class="ms-3 me-1" style="font-size:0.82rem;color:var(--muted)">
      <i class="bi bi-person-circle"></i> {user_name}
    </span>
    <a href="/app/logout" class="btn btn-sm"
       style="border:1.5px solid var(--border);border-radius:8px;font-size:0.82rem;color:var(--muted);padding:0.3rem 0.7rem">
      <i class="bi bi-box-arrow-right"></i> Sign out
    </a>
  </div>
</nav>"""


# ── Bar chart helper ──────────────────────────────────────────────────────────
def _bar_chart(data: dict, prefix: str = "₹") -> str:
    if not data:
        return '<p class="text-muted small">No data yet.</p>'
    mx = max(data.values()) or 1
    rows = ""
    for k, v in sorted(data.items(), key=lambda x: -x[1]):
        pct = v / mx * 100
        rows += f"""
      <div class="bar-row">
        <div class="bar-label" title="{k}">{k}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>
        <div class="bar-val">{prefix}{v:,.0f}</div>
      </div>"""
    return f'<div class="bar-chart">{rows}</div>'


# ── MCP helper ────────────────────────────────────────────────────────────────
async def _mcp(token: str, tool: str, arguments: dict) -> dict | None:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{API_BASE}/",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": tool, "arguments": arguments}},
            timeout=15,
        )
    if not r.is_success:
        return None
    data = r.json()
    if "error" in data:
        return None
    try:
        return json.loads(data["result"]["content"][0]["text"])
    except Exception:
        return None


# ── REST helper ───────────────────────────────────────────────────────────────
async def _rest(token: str, method: str, path: str, **kwargs) -> tuple[int, any]:
    """Returns (status_code, parsed_json_or_None)."""
    async with httpx.AsyncClient() as client:
        fn = getattr(client, method.lower())
        r = await fn(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
            **kwargs,
        )
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


# ── Register OAuth client once ────────────────────────────────────────────────
_CLIENT_ID: str | None = None

async def _get_client_id() -> str:
    global _CLIENT_ID
    if _CLIENT_ID:
        return _CLIENT_ID
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_BASE}/register",
                              json={"redirect_uris": [REDIRECT_URI]})
        _CLIENT_ID = r.json()["client_id"]
    return _CLIENT_ID


# ── Balance formatting helper ─────────────────────────────────────────────────
def _fmt_balance(amount: float) -> str:
    if amount > 0.01:
        return f'<span class="balance-positive">+₹{amount:,.2f}</span>'
    elif amount < -0.01:
        return f'<span class="balance-negative">-₹{abs(amount):,.2f}</span>'
    return f'<span class="balance-zero">₹0.00</span>'


# ── Role badge helper ─────────────────────────────────────────────────────────
def _role_badge(role: str) -> str:
    role = (role or "member").lower()
    if role == "owner":
        return '<span class="badge-owner"><i class="bi bi-crown me-1"></i>Owner</span>'
    if role == "admin":
        return '<span class="badge-admin"><i class="bi bi-shield-check me-1"></i>Admin</span>'
    return '<span class="badge-member"><i class="bi bi-person me-1"></i>Member</span>'


# ── Request status badge helper ───────────────────────────────────────────────
def _req_badge(status: str) -> str:
    status = (status or "pending").lower()
    if status == "approved":
        return '<span class="badge-req-approved">✓ Approved</span>'
    if status == "rejected":
        return '<span class="badge-req-rejected">✗ Rejected</span>'
    return '<span class="badge-req-pending">⏳ Pending</span>'


# ── Group type constants ──────────────────────────────────────────────────────
GROUP_TYPE_ICONS = {
    "family": "🏠", "friends": "🎉", "trip": "✈️",
    "office": "💼", "roommates": "🏢", "event": "🎊", "other": "👥",
}
GROUP_TYPES  = ["family", "friends", "trip", "office", "roommates", "event", "other"]
SPLIT_TYPES  = ["equal", "percentage", "fixed", "by_days", "custom"]
EXP_CATEGORIES = ["food", "travel", "hotel", "fuel", "entertainment", "shopping", "miscellaneous"]


# ── Admin section tab strip ───────────────────────────────────────────────────
def _admin_tabs(group_id: int, active: str) -> str:
    tabs = [
        ("overview",  f"/app/groups/{group_id}",          "bi-grid-1x2",      "Overview"),
        ("expenses",  f"/app/groups/{group_id}/expenses",  "bi-list-ul",       "Expenses"),
        ("settle",    f"/app/groups/{group_id}/settle",    "bi-calculator",    "Settle"),
        ("members",   f"/app/groups/{group_id}/members",   "bi-people",        "Members"),
        ("roles",     f"/app/groups/{group_id}/roles",     "bi-shield-lock",   "Roles"),
        ("requests",  f"/app/groups/{group_id}/requests",  "bi-person-check",  "Requests"),
        ("invite",    f"/app/groups/{group_id}/invite",    "bi-key",           "Invite"),
        ("audit",     f"/app/groups/{group_id}/audit",     "bi-clock-history", "Audit"),
    ]
    items = ""
    for key, href, icon, label in tabs:
        cls = "admin-tab active" if key == active else "admin-tab"
        items += f'<a href="{href}" class="{cls}"><i class="bi {icon} me-1"></i>{label}</a>'
    return f'<div class="admin-tabs">{items}</div>'


async def _get_user_names(token: str, user_ids: list[int]) -> dict[int, str]:
    """Returns {user_id: display_name} for a list of user IDs."""
    names = {}
    for uid in user_ids:
        profile = await _mcp(token, "get_profile", {}) or {}
        # get_profile only returns the caller's profile, so use REST /users/{id} if available
        # For now, batch via group summary data which already has names
        names[uid] = f"User {uid}"
    return names


# ══════════════════════════════════════════════════════════════════════════════
def mount_frontend(app):
# ══════════════════════════════════════════════════════════════════════════════

    def _tok(exp_token):
        return exp_token if exp_token else None

    # ── /app/login ────────────────────────────────────────────────────────────
    @app.get("/app/login")
    async def app_login(request: Request):
        client_id           = await _get_client_id()
        verifier, challenge = _pkce()
        state               = secrets.token_urlsafe(16)
        _VERIFIERS[state]   = {"verifier": verifier, "client_id": client_id}
        auth_url = (
            f"{API_BASE}/oauth/authorize"
            f"?client_id={urllib.parse.quote(client_id)}"
            f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
            f"&response_type=code"
            f"&code_challenge={urllib.parse.quote(challenge)}"
            f"&code_challenge_method=S256"
            f"&scope=mcp"
            f"&state={urllib.parse.quote(state)}"
        )
        return RedirectResponse(auth_url, status_code=302)

    # ── /app/callback ─────────────────────────────────────────────────────────
    @app.get("/app/callback")
    async def app_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        if error or not code:
            return RedirectResponse("/app/login", status_code=302)
        stored = _VERIFIERS.pop(state, None)
        if not stored:
            return _page("Error", '<div class="page-content"><div class="alert-danger-custom">Invalid state. <a href="/app/login">Try again</a>.</div></div>')
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{API_BASE}/oauth/token", data={
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  REDIRECT_URI,
                "client_id":     stored["client_id"],
                "code_verifier": stored["verifier"],
            })
        token = r.json().get("access_token") if r.is_success else None
        if not token:
            return _page("Error", '<div class="page-content"><div class="alert-danger-custom">Token exchange failed. <a href="/app/login">Try again</a>.</div></div>')
        resp = RedirectResponse("/app", status_code=302)
        resp.set_cookie("exp_token", token, httponly=True, samesite="lax", max_age=86400)
        return resp

    # ── /app/logout ───────────────────────────────────────────────────────────
    @app.get("/app/logout")
    async def app_logout():
        resp = RedirectResponse("/app/login", status_code=302)
        resp.delete_cookie("exp_token")
        return resp

    # ── /app — Dashboard ──────────────────────────────────────────────────────
    @app.get("/app")
    async def app_dashboard(request: Request, exp_token: str | None = Cookie(default=None)):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        summary = await _mcp(token, "get_summary", {}) or {}
        profile = await _mcp(token, "get_profile", {}) or {}

        total   = summary.get("total", 0)
        count   = summary.get("count", 0)
        by_cat  = summary.get("by_category", {})
        by_pay  = summary.get("by_payment_method", {})
        top_cat = max(by_cat.items(), key=lambda x: x[1], default=("—", 0))
        avg     = (total / count) if count else 0
        uname   = profile.get("nickname") or profile.get("name") or "User"

        body = f"""
{_navbar(uname)}
<div class="page-content">
  <div class="d-flex align-items-center justify-content-between mb-4">
    <div>
      <h5 class="mb-0 fw-semibold">Dashboard</h5>
      <p class="mb-0 text-muted" style="font-size:0.82rem">Welcome back, {uname} 👋</p>
    </div>
    <div class="d-flex gap-2">
      <a href="/app/groups/join"   class="btn-outline-accent"><i class="bi bi-key"></i>Join Group</a>
      <a href="/app/groups/create" class="btn-outline-accent"><i class="bi bi-people"></i>New Group</a>
      <a href="/app/add"           class="btn-accent"><i class="bi bi-plus-lg"></i>Add Expense</a>
    </div>
  </div>
  <div class="row g-3 mb-4">
    <div class="col-sm-6 col-lg-3">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#eef2ff;color:#6366f1"><i class="bi bi-currency-rupee"></i></div>
        <div><div class="val">₹{total:,.0f}</div><div class="lbl">Total Spent</div></div>
      </div>
    </div>
    <div class="col-sm-6 col-lg-3">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#f0fdf4;color:#16a34a"><i class="bi bi-receipt"></i></div>
        <div><div class="val">{count}</div><div class="lbl">Transactions</div></div>
      </div>
    </div>
    <div class="col-sm-6 col-lg-3">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#fff7ed;color:#ea580c"><i class="bi bi-tag"></i></div>
        <div><div class="val">{top_cat[0]}</div><div class="lbl">Top Category</div></div>
      </div>
    </div>
    <div class="col-sm-6 col-lg-3">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#fdf4ff;color:#9333ea"><i class="bi bi-calculator"></i></div>
        <div><div class="val">₹{avg:,.0f}</div><div class="lbl">Avg / Transaction</div></div>
      </div>
    </div>
  </div>
  <div class="row g-3">
    <div class="col-lg-6">
      <div class="card p-4">
        <div class="section-title"><i class="bi bi-bar-chart me-2" style="color:var(--accent)"></i>Spend by Category</div>
        {_bar_chart(by_cat)}
      </div>
    </div>
    <div class="col-lg-6">
      <div class="card p-4">
        <div class="section-title"><i class="bi bi-credit-card me-2" style="color:#16a34a"></i>Spend by Payment Method</div>
        {_bar_chart(by_pay)}
      </div>
    </div>
  </div>
</div>"""
        return _page("Dashboard", body)

    # ── /app/expenses ─────────────────────────────────────────────────────────
    @app.get("/app/expenses")
    async def app_expenses(
        request: Request, exp_token: str | None = Cookie(default=None),
        category: str = "", payment: str = "",
        month: str = "", year: str = "", msg: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile  = await _mcp(token, "get_profile", {}) or {}
        uname    = profile.get("nickname") or profile.get("name") or "User"
        args     = {}
        if category: args["category"]       = category
        if payment:  args["payment_method"] = payment
        if month:    args["month"]           = int(month)
        if year:     args["year"]            = int(year)

        data     = await _mcp(token, "list_expenses", args) or {}
        expenses = data.get("expenses", [])

        CATEGORIES = ["Food","Transport","Shopping","Health","Utilities","Entertainment","Other"]
        PAYMENTS   = ["Cash","Credit Card","Debit Card","UPI","Net Banking","Other"]
        cat_opts   = "".join(f'<option value="{c}" {"selected" if c==category else ""}>{c}</option>' for c in CATEGORIES)
        pay_opts   = "".join(f'<option value="{p}" {"selected" if p==payment else ""}>{p}</option>' for p in PAYMENTS)
        month_opts = "".join(f'<option value="{m}" {"selected" if str(m)==month else ""}>{m:02d}</option>' for m in range(1,13))
        year_opts  = "".join(f'<option value="{y}" {"selected" if str(y)==year else ""}>{y}</option>' for y in range(2022,2027))

        rows = ""
        for e in expenses:
            rec = "🔁" if e.get("is_recurring") else ""
            rows += f"""
            <tr>
              <td><span class="text-muted" style="font-family:'DM Mono',monospace;font-size:0.78rem">#{e['id']}</span></td>
              <td>{e['date']}</td>
              <td><span class="badge-cat">{e.get('category','')}</span></td>
              <td style="font-family:'DM Mono',monospace;font-weight:500">₹{e['amount']:,.2f}</td>
              <td><span class="badge-pay">{e.get('payment_method','')}</span></td>
              <td style="font-size:0.8rem;color:var(--muted)">{e.get('tags','') or ''}</td>
              <td style="text-align:center">{rec}</td>
              <td style="font-size:0.82rem;color:var(--muted)">{e.get('description','') or ''}</td>
              <td>
                <a href="/app/expenses/edit/{e['id']}" class="btn btn-sm btn-outline-accent me-1" style="font-size:0.78rem;padding:2px 8px">
                  <i class="bi bi-pencil"></i>
                </a>
                <a href="/app/expenses/delete/{e['id']}"
                   class="btn btn-sm" style="border:1.5px solid #fee2e2;color:#ef4444;font-size:0.78rem;padding:2px 8px;border-radius:7px"
                   onclick="return confirm('Delete this expense?')">
                  <i class="bi bi-trash"></i>
                </a>
              </td>
            </tr>"""
        if not rows:
            rows = '<tr><td colspan="9" class="text-center text-muted py-4">No expenses found.</td></tr>'

        alert = ""
        if msg == "deleted":
            alert = '<div class="alert-danger-custom mb-3"><i class="bi bi-check-circle me-1"></i>Expense deleted.</div>'
        elif msg == "saved":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Expense updated.</div>'

        body = f"""
{_navbar(uname)}
<div class="page-content">
  <div class="d-flex align-items-center justify-content-between mb-3">
    <h5 class="mb-0 fw-semibold">All Expenses</h5>
    <a href="/app/add" class="btn-accent"><i class="bi bi-plus-lg"></i>Add Expense</a>
  </div>
  {alert}
  <form method="get" action="/app/expenses" class="card p-3 mb-3">
    <div class="row g-2 align-items-end">
      <div class="col-sm-3">
        <label class="form-label">Category</label>
        <select name="category" class="form-select"><option value="">All</option>{cat_opts}</select>
      </div>
      <div class="col-sm-3">
        <label class="form-label">Payment</label>
        <select name="payment" class="form-select"><option value="">All</option>{pay_opts}</select>
      </div>
      <div class="col-sm-2">
        <label class="form-label">Month</label>
        <select name="month" class="form-select"><option value="">All</option>{month_opts}</select>
      </div>
      <div class="col-sm-2">
        <label class="form-label">Year</label>
        <select name="year" class="form-select"><option value="">All</option>{year_opts}</select>
      </div>
      <div class="col-sm-2">
        <button type="submit" class="btn-accent w-100" style="height:38px"><i class="bi bi-funnel me-1"></i>Filter</button>
      </div>
    </div>
  </form>
  <div class="card" style="overflow:hidden">
    <div style="overflow-x:auto">
      <table class="table mb-0">
        <thead>
          <tr><th>ID</th><th>Date</th><th>Category</th><th>Amount</th>
          <th>Payment</th><th>Tags</th><th>Rec.</th><th>Description</th><th>Actions</th></tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>
  <p class="text-muted mt-2" style="font-size:0.8rem">{len(expenses)} record(s)</p>
</div>"""
        return _page("Expenses", body)

    # ── /app/expenses/edit/{id} ───────────────────────────────────────────────
    @app.get("/app/expenses/edit/{expense_id}")
    async def app_edit_expense(expense_id: int, request: Request,
                               exp_token: str | None = Cookie(default=None)):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"
        e       = await _mcp(token, "get_expense", {"expense_id": expense_id})
        if not e or "error" in e:
            return RedirectResponse("/app/expenses", status_code=302)

        CATEGORIES = ["Food","Transport","Shopping","Health","Utilities","Entertainment","Other"]
        PAYMENTS   = ["Cash","Credit Card","Debit Card","UPI","Net Banking","Other"]
        cat_opts   = "".join(f'<option {"selected" if c==e.get("category") else ""}>{c}</option>' for c in CATEGORIES)
        pay_opts   = "".join(f'<option {"selected" if p==e.get("payment_method") else ""}>{p}</option>' for p in PAYMENTS)
        chk        = "checked" if e.get("is_recurring") else ""

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:680px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/expenses" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">Edit Expense #{expense_id}</h5>
  </div>
  <div class="card p-4">
    <form method="post" action="/app/expenses/edit/{expense_id}">
      <div class="row g-3">
        <div class="col-sm-6">
          <label class="form-label">Amount (₹)</label>
          <input class="form-control" type="number" step="0.01" name="amount" value="{e.get('amount','')}" required>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Date</label>
          <input class="form-control" type="date" name="date" value="{e.get('date','')}" required>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Category</label>
          <select class="form-select" name="category">{cat_opts}</select>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Payment Method</label>
          <select class="form-select" name="payment_method">{pay_opts}</select>
        </div>
        <div class="col-12">
          <label class="form-label">Description</label>
          <input class="form-control" type="text" name="description" value="{e.get('description','') or ''}">
        </div>
        <div class="col-sm-8">
          <label class="form-label">Tags</label>
          <input class="form-control" type="text" name="tags" value="{e.get('tags','') or ''}">
        </div>
        <div class="col-sm-4 d-flex align-items-end pb-1">
          <div class="form-check">
            <input class="form-check-input" type="checkbox" name="is_recurring" id="rec" {chk}>
            <label class="form-check-label" for="rec" style="font-size:0.85rem">Recurring</label>
          </div>
        </div>
        <div class="col-12 d-flex gap-2 mt-2">
          <button type="submit" class="btn-accent px-4"><i class="bi bi-floppy me-1"></i>Save Changes</button>
          <a href="/app/expenses" class="btn-outline-accent px-4">Cancel</a>
        </div>
      </div>
    </form>
  </div>
</div>"""
        return _page(f"Edit #{expense_id}", body)

    @app.post("/app/expenses/edit/{expense_id}")
    async def app_edit_expense_post(
        expense_id: int, request: Request, exp_token: str | None = Cookie(default=None),
        amount: float = Form(0), date: str = Form(""), category: str = Form(""),
        payment_method: str = Form(""), description: str = Form(""),
        tags: str = Form(""), is_recurring: str = Form(""),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "update_expense", {
            "expense_id": expense_id, "amount": amount, "date": date,
            "category": category, "payment_method": payment_method,
            "description": description or None, "tags": tags or None,
            "is_recurring": is_recurring == "on",
        })
        return RedirectResponse("/app/expenses?msg=saved", status_code=302)

    @app.get("/app/expenses/delete/{expense_id}")
    async def app_delete_expense(expense_id: int, exp_token: str | None = Cookie(default=None)):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "delete_expense", {"expense_id": expense_id})
        return RedirectResponse("/app/expenses?msg=deleted", status_code=302)

    # ── /app/add ──────────────────────────────────────────────────────────────
    @app.get("/app/add")
    async def app_add(request: Request, exp_token: str | None = Cookie(default=None), msg: str = ""):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        profile    = await _mcp(token, "get_profile", {}) or {}
        uname      = profile.get("nickname") or profile.get("name") or "User"
        today      = str(_date.today())
        CATEGORIES = ["Food","Transport","Shopping","Health","Utilities","Entertainment","Other"]
        PAYMENTS   = ["Cash","Credit Card","Debit Card","UPI","Net Banking","Other"]
        cat_opts   = "".join(f'<option {"selected" if c=="Food" else ""}>{c}</option>' for c in CATEGORIES)
        pay_opts   = "".join(f'<option {"selected" if p=="UPI" else ""}>{p}</option>' for p in PAYMENTS)
        alert      = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Expense added!</div>' if msg == "added" else ""

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:680px">
  <h5 class="mb-4 fw-semibold">Add Expense</h5>
  {alert}
  <div class="card p-4">
    <form method="post" action="/app/add">
      <div class="row g-3">
        <div class="col-sm-6">
          <label class="form-label">Amount (₹) *</label>
          <input class="form-control" type="number" step="0.01" name="amount" placeholder="0.00" required autofocus>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Date *</label>
          <input class="form-control" type="date" name="date" value="{today}" required>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Category *</label>
          <select class="form-select" name="category">{cat_opts}</select>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Payment Method</label>
          <select class="form-select" name="payment_method">{pay_opts}</select>
        </div>
        <div class="col-12">
          <label class="form-label">Description</label>
          <input class="form-control" type="text" name="description" placeholder="What was this for?">
        </div>
        <div class="col-sm-8">
          <label class="form-label">Tags <span style="font-size:0.75rem;color:var(--muted)">(comma-separated)</span></label>
          <input class="form-control" type="text" name="tags" placeholder="food, work, weekend">
        </div>
        <div class="col-sm-4 d-flex align-items-end pb-1">
          <div class="form-check">
            <input class="form-check-input" type="checkbox" name="is_recurring" id="rec2">
            <label class="form-check-label" for="rec2" style="font-size:0.85rem">Recurring</label>
          </div>
        </div>
        <div class="col-12 mt-2">
          <button type="submit" class="btn-accent px-5" style="height:42px;font-size:0.95rem">
            <i class="bi bi-plus-lg me-1"></i>Add Expense
          </button>
        </div>
      </div>
    </form>
  </div>
</div>"""
        return _page("Add Expense", body)

    @app.post("/app/add")
    async def app_add_post(
        request: Request, exp_token: str | None = Cookie(default=None),
        amount: float = Form(0), date: str = Form(""), category: str = Form(""),
        payment_method: str = Form(""), description: str = Form(""),
        tags: str = Form(""), is_recurring: str = Form(""),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "create_expense", {
            "amount": amount, "category": category, "date": date,
            "payment_method": payment_method,
            "description": description or None,
            "tags": tags or None,
            "is_recurring": is_recurring == "on",
        })
        return RedirectResponse("/app/add?msg=added", status_code=302)

    # ── /app/profile ──────────────────────────────────────────────────────────
    @app.get("/app/profile")
    async def app_profile(request: Request, exp_token: str | None = Cookie(default=None)):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        profile  = await _mcp(token, "get_profile", {}) or {}
        uname    = profile.get("nickname") or profile.get("name") or "User"
        summary  = await _mcp(token, "get_summary", {}) or {}
        initials = "".join(w[0].upper() for w in profile.get("name", "U").split()[:2])

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:560px">
  <h5 class="mb-4 fw-semibold">Profile</h5>
  <div class="card p-4 mb-3">
    <div class="d-flex align-items-center gap-3 mb-4">
      <div style="width:56px;height:56px;border-radius:50%;background:var(--accent-soft);
                  color:var(--accent);font-size:1.2rem;font-weight:600;
                  display:flex;align-items:center;justify-content:center">{initials}</div>
      <div>
        <div style="font-weight:600;font-size:1rem">{profile.get('name','')}</div>
        <div style="font-size:0.85rem;color:var(--muted)">{profile.get('email','')}</div>
      </div>
    </div>
    <table style="width:100%;font-size:0.875rem">
      <tr><td style="color:var(--muted);padding:6px 0;width:140px">Nickname</td>
          <td style="font-weight:500">{profile.get('nickname') or '—'}</td></tr>
      <tr><td style="color:var(--muted);padding:6px 0">Phone</td>
          <td style="font-weight:500">{profile.get('phone') or '—'}</td></tr>
      <tr><td style="color:var(--muted);padding:6px 0">Total Spent</td>
          <td style="font-weight:500;font-family:'DM Mono',monospace">₹{summary.get('total',0):,.2f}</td></tr>
      <tr><td style="color:var(--muted);padding:6px 0">Transactions</td>
          <td style="font-weight:500">{summary.get('count',0)}</td></tr>
    </table>
  </div>
  <a href="/app/logout" class="btn-outline-accent"><i class="bi bi-box-arrow-right me-1"></i>Sign Out</a>
</div>"""
        return _page("Profile", body)

    # ══════════════════════════════════════════════════════════════════════════
    # GROUP ROUTES
    # ══════════════════════════════════════════════════════════════════════════

    # ── /app/groups — list all groups the user belongs to ─────────────────────
    @app.get("/app/groups")
    async def app_groups(
        request: Request, exp_token: str | None = Cookie(default=None), msg: str = ""
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"
        uid     = profile.get("id")

        # Only groups the user is a member of — privacy requirement
        status_code, all_groups = await _rest(token, "GET", "/groups")
        groups = all_groups if isinstance(all_groups, list) else []
        print("\n=== GROUPS FROM API ===")
        for g in groups:
            print(g)
        # Filter to groups where the user is an active member
        # (the backend should already do this when auth middleware is in place;
        #  this is a client-side defence for the stub REST layer)
        if uid:
            filtered = []
            for g in groups:
                sc2, members = await _rest(token, "GET", f"/groups/{g['id']}/members")
                member_ids = [m["user_id"] for m in (members or [])]
                if uid in member_ids:
                    filtered.append(g)
            groups = filtered

        alert = ""
        if msg == "created":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Group created!</div>'
        elif msg == "archived":
            alert = '<div class="alert-warn-custom mb-3"><i class="bi bi-archive me-1"></i>Group archived.</div>'
        elif msg == "joined":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Join request submitted — awaiting approval.</div>'

        cards = ""
        if not groups:
            cards = """
            <div class="col-12 text-center py-5 text-muted">
              <i class="bi bi-people" style="font-size:2.5rem;opacity:0.3"></i>
              <p class="mt-3">You're not in any groups yet.</p>
              <div class="d-flex justify-content-center gap-2 mt-3">
                <a href="/app/groups/join"   class="btn-outline-accent"><i class="bi bi-key"></i>Join via Invite Code</a>
                <a href="/app/groups/create" class="btn-accent"><i class="bi bi-plus-lg"></i>Create Group</a>
              </div>
            </div>"""
        else:
            for g in groups:
                icon   = GROUP_TYPE_ICONS.get(g.get("group_type", "other"), "👥")
                status = g.get("status", "active")
                badge  = (
                    '<span class="badge-archived">Archived</span>'
                    if status == "archived"
                    else '<span class="badge-active">Active</span>'
                )
                cards += f"""
                <div class="col-sm-6 col-lg-4">
                  <a href="/app/groups/{g['id']}" class="group-card">
                    <div class="d-flex align-items-center justify-content-between mb-2">
                      <span style="font-size:1.5rem">{icon}</span>
                      {badge}
                    </div>
                    <div style="font-weight:600;font-size:0.95rem">{g['name']}</div>

                    <div style="font-size:0.8rem;color:var(--muted);margin-top:2px">
                    {g.get('description') or g.get('group_type','').capitalize()}
                    </div>

                    <div class="mt-2">
                    <div style="font-size:0.72rem;color:var(--muted);margin-bottom:3px">
                        Invite Code
                    </div>
                    <div style="
                        font-family:'DM Mono',monospace;
                        font-size:0.9rem;
                        font-weight:600;
                        color:var(--accent);
                        background:var(--accent-soft);
                        border-radius:6px;
                        padding:4px 8px;
                        display:inline-block;
                        letter-spacing:1px;">
                        {g.get('invite_code','N/A')}
                    </div>
                    </div>

                    <div class="mt-2" style="font-size:0.78rem;color:var(--muted)">
                    <i class="bi bi-calendar3 me-1"></i>
                    Created {g.get('created_at','')[:10]}
                    </div>
                  </a>
                </div>"""

        body = f"""
{_navbar(uname)}
<div class="page-content">
  <div class="d-flex align-items-center justify-content-between mb-4">
    <div>
      <h5 class="mb-0 fw-semibold">My Groups</h5>
      <p class="mb-0 text-muted" style="font-size:0.82rem">Groups you belong to — discoverable only via invite code</p>
    </div>
    <div class="d-flex gap-2">
      <a href="/app/groups/join"   class="btn-outline-accent"><i class="bi bi-key"></i>Join via Code</a>
      <a href="/app/groups/create" class="btn-accent"><i class="bi bi-plus-lg"></i>New Group</a>
    </div>
  </div>
  {alert}
  <div class="row g-3">{cards}</div>
</div>"""
        return _page("Groups", body)

    # ── /app/groups/create ────────────────────────────────────────────────────
    @app.get("/app/groups/create")
    async def app_groups_create(request: Request, exp_token: str | None = Cookie(default=None)):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"

        type_opts = "".join(
            f'<option value="{t}">{GROUP_TYPE_ICONS.get(t,"")} {t.capitalize()}</option>'
            for t in GROUP_TYPES
        )

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:680px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">Create Group</h5>
  </div>
  <div class="card p-4">
    <form method="post" action="/app/groups/create">
      <div class="row g-3">
        <div class="col-12">
          <label class="form-label">Group Name *</label>
          <input class="form-control" type="text" name="name" placeholder="e.g. Goa Trip, Flat 302" required autofocus>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Group Type</label>
          <select class="form-select" name="group_type">{type_opts}</select>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Description <span style="color:var(--muted);font-size:0.75rem">(optional)</span></label>
          <input class="form-control" type="text" name="description" placeholder="Short description">
        </div>
        <div class="col-12">
          <label class="form-label">
            Initial Member User IDs
            <span style="color:var(--muted);font-size:0.75rem">(comma-separated, optional)</span>
          </label>
          <input class="form-control" type="text" name="member_ids" placeholder="e.g. 2, 3, 4">
          <div style="font-size:0.78rem;color:var(--muted);margin-top:4px">
            <i class="bi bi-info-circle me-1"></i>You are automatically the Owner.
            An invite code is generated automatically — share it to let others join.
          </div>
        </div>
        <div class="col-12 d-flex gap-2 mt-2">
          <button type="submit" class="btn-accent px-4"><i class="bi bi-people me-1"></i>Create Group</button>
          <a href="/app/groups" class="btn-outline-accent px-4">Cancel</a>
        </div>
      </div>
    </form>
  </div>
</div>"""
        return _page("Create Group", body)

    @app.post("/app/groups/create")
    async def app_groups_create_post(
        request: Request, exp_token: str | None = Cookie(default=None),
        name: str = Form(""), group_type: str = Form("other"),
        description: str = Form(""), member_ids: str = Form(""),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        ids = [int(x.strip()) for x in member_ids.split(",") if x.strip().isdigit()]

        result = await _mcp(token, "create_group", {
            "name": name,
            "group_type": group_type,
            "description": description or None,
            "member_user_ids": ids,
        })
        print("=== CREATE GROUP RESULT ===")
        print(result)                    # ← Add this
        import traceback
        if not result:
            print("MCP call failed or returned None")

        if result and "error" not in result:
            return RedirectResponse(f"/app/groups/{result['id']}", status_code=302)
        return RedirectResponse("/app/groups?msg=error", status_code=302)

    # ══════════════════════════════════════════════════════════════════════════
    # JOIN VIA INVITE CODE
    # ══════════════════════════════════════════════════════════════════════════

    # ── /app/groups/join — enter invite code ──────────────────────────────────
    @app.get("/app/groups/join")
    async def app_groups_join(
        request: Request, exp_token: str | None = Cookie(default=None),
        error: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"

        err_html = f'<div class="alert-danger-custom mb-3"><i class="bi bi-exclamation-circle me-1"></i>{error}</div>' if error else ""

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:520px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Groups</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">Join a Group</h5>
  </div>
  {err_html}
  <div class="card p-5 text-center">
    <div style="font-size:3rem;margin-bottom:1rem">🔑</div>
    <h5 class="fw-semibold mb-1">Enter Invite Code</h5>
    <p class="text-muted mb-4" style="font-size:0.88rem">
      Groups are private and discoverable only via an invite code shared by the owner or an admin.
    </p>
    <form method="post" action="/app/groups/join">
      <div class="mb-3">
        <input class="form-control text-center" type="text" name="code"
               placeholder="e.g. GOA7X9K2"
               style="font-family:'DM Mono',monospace;font-size:1.2rem;letter-spacing:4px;text-transform:uppercase"
               maxlength="12" required autofocus oninput="this.value=this.value.toUpperCase()">
        <div style="font-size:0.78rem;color:var(--muted);margin-top:6px">
          Codes are 8 characters, uppercase alphanumeric.
        </div>
      </div>
      <button type="submit" class="btn-accent w-100" style="height:44px;font-size:1rem;justify-content:center">
        <i class="bi bi-search me-1"></i>Look Up Group
      </button>
    </form>
  </div>
</div>"""
        return _page("Join Group", body)

    @app.post("/app/groups/join")
    async def app_groups_join_post(
        exp_token: str | None = Cookie(default=None),
        code: str = Form(""),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        code = code.strip().upper()
        if not code:
            return RedirectResponse("/app/groups/join?error=Please+enter+a+code", status_code=302)
        return RedirectResponse(f"/app/groups/join/{code}", status_code=302)

    # ── /app/groups/join/{code} — preview & submit request ───────────────────
    @app.get("/app/groups/join/{code}")
    async def app_groups_join_preview(
        code: str, request: Request,
        exp_token: str | None = Cookie(default=None), msg: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"

        # Validate code and fetch preview
        sc, result = await _rest(token, "GET", f"/groups/join/{code.upper()}")

        if sc == 404 or not result or "error" in (result or {}):
            err = (result or {}).get("detail", "Invalid or expired invite code.")
            return _page("Join Group", f"""
{_navbar(uname)}
<div class="page-content" style="max-width:520px">
  <div class="alert-danger-custom mb-3"><i class="bi bi-x-circle me-1"></i>{err}</div>
  <a href="/app/groups/join" class="btn-outline-accent"><i class="bi bi-arrow-left me-1"></i>Try Another Code</a>
</div>""")

        icon       = GROUP_TYPE_ICONS.get(result.get("group_type", "other"), "👥")
        alert      = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Join request submitted! You will be added once an admin approves.</div>' if msg == "requested" else ""
        btn_html   = "" if msg == "requested" else f"""
        <form method="post" action="/app/groups/join/{code}">
          <button type="submit" class="btn-accent w-100 mt-4" style="height:44px;font-size:1rem;justify-content:center">
            <i class="bi bi-person-plus me-1"></i>Request to Join
          </button>
        </form>"""

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:520px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups/join" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">Group Preview</h5>
  </div>
  {alert}
  <div class="join-preview">
    <div style="font-size:3rem;margin-bottom:0.75rem">{icon}</div>
    <h4 class="fw-semibold mb-1">{result.get('group_name','')}</h4>
    <p class="text-muted mb-3" style="font-size:0.9rem">{result.get('description') or result.get('group_type','').capitalize()}</p>
    <div class="d-flex justify-content-center gap-4 mb-1" style="font-size:0.85rem;color:var(--muted)">
      <div><i class="bi bi-people me-1"></i><strong style="color:var(--text)">{result.get('member_count', '?')}</strong> members</div>
      <div><i class="bi bi-tag me-1"></i><strong style="color:var(--text)">{result.get('group_type','other').capitalize()}</strong></div>
    </div>
  </div>
  <div class="alert-warn-custom mt-3" style="font-size:0.82rem">
    <i class="bi bi-info-circle me-1"></i>
    Your request will be reviewed by a group admin before you are added.
  </div>
  {btn_html}
</div>"""
        return _page("Join Group", body)

    @app.post("/app/groups/join/{code}")
    async def app_groups_join_request_post(
        code: str, exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        result = await _mcp(token, "request_group_join", {"invite_code": code.upper()})
        if result and "error" not in result:
            return RedirectResponse(f"/app/groups/join/{code}?msg=requested", status_code=302)
        err = urllib.parse.quote((result or {}).get("error", "Failed to submit request."))
        return RedirectResponse(f"/app/groups/join?error={err}", status_code=302)

    # ══════════════════════════════════════════════════════════════════════════
    # GROUP DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════

    @app.get("/app/groups/{group_id}")
    async def app_group_detail(
        group_id: int, request: Request,
        exp_token: str | None = Cookie(default=None), msg: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile  = await _mcp(token, "get_profile", {}) or {}
        uname    = profile.get("nickname") or profile.get("name") or "User"
        uid      = profile.get("id")

        summary  = await _mcp(token, "get_group_summary", {"group_id": group_id}) or {}
        if "error" in summary:
            # Non-member trying to access — privacy enforcement
            return _page("Access Denied", f"""
{_navbar(uname)}
<div class="page-content" style="max-width:520px">
  <div class="alert-danger-custom">
    <i class="bi bi-lock me-1"></i>
    You are not a member of this group or it does not exist.
    <a href="/app/groups" class="ms-3">My Groups</a>
  </div>
</div>""")

        data     = await _mcp(token, "list_group_expenses", {"group_id": group_id}) or {}
        expenses = data.get("expenses", [])

        # Determine caller's role for conditional UI
        sc, members_raw = await _rest(token, "GET", f"/groups/{group_id}/members")
        members_list    = members_raw if isinstance(members_raw, list) else []
        caller_role     = "member"
        for m in members_list:
            if m.get("user_id") == uid:
                caller_role = (m.get("role") or "member").lower()
                break
        is_admin_plus = caller_role in ("owner", "admin")

        icon     = GROUP_TYPE_ICONS.get(summary.get("group_type", "other"), "👥")
        status   = summary.get("status", "active")
        archived = status == "archived"

        alert = ""
        if msg == "added":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Expense added!</div>'
        elif msg == "settled":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Settlements calculated!</div>'

        # Pending join requests badge (admin/owner only)
        req_badge = ""
        if is_admin_plus:
            sc2, reqs = await _rest(token, "GET", f"/groups/{group_id}/join-requests?status=pending")
            pending_count = len(reqs) if isinstance(reqs, list) else 0
            if pending_count:
                req_badge = f' <span style="background:#ef4444;color:#fff;border-radius:20px;font-size:0.65rem;padding:1px 6px;font-weight:600">{pending_count}</span>'
                
        user_name_map = {
            mb['user_id']: mb.get('user_name', f"User {mb['user_id']}")
            for mb in summary.get('member_balances', [])
        }

        # Member balance table
        bal_rows = ""
        for mb in summary.get("member_balances", []):
            name     = mb.get('user_name', f"User {mb['user_id']}")
            initials = "".join(w[0].upper() for w in name.split()[:2])
            role_b   = _role_badge(mb.get('role', 'member'))
            bal_rows += f"""
            <tr>
              <td>
                <div style="width:28px;height:28px;border-radius:50%;background:var(--accent-soft);
                            color:var(--accent);font-size:0.75rem;font-weight:600;
                            display:inline-flex;align-items:center;justify-content:center;
                            margin-right:8px">{initials}</div>
                {name} {role_b}
              </td>
              <td style="font-family:'DM Mono',monospace">₹{mb['total_paid']:,.2f}</td>
              <td style="font-family:'DM Mono',monospace">₹{mb['total_share']:,.2f}</td>
              <td>{_fmt_balance(mb['net_balance'])}</td>
            </tr>"""

        # Recent expenses
        exp_rows = ""
        for e in expenses[:10]:
            exp_rows += f"""
            <tr>
              <td style="font-size:0.82rem;font-weight:500">{e.get('title','')}</td>
              <td><span class="badge-cat">{e.get('category','')}</span></td>
              <td style="font-family:'DM Mono',monospace;font-weight:500">₹{e['amount']:,.2f}</td>
              <td style="font-size:0.82rem;color:var(--muted)">{user_name_map.get(e.get('paid_by'), f"User {e.get('paid_by','')}")}</td>
              <td><span class="badge-type">{e.get('split_type','')}</span></td>
              <td style="font-size:0.82rem;color:var(--muted)">{e.get('date','')}</td>
            </tr>"""
        if not exp_rows:
            exp_rows = '<tr><td colspan="6" class="text-center text-muted py-3">No expenses yet.</td></tr>'

        # Action buttons — all members can add expenses; admin+ get extra tools
        actions = ""
        if not archived:
            admin_btns = ""
            if is_admin_plus:
                admin_btns = f"""
                <a href="/app/groups/{group_id}/roles"    class="btn-outline-accent"><i class="bi bi-shield-lock"></i>Roles</a>
                <a href="/app/groups/{group_id}/requests" class="btn-outline-accent">
                  <i class="bi bi-person-check"></i>Requests{req_badge}
                </a>
                <a href="/app/groups/{group_id}/invite"   class="btn-outline-accent"><i class="bi bi-key"></i>Invite Code</a>"""
            archive_btn = ""
            if caller_role == "owner":
                archive_btn = f"""
                <a href="/app/groups/{group_id}/archive"
                   onclick="return confirm('Archive this group? No new expenses can be added.')"
                   class="btn btn-sm" style="border:1.5px solid #fde68a;color:#92400e;border-radius:8px;font-size:0.9rem;padding:0.45rem 1rem">
                  <i class="bi bi-archive me-1"></i>Archive
                </a>"""
            actions = f"""
            <div class="d-flex gap-2 flex-wrap">
              <a href="/app/groups/{group_id}/add"    class="btn-accent"><i class="bi bi-plus-lg"></i>Add Expense</a>
              <a href="/app/groups/{group_id}/settle" class="btn-outline-accent"><i class="bi bi-calculator"></i>Settle Up</a>
              <a href="/app/groups/{group_id}/members" class="btn-outline-accent"><i class="bi bi-people"></i>Members</a>
              {admin_btns}
              {archive_btn}
            </div>"""
        else:
            actions = '<span class="badge-archived" style="font-size:0.85rem;padding:6px 14px"><i class="bi bi-archive me-1"></i>Archived</span>'

        body = f"""
{_navbar(uname)}
<div class="page-content">
  <div class="d-flex align-items-center gap-2 mb-1">
    <a href="/app/groups" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Groups</a>
    <span class="text-muted">/</span>
    <span style="font-size:0.85rem;color:var(--text)">{summary.get('group_name','')}</span>
  </div>
  <div class="d-flex align-items-start justify-content-between mb-4 mt-2 flex-wrap gap-3">
    <div class="d-flex align-items-center gap-3">
      <span style="font-size:2.2rem">{icon}</span>
      <div>
        <h5 class="mb-0 fw-semibold">{summary.get('group_name','')}</h5>
        <div class="d-flex align-items-center gap-2 mt-1">
          <span class="badge-type">{status.capitalize()}</span>
          {_role_badge(caller_role)}
        </div>
      </div>
    </div>
    {actions}
  </div>
  {alert}

  <!-- Metrics -->
  <div class="row g-3 mb-4">
    <div class="col-sm-6 col-lg-3">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#eef2ff;color:#6366f1"><i class="bi bi-currency-rupee"></i></div>
        <div><div class="val">₹{summary.get('total_expenses',0):,.0f}</div><div class="lbl">Total Expenses</div></div>
      </div>
    </div>
    <div class="col-sm-6 col-lg-3">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#f0fdf4;color:#16a34a"><i class="bi bi-receipt"></i></div>
        <div><div class="val">{summary.get('expense_count',0)}</div><div class="lbl">Expenses</div></div>
      </div>
    </div>
    <div class="col-sm-6 col-lg-3">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#fff7ed;color:#ea580c"><i class="bi bi-people"></i></div>
        <div><div class="val">{summary.get('total_members',0)}</div><div class="lbl">Members</div></div>
      </div>
    </div>
    <div class="col-sm-6 col-lg-3">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#fdf4ff;color:#9333ea"><i class="bi bi-hourglass-split"></i></div>
        <div><div class="val">{summary.get('pending_settlements',0)}</div><div class="lbl">Pending Settlements</div></div>
      </div>
    </div>
  </div>

  <div class="row g-3">
    <!-- Member Balances -->
    <div class="col-lg-5">
      <div class="card p-4">
        <div class="section-title"><i class="bi bi-person-lines-fill me-2" style="color:var(--accent)"></i>Member Balances</div>
        <div style="overflow-x:auto">
          <table class="table mb-0">
            <thead><tr><th>Member</th><th>Paid</th><th>Share</th><th>Net</th></tr></thead>
            <tbody>{bal_rows}</tbody>
          </table>
        </div>
        <div style="font-size:0.75rem;color:var(--muted);margin-top:8px">
          <span style="color:#15803d">+₹ = owed money</span> &nbsp;·&nbsp;
          <span style="color:#b91c1c">-₹ = owes money</span>
        </div>
      </div>
    </div>

    <!-- Recent Expenses -->
    <div class="col-lg-7">
      <div class="card p-4">
        <div class="d-flex align-items-center justify-content-between mb-3">
          <div class="section-title mb-0"><i class="bi bi-list-ul me-2" style="color:#16a34a"></i>Recent Expenses</div>
          <a href="/app/groups/{group_id}/expenses" style="font-size:0.82rem;color:var(--accent)">View all →</a>
        </div>
        <div style="overflow-x:auto">
          <table class="table mb-0">
            <thead><tr><th>Title</th><th>Category</th><th>Amount</th><th>Paid By</th><th>Split</th><th>Date</th></tr></thead>
            <tbody>{exp_rows}</tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>"""
        return _page(summary.get("group_name", "Group"), body)

    # ── /app/groups/{id}/add — Add Group Expense ──────────────────────────────
    @app.get("/app/groups/{group_id}/add")
    async def app_group_add_expense(
        group_id: int, request: Request, exp_token: str | None = Cookie(default=None)
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"
        summary = await _mcp(token, "get_group_summary", {"group_id": group_id}) or {}
        if "error" in summary:
            return RedirectResponse("/app/groups", status_code=302)
        members = summary.get("member_balances", [])
        today   = str(_date.today())

        cat_opts   = "".join(f'<option value="{c}">{c}</option>' for c in EXP_CATEGORIES)
        split_opts = "".join(f'<option value="{s}">{s}</option>' for s in SPLIT_TYPES)
        payer_opts = "".join(
            f'<option value="{m["user_id"]}">User {m["user_id"]}</option>'
            for m in members
        )
        member_checkboxes = "".join(
            f"""<div class="form-check form-check-inline">
                  <input class="form-check-input participant-check" type="checkbox"
                         name="participant_ids" value="{m['user_id']}" id="p{m['user_id']}" checked>
                  <label class="form-check-label" for="p{m['user_id']}" style="font-size:0.85rem">
                    User {m['user_id']}
                  </label>
                </div>"""
            for m in members
        )

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:760px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups/{group_id}" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">Add Group Expense</h5>
  </div>
  <div class="card p-4">
    <form method="post" action="/app/groups/{group_id}/add">
      <div class="row g-3">
        <div class="col-sm-8">
          <label class="form-label">Title *</label>
          <input class="form-control" type="text" name="title" placeholder="e.g. Hotel Booking, Dinner" required autofocus>
        </div>
        <div class="col-sm-4">
          <label class="form-label">Date *</label>
          <input class="form-control" type="date" name="date" value="{today}" required>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Amount (₹) *</label>
          <input class="form-control" type="number" step="0.01" name="amount" id="amount" placeholder="0.00" required>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Category</label>
          <select class="form-select" name="category">{cat_opts}</select>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Paid By *</label>
          <select class="form-select" name="paid_by">{payer_opts}</select>
        </div>
        <div class="col-sm-6">
          <label class="form-label">Split Type *</label>
          <select class="form-select" name="split_type" id="split_type" onchange="onSplitChange()">{split_opts}</select>
        </div>
        <div class="col-12">
          <label class="form-label">Description</label>
          <input class="form-control" type="text" name="description" placeholder="Optional notes">
        </div>
        <div class="col-12" id="section-equal">
          <label class="form-label">Participants</label>
          <div>{member_checkboxes}</div>
        </div>
        <div class="col-12" id="section-custom" style="display:none">
          <label class="form-label">
            Share Values
            <span id="share-hint" style="font-size:0.75rem;color:var(--muted);font-weight:400">
              — enter percentage per member (must sum to 100)
            </span>
          </label>
          <div id="participant-rows">
            {"".join(f'''<div class="prow">
              <span style="font-size:0.85rem;width:70px;color:var(--muted)">User {m["user_id"]}</span>
              <input class="form-control share-input" type="number" step="0.01" min="0"
                     name="share_{m['user_id']}" placeholder="0"
                     style="width:120px;flex:none">
            </div>''' for m in members)}
          </div>
          <div id="share-sum-hint" style="font-size:0.78rem;color:var(--muted);margin-top:4px"></div>
        </div>
        <div class="col-12 d-flex gap-2 mt-2">
          <button type="submit" class="btn-accent px-4"><i class="bi bi-plus-lg me-1"></i>Add Expense</button>
          <a href="/app/groups/{group_id}" class="btn-outline-accent px-4">Cancel</a>
        </div>
      </div>
    </form>
  </div>
</div>
<script>
const MEMBERS = {json.dumps([m["user_id"] for m in members])};
function onSplitChange() {{
  const st   = document.getElementById('split_type').value;
  const eq   = document.getElementById('section-equal');
  const cu   = document.getElementById('section-custom');
  const hint = document.getElementById('share-hint');
  const hints = {{
    percentage: '— enter percentage per member (must sum to 100)',
    fixed:      '— enter INR amount per member (must sum to total)',
    by_days:    '— enter number of days each member stayed',
    custom:     '— enter arbitrary INR amount per member',
  }};
  if (st === 'equal') {{ eq.style.display=''; cu.style.display='none'; }}
  else                {{ eq.style.display='none'; cu.style.display=''; }}
  hint.textContent = hints[st] || '';
  updateSumHint();
}}
function updateSumHint() {{
  const inputs = document.querySelectorAll('.share-input');
  let total = 0;
  inputs.forEach(i => total += parseFloat(i.value || 0));
  const el = document.getElementById('share-sum-hint');
  const st = document.getElementById('split_type').value;
  if (st === 'percentage') {{
    el.textContent = `Sum: ${{total.toFixed(2)}}% ${{Math.abs(total-100)<0.01 ? '✅' : '(must equal 100)'}}`;
  }} else if (st === 'fixed' || st === 'custom') {{
    const amt = parseFloat(document.getElementById('amount').value || 0);
    el.textContent = `Sum: ₹${{total.toFixed(2)}} / ₹${{amt.toFixed(2)}}`;
  }} else {{
    el.textContent = `Total days: ${{total.toFixed(0)}}`;
  }}
}}
document.querySelectorAll('.share-input').forEach(i => i.addEventListener('input', updateSumHint));
document.getElementById('amount').addEventListener('input', updateSumHint);
</script>"""
        return _page("Add Group Expense", body)

    @app.post("/app/groups/{group_id}/add")
    async def app_group_add_expense_post(
        group_id: int, request: Request, exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        form       = await request.form()
        split_type = form.get("split_type", "equal")
        amount     = float(form.get("amount", 0))
        paid_by    = int(form.get("paid_by", 0))

        args = {
            "group_id":    group_id,
            "title":       form.get("title", ""),
            "amount":      amount,
            "category":    form.get("category", "miscellaneous"),
            "paid_by":     paid_by,
            "split_type":  split_type,
            "date":        form.get("date", str(_date.today())),
            "description": form.get("description") or None,
        }

        if split_type == "equal":
            participant_ids = [int(v) for v in form.getlist("participant_ids")]
            args["participant_user_ids"] = participant_ids or [paid_by]
        else:
            participants = []
            for key, val in form.items():
                if key.startswith("share_") and val:
                    uid = int(key.replace("share_", ""))
                    sv  = float(val)
                    if sv > 0:
                        participants.append({"user_id": uid, "share_value": sv})
            args["participants"] = participants

        await _mcp(token, "add_group_expense", args)
        return RedirectResponse(f"/app/groups/{group_id}?msg=added", status_code=302)

    # ── /app/groups/{id}/expenses — Full expense list ─────────────────────────
    @app.get("/app/groups/{group_id}/expenses")
    async def app_group_expenses(
        group_id: int, request: Request,
        exp_token: str | None = Cookie(default=None),
        category: str = "", paid_by: str = "",
        month: str = "", year: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"
        summary = await _mcp(token, "get_group_summary", {"group_id": group_id}) or {}
        if "error" in summary:
            return RedirectResponse("/app/groups", status_code=302)

        user_name_map = {
            mb['user_id']: mb.get('user_name', f"User {mb['user_id']}")
            for mb in summary.get('member_balances', [])
        }


        args = {"group_id": group_id}
        if category: args["category"] = category
        if paid_by:  args["paid_by"]  = int(paid_by)
        if month:    args["month"]    = int(month)
        if year:     args["year"]     = int(year)

        data     = await _mcp(token, "list_group_expenses", args) or {}
        expenses = data.get("expenses", [])

        cat_opts   = "".join(f'<option value="{c}" {"selected" if c==category else ""}>{c}</option>' for c in EXP_CATEGORIES)
        month_opts = "".join(f'<option value="{m}" {"selected" if str(m)==month else ""}>{m:02d}</option>' for m in range(1,13))
        year_opts  = "".join(f'<option value="{y}" {"selected" if str(y)==year else ""}>{y}</option>' for y in range(2022,2027))

        rows = ""
        for e in expenses:
            settled = '<span style="color:#15803d;font-size:0.78rem">✓ Settled</span>' if e.get("is_settled") else ''
            rows += f"""
            <tr>
              <td style="font-weight:500;font-size:0.875rem">{e.get('title','')}</td>
              <td><span class="badge-cat">{e.get('category','')}</span></td>
              <td style="font-family:'DM Mono',monospace;font-weight:500">₹{e['amount']:,.2f}</td>
              <td style="font-size:0.82rem;color:var(--muted)">{user_name_map.get(e.get('paid_by'), f"User {e.get('paid_by','')}")}</td>
              <td><span class="badge-type">{e.get('split_type','')}</span></td>
              <td style="font-size:0.82rem;color:var(--muted)">{e.get('date','')}</td>
              <td>{settled}</td>
            </tr>"""
        if not rows:
            rows = '<tr><td colspan="7" class="text-center text-muted py-4">No expenses found.</td></tr>'

        body = f"""
{_navbar(uname)}
<div class="page-content">
  <div class="d-flex align-items-center justify-content-between mb-3">
    <div class="d-flex align-items-center gap-2">
      <a href="/app/groups/{group_id}" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i></a>
      <h5 class="mb-0 fw-semibold">{summary.get('group_name','')} — Expenses</h5>
    </div>
    <a href="/app/groups/{group_id}/add" class="btn-accent"><i class="bi bi-plus-lg"></i>Add Expense</a>
  </div>
  <form method="get" action="/app/groups/{group_id}/expenses" class="card p-3 mb-3">
    <div class="row g-2 align-items-end">
      <div class="col-sm-3">
        <label class="form-label">Category</label>
        <select name="category" class="form-select"><option value="">All</option>{cat_opts}</select>
      </div>
      <div class="col-sm-3">
        <label class="form-label">Paid By (User ID)</label>
        <input class="form-control" type="number" name="paid_by" value="{paid_by}" placeholder="Any">
      </div>
      <div class="col-sm-2">
        <label class="form-label">Month</label>
        <select name="month" class="form-select"><option value="">All</option>{month_opts}</select>
      </div>
      <div class="col-sm-2">
        <label class="form-label">Year</label>
        <select name="year" class="form-select"><option value="">All</option>{year_opts}</select>
      </div>
      <div class="col-sm-2">
        <button type="submit" class="btn-accent w-100" style="height:38px"><i class="bi bi-funnel me-1"></i>Filter</button>
      </div>
    </div>
  </form>
  <div class="card" style="overflow:hidden">
    <div style="overflow-x:auto">
      <table class="table mb-0">
        <thead><tr><th>Title</th><th>Category</th><th>Amount</th><th>Paid By</th><th>Split Type</th><th>Date</th><th>Status</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>
  <p class="text-muted mt-2" style="font-size:0.8rem">{len(expenses)} record(s)</p>
</div>"""
        return _page("Group Expenses", body)

    # ── /app/groups/{id}/settle ───────────────────────────────────────────────
    @app.get("/app/groups/{group_id}/settle")
    async def app_group_settle(
        group_id: int, request: Request,
        exp_token: str | None = Cookie(default=None), msg: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile  = await _mcp(token, "get_profile", {}) or {}
        uname    = profile.get("nickname") or profile.get("name") or "User"
        summary  = await _mcp(token, "get_group_summary", {"group_id": group_id}) or {}
        if "error" in summary:
            return RedirectResponse("/app/groups", status_code=302)
        user_name_map = {
            mb['user_id']: mb.get('user_name', f"User {mb['user_id']}")
            for mb in summary.get('member_balances', [])
        }


        sc, settlements = await _rest(token, "GET", f"/groups/{group_id}/settlements")
        settlements = settlements if isinstance(settlements, list) else []

        alert = ""
        if msg == "calculated":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Settlements recalculated using debt simplification.</div>'

        pending   = [s for s in settlements if s.get("status") == "pending"]
        settled_l = [s for s in settlements if s.get("status") == "settled"]

        debt_rows = ""
        if not settlements:
            debt_rows = '<div class="text-muted text-center py-4"><i class="bi bi-check2-circle" style="font-size:2rem;opacity:0.3"></i><p class="mt-2">No settlements yet. Click "Recalculate" to compute who owes whom.</p></div>'
        else:
            for s in pending:
                debt_rows += f"""
                <div class="debt-row">
                  <div class="debt-arrow"><i class="bi bi-arrow-right"></i></div>
                  <div style="flex:1">
                    <span style="font-weight:500">{user_name_map.get(s['from_user_id'], f"User {s['from_user_id']}")}</span>
                    <span class="text-muted mx-2">owes</span>
                    <span style="font-weight:500">{user_name_map.get(s['to_user_id'], f"User {s['to_user_id']}")}</span>
                  </div>
                  <div style="font-family:'DM Mono',monospace;font-weight:600;color:#b91c1c">₹{s['amount']:,.2f}</div>
                  <form method="post" action="/app/groups/{group_id}/settlements/{s['id']}/settle" class="ms-3">
                    <button type="submit" class="btn btn-sm"
                            style="border:1.5px solid #bbf7d0;color:#15803d;border-radius:7px;font-size:0.78rem;padding:3px 10px">
                      ✓ Mark Settled
                    </button>
                  </form>
                </div>"""
            for s in settled_l:
                debt_rows += f"""
                <div class="debt-row" style="opacity:0.5">
                  <div style="width:32px;height:32px;border-radius:50%;background:#f0fdf4;color:#15803d;
                              display:flex;align-items:center;justify-content:center;font-size:0.85rem;flex-shrink:0">
                    <i class="bi bi-check-lg"></i>
                  </div>
                  <div style="flex:1">
                    <span style="font-weight:500">{user_name_map.get(s['from_user_id'], f"User {s['from_user_id']}")}</span>
                    <span class="text-muted mx-2">paid</span>
                    <span style="font-weight:500">{user_name_map.get(s['to_user_id'], f"User {s['to_user_id']}")}</span>
                  </div>
                  <div style="font-family:'DM Mono',monospace;color:#15803d">₹{s['amount']:,.2f} <span style="font-size:0.75rem">settled</span></div>
                </div>"""

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:760px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups/{group_id}" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">{summary.get('group_name','')} — Settle Up</h5>
  </div>
  {alert}
  <div class="row g-3 mb-4">
    <div class="col-sm-4">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#fef2f2;color:#ef4444"><i class="bi bi-hourglass-split"></i></div>
        <div><div class="val">{len(pending)}</div><div class="lbl">Pending</div></div>
      </div>
    </div>
    <div class="col-sm-4">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#f0fdf4;color:#16a34a"><i class="bi bi-check-circle"></i></div>
        <div><div class="val">{len(settled_l)}</div><div class="lbl">Settled</div></div>
      </div>
    </div>
    <div class="col-sm-4">
      <div class="metric-card d-flex align-items-center gap-3">
        <div class="icon-wrap" style="background:#eef2ff;color:#6366f1"><i class="bi bi-currency-rupee"></i></div>
        <div><div class="val">₹{sum(s['amount'] for s in pending):,.0f}</div><div class="lbl">Outstanding</div></div>
      </div>
    </div>
  </div>
  <div class="card p-4 mb-3">
    <div class="d-flex align-items-center justify-content-between mb-3">
      <div>
        <div class="section-title mb-1"><i class="bi bi-calculator me-2" style="color:var(--accent)"></i>Debt Simplification</div>
        <div style="font-size:0.82rem;color:var(--muted)">Minimises the number of transactions to settle all debts.</div>
      </div>
      <form method="post" action="/app/groups/{group_id}/settle/calculate">
        <button type="submit" class="btn-accent"><i class="bi bi-arrow-repeat me-1"></i>Recalculate</button>
      </form>
    </div>
    <div style="border:1px solid var(--border);border-radius:8px;overflow:hidden">{debt_rows}</div>
  </div>
</div>"""
        return _page("Settle Up", body)

    @app.post("/app/groups/{group_id}/settle/calculate")
    async def app_group_settle_calculate(
        group_id: int, exp_token: str | None = Cookie(default=None)
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "calculate_group_settlement", {"group_id": group_id})
        return RedirectResponse(f"/app/groups/{group_id}/settle?msg=calculated", status_code=302)

    @app.post("/app/groups/{group_id}/settlements/{settlement_id}/settle")
    async def app_mark_settled(
        group_id: int, settlement_id: int,
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _rest(token, "PATCH", f"/groups/{group_id}/settlements/{settlement_id}/settle")
        return RedirectResponse(f"/app/groups/{group_id}/settle", status_code=302)

    # ── /app/groups/{id}/members ──────────────────────────────────────────────
    @app.get("/app/groups/{group_id}/members")
    async def app_group_members(
        group_id: int, request: Request,
        exp_token: str | None = Cookie(default=None), msg: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"
        summary = await _mcp(token, "get_group_summary", {"group_id": group_id}) or {}
        if "error" in summary:
            return RedirectResponse("/app/groups", status_code=302)

        user_name_map = {
            mb['user_id']: mb.get('user_name', f"User {mb['user_id']}")
            for mb in summary.get('member_balances', [])
        }

        sc, members = await _rest(token, "GET", f"/groups/{group_id}/members")
        members = members if isinstance(members, list) else []

        uid         = profile.get("id")
        caller_role = "member"
        for m in members:
            if m.get("user_id") == uid:
                caller_role = (m.get("role") or "member").lower()
                break
        is_admin_plus = caller_role in ("owner", "admin")


        alert = ""
        if msg == "added":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Member added.</div>'
        elif msg == "removed":
            alert = '<div class="alert-danger-custom mb-3"><i class="bi bi-check-circle me-1"></i>Member removed.</div>'

        rows = ""
        for m in members:
            role = (m.get("role") or "member").lower()
            remove_btn = ""
            if is_admin_plus and role != "owner" and m.get("user_id") != uid:
                remove_btn = f"""
                <form method="post" action="/app/groups/{group_id}/members/{m['user_id']}/remove" class="d-inline">
                  <button type="submit" class="btn btn-sm"
                          style="border:1.5px solid #fee2e2;color:#ef4444;border-radius:7px;font-size:0.78rem;padding:2px 8px"
                          onclick="return confirm('Remove this member?')">
                    <i class="bi bi-person-dash"></i>
                  </button>
                </form>"""

            mname    = user_name_map.get(m['user_id'], f"User {m['user_id']}")
            minitials = "".join(w[0].upper() for w in mname.split()[:2])
            rows += f"""
            <tr>
              <td>
                <div style="width:28px;height:28px;border-radius:50%;background:var(--accent-soft);
                            color:var(--accent);font-size:0.75rem;font-weight:600;
                            display:inline-flex;align-items:center;justify-content:center;
                            margin-right:8px">{minitials}</div>
                {mname} {"(you)" if m.get("user_id") == uid else ""}
              </td>"""


        if not rows:
            rows = '<tr><td colspan="4" class="text-center text-muted py-3">No members.</td></tr>'

        add_form = ""
        if is_admin_plus:
            add_form = f"""
            <div class="card p-4 mb-3">
              <div class="section-title"><i class="bi bi-person-plus me-2" style="color:var(--accent)"></i>Add Member by User ID</div>
              <form method="post" action="/app/groups/{group_id}/members/add">
                <div class="row g-2 align-items-end">
                  <div class="col-sm-8">
                    <label class="form-label">User ID</label>
                    <input class="form-control" type="number" name="user_id" placeholder="Enter user ID" required>
                  </div>
                  <div class="col-sm-4">
                    <button type="submit" class="btn-accent w-100"><i class="bi bi-plus-lg me-1"></i>Add</button>
                  </div>
                </div>
              </form>
            </div>"""

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:680px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups/{group_id}" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">{summary.get('group_name','')} — Members</h5>
  </div>
  {alert}
  {add_form}
  <div class="card" style="overflow:hidden">
    <div style="overflow-x:auto">
      <table class="table mb-0">
        <thead><tr><th>Member</th><th>Role</th><th>Joined</th><th>Action</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>
</div>"""
        return _page("Group Members", body)

    @app.post("/app/groups/{group_id}/members/add")
    async def app_group_add_member(
        group_id: int, user_id: int = Form(...),
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "add_group_member", {"group_id": group_id, "user_id": user_id})
        return RedirectResponse(f"/app/groups/{group_id}/members?msg=added", status_code=302)

    @app.post("/app/groups/{group_id}/members/{user_id}/remove")
    async def app_group_remove_member(
        group_id: int, user_id: int,
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "remove_group_member", {"group_id": group_id, "user_id": user_id})
        return RedirectResponse(f"/app/groups/{group_id}/members?msg=removed", status_code=302)

    # ── /app/groups/{id}/archive ──────────────────────────────────────────────
    @app.get("/app/groups/{group_id}/archive")
    async def app_group_archive(
        group_id: int, exp_token: str | None = Cookie(default=None)
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "archive_group", {"group_id": group_id})
        return RedirectResponse("/app/groups?msg=archived", status_code=302)

    # ══════════════════════════════════════════════════════════════════════════
    # INVITE CODE MANAGEMENT (admin/owner only)
    # ══════════════════════════════════════════════════════════════════════════

    @app.get("/app/groups/{group_id}/invite")
    async def app_group_invite(
        group_id: int, request: Request,
        exp_token: str | None = Cookie(default=None), msg: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"
        uid     = profile.get("id")

        summary = await _mcp(token, "get_group_summary", {"group_id": group_id}) or {}
        if "error" in summary:
            return RedirectResponse("/app/groups", status_code=302)

        # RBAC: only admin/owner can view invite code
        sc, members_raw = await _rest(token, "GET", f"/groups/{group_id}/members")
        members_list    = members_raw if isinstance(members_raw, list) else []
        caller_role     = "member"
        for m in members_list:
            if m.get("user_id") == uid:
                caller_role = (m.get("role") or "member").lower()
                break

        if caller_role not in ("owner", "admin"):
            return _page("Access Denied", f"""
{_navbar(uname)}
<div class="page-content" style="max-width:520px">
  <div class="alert-danger-custom">
    <i class="bi bi-lock me-1"></i>
    Only Owners and Admins can view invite codes.
    <a href="/app/groups/{group_id}" class="ms-3">Back to Group</a>
  </div>
</div>""")

        invite_data = await _mcp(token, "get_invite_code", {"group_id": group_id}) or {}
        code        = invite_data.get("invite_code", "—")
        regen_at    = invite_data.get("regenerated_at") or invite_data.get("created_at", "")

        alert = ""
        if msg == "regenerated":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-arrow-repeat me-1"></i>Invite code regenerated. The old code is now invalid.</div>'

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:640px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups/{group_id}" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">{summary.get('group_name','')} — Invite Code</h5>
  </div>
  {alert}
  <div class="card p-5">
    <div class="section-title text-center mb-2">
      <i class="bi bi-key me-2" style="color:var(--accent)"></i>Group Invite Code
    </div>
    <p class="text-muted text-center mb-4" style="font-size:0.85rem">
      Share this code with people you want to invite.
      They'll submit a join request which you must approve.
      Only you and other admins can see this.
    </p>
    <div class="invite-code-box mb-2" onclick="copyCode()" title="Click to copy">{code}</div>
    <p class="text-muted text-center" style="font-size:0.75rem">
      <i class="bi bi-clipboard me-1"></i>Click to copy &nbsp;·&nbsp;
      Last updated: {str(regen_at)[:19] if regen_at else '—'}
    </p>
    <hr class="my-4">
    <div class="d-flex align-items-start gap-3 p-3" style="background:#fffbeb;border-radius:8px;border:1px solid #fde68a">
      <i class="bi bi-exclamation-triangle" style="color:#92400e;margin-top:2px"></i>
      <div style="font-size:0.82rem;color:#92400e">
        <strong>Regenerating</strong> immediately invalidates the current code.
        Anyone who hasn't submitted a join request yet won't be able to use the old code.
      </div>
    </div>
    <form method="post" action="/app/groups/{group_id}/invite/regenerate" class="mt-3">
      <button type="submit" class="btn-outline-accent w-100"
              onclick="return confirm('Regenerate invite code? The current code will stop working immediately.')"
              style="justify-content:center">
        <i class="bi bi-arrow-repeat me-1"></i>Regenerate Code
      </button>
    </form>
  </div>
</div>
<script>
function copyCode() {{
  navigator.clipboard.writeText("{code}").then(() => {{
    const el = document.querySelector('.invite-code-box');
    const orig = el.textContent;
    el.textContent = '✓ Copied!';
    setTimeout(() => el.textContent = orig, 1500);
  }});
}}
</script>"""
        return _page("Invite Code", body)

    @app.post("/app/groups/{group_id}/invite/regenerate")
    async def app_group_invite_regenerate(
        group_id: int, exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "regenerate_invite_code", {"group_id": group_id})
        return RedirectResponse(f"/app/groups/{group_id}/invite?msg=regenerated", status_code=302)

    # ══════════════════════════════════════════════════════════════════════════
    # JOIN REQUEST MANAGEMENT (admin/owner only)
    # ══════════════════════════════════════════════════════════════════════════

    @app.get("/app/groups/{group_id}/requests")
    async def app_group_requests(
        group_id: int, request: Request,
        exp_token: str | None = Cookie(default=None),
        status_filter: str = "pending", msg: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"
        uid     = profile.get("id")

        summary = await _mcp(token, "get_group_summary", {"group_id": group_id}) or {}
        if "error" in summary:
            return RedirectResponse("/app/groups", status_code=302)

        # RBAC check
        sc, members_raw = await _rest(token, "GET", f"/groups/{group_id}/members")
        members_list    = members_raw if isinstance(members_raw, list) else []
        caller_role     = "member"
        for m in members_list:
            if m.get("user_id") == uid:
                caller_role = (m.get("role") or "member").lower()
                break

        if caller_role not in ("owner", "admin"):
            return _page("Access Denied", f"""
{_navbar(uname)}
<div class="page-content" style="max-width:520px">
  <div class="alert-danger-custom"><i class="bi bi-lock me-1"></i>Admins and Owners only.
    <a href="/app/groups/{group_id}" class="ms-3">Back</a>
  </div>
</div>""")

        sc2, reqs_raw = await _rest(
            token, "GET",
            f"/groups/{group_id}/join-requests" + (f"?status={status_filter}" if status_filter else "")
        )
        reqs = reqs_raw if isinstance(reqs_raw, list) else []

        alert = ""
        if msg == "approved":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Request approved.</div>'
        elif msg == "rejected":
            alert = '<div class="alert-danger-custom mb-3"><i class="bi bi-x-circle me-1"></i>Request rejected.</div>'
        elif msg == "bulk_done":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-check-circle me-1"></i>Bulk action applied.</div>'

        rows = ""
        for r in reqs:
            st    = r.get("status", "pending").lower()
            badge = _req_badge(st)
            btns  = ""
            if st == "pending":
                btns = f"""
                <form method="post" action="/app/groups/{group_id}/requests/{r['id']}/approve" class="d-inline me-1">
                  <button type="submit" class="btn btn-sm"
                          style="border:1.5px solid #bbf7d0;color:#15803d;border-radius:7px;font-size:0.78rem;padding:2px 8px">
                    ✓ Approve
                  </button>
                </form>
                <form method="post" action="/app/groups/{group_id}/requests/{r['id']}/reject" class="d-inline">
                  <button type="submit" class="btn btn-sm"
                          style="border:1.5px solid #fecaca;color:#b91c1c;border-radius:7px;font-size:0.78rem;padding:2px 8px">
                    ✗ Reject
                  </button>
                </form>"""
            rows += f"""
            <tr>
              <td style="font-size:0.85rem"><input type="checkbox" class="req-check form-check-input" value="{r['id']}"> User {r.get('user_id','')}</td>
              <td style="font-size:0.8rem;color:var(--muted)">{str(r.get('requested_at',''))[:16]}</td>
              <td>{badge}</td>
              <td style="font-size:0.8rem;color:var(--muted)">{r.get('approved_by') or '—'}</td>
              <td>{btns}</td>
            </tr>"""

        if not rows:
            rows = f'<tr><td colspan="5" class="text-center text-muted py-4">No {status_filter} requests.</td></tr>'

        status_tabs = ""
        for sf, label in [("pending","Pending"),("approved","Approved"),("rejected","Rejected"),("","All")]:
            active = "active" if sf == status_filter else ""
            status_tabs += f'<a href="?status_filter={sf}" class="admin-tab {active}">{label}</a>'

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:800px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups/{group_id}" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">{summary.get('group_name','')} — Join Requests</h5>
  </div>
  {alert}
  <div class="admin-tabs mb-3">{status_tabs}</div>

  <!-- Bulk actions (only on pending) -->
  {"" if status_filter != "pending" else f'''
  <div class="d-flex gap-2 mb-3">
    <form method="post" action="/app/groups/{group_id}/requests/bulk-approve">
      <input type="hidden" name="ids" id="bulk-ids-approve">
      <button type="submit" onclick="return fillBulk('bulk-ids-approve')"
              class="btn btn-sm" style="border:1.5px solid #bbf7d0;color:#15803d;border-radius:7px;font-size:0.82rem;padding:4px 12px">
        ✓ Bulk Approve Selected
      </button>
    </form>
    <form method="post" action="/app/groups/{group_id}/requests/bulk-reject">
      <input type="hidden" name="ids" id="bulk-ids-reject">
      <button type="submit" onclick="return fillBulk('bulk-ids-reject')"
              class="btn btn-sm" style="border:1.5px solid #fecaca;color:#b91c1c;border-radius:7px;font-size:0.82rem;padding:4px 12px">
        ✗ Bulk Reject Selected
      </button>
    </form>
  </div>'''}

  <div class="card" style="overflow:hidden">
    <div style="overflow-x:auto">
      <table class="table mb-0">
        <thead><tr><th>Requester</th><th>Requested At</th><th>Status</th><th>Reviewed By</th><th>Actions</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>
</div>
<script>
function fillBulk(inputId) {{
  const checked = [...document.querySelectorAll('.req-check:checked')].map(c => c.value);
  if (!checked.length) {{ alert('Select at least one request.'); return false; }}
  document.getElementById(inputId).value = checked.join(',');
  return true;
}}
</script>"""
        return _page("Join Requests", body)

    @app.post("/app/groups/{group_id}/requests/{request_id}/approve")
    async def app_group_approve_request(
        group_id: int, request_id: int,
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "approve_join_request", {"group_id": group_id, "join_request_id": request_id})
        return RedirectResponse(f"/app/groups/{group_id}/requests?msg=approved", status_code=302)

    @app.post("/app/groups/{group_id}/requests/{request_id}/reject")
    async def app_group_reject_request(
        group_id: int, request_id: int,
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "reject_join_request",  {"group_id": group_id, "join_request_id": request_id})
        return RedirectResponse(f"/app/groups/{group_id}/requests?msg=rejected", status_code=302)

    @app.post("/app/groups/{group_id}/requests/bulk-approve")
    async def app_group_bulk_approve(
        group_id: int, ids: str = Form(""),
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        for rid in [x.strip() for x in ids.split(",") if x.strip().isdigit()]:
            await _mcp(token, "approve_join_request", {"group_id": group_id, "join_request_id": int(rid)})
        return RedirectResponse(f"/app/groups/{group_id}/requests?msg=bulk_done", status_code=302)

    @app.post("/app/groups/{group_id}/requests/bulk-reject")
    async def app_group_bulk_reject(
        group_id: int, ids: str = Form(""),
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        for rid in [x.strip() for x in ids.split(",") if x.strip().isdigit()]:
            await _mcp(token, "reject_join_request",  {"group_id": group_id, "join_request_id": int(rid)})
        return RedirectResponse(f"/app/groups/{group_id}/requests?msg=bulk_done", status_code=302)

    # ══════════════════════════════════════════════════════════════════════════
    # ROLE MANAGEMENT (admin/owner only)
    # ══════════════════════════════════════════════════════════════════════════

    @app.get("/app/groups/{group_id}/roles")
    async def app_group_roles(
        group_id: int, request: Request,
        exp_token: str | None = Cookie(default=None), msg: str = "",
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"
        uid     = profile.get("id")

        summary = await _mcp(token, "get_group_summary", {"group_id": group_id}) or {}
        if "error" in summary:
            return RedirectResponse("/app/groups", status_code=302)

        sc, members_raw = await _rest(token, "GET", f"/groups/{group_id}/members")
        members         = members_raw if isinstance(members_raw, list) else []
        caller_role     = "member"
        for m in members:
            if m.get("user_id") == uid:
                caller_role = (m.get("role") or "member").lower()
                break

        if caller_role not in ("owner", "admin"):
            return _page("Access Denied", f"""
{_navbar(uname)}
<div class="page-content" style="max-width:520px">
  <div class="alert-danger-custom"><i class="bi bi-lock me-1"></i>Admins and Owners only.
    <a href="/app/groups/{group_id}" class="ms-3">Back</a>
  </div>
</div>""")

        alert = ""
        if msg == "promoted":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-shield-check me-1"></i>Member promoted to Admin.</div>'
        elif msg == "demoted":
            alert = '<div class="alert-warn-custom mb-3"><i class="bi bi-person me-1"></i>Admin demoted to Member.</div>'
        elif msg == "transferred":
            alert = '<div class="alert-success-custom mb-3"><i class="bi bi-crown me-1"></i>Ownership transferred.</div>'

        rows = ""
        for m in members:
            role = (m.get("role") or "member").lower()
            actions = ""

            if caller_role == "owner" and m.get("user_id") != uid:
                if role == "member":
                    actions += f"""
                    <form method="post" action="/app/groups/{group_id}/roles/{m['user_id']}/promote" class="d-inline me-1">
                      <button type="submit" class="btn btn-sm"
                              style="border:1.5px solid #e9d5ff;color:#9333ea;border-radius:7px;font-size:0.78rem;padding:2px 8px">
                        <i class="bi bi-shield-plus"></i> Promote to Admin
                      </button>
                    </form>"""
                elif role == "admin":
                    member_id = m["user_id"]

                    actions += f"""
                    <form method="post" action="/app/groups/{group_id}/roles/{member_id}/transfer" class="d-inline">
                    <button type="submit" class="btn btn-sm"
                            onclick="return confirm('Transfer ownership to User {member_id}? You will become an Admin.')"
                            style="border:1.5px solid #eef2ff;color:#6366f1;border-radius:7px;font-size:0.78rem;padding:2px 8px">
                        <i class="bi bi-crown"></i> Transfer Ownership
                    </button>
                    </form>
                    """

            elif caller_role == "admin" and m.get("user_id") != uid and role == "member":
                # Admins can only promote members (not demote or transfer)
                actions += f"""
                <form method="post" action="/app/groups/{group_id}/roles/{m['user_id']}/promote" class="d-inline me-1">
                  <button type="submit" class="btn btn-sm"
                          style="border:1.5px solid #e9d5ff;color:#9333ea;border-radius:7px;font-size:0.78rem;padding:2px 8px">
                    <i class="bi bi-shield-plus"></i> Promote to Admin
                  </button>
                </form>
                """

            rows += f"""
            <tr>
              <td>
                <div style="width:28px;height:28px;border-radius:50%;background:var(--accent-soft);
                            color:var(--accent);font-size:0.75rem;font-weight:600;
                            display:inline-flex;align-items:center;justify-content:center;
                            margin-right:8px">U</div>
                User {m['user_id']} {"(you)" if m.get("user_id") == uid else ""}
              </td>
              <td>{_role_badge(role)}</td>
              <td style="font-size:0.82rem;color:var(--muted)">{str(m.get('joined_at',''))[:10]}</td>
              <td>{actions}</td>
            </tr>"""

        if not rows:
            rows = '<tr><td colspan="4" class="text-center text-muted py-3">No members.</td></tr>'

        # Role permission summary
        perm_table = """
        <div class="card p-4 mt-4">
          <div class="section-title"><i class="bi bi-shield-lock me-2" style="color:var(--accent)"></i>Role Permissions</div>
          <div style="overflow-x:auto">
            <table class="table mb-0" style="font-size:0.82rem">
              <thead><tr><th>Permission</th><th>Owner</th><th>Admin</th><th>Member</th></tr></thead>
              <tbody>
                <tr><td>Add expenses</td><td>✅</td><td>✅</td><td>✅</td></tr>
                <tr><td>View expenses &amp; settlements</td><td>✅</td><td>✅</td><td>✅</td></tr>
                <tr><td>Approve/reject join requests</td><td>✅</td><td>✅</td><td>❌</td></tr>
                <tr><td>View &amp; regenerate invite code</td><td>✅</td><td>✅</td><td>❌</td></tr>
                <tr><td>Add/remove members</td><td>✅</td><td>✅</td><td>❌</td></tr>
                <tr><td>Promote members to admin</td><td>✅</td><td>✅</td><td>❌</td></tr>
                <tr><td>Demote admins</td><td>✅</td><td>❌</td><td>❌</td></tr>
                <tr><td>Transfer ownership</td><td>✅</td><td>❌</td><td>❌</td></tr>
                <tr><td>Archive group</td><td>✅</td><td>❌</td><td>❌</td></tr>
              </tbody>
            </table>
          </div>
        </div>"""

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:800px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups/{group_id}" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">{summary.get('group_name','')} — Role Management</h5>
  </div>
  {alert}
  <div class="card" style="overflow:hidden">
    <div style="overflow-x:auto">
      <table class="table mb-0">
        <thead><tr><th>Member</th><th>Current Role</th><th>Joined</th><th>Actions</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>
  {perm_table}
</div>"""
        return _page("Role Management", body)

    @app.post("/app/groups/{group_id}/roles/{user_id}/promote")
    async def app_group_promote(
        group_id: int, user_id: int,
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "change_member_role",   {"group_id": group_id, "user_id": user_id, "new_role": "admin"})
        return RedirectResponse(f"/app/groups/{group_id}/roles?msg=promoted", status_code=302)

    @app.post("/app/groups/{group_id}/roles/{user_id}/demote")
    async def app_group_demote(
        group_id: int, user_id: int,
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "change_member_role",   {"group_id": group_id, "user_id": user_id, "new_role": "member"})
        return RedirectResponse(f"/app/groups/{group_id}/roles?msg=demoted", status_code=302)

    @app.post("/app/groups/{group_id}/roles/{user_id}/transfer")
    async def app_group_transfer_ownership(
        group_id: int, user_id: int,
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)
        await _mcp(token, "transfer_ownership",   {"group_id": group_id, "new_owner_user_id": user_id})
        return RedirectResponse(f"/app/groups/{group_id}/roles?msg=transferred", status_code=302)

    # ══════════════════════════════════════════════════════════════════════════
    # AUDIT LOG (admin/owner only)
    # ══════════════════════════════════════════════════════════════════════════

    @app.get("/app/groups/{group_id}/audit")
    async def app_group_audit(
        group_id: int, request: Request,
        exp_token: str | None = Cookie(default=None),
    ):
        token = _tok(exp_token)
        if not token:
            return RedirectResponse("/app/login", status_code=302)

        profile = await _mcp(token, "get_profile", {}) or {}
        uname   = profile.get("nickname") or profile.get("name") or "User"
        uid     = profile.get("id")

        summary = await _mcp(token, "get_group_summary", {"group_id": group_id}) or {}
        if "error" in summary:
            return RedirectResponse("/app/groups", status_code=302)

        sc, members_raw = await _rest(token, "GET", f"/groups/{group_id}/members")
        members_list    = members_raw if isinstance(members_raw, list) else []
        caller_role     = "member"
        for m in members_list:
            if m.get("user_id") == uid:
                caller_role = (m.get("role") or "member").lower()
                break

        if caller_role not in ("owner", "admin"):
            return _page("Access Denied", f"""
{_navbar(uname)}
<div class="page-content" style="max-width:520px">
  <div class="alert-danger-custom"><i class="bi bi-lock me-1"></i>Admins and Owners only.
    <a href="/app/groups/{group_id}" class="ms-3">Back</a>
  </div>
</div>""")

        sc2, logs = await _rest(token, "GET", f"/groups/{group_id}/audit-logs")
        logs = logs if isinstance(logs, list) else []

        # Action type → colour
        ACTION_COLORS = {
            "approve_join":        "#15803d",
            "reject_join":         "#b91c1c",
            "promote_admin":       "#9333ea",
            "demote_admin":        "#92400e",
            "transfer_ownership":  "#6366f1",
            "add_member":          "#15803d",
            "remove_member":       "#b91c1c",
            "regenerate_code":     "#ea580c",
            "archive_group":       "#6b7280",
            "add_expense":         "#0369a1",
        }

        rows = ""
        for log in logs:
            action   = log.get("action_type", "unknown")
            color    = ACTION_COLORS.get(action, "#6b7280")
            rows += f"""
            <div class="audit-row">
              <div class="audit-dot" style="background:{color}"></div>
              <div style="flex:1">
                <span style="font-weight:500;color:{color}">{action.replace('_',' ').title()}</span>
                <span class="text-muted mx-2">·</span>
                <span>by User {log.get('performed_by','?')}</span>
                {f'<span class="text-muted mx-1">→</span> User {log["target_user"]}' if log.get("target_user") else ""}
              </div>
              <div style="font-size:0.78rem;color:var(--muted);white-space:nowrap">
                {str(log.get('timestamp',''))[:16]}
              </div>
            </div>"""

        if not rows:
            rows = '<div class="text-center text-muted py-4"><i class="bi bi-clock-history" style="font-size:2rem;opacity:0.3"></i><p class="mt-2">No audit events yet.</p></div>'

        body = f"""
{_navbar(uname)}
<div class="page-content" style="max-width:760px">
  <div class="d-flex align-items-center gap-2 mb-4">
    <a href="/app/groups/{group_id}" class="text-muted" style="font-size:0.85rem"><i class="bi bi-arrow-left"></i> Back</a>
    <span class="text-muted">/</span>
    <h5 class="mb-0 fw-semibold">{summary.get('group_name','')} — Audit Log</h5>
  </div>
  <div class="card p-4">
    <div class="section-title"><i class="bi bi-clock-history me-2" style="color:var(--accent)"></i>All Admin Actions</div>
    <div style="border:1px solid var(--border);border-radius:8px;overflow:hidden">
      {rows}
    </div>
  </div>
</div>"""
        return _page("Audit Log", body)

    # ══════════════════════════════════════════════════════════════════════════
    # /app/ redirect
    # ══════════════════════════════════════════════════════════════════════════

    @app.get("/app/")
    async def app_root_slash(exp_token: str | None = Cookie(default=None)):
        if not exp_token:
            return RedirectResponse("/app/login", status_code=302)
        return RedirectResponse("/app", status_code=302)