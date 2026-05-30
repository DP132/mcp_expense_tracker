# import asyncio
# import json
# import secrets
# import urllib.parse
# import logging
# import hashlib
# import hmac
# from datetime import datetime, timedelta
# from contextlib import asynccontextmanager
# from typing import Optional

# from fastapi import FastAPI, Depends, HTTPException, Request, Form
# from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse
# from sqlalchemy.orm import Session
# from sqlalchemy import extract
# from pydantic import BaseModel, ConfigDict
# from datetime import date

# from db import Expense, User, OAuthClient, AuthCode, AccessToken, get_db, init_db

# # ─── Logging ──────────────────────────────────────────────────────────────────
# logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
# log = logging.getLogger("expense-mcp")


# # ─── Password Hashing ─────────────────────────────────────────────────────────

# def hash_password(password: str) -> str:
#     salt = secrets.token_hex(16)
#     hashed = hashlib.sha256((salt + password).encode()).hexdigest()
#     return f"{salt}:{hashed}"

# def verify_password(password: str, hashed: str) -> bool:
#     try:
#         salt, stored_hash = hashed.split(":")
#         return hmac.compare_digest(
#             hashlib.sha256((salt + password).encode()).hexdigest(),
#             stored_hash
#         )
#     except Exception:
#         return False


# # ─── DB-backed OAuth Helpers ──────────────────────────────────────────────────

# def store_client(client_id: str, client_secret: str, redirect_uris: list):
#     db = next(get_db())
#     try:
#         existing = db.query(OAuthClient).filter(OAuthClient.client_id == client_id).first()
#         if existing:
#             existing.client_secret = client_secret
#             existing.redirect_uris = json.dumps(redirect_uris)
#         else:
#             db.add(OAuthClient(
#                 client_id=client_id,
#                 client_secret=client_secret,
#                 redirect_uris=json.dumps(redirect_uris),
#             ))
#         db.commit()
#     finally:
#         db.close()

# def store_auth_code(code: str, user_id: int, client_id: str, redirect_uri: str,
#                     code_challenge: str, code_challenge_method: str):
#     db = next(get_db())
#     try:
#         db.add(AuthCode(
#             code=code, user_id=user_id, client_id=client_id,
#             redirect_uri=redirect_uri, code_challenge=code_challenge,
#             code_challenge_method=code_challenge_method,
#             expires_at=datetime.utcnow() + timedelta(minutes=10),
#         ))
#         db.commit()
#     finally:
#         db.close()

# def get_auth_code(code: str) -> Optional[dict]:
#     db = next(get_db())
#     try:
#         row = db.query(AuthCode).filter(AuthCode.code == code).first()
#         if not row:
#             return None
#         return {
#             "user_id":               row.user_id,
#             "client_id":             row.client_id,
#             "redirect_uri":          row.redirect_uri,
#             "code_challenge":        row.code_challenge,
#             "code_challenge_method": row.code_challenge_method,
#             "expires_at":            row.expires_at,
#         }
#     finally:
#         db.close()

# def delete_auth_code(code: str):
#     db = next(get_db())
#     try:
#         db.query(AuthCode).filter(AuthCode.code == code).delete()
#         db.commit()
#     finally:
#         db.close()

# def store_access_token(token: str, user_id: int, client_id: str):
#     db = next(get_db())
#     try:
#         db.add(AccessToken(
#             token=token, user_id=user_id, client_id=client_id,
#             expires_at=datetime.utcnow() + timedelta(hours=24),
#         ))
#         db.commit()
#     finally:
#         db.close()

# def get_access_token(token: str) -> Optional[dict]:
#     db = next(get_db())
#     try:
#         row = db.query(AccessToken).filter(AccessToken.token == token).first()
#         if not row:
#             return None
#         return {
#             "user_id":    row.user_id,
#             "client_id":  row.client_id,
#             "expires_at": row.expires_at,
#         }
#     finally:
#         db.close()

# def delete_access_token(token: str):
#     db = next(get_db())
#     try:
#         db.query(AccessToken).filter(AccessToken.token == token).delete()
#         db.commit()
#     finally:
#         db.close()


# # ─── App Lifespan ─────────────────────────────────────────────────────────────

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     init_db()
#     yield

# app = FastAPI(title="Expense Tracker API", lifespan=lifespan)


# # ─── Pydantic Schemas ─────────────────────────────────────────────────────────

# class UserCreate(BaseModel):
#     name: str
#     nickname: Optional[str] = None
#     email: str
#     phone: Optional[str] = None
#     password: str

# class UserOut(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     id: int
#     name: str
#     nickname: Optional[str]
#     email: str
#     phone: Optional[str]

# class ExpenseCreate(BaseModel):
#     amount: float
#     category: str
#     date: date
#     description: Optional[str] = None
#     tags: Optional[str] = None
#     is_recurring: bool = False
#     payment_method: Optional[str] = None

# class ExpenseUpdate(BaseModel):
#     amount: Optional[float] = None
#     category: Optional[str] = None
#     date: Optional[date] = None
#     description: Optional[str] = None
#     tags: Optional[str] = None
#     is_recurring: Optional[bool] = None
#     payment_method: Optional[str] = None

# class ExpenseOut(ExpenseCreate):
#     model_config = ConfigDict(from_attributes=True)
#     id: int
#     user_id: int


# # ─── MCP Tools ────────────────────────────────────────────────────────────────

# MCP_TOOLS = [
#     {
#         "name": "create_expense",
#         "description": "Create a new expense record for the authenticated user.",
#         "inputSchema": {
#             "type": "object",
#             "properties": {
#                 "amount":         {"type": "number",  "description": "Amount in INR"},
#                 "category":       {"type": "string",  "description": "Food, Transport, Shopping, Health, Utilities, Entertainment, Other"},
#                 "date":           {"type": "string",  "description": "Date in YYYY-MM-DD format"},
#                 "description":    {"type": "string",  "description": "Optional description"},
#                 "tags":           {"type": "string",  "description": "Comma-separated tags"},
#                 "is_recurring":   {"type": "boolean", "description": "True if recurring"},
#                 "payment_method": {"type": "string",  "description": "Cash, Credit Card, Debit Card, UPI, Net Banking, Other"},
#             },
#             "required": ["amount", "category", "date"],
#         },
#     },
#     {
#         "name": "list_expenses",
#         "description": "List expenses for the authenticated user with optional filters.",
#         "inputSchema": {
#             "type": "object",
#             "properties": {
#                 "category":       {"type": "string"},
#                 "payment_method": {"type": "string"},
#                 "is_recurring":   {"type": "boolean"},
#                 "month":          {"type": "integer", "description": "1-12"},
#                 "year":           {"type": "integer"},
#             },
#         },
#     },
#     {
#         "name": "get_expense",
#         "description": "Get a single expense by ID.",
#         "inputSchema": {
#             "type": "object",
#             "properties": {"expense_id": {"type": "integer"}},
#             "required": ["expense_id"],
#         },
#     },
#     {
#         "name": "update_expense",
#         "description": "Update an existing expense by ID.",
#         "inputSchema": {
#             "type": "object",
#             "properties": {
#                 "expense_id":     {"type": "integer"},
#                 "amount":         {"type": "number"},
#                 "category":       {"type": "string"},
#                 "date":           {"type": "string"},
#                 "description":    {"type": "string"},
#                 "tags":           {"type": "string"},
#                 "is_recurring":   {"type": "boolean"},
#                 "payment_method": {"type": "string"},
#             },
#             "required": ["expense_id"],
#         },
#     },
#     {
#         "name": "delete_expense",
#         "description": "Delete an expense by ID.",
#         "inputSchema": {
#             "type": "object",
#             "properties": {"expense_id": {"type": "integer"}},
#             "required": ["expense_id"],
#         },
#     },
#     {
#         "name": "get_summary",
#         "description": "Get total spend, count, breakdown by category and payment method for the authenticated user.",
#         "inputSchema": {"type": "object", "properties": {}},
#     },
#     {
#         "name": "get_profile",
#         "description": "Get the authenticated user's profile.",
#         "inputSchema": {"type": "object", "properties": {}},
#     },
# ]


# # ─── Tool Executor ────────────────────────────────────────────────────────────

# def run_tool(name: str, arguments: dict, user_id: int) -> dict:
#     db = next(get_db())
#     try:
#         if name == "create_expense":
#             expense = Expense(
#                 user_id=user_id,
#                 amount=arguments["amount"],
#                 category=arguments["category"],
#                 date=arguments["date"],
#                 description=arguments.get("description"),
#                 tags=arguments.get("tags"),
#                 is_recurring=arguments.get("is_recurring", False),
#                 payment_method=arguments.get("payment_method"),
#             )
#             db.add(expense)
#             db.commit()
#             db.refresh(expense)
#             return _expense_dict(expense)

#         elif name == "list_expenses":
#             q = db.query(Expense).filter(Expense.user_id == user_id)
#             if arguments.get("category"):
#                 q = q.filter(Expense.category == arguments["category"])
#             if arguments.get("payment_method"):
#                 q = q.filter(Expense.payment_method == arguments["payment_method"])
#             if arguments.get("is_recurring") is not None:
#                 q = q.filter(Expense.is_recurring == arguments["is_recurring"])
#             if arguments.get("month"):
#                 q = q.filter(extract("month", Expense.date) == arguments["month"])
#             if arguments.get("year"):
#                 q = q.filter(extract("year", Expense.date) == arguments["year"])
#             return {"expenses": [_expense_dict(e) for e in q.order_by(Expense.date.desc()).all()]}

#         elif name == "get_expense":
#             e = db.query(Expense).filter(
#                 Expense.id == arguments["expense_id"],
#                 Expense.user_id == user_id
#             ).first()
#             return _expense_dict(e) if e else {"error": "Expense not found"}

#         elif name == "update_expense":
#             e = db.query(Expense).filter(
#                 Expense.id == arguments["expense_id"],
#                 Expense.user_id == user_id
#             ).first()
#             if not e:
#                 return {"error": "Expense not found"}
#             for field in ["amount", "category", "date", "description", "tags", "is_recurring", "payment_method"]:
#                 if field in arguments:
#                     setattr(e, field, arguments[field])
#             db.commit()
#             db.refresh(e)
#             return _expense_dict(e)

#         elif name == "delete_expense":
#             e = db.query(Expense).filter(
#                 Expense.id == arguments["expense_id"],
#                 Expense.user_id == user_id
#             ).first()
#             if not e:
#                 return {"error": "Expense not found"}
#             db.delete(e)
#             db.commit()
#             return {"success": True, "deleted_id": arguments["expense_id"]}

#         elif name == "get_summary":
#             expenses = db.query(Expense).filter(Expense.user_id == user_id).all()
#             total = sum(e.amount for e in expenses)
#             by_cat, by_pay = {}, {}
#             for e in expenses:
#                 by_cat[e.category] = by_cat.get(e.category, 0) + e.amount
#                 if e.payment_method:
#                     by_pay[e.payment_method] = by_pay.get(e.payment_method, 0) + e.amount
#             return {
#                 "total":              round(total, 2),
#                 "count":              len(expenses),
#                 "by_category":        {k: round(v, 2) for k, v in by_cat.items()},
#                 "by_payment_method":  {k: round(v, 2) for k, v in by_pay.items()},
#             }

#         elif name == "get_profile":
#             user = db.query(User).filter(User.id == user_id).first()
#             if not user:
#                 return {"error": "User not found"}
#             return {
#                 "id": user.id, "name": user.name, "nickname": user.nickname,
#                 "email": user.email, "phone": user.phone,
#             }

#         return {"error": f"Unknown tool: {name}"}
#     finally:
#         db.close()


# def _expense_dict(e) -> dict:
#     return {
#         "id": e.id, "user_id": e.user_id, "amount": e.amount,
#         "category": e.category, "date": str(e.date), "description": e.description,
#         "tags": e.tags, "is_recurring": e.is_recurring, "payment_method": e.payment_method,
#     }


# # ─── OAuth Discovery ──────────────────────────────────────────────────────────

# @app.get("/.well-known/oauth-protected-resource")
# def oauth_protected_resource(request: Request):
#     base = str(request.base_url).rstrip("/")
#     log.info(f"[OAUTH] oauth-protected-resource | base={base}")
#     return {"resource": base, "authorization_servers": [base]}

# @app.get("/.well-known/oauth-authorization-server")
# def oauth_authorization_server(request: Request):
#     base = str(request.base_url).rstrip("/")
#     log.info(f"[OAUTH] oauth-authorization-server | base={base}")
#     return {
#         "issuer":                                base,
#         "authorization_endpoint":                f"{base}/oauth/authorize",
#         "token_endpoint":                        f"{base}/oauth/token",
#         "registration_endpoint":                 f"{base}/register",
#         "response_types_supported":              ["code"],
#         "grant_types_supported":                 ["authorization_code"],
#         "token_endpoint_auth_methods_supported": ["none"],
#         "code_challenge_methods_supported":      ["S256", "plain"],
#         "scopes_supported":                      ["mcp"],
#     }

# @app.post("/register")
# async def oauth_register(request: Request):
#     body = await request.json()
#     log.info(f"[OAUTH] /register | body={json.dumps(body)}")
#     client_id     = secrets.token_urlsafe(16)
#     client_secret = secrets.token_urlsafe(32)
#     store_client(client_id, client_secret, body.get("redirect_uris", []))
#     log.info(f"[OAUTH] Registered client_id={client_id}")
#     return {
#         "client_id":                client_id,
#         "client_secret":            client_secret,
#         "redirect_uris":            body.get("redirect_uris", []),
#         "grant_types":              ["authorization_code"],
#         "response_types":           ["code"],
#         "token_endpoint_auth_method": "none",
#     }


# # ─── Authorization: Login + Allow/Deny page ───────────────────────────────────

# @app.get("/oauth/authorize")
# async def oauth_authorize(
#     request: Request,
#     client_id: str = "", redirect_uri: str = "", state: str = "",
#     code_challenge: str = "", code_challenge_method: str = "S256",
#     scope: str = "mcp", response_type: str = "code",
# ):
#     log.info(f"[OAUTH] /oauth/authorize | client_id={client_id} redirect_uri={redirect_uri}")
#     html = f"""<!DOCTYPE html>
# <html>
# <head>
#     <title>Expense Tracker — Sign In</title>
#     <style>
#         * {{ box-sizing: border-box; margin: 0; padding: 0; }}
#         body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
#         .card {{ background: white; border-radius: 16px; padding: 40px; width: 380px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); }}
#         .logo {{ font-size: 36px; text-align: center; margin-bottom: 8px; }}
#         h2 {{ text-align: center; color: #111; font-size: 20px; margin-bottom: 4px; }}
#         .subtitle {{ text-align: center; color: #666; font-size: 14px; margin-bottom: 28px; }}
#         label {{ display: block; font-size: 13px; font-weight: 600; color: #444; margin-bottom: 6px; }}
#         input {{ width: 100%; padding: 10px 14px; border: 1.5px solid #ddd; border-radius: 8px; font-size: 14px; margin-bottom: 16px; outline: none; transition: border 0.2s; }}
#         input:focus {{ border-color: #4f46e5; }}
#         .btn-row {{ display: flex; gap: 10px; margin-top: 8px; }}
#         button {{ flex: 1; padding: 11px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; border: none; transition: opacity 0.2s; }}
#         button:hover {{ opacity: 0.88; }}
#         .allow {{ background: #4f46e5; color: white; }}
#         .deny  {{ background: #f3f4f6; color: #374151; }}
#         .register-link {{ text-align: center; margin-top: 20px; font-size: 13px; color: #666; }}
#         .register-link a {{ color: #4f46e5; text-decoration: none; font-weight: 600; }}
#         .divider {{ border: none; border-top: 1px solid #e5e7eb; margin: 20px 0; }}
#     </style>
# </head>
# <body>
# <div class="card">
#     <div class="logo">💸</div>
#     <h2>Expense Tracker</h2>
#     <p class="subtitle">Sign in to allow <strong>Claude</strong> to access your expenses</p>
#     <hr class="divider">
#     <form method="post" action="/oauth/login">
#         <input type="hidden" name="client_id"             value="{client_id}">
#         <input type="hidden" name="redirect_uri"          value="{redirect_uri}">
#         <input type="hidden" name="state"                 value="{state}">
#         <input type="hidden" name="code_challenge"        value="{code_challenge}">
#         <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
#         <label>Email</label>
#         <input type="email" name="email" placeholder="you@example.com" required autofocus>
#         <label>Password</label>
#         <input type="password" name="password" placeholder="••••••••" required>
#         <div class="btn-row">
#             <button class="allow" type="submit" name="action" value="allow">✅ Sign In & Allow</button>
#             <button class="deny"  type="submit" name="action" value="deny">❌ Deny</button>
#         </div>
#     </form>
#     <p class="register-link">No account? <a href="/register-user?redirect_uri={urllib.parse.quote(redirect_uri)}&client_id={client_id}&state={state}&code_challenge={code_challenge}&code_challenge_method={code_challenge_method}">Create one</a></p>
# </div>
# </body>
# </html>"""
#     return HTMLResponse(content=html)


# @app.post("/oauth/login")
# async def oauth_login(
#     client_id: str             = Form(...),
#     redirect_uri: str          = Form(...),
#     state: str                 = Form(""),
#     code_challenge: str        = Form(""),
#     code_challenge_method: str = Form("S256"),
#     action: str                = Form(...),
#     email: str                 = Form(""),
#     password: str              = Form(""),
# ):
#     log.info(f"[OAUTH] /oauth/login | action={action} email={email}")

#     if action == "deny":
#         params = urllib.parse.urlencode({"error": "access_denied", "state": state})
#         return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=302)

#     db = next(get_db())
#     try:
#         user = db.query(User).filter(User.email == email).first()
#         if not user or not verify_password(password, user.hashed_password):
#             log.warning(f"[OAUTH] Login failed for email={email}")
#             error_html = f"""<!DOCTYPE html>
# <html>
# <head>
#     <title>Expense Tracker — Sign In</title>
#     <style>
#         * {{ box-sizing: border-box; margin: 0; padding: 0; }}
#         body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
#         .card {{ background: white; border-radius: 16px; padding: 40px; width: 380px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); }}
#         .logo {{ font-size: 36px; text-align: center; margin-bottom: 8px; }}
#         h2 {{ text-align: center; color: #111; font-size: 20px; margin-bottom: 4px; }}
#         .subtitle {{ text-align: center; color: #666; font-size: 14px; margin-bottom: 28px; }}
#         label {{ display: block; font-size: 13px; font-weight: 600; color: #444; margin-bottom: 6px; }}
#         input {{ width: 100%; padding: 10px 14px; border: 1.5px solid #ddd; border-radius: 8px; font-size: 14px; margin-bottom: 16px; outline: none; }}
#         input:focus {{ border-color: #4f46e5; }}
#         .error {{ background: #fee2e2; color: #dc2626; padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 16px; }}
#         .btn-row {{ display: flex; gap: 10px; margin-top: 8px; }}
#         button {{ flex: 1; padding: 11px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; border: none; }}
#         .allow {{ background: #4f46e5; color: white; }}
#         .deny  {{ background: #f3f4f6; color: #374151; }}
#         .register-link {{ text-align: center; margin-top: 20px; font-size: 13px; color: #666; }}
#         .register-link a {{ color: #4f46e5; text-decoration: none; font-weight: 600; }}
#         .divider {{ border: none; border-top: 1px solid #e5e7eb; margin: 20px 0; }}
#     </style>
# </head>
# <body>
# <div class="card">
#     <div class="logo">💸</div>
#     <h2>Expense Tracker</h2>
#     <p class="subtitle">Sign in to allow <strong>Claude</strong> to access your expenses</p>
#     <hr class="divider">
#     <div class="error">❌ Invalid email or password. Please try again.</div>
#     <form method="post" action="/oauth/login">
#         <input type="hidden" name="client_id"             value="{client_id}">
#         <input type="hidden" name="redirect_uri"          value="{redirect_uri}">
#         <input type="hidden" name="state"                 value="{state}">
#         <input type="hidden" name="code_challenge"        value="{code_challenge}">
#         <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
#         <label>Email</label>
#         <input type="email" name="email" value="{email}" required autofocus>
#         <label>Password</label>
#         <input type="password" name="password" required>
#         <div class="btn-row">
#             <button class="allow" type="submit" name="action" value="allow">✅ Sign In & Allow</button>
#             <button class="deny"  type="submit" name="action" value="deny">❌ Deny</button>
#         </div>
#     </form>
#     <p class="register-link">No account? <a href="/register-user?redirect_uri={urllib.parse.quote(redirect_uri)}&client_id={client_id}&state={state}&code_challenge={code_challenge}&code_challenge_method={code_challenge_method}">Create one</a></p>
# </div>
# </body>
# </html>"""
#             return HTMLResponse(content=error_html, status_code=200)

#         code = secrets.token_urlsafe(32)
#         store_auth_code(code, user.id, client_id, redirect_uri, code_challenge, code_challenge_method)
#         log.info(f"[OAUTH] Login success user_id={user.id} email={email} code={code[:10]}...")
#         params = urllib.parse.urlencode({"code": code, "state": state})
#         return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=302)
#     finally:
#         db.close()


# # ─── User Registration Page ───────────────────────────────────────────────────

# @app.get("/register-user")
# async def register_user_page(
#     redirect_uri: str = "", client_id: str = "", state: str = "",
#     code_challenge: str = "", code_challenge_method: str = "S256",
#     error: str = "",
# ):
#     error_html = f'<div class="error">❌ {error}</div>' if error else ""
#     html = f"""<!DOCTYPE html>
# <html>
# <head>
#     <title>Expense Tracker — Create Account</title>
#     <style>
#         * {{ box-sizing: border-box; margin: 0; padding: 0; }}
#         body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }}
#         .card {{ background: white; border-radius: 16px; padding: 40px; width: 420px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); }}
#         .logo {{ font-size: 36px; text-align: center; margin-bottom: 8px; }}
#         h2 {{ text-align: center; color: #111; font-size: 20px; margin-bottom: 4px; }}
#         .subtitle {{ text-align: center; color: #666; font-size: 14px; margin-bottom: 24px; }}
#         label {{ display: block; font-size: 13px; font-weight: 600; color: #444; margin-bottom: 5px; }}
#         input {{ width: 100%; padding: 10px 14px; border: 1.5px solid #ddd; border-radius: 8px; font-size: 14px; margin-bottom: 14px; outline: none; transition: border 0.2s; }}
#         input:focus {{ border-color: #4f46e5; }}
#         .error {{ background: #fee2e2; color: #dc2626; padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 14px; }}
#         .optional {{ color: #9ca3af; font-weight: 400; }}
#         button {{ width: 100%; padding: 12px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; border: none; background: #4f46e5; color: white; margin-top: 4px; }}
#         button:hover {{ opacity: 0.88; }}
#         .login-link {{ text-align: center; margin-top: 18px; font-size: 13px; color: #666; }}
#         .login-link a {{ color: #4f46e5; text-decoration: none; font-weight: 600; }}
#         .divider {{ border: none; border-top: 1px solid #e5e7eb; margin: 18px 0; }}
#     </style>
# </head>
# <body>
# <div class="card">
#     <div class="logo">💸</div>
#     <h2>Create Account</h2>
#     <p class="subtitle">Sign up to use Expense Tracker with Claude</p>
#     <hr class="divider">
#     {error_html}
#     <form method="post" action="/register-user">
#         <input type="hidden" name="redirect_uri"          value="{redirect_uri}">
#         <input type="hidden" name="client_id"             value="{client_id}">
#         <input type="hidden" name="state"                 value="{state}">
#         <input type="hidden" name="code_challenge"        value="{code_challenge}">
#         <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
#         <label>Full Name</label>
#         <input type="text" name="name" placeholder="John Doe" required>
#         <label>Nickname <span class="optional">(optional)</span></label>
#         <input type="text" name="nickname" placeholder="Johnny">
#         <label>Email</label>
#         <input type="email" name="email" placeholder="you@example.com" required>
#         <label>Phone <span class="optional">(optional)</span></label>
#         <input type="tel" name="phone" placeholder="+91 9999999999">
#         <label>Password</label>
#         <input type="password" name="password" placeholder="Min 8 characters" required minlength="8">
#         <button type="submit">🚀 Create Account & Continue</button>
#     </form>
#     <p class="login-link">Already have an account? <a href="/oauth/authorize?client_id={client_id}&redirect_uri={urllib.parse.quote(redirect_uri)}&state={state}&code_challenge={code_challenge}&code_challenge_method={code_challenge_method}">Sign in</a></p>
# </div>
# </body>
# </html>"""
#     return HTMLResponse(content=html)


# @app.post("/register-user")
# async def register_user_submit(
#     name: str                  = Form(...),
#     email: str                 = Form(...),
#     password: str              = Form(...),
#     nickname: str              = Form(""),
#     phone: str                 = Form(""),
#     redirect_uri: str          = Form(...),
#     client_id: str             = Form(...),
#     state: str                 = Form(""),
#     code_challenge: str        = Form(""),
#     code_challenge_method: str = Form("S256"),
# ):
#     log.info(f"[AUTH] Register user email={email}")
#     db = next(get_db())
#     try:
#         existing = db.query(User).filter(User.email == email).first()
#         if existing:
#             log.warning(f"[AUTH] Email already registered: {email}")
#             error_params = urllib.parse.urlencode({
#                 "redirect_uri": redirect_uri, "client_id": client_id, "state": state,
#                 "code_challenge": code_challenge, "code_challenge_method": code_challenge_method,
#                 "error": "Email already registered.",
#             })
#             return RedirectResponse(url=f"/register-user?{error_params}", status_code=302)

#         if len(password) < 8:
#             error_params = urllib.parse.urlencode({
#                 "redirect_uri": redirect_uri, "client_id": client_id, "state": state,
#                 "code_challenge": code_challenge, "code_challenge_method": code_challenge_method,
#                 "error": "Password must be at least 8 characters.",
#             })
#             return RedirectResponse(url=f"/register-user?{error_params}", status_code=302)

#         user = User(
#             name=name, nickname=nickname or None, email=email,
#             phone=phone or None, hashed_password=hash_password(password),
#         )
#         db.add(user)
#         db.commit()
#         db.refresh(user)
#         log.info(f"[AUTH] User created user_id={user.id} email={email}")

#         code = secrets.token_urlsafe(32)
#         store_auth_code(code, user.id, client_id, redirect_uri, code_challenge, code_challenge_method)
#         log.info(f"[AUTH] Auto-login after register user_id={user.id} code={code[:10]}...")
#         params = urllib.parse.urlencode({"code": code, "state": state})
#         return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=302)
#     finally:
#         db.close()


# # ─── Token Endpoint ───────────────────────────────────────────────────────────

# @app.post("/oauth/token")
# async def oauth_token(request: Request):
#     content_type = request.headers.get("content-type", "")
#     raw_body = await request.body()
#     log.info(f"[OAUTH] /oauth/token | raw={raw_body.decode()[:300]}")

#     if "application/json" in content_type:
#         body = json.loads(raw_body)
#     else:
#         form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
#         body = {k: v[0] for k, v in form.items()}

#     log.info(f"[OAUTH] /oauth/token parsed={json.dumps(body)}")

#     grant_type = body.get("grant_type")
#     code       = body.get("code")

#     if grant_type != "authorization_code":
#         log.error(f"[OAUTH] unsupported grant_type={grant_type}")
#         raise HTTPException(status_code=400, detail={"error": "unsupported_grant_type"})

#     code_data = get_auth_code(code)
#     log.info(f"[OAUTH] Looking up code={code[:10] if code else 'NONE'}... found={code_data is not None}")

#     if not code_data:
#         log.error("[OAUTH] invalid_grant — code not found")
#         raise HTTPException(status_code=400, detail={"error": "invalid_grant"})

#     if datetime.utcnow() > code_data["expires_at"]:
#         delete_auth_code(code)
#         log.error("[OAUTH] invalid_grant — code expired")
#         raise HTTPException(status_code=400, detail={"error": "invalid_grant", "error_description": "code expired"})

#     access_token = secrets.token_urlsafe(32)
#     store_access_token(access_token, code_data["user_id"], code_data["client_id"])
#     delete_auth_code(code)
#     log.info(f"[OAUTH] Token issued: {access_token[:10]}... user_id={code_data['user_id']}")

#     return {"access_token": access_token, "token_type": "bearer", "expires_in": 86400, "scope": "mcp"}


# # ─── Token Validation ─────────────────────────────────────────────────────────

# def _get_token(request: Request) -> Optional[str]:
#     auth = request.headers.get("authorization", "")
#     log.debug(f"[MCP] Auth header: {auth[:40] if auth else 'MISSING'}")
#     if auth.lower().startswith("bearer "):
#         return auth[7:]
#     return None

# def _validate_token(token: Optional[str]) -> Optional[int]:
#     if not token:
#         log.warning("[MCP] No token")
#         return None
#     data = get_access_token(token)
#     if not data:
#         log.warning(f"[MCP] Token not found: {token[:10]}...")
#         return None
#     if datetime.utcnow() > data["expires_at"]:
#         delete_access_token(token)
#         log.warning("[MCP] Token expired")
#         return None
#     log.info(f"[MCP] Token valid — user_id={data['user_id']}")
#     return data["user_id"]


# # ─── MCP Endpoints ────────────────────────────────────────────────────────────

# async def _handle_mcp(msg: dict, user_id: int) -> dict:
#     method = msg.get("method")
#     msg_id = msg.get("id")
#     params = msg.get("params", {})
#     log.info(f"[MCP] method={method} id={msg_id} user_id={user_id}")

#     if method == "initialize":
#         return {"jsonrpc": "2.0", "id": msg_id, "result": {
#             "protocolVersion": "2024-11-05",
#             "serverInfo": {"name": "expense-tracker", "version": "1.0.0"},
#             "capabilities": {"tools": {}},
#         }}
#     elif method == "tools/list":
#         return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": MCP_TOOLS}}
#     elif method == "tools/call":
#         tool_name = params.get("name")
#         arguments  = params.get("arguments", {})
#         log.info(f"[MCP] tools/call name={tool_name} user_id={user_id}")
#         result = run_tool(tool_name, arguments, user_id)
#         return {"jsonrpc": "2.0", "id": msg_id, "result": {
#             "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
#         }}
#     elif method == "ping":
#         return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

#     log.warning(f"[MCP] Unknown method: {method}")
#     return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


# @app.post("/")
# async def root_post(request: Request):
#     token   = _get_token(request)
#     user_id = _validate_token(token)
#     if not user_id:
#         raise HTTPException(status_code=401, detail="Unauthorized",
#                             headers={"WWW-Authenticate": 'Bearer realm="expense-tracker"'})
#     body = await request.json()
#     log.info(f"[MCP] POST / method={body.get('method')} user_id={user_id}")
#     return await _handle_mcp(body, user_id)


# @app.get("/")
# async def root_get(request: Request):
#     token   = _get_token(request)
#     user_id = _validate_token(token)
#     if user_id:
#         async def event_stream():
#             yield _sse({"jsonrpc": "2.0", "method": "notifications/initialized",
#                         "params": {"serverInfo": {"name": "expense-tracker", "version": "1.0.0"},
#                                    "capabilities": {"tools": {}}}})
#             async for chunk in request.stream():
#                 if not chunk: continue
#                 try:
#                     msg = json.loads(chunk)
#                     response = await _handle_mcp(msg, user_id)
#                     if response: yield _sse(response)
#                 except Exception as e:
#                     log.error(f"[MCP] SSE error: {e}")
#                     yield _sse({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}, "id": None})
#         return StreamingResponse(event_stream(), media_type="text/event-stream",
#                                  headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
#     return {"status": "ok", "message": "Expense Tracker API running"}


# def _sse(data: dict) -> str:
#     return f"data: {json.dumps(data)}\n\n"


# # ─── REST Routes ──────────────────────────────────────────────────────────────

# @app.post("/users", response_model=UserOut, status_code=201)
# def create_user(payload: UserCreate, db: Session = Depends(get_db)):
#     if db.query(User).filter(User.email == payload.email).first():
#         raise HTTPException(status_code=400, detail="Email already registered")
#     user = User(
#         name=payload.name, nickname=payload.nickname, email=payload.email,
#         phone=payload.phone, hashed_password=hash_password(payload.password),
#     )
#     db.add(user); db.commit(); db.refresh(user)
#     return user

# @app.post("/expenses", response_model=ExpenseOut, status_code=201)
# def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)):
#     expense = Expense(**payload.model_dump(), user_id=1)
#     db.add(expense); db.commit(); db.refresh(expense)
#     return expense

# @app.get("/expenses", response_model=list[ExpenseOut])
# def list_expenses(
#     category: Optional[str] = None, payment_method: Optional[str] = None,
#     is_recurring: Optional[bool] = None, month: Optional[int] = None,
#     year: Optional[int] = None, db: Session = Depends(get_db),
# ):
#     q = db.query(Expense)
#     if category:        q = q.filter(Expense.category == category)
#     if payment_method:  q = q.filter(Expense.payment_method == payment_method)
#     if is_recurring is not None: q = q.filter(Expense.is_recurring == is_recurring)
#     if month:           q = q.filter(extract("month", Expense.date) == month)
#     if year:            q = q.filter(extract("year", Expense.date) == year)
#     return q.order_by(Expense.date.desc()).all()

# @app.get("/expenses/{expense_id}", response_model=ExpenseOut)
# def get_expense(expense_id: int, db: Session = Depends(get_db)):
#     e = db.query(Expense).filter(Expense.id == expense_id).first()
#     if not e: raise HTTPException(status_code=404, detail="Expense not found")
#     return e

# @app.put("/expenses/{expense_id}", response_model=ExpenseOut)
# def update_expense(expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)):
#     e = db.query(Expense).filter(Expense.id == expense_id).first()
#     if not e: raise HTTPException(status_code=404, detail="Expense not found")
#     for field, value in payload.model_dump(exclude_unset=True).items():
#         setattr(e, field, value)
#     db.commit(); db.refresh(e)
#     return e

# @app.delete("/expenses/{expense_id}", status_code=204)
# def delete_expense(expense_id: int, db: Session = Depends(get_db)):
#     e = db.query(Expense).filter(Expense.id == expense_id).first()
#     if not e: raise HTTPException(status_code=404, detail="Expense not found")
#     db.delete(e); db.commit()

# @app.get("/summary")
# def summary(db: Session = Depends(get_db)):
#     expenses = db.query(Expense).all()
#     total = sum(e.amount for e in expenses)
#     by_category, by_payment = {}, {}
#     for e in expenses:
#         by_category[e.category] = by_category.get(e.category, 0) + e.amount
#         if e.payment_method:
#             by_payment[e.payment_method] = by_payment.get(e.payment_method, 0) + e.amount
#     return {
#         "total": round(total, 2),
#         "by_category": {k: round(v, 2) for k, v in by_category.items()},
#         "by_payment_method": {k: round(v, 2) for k, v in by_payment.items()},
#         "count": len(expenses),
#     }


# from frontend import mount_frontend
# mount_frontend(app)





import asyncio
import json
import secrets
import string
import time
import urllib.parse
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional, List
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse

from fastapi import FastAPI, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
from sqlalchemy import extract
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from datetime import date
from db import JoinRequestStatus


from db import (
    Expense, User, OAuthClient, AuthCode, AccessToken,
    Group, GroupMember, GroupExpense, ExpenseParticipant, SettlementRecord,
    GroupType, GroupMemberRole, SplitType, GroupStatus, ExpenseCategory, SettlementStatus,
    get_db, init_db
)

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("expense-mcp")

# ─────────────────────────────────────────────────────────────────────────────
# V3 DB MODELS — imported lazily so existing data is preserved
# These must be defined/imported from db.py; we reference them by name and
# guard with hasattr so the file is importable even before the migration runs.
# ─────────────────────────────────────────────────────────────────────────────

def _get_join_request_model():
    try:
        from db import JoinRequest
        return JoinRequest
    except ImportError:
        raise RuntimeError("JoinRequest model not found in db.py")

def _get_audit_log_model():
    try:
        from db import AuditLog
        return AuditLog
    except ImportError:
        raise RuntimeError("AuditLog model not found in db.py")

# ─── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, stored_hash = hashed.split(":")
        return hmac.compare_digest(
            hashlib.sha256((salt + password).encode()).hexdigest(),
            stored_hash,
        )
    except Exception:
        return False


# ─── Invite Code Generator ────────────────────────────────────────────────────

_INVITE_ALPHABET = string.ascii_uppercase + string.digits

def generate_invite_code(length: int = 8) -> str:
    """Generate a unique uppercase alphanumeric invite code."""
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(length))


# ─── DB-backed OAuth Helpers ──────────────────────────────────────────────────

def store_client(client_id: str, client_secret: str, redirect_uris: list):
    db = next(get_db())
    try:
        existing = db.query(OAuthClient).filter(OAuthClient.client_id == client_id).first()
        if existing:
            existing.client_secret = client_secret
            existing.redirect_uris = json.dumps(redirect_uris)
        else:
            db.add(OAuthClient(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uris=json.dumps(redirect_uris),
            ))
        db.commit()
        log.info(f"[OAuth] Client stored/updated: client_id={client_id}")
    except Exception:
        db.rollback()
        log.exception(f"[OAuth] Failed to store client: client_id={client_id}")
        raise
    finally:
        db.close()


def store_auth_code(code: str, user_id: int, client_id: str, redirect_uri: str,
                    code_challenge: str, code_challenge_method: str):
    db = next(get_db())
    try:
        db.add(AuthCode(
            code=code, user_id=user_id, client_id=client_id,
            redirect_uri=redirect_uri, code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        ))
        db.commit()
        log.info(f"[OAuth] Auth code stored: user_id={user_id} client_id={client_id}")
    except Exception:
        db.rollback()
        log.exception(f"[OAuth] Failed to store auth code: user_id={user_id}")
        raise
    finally:
        db.close()


def get_auth_code(code: str) -> Optional[dict]:
    db = next(get_db())
    try:
        row = db.query(AuthCode).filter(AuthCode.code == code).first()
        if not row:
            return None
        return {
            "user_id":               row.user_id,
            "client_id":             row.client_id,
            "redirect_uri":          row.redirect_uri,
            "code_challenge":        row.code_challenge,
            "code_challenge_method": row.code_challenge_method,
            "expires_at":            row.expires_at,
        }
    except Exception:
        log.exception("[OAuth] Failed to get auth code")
        return None
    finally:
        db.close()


def delete_auth_code(code: str):
    db = next(get_db())
    try:
        db.query(AuthCode).filter(AuthCode.code == code).delete()
        db.commit()
    except Exception:
        db.rollback()
        log.exception("[OAuth] Failed to delete auth code")
    finally:
        db.close()


def store_access_token(token: str, user_id: int, client_id: str):
    db = next(get_db())
    try:
        db.add(AccessToken(
            token=token, user_id=user_id, client_id=client_id,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        ))
        db.commit()
        log.info(f"[OAuth] Access token stored: user_id={user_id} client_id={client_id}")
    except Exception:
        db.rollback()
        log.exception(f"[OAuth] Failed to store access token: user_id={user_id}")
        raise
    finally:
        db.close()


def get_access_token(token: str) -> Optional[dict]:
    db = next(get_db())
    try:
        row = db.query(AccessToken).filter(AccessToken.token == token).first()
        if not row:
            return None
        return {
            "user_id":    row.user_id,
            "client_id":  row.client_id,
            "expires_at": row.expires_at,
        }
    except Exception:
        log.exception("[OAuth] Failed to get access token")
        return None
    finally:
        db.close()


def delete_access_token(token: str):
    db = next(get_db())
    try:
        db.query(AccessToken).filter(AccessToken.token == token).delete()
        db.commit()
    except Exception:
        db.rollback()
        log.exception("[OAuth] Failed to delete access token")
    finally:
        db.close()


# ─── App Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("[Startup] Initialising database…")
    try:
        init_db()
        log.info("[Startup] Database ready.")
    except Exception:
        log.exception("[Startup] Database init failed.")
        raise
    log.info("[Startup] Expense Tracker API V3 is live.")
    yield
    log.info("[Shutdown] Expense Tracker API V3 shutting down.")


app = FastAPI(title="Expense Tracker API V3", lifespan=lifespan)


# ─── Request Logging Middleware ───────────────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        method = request.method
        path   = request.url.path
        log.info(f"[HTTP] → {method} {path}")
        try:
            response = await call_next(request)
            elapsed = (time.perf_counter() - start) * 1000
            log.info(f"[HTTP] ← {method} {path} status={response.status_code} [{elapsed:.1f}ms]")
            return response
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            log.exception(f"[HTTP] ✗ {method} {path} UNHANDLED EXCEPTION [{elapsed:.1f}ms]")
            raise

app.add_middleware(RequestLoggingMiddleware)


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

# ── Existing schemas ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    nickname: Optional[str] = None
    email: str
    phone: Optional[str] = None
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    nickname: Optional[str]
    email: str
    phone: Optional[str]


class ExpenseCreate(BaseModel):
    amount: float
    category: str
    date: date
    description: Optional[str] = None
    tags: Optional[str] = None
    is_recurring: bool = False
    payment_method: Optional[str] = None


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    category: Optional[str] = None
    date: Optional[date] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    is_recurring: Optional[bool] = None
    payment_method: Optional[str] = None


class ExpenseOut(ExpenseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int


# ── Group schemas ─────────────────────────────────────────────────────────────

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    group_type: GroupType = GroupType.other
    member_user_ids: List[int] = []


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str]
    group_type: GroupType
    status: GroupStatus
    created_by: int
    created_at: datetime


class GroupMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_id: int
    user_id: int
    role: GroupMemberRole
    joined_at: datetime
    is_active: bool


class ParticipantInput(BaseModel):
    user_id: int
    share_value: Optional[float] = None


class GroupExpenseCreate(BaseModel):
    title: str
    amount: float
    category: ExpenseCategory = ExpenseCategory.miscellaneous
    paid_by: int
    split_type: SplitType = SplitType.equal
    date: date
    description: Optional[str] = None
    participant_user_ids: Optional[List[int]] = None
    participants: Optional[List[ParticipantInput]] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class GroupExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_id: int
    title: str
    amount: float
    category: ExpenseCategory
    paid_by: int
    split_type: SplitType
    date: date
    description: Optional[str]
    is_settled: bool
    created_at: datetime


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    expense_id: int
    user_id: int
    share_value: Optional[float]
    share_amount: float
    is_settled: bool


class SettlementRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_id: int
    from_user_id: int
    to_user_id: int
    amount: float
    status: SettlementStatus
    created_at: datetime
    settled_at: Optional[datetime]
    note: Optional[str]


class MemberBalance(BaseModel):
    user_id: int
    total_paid: float
    total_share: float
    net_balance: float


class GroupDashboard(BaseModel):
    group_id: int
    group_name: str
    status: GroupStatus
    total_members: int
    total_expenses: float
    expense_count: int
    pending_settlements: int
    member_balances: List[MemberBalance]


class DebtEdge(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: float


# ── V3 schemas ────────────────────────────────────────────────────────────────

# AFTER (clean version)
class JoinRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: int
    group_id: int
    user_id: int
    status: str
    requested_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    note: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def remap_fields(cls, data):
        if hasattr(data, '__dict__'):
            # SQLAlchemy ORM object — remap column names
            d = {
                'id':           data.id,
                'group_id':     data.group_id,
                'user_id':      data.user_id,
                'status':       data.status,
                'requested_at': data.requested_at,
                'resolved_at':  getattr(data, 'approved_at', None),
                'resolved_by':  getattr(data, 'approved_by', None),
                'note':         None,
            }
            return d
        return data


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_id: int
    actor_user_id: int
    action: str
    target_user_id: Optional[int]
    detail: Optional[str]
    created_at: datetime


class RoleChangeRequest(BaseModel):
    user_id: int
    new_role: str  # "admin" | "member"


class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: int


class RegenerateInviteResponse(BaseModel):
    group_id: int
    invite_code: str


class JoinByCodeRequest(BaseModel):
    invite_code: str


# ─────────────────────────────────────────────────────────────────────────────
# SETTLEMENT & DEBT SIMPLIFICATION LOGIC (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def compute_split_shares(
    total_amount: float,
    split_type: SplitType,
    participant_user_ids: Optional[List[int]],
    participants: Optional[List[ParticipantInput]],
) -> List[dict]:
    if split_type == SplitType.equal:
        ids = participant_user_ids or []
        if not ids:
            raise ValueError("participant_user_ids required for equal split")
        share = round(total_amount / len(ids), 2)
        shares = [{"user_id": uid, "share_value": None, "share_amount": share} for uid in ids]
        diff = round(total_amount - share * len(ids), 2)
        shares[-1]["share_amount"] = round(shares[-1]["share_amount"] + diff, 2)
        return shares

    if not participants:
        raise ValueError(f"participants required for split_type={split_type}")

    if split_type == SplitType.percentage:
        total_pct = sum(p.share_value for p in participants)
        if abs(total_pct - 100.0) > 0.01:
            raise ValueError(f"Percentages must sum to 100, got {total_pct}")
        return [
            {
                "user_id": p.user_id,
                "share_value": p.share_value,
                "share_amount": round(total_amount * p.share_value / 100, 2),
            }
            for p in participants
        ]

    if split_type == SplitType.fixed:
        total_fixed = sum(p.share_value for p in participants)
        if abs(total_fixed - total_amount) > 0.01:
            raise ValueError(f"Fixed amounts must sum to {total_amount}, got {total_fixed}")
        return [
            {"user_id": p.user_id, "share_value": p.share_value, "share_amount": round(p.share_value, 2)}
            for p in participants
        ]

    if split_type == SplitType.by_days:
        total_days = sum(p.share_value for p in participants)
        if total_days <= 0:
            raise ValueError("Total days must be > 0")
        return [
            {
                "user_id": p.user_id,
                "share_value": p.share_value,
                "share_amount": round(total_amount * p.share_value / total_days, 2),
            }
            for p in participants
        ]

    if split_type == SplitType.custom:
        return [
            {"user_id": p.user_id, "share_value": None, "share_amount": round(p.share_value, 2)}
            for p in participants
        ]

    raise ValueError(f"Unknown split_type: {split_type}")


def compute_net_balances(db: Session, group_id: int) -> dict:
    balances: dict = defaultdict(float)
    expenses = db.query(GroupExpense).filter(GroupExpense.group_id == group_id).all()
    for expense in expenses:
        balances[expense.paid_by] += expense.amount
        for p in expense.participants:
            balances[p.user_id] -= p.share_amount
    return dict(balances)


def simplify_debts(net_balances: dict) -> List[DebtEdge]:
    creditors = sorted(
        [(uid, bal) for uid, bal in net_balances.items() if bal > 0.001],
        key=lambda x: x[1],
    )
    debtors = sorted(
        [(uid, -bal) for uid, bal in net_balances.items() if bal < -0.001],
        key=lambda x: x[1],
    )

    transactions: List[DebtEdge] = []
    i, j = len(creditors) - 1, len(debtors) - 1
    creditors = list(creditors)
    debtors   = list(debtors)

    while i >= 0 and j >= 0:
        cred_uid, cred_amt = creditors[i]
        debt_uid, debt_amt = debtors[j]

        settled = min(cred_amt, debt_amt)
        transactions.append(DebtEdge(
            from_user_id=debt_uid,
            to_user_id=cred_uid,
            amount=round(settled, 2),
        ))

        creditors[i] = (cred_uid, round(cred_amt - settled, 2))
        debtors[j]   = (debt_uid, round(debt_amt - settled, 2))

        if creditors[i][1] < 0.001:
            i -= 1
        if debtors[j][1] < 0.001:
            j -= 1

    return transactions


# ─────────────────────────────────────────────────────────────────────────────
# V3 PERMISSION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def assert_member(db: Session, group_id: int, user_id: int) -> GroupMember:
    """Assert caller is an active group member. Returns membership row."""
    membership = (
        db.query(GroupMember)
        .filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        )
        .first()
    )
    if not membership:
        log.warning(f"[Permission] DENY member check: user_id={user_id} group_id={group_id}")
        raise HTTPException(status_code=403, detail="Not a member of this group")
    return membership


def assert_admin(db: Session, group_id: int, user_id: int) -> GroupMember:
    """Assert caller is an active admin or owner. Returns membership row."""
    membership = assert_member(db, group_id, user_id)
    if membership.role not in (GroupMemberRole.admin, GroupMemberRole.owner):
        log.warning(
            f"[Permission] DENY admin check: user_id={user_id} group_id={group_id} role={membership.role}"
        )
        raise HTTPException(status_code=403, detail="Admin or owner permission required")
    return membership


def assert_owner(db: Session, group_id: int, user_id: int) -> GroupMember:
    """Assert caller is the group owner. Returns membership row."""
    membership = assert_member(db, group_id, user_id)
    if membership.role != GroupMemberRole.owner:
        log.warning(
            f"[Permission] DENY owner check: user_id={user_id} group_id={group_id} role={membership.role}"
        )
        raise HTTPException(status_code=403, detail="Owner permission required")
    return membership


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY HELPERS (kept for backward compat with existing REST routes)
# ─────────────────────────────────────────────────────────────────────────────

def _assert_active_member(db: Session, group_id: int, user_id: int, require_admin: bool = False):
    """Backward-compatible wrapper around assert_member / assert_admin."""
    if require_admin:
        return assert_admin(db, group_id, user_id)
    return assert_member(db, group_id, user_id)


def _assert_active_group(db: Session, group_id: int) -> Group:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.status == GroupStatus.archived:
        raise HTTPException(status_code=400, detail="Group is archived — no modifications allowed")
    return group


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOG HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _write_audit(
    db: Session,
    group_id: int,
    actor_user_id: int,
    action: str,
    target_user_id: Optional[int] = None,
    detail: Optional[str] = None,
):
    try:
        GroupAuditLog = _get_audit_log_model()
        entry = GroupAuditLog(
            group_id=group_id,
            performed_by=actor_user_id,
            action_type=action,
            target_user=target_user_id,
            metadata_json=detail,
        )
        db.add(entry)
        log.debug(
            f"[Audit] group_id={group_id} actor={actor_user_id} action={action} "
            f"target={target_user_id} detail={detail!r}"
        )
    except RuntimeError:
        log.warning(
            f"[Audit] GroupAuditLog model unavailable — skipping audit for action={action}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# INVITE CODE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_invite_code(db: Session, group: Group) -> str:
    """
    Return existing invite code or generate + persist a new one.
    Assumes 'invite_code' column exists on Group (added in V3 migration).
    Falls back gracefully if the column is absent.
    """
    try:
        if getattr(group, "invite_code", None):
            return group.invite_code
        code = generate_invite_code()
        group.invite_code = code
        db.commit()
        log.info(f"[InviteCode] Generated invite code for group_id={group.id}: {code}")
        return code
    except Exception:
        db.rollback()
        log.exception(f"[InviteCode] Failed to generate invite code for group_id={group.id}")
        raise


def get_group_by_code(db: Session, invite_code: str) -> Optional[Group]:
    """Return the group with the given invite code, or None."""
    try:
        return db.query(Group).filter(Group.invite_code == invite_code).first()
    except Exception:
        log.exception(f"[InviteCode] DB error looking up invite_code={invite_code}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# MCP TOOLS REGISTRY  (existing + V3 additions)
# ─────────────────────────────────────────────────────────────────────────────

MCP_TOOLS = [
    # ── personal expense tools (unchanged) ──────────────────────────────────
    {
        "name": "create_expense",
        "description": "Create a new personal expense record for the authenticated user.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "amount":         {"type": "number",  "description": "Amount in INR"},
                "category":       {"type": "string",  "description": "Food, Transport, Shopping, Health, Utilities, Entertainment, Other"},
                "date":           {"type": "string",  "description": "Date in YYYY-MM-DD format"},
                "description":    {"type": "string",  "description": "Optional description"},
                "tags":           {"type": "string",  "description": "Comma-separated tags"},
                "is_recurring":   {"type": "boolean", "description": "True if recurring"},
                "payment_method": {"type": "string",  "description": "Cash, Credit Card, Debit Card, UPI, Net Banking, Other"},
            },
            "required": ["amount", "category", "date"],
        },
    },
    {
        "name": "list_expenses",
        "description": "List personal expenses for the authenticated user with optional filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category":       {"type": "string"},
                "payment_method": {"type": "string"},
                "is_recurring":   {"type": "boolean"},
                "month":          {"type": "integer", "description": "1-12"},
                "year":           {"type": "integer"},
            },
        },
    },
    {
        "name": "get_expense",
        "description": "Get a single personal expense by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"expense_id": {"type": "integer"}},
            "required": ["expense_id"],
        },
    },
    {
        "name": "update_expense",
        "description": "Update an existing personal expense by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expense_id":     {"type": "integer"},
                "amount":         {"type": "number"},
                "category":       {"type": "string"},
                "date":           {"type": "string"},
                "description":    {"type": "string"},
                "tags":           {"type": "string"},
                "is_recurring":   {"type": "boolean"},
                "payment_method": {"type": "string"},
            },
            "required": ["expense_id"],
        },
    },
    {
        "name": "delete_expense",
        "description": "Delete a personal expense by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"expense_id": {"type": "integer"}},
            "required": ["expense_id"],
        },
    },
    {
        "name": "get_summary",
        "description": "Get total spend, count, breakdown by category and payment method.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_profile",
        "description": "Get the authenticated user's profile.",
        "inputSchema": {"type": "object", "properties": {}},
    },

    # ── group tools (existing) ────────────────────────────────────────────────
    {
        "name": "create_group",
        "description": "Create a new expense group. The authenticated user becomes the owner.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name":            {"type": "string"},
                "description":     {"type": "string"},
                "group_type":      {"type": "string", "enum": ["family","friends","trip","office","roommates","event","other"]},
                "member_user_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["name"],
        },
    },
    {
        "name": "add_group_member",
        "description": "Add a user to a group. Requires admin or owner role.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
                "user_id":  {"type": "integer"},
            },
            "required": ["group_id", "user_id"],
        },
    },
    {
        "name": "remove_group_member",
        "description": "Remove a member from a group. Requires admin or owner role.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
                "user_id":  {"type": "integer"},
            },
            "required": ["group_id", "user_id"],
        },
    },
    {
        "name": "add_group_expense",
        "description": (
            "Add an expense to a group. Supports equal, percentage, fixed, by_days, custom splits. "
            "For equal split supply participant_user_ids. "
            "For percentage/fixed/by_days/custom supply participants with user_id and share_value."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id":             {"type": "integer"},
                "title":                {"type": "string"},
                "amount":               {"type": "number"},
                "category":             {"type": "string", "enum": ["food","travel","hotel","fuel","entertainment","shopping","miscellaneous"]},
                "paid_by":              {"type": "integer"},
                "split_type":           {"type": "string", "enum": ["equal","percentage","fixed","by_days","custom"]},
                "date":                 {"type": "string", "description": "YYYY-MM-DD"},
                "description":          {"type": "string"},
                "participant_user_ids": {"type": "array", "items": {"type": "integer"}},
                "participants": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "user_id":     {"type": "integer"},
                            "share_value": {"type": "number"},
                        },
                        "required": ["user_id", "share_value"],
                    },
                },
            },
            "required": ["group_id", "title", "amount", "paid_by", "split_type", "date"],
        },
    },
    {
        "name": "get_group_summary",
        "description": (
            "Get the V3 dashboard summary for a group. "
            "Includes member_count, admin_count, pending_join_requests, invite_code_present, caller_role, "
            "member balances, and pending settlements."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"group_id": {"type": "integer"}},
            "required": ["group_id"],
        },
    },
    {
        "name": "calculate_group_settlement",
        "description": "Calculate and persist simplified debt transactions for a group.",
        "inputSchema": {
            "type": "object",
            "properties": {"group_id": {"type": "integer"}},
            "required": ["group_id"],
        },
    },
    {
        "name": "simplify_debts",
        "description": "Return simplified debt graph for a group without persisting.",
        "inputSchema": {
            "type": "object",
            "properties": {"group_id": {"type": "integer"}},
            "required": ["group_id"],
        },
    },
    {
        "name": "get_member_balance",
        "description": "Get the net balance of a specific member in a group.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
                "user_id":  {"type": "integer"},
            },
            "required": ["group_id", "user_id"],
        },
    },
    {
        "name": "archive_group",
        "description": "Archive a group (locks it from new expenses). Requires owner role.",
        "inputSchema": {
            "type": "object",
            "properties": {"group_id": {"type": "integer"}},
            "required": ["group_id"],
        },
    },
    {
        "name": "list_group_expenses",
        "description": "List all expenses in a group with optional filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
                "category": {"type": "string"},
                "paid_by":  {"type": "integer"},
                "month":    {"type": "integer"},
                "year":     {"type": "integer"},
            },
            "required": ["group_id"],
        },
    },

    # ── V3 new tools ──────────────────────────────────────────────────────────
    {
        "name": "get_invite_code",
        "description": "Get (or generate) the invite code for a group. Requires admin or owner role.",
        "inputSchema": {
            "type": "object",
            "properties": {"group_id": {"type": "integer"}},
            "required": ["group_id"],
        },
    },
    {
        "name": "regenerate_invite_code",
        "description": "Regenerate the invite code for a group (invalidating the old one). Requires admin or owner role.",
        "inputSchema": {
            "type": "object",
            "properties": {"group_id": {"type": "integer"}},
            "required": ["group_id"],
        },
    },
    {
        "name": "request_group_join",
        "description": "Submit a join request for a group using its invite code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "invite_code": {"type": "string", "description": "8-character uppercase invite code"},
            },
            "required": ["invite_code"],
        },
    },
    {
        "name": "approve_join_request",
        "description": "Approve a pending join request. Requires admin or owner role.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id":         {"type": "integer"},
                "join_request_id":  {"type": "integer"},
            },
            "required": ["group_id", "join_request_id"],
        },
    },
    {
        "name": "reject_join_request",
        "description": "Reject a pending join request. Requires admin or owner role.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id":        {"type": "integer"},
                "join_request_id": {"type": "integer"},
                "note":            {"type": "string", "description": "Optional rejection reason"},
            },
            "required": ["group_id", "join_request_id"],
        },
    },
    {
        "name": "list_join_requests",
        "description": "List join requests for a group. Requires admin or owner role.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
                "status":   {"type": "string", "enum": ["pending", "approved", "rejected"], "description": "Filter by status"},
            },
            "required": ["group_id"],
        },
    },
    {
        "name": "change_member_role",
        "description": "Promote or demote a member to admin or member. Only the owner can call this.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id":  {"type": "integer"},
                "user_id":   {"type": "integer"},
                "new_role":  {"type": "string", "enum": ["admin", "member"]},
            },
            "required": ["group_id", "user_id", "new_role"],
        },
    },
    {
        "name": "transfer_ownership",
        "description": "Transfer group ownership to another active member. Only the current owner can call this.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id":          {"type": "integer"},
                "new_owner_user_id": {"type": "integer"},
            },
            "required": ["group_id", "new_owner_user_id"],
        },
    },
    {
        "name": "deactivate_member",
        "description": "Deactivate (soft-remove) a group member. Requires admin or owner. Cannot remove the owner.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
                "user_id":  {"type": "integer"},
            },
            "required": ["group_id", "user_id"],
        },
    },
    {
        "name": "reactivate_member",
        "description": "Reactivate a previously deactivated group member. Requires admin or owner.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
                "user_id":  {"type": "integer"},
            },
            "required": ["group_id", "user_id"],
        },
    },
    {
        "name": "get_group_audit_log",
        "description": "Get the audit log for a group. Requires member access.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
                "limit":    {"type": "integer", "description": "Max entries to return (default 50)"},
            },
            "required": ["group_id"],
        },
    },
    {
        "name": "unarchive_group",
        "description": "Unarchive a previously archived group. Requires owner role.",
        "inputSchema": {
            "type": "object",
            "properties": {"group_id": {"type": "integer"}},
            "required": ["group_id"],
        },
    },
    {
        "name": "list_my_groups",
        "description": "List all groups the authenticated user is an active member of (private group visibility).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# TOOL EXECUTOR
# ─────────────────────────────────────────────────────────────────────────────

def run_tool(name: str, arguments: dict, user_id: int) -> dict:
    db = next(get_db())
    t0 = time.perf_counter()
    try:
        result = _dispatch_tool(name, arguments, user_id, db)
        elapsed = (time.perf_counter() - t0) * 1000
        log.info(f"[MCP Tool] name={name} user_id={user_id} [{elapsed:.1f}ms] ok")
        return result
    except HTTPException as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        log.warning(f"[MCP Tool] name={name} user_id={user_id} [{elapsed:.1f}ms] HTTP {exc.status_code}: {exc.detail}")
        return {"error": exc.detail}
    except Exception:
        elapsed = (time.perf_counter() - t0) * 1000
        log.exception(f"[MCP Tool] name={name} user_id={user_id} [{elapsed:.1f}ms] UNHANDLED EXCEPTION")
        return {"error": "Internal server error"}
    finally:
        db.close()


def _dispatch_tool(name: str, arguments: dict, user_id: int, db: Session) -> dict:  # noqa: C901 (long but structured)
    # ── personal expense tools ────────────────────────────────────────────────

    if name == "create_expense":
        log.debug(f"[Tool] create_expense user_id={user_id} amount={arguments.get('amount')}")
        expense = Expense(
            user_id=user_id,
            amount=arguments["amount"],
            category=arguments["category"],
            date=arguments["date"],
            description=arguments.get("description"),
            tags=arguments.get("tags"),
            is_recurring=arguments.get("is_recurring", False),
            payment_method=arguments.get("payment_method"),
        )
        db.add(expense)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] create_expense DB commit failed user_id={user_id}")
            return {"error": "Database error while creating expense"}
        db.refresh(expense)
        log.info(f"[Tool] create_expense created expense_id={expense.id} user_id={user_id}")
        return _expense_dict(expense)

    elif name == "list_expenses":
        q = db.query(Expense).filter(Expense.user_id == user_id)
        if arguments.get("category"):
            q = q.filter(Expense.category == arguments["category"])
        if arguments.get("payment_method"):
            q = q.filter(Expense.payment_method == arguments["payment_method"])
        if arguments.get("is_recurring") is not None:
            q = q.filter(Expense.is_recurring == arguments["is_recurring"])
        if arguments.get("month"):
            q = q.filter(extract("month", Expense.date) == arguments["month"])
        if arguments.get("year"):
            q = q.filter(extract("year", Expense.date) == arguments["year"])
        return {"expenses": [_expense_dict(e) for e in q.order_by(Expense.date.desc()).all()]}

    elif name == "get_expense":
        e = db.query(Expense).filter(
            Expense.id == arguments["expense_id"],
            Expense.user_id == user_id,
        ).first()
        return _expense_dict(e) if e else {"error": "Expense not found"}

    elif name == "update_expense":
        e = db.query(Expense).filter(
            Expense.id == arguments["expense_id"],
            Expense.user_id == user_id,
        ).first()
        if not e:
            return {"error": "Expense not found"}
        for field in ["amount", "category", "date", "description", "tags", "is_recurring", "payment_method"]:
            if field in arguments:
                setattr(e, field, arguments[field])
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] update_expense DB commit failed expense_id={arguments['expense_id']}")
            return {"error": "Database error while updating expense"}
        db.refresh(e)
        log.info(f"[Tool] update_expense updated expense_id={e.id}")
        return _expense_dict(e)

    elif name == "delete_expense":
        e = db.query(Expense).filter(
            Expense.id == arguments["expense_id"],
            Expense.user_id == user_id,
        ).first()
        if not e:
            return {"error": "Expense not found"}
        db.delete(e)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] delete_expense DB commit failed expense_id={arguments['expense_id']}")
            return {"error": "Database error while deleting expense"}
        log.info(f"[Tool] delete_expense deleted expense_id={arguments['expense_id']}")
        return {"success": True, "deleted_id": arguments["expense_id"]}

    elif name == "get_summary":
        expenses = db.query(Expense).filter(Expense.user_id == user_id).all()
        total = sum(e.amount for e in expenses)
        by_cat, by_pay = {}, {}
        for e in expenses:
            by_cat[e.category] = by_cat.get(e.category, 0) + e.amount
            if e.payment_method:
                by_pay[e.payment_method] = by_pay.get(e.payment_method, 0) + e.amount
        return {
            "total":             round(total, 2),
            "count":             len(expenses),
            "by_category":       {k: round(v, 2) for k, v in by_cat.items()},
            "by_payment_method": {k: round(v, 2) for k, v in by_pay.items()},
        }

    elif name == "get_profile":
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}
        return {
            "id": user.id, "name": user.name, "nickname": user.nickname,
            "email": user.email, "phone": user.phone,
        }

    # ── existing group tools ──────────────────────────────────────────────────

    elif name == "create_group":
        log.info(
            f"[Tool] create_group user_id={user_id} name={arguments.get('name')!r} "
            f"type={arguments.get('group_type','other')}"
        )
        # Generate invite code upfront
        invite_code = generate_invite_code()
        group = Group(
            name=arguments["name"],
            description=arguments.get("description"),
            group_type=GroupType(arguments.get("group_type", "other")),
            created_by=user_id,
        )
        # Attach invite_code only if the column exists
        try:
            group.invite_code = invite_code
        except AttributeError:
            log.warning("[Tool] create_group — Group.invite_code column not found; skipping invite code assignment")

        db.add(group)
        db.flush()

        db.add(GroupMember(group_id=group.id, user_id=user_id, role=GroupMemberRole.owner))

        for mid in arguments.get("member_user_ids", []):
            if mid != user_id:
                if not db.query(User).filter(User.id == mid).first():
                    db.rollback()
                    log.warning(f"[Tool] create_group rollback — user_id={mid} not found")
                    return {"error": f"User {mid} not found"}
                db.add(GroupMember(group_id=group.id, user_id=mid, role=GroupMemberRole.member))

        _write_audit(db, group.id, user_id, "group_created", detail=f"name={group.name!r}")

        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] create_group DB commit failed user_id={user_id}")
            return {"error": "Database error while creating group"}

        db.refresh(group)
        log.info(
            f"[Tool] create_group created group_id={group.id} name={group.name!r} "
            f"invite_code={invite_code} user_id={user_id}"
        )
        result = _group_dict(group)
        result["invite_code"] = invite_code
        return result

    elif name == "add_group_member":
        group_id        = arguments["group_id"]
        target_user_id  = arguments["user_id"]
        log.info(f"[Tool] add_group_member group_id={group_id} target={target_user_id} caller={user_id}")

        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}
        if group.status == GroupStatus.archived:
            return {"error": "Group is archived"}

        try:
            assert_admin(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        existing = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_user_id,
        ).first()

        if existing:
            if existing.is_active:
                return {"error": "User is already a member"}
            existing.is_active = True
            _write_audit(db, group_id, user_id, "member_reactivated", target_user_id=target_user_id)
            try:
                db.commit()
            except Exception:
                db.rollback()
                log.exception(f"[Tool] add_group_member reactivate DB commit failed")
                return {"error": "Database error"}
            log.info(f"[Tool] add_group_member reactivated user_id={target_user_id} group_id={group_id}")
            return {"success": True, "message": "Member re-added", "user_id": target_user_id}

        if not db.query(User).filter(User.id == target_user_id).first():
            return {"error": f"User {target_user_id} not found"}

        db.add(GroupMember(group_id=group_id, user_id=target_user_id, role=GroupMemberRole.member))
        _write_audit(db, group_id, user_id, "member_added", target_user_id=target_user_id)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] add_group_member DB commit failed group_id={group_id}")
            return {"error": "Database error"}
        log.info(f"[Tool] add_group_member added user_id={target_user_id} group_id={group_id}")
        return {"success": True, "message": "Member added", "user_id": target_user_id}

    elif name == "remove_group_member":
        group_id       = arguments["group_id"]
        target_user_id = arguments["user_id"]
        log.info(f"[Tool] remove_group_member group_id={group_id} target={target_user_id} caller={user_id}")

        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        try:
            assert_admin(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        target = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_user_id,
            GroupMember.is_active == True,
        ).first()
        if not target:
            return {"error": "Member not found or already removed"}
        if target.role == GroupMemberRole.owner:
            log.warning(f"[Tool] remove_group_member attempted to remove owner user_id={target_user_id}")
            return {"error": "Cannot remove the group owner"}

        target.is_active = False
        _write_audit(db, group_id, user_id, "member_removed", target_user_id=target_user_id)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] remove_group_member DB commit failed group_id={group_id}")
            return {"error": "Database error"}
        log.info(f"[Tool] remove_group_member removed user_id={target_user_id} group_id={group_id}")
        return {"success": True, "message": "Member removed", "user_id": target_user_id}

    elif name == "add_group_expense":
        group_id = arguments["group_id"]
        log.info(
            f"[Tool] add_group_expense group_id={group_id} title={arguments.get('title')!r} "
            f"amount={arguments.get('amount')} paid_by={arguments.get('paid_by')} caller={user_id}"
        )
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}
        if group.status == GroupStatus.archived:
            return {"error": "Group is archived"}

        try:
            assert_member(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        split_type = SplitType(arguments["split_type"])
        raw_parts  = arguments.get("participants")
        part_inputs = [ParticipantInput(**p) for p in raw_parts] if raw_parts else None

        try:
            shares = compute_split_shares(
                total_amount=arguments["amount"],
                split_type=split_type,
                participant_user_ids=arguments.get("participant_user_ids"),
                participants=part_inputs,
            )
        except ValueError as e:
            return {"error": str(e)}

        expense_date = (
            date.fromisoformat(arguments["date"])
            if isinstance(arguments["date"], str)
            else arguments["date"]
        )

        expense = GroupExpense(
            group_id=group_id,
            title=arguments["title"],
            amount=arguments["amount"],
            category=ExpenseCategory(arguments.get("category", "miscellaneous")),
            paid_by=arguments["paid_by"],
            split_type=split_type,
            date=expense_date,
            description=arguments.get("description"),
        )
        db.add(expense)
        db.flush()

        for s in shares:
            db.add(ExpenseParticipant(
                expense_id=expense.id,
                user_id=s["user_id"],
                share_value=s["share_value"],
                share_amount=s["share_amount"],
            ))

        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] add_group_expense DB commit failed group_id={group_id}")
            return {"error": "Database error while adding expense"}

        db.refresh(expense)
        log.info(f"[Tool] add_group_expense created expense_id={expense.id} group_id={group_id}")
        return _group_expense_dict(expense, shares)

    elif name == "get_group_summary":
        group_id = arguments["group_id"]
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        try:
            membership = assert_member(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        expenses = db.query(GroupExpense).filter(GroupExpense.group_id == group_id).all()
        total_amount = sum(e.amount for e in expenses)

        pending_settlements = db.query(SettlementRecord).filter(
            SettlementRecord.group_id == group_id,
            SettlementRecord.status == SettlementStatus.pending,
        ).count()

        net_balances = compute_net_balances(db, group_id)

        paid_by_map: dict = defaultdict(float)
        share_map:   dict = defaultdict(float)
        for e in expenses:
            paid_by_map[e.paid_by] += e.amount
            for p in e.participants:
                share_map[p.user_id] += p.share_amount

        members = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.is_active == True,
        ).all()

        admin_count = sum(
            1 for m in members if m.role in (GroupMemberRole.admin, GroupMemberRole.owner)
        )

        # V3: pending join requests count
        pending_join_requests = 0
        try:
            GroupJoinRequest = _get_join_request_model()
            pending_join_requests = db.query(GroupJoinRequest).filter(
                GroupJoinRequest.group_id == group_id,
                GroupJoinRequest.status == "pending",
            ).count()
        except RuntimeError:
            log.warning("[Tool] get_group_summary — GroupJoinRequest model unavailable; pending_join_requests=0")

        # V3: invite code present?
        invite_code_present = bool(getattr(group, "invite_code", None))

        member_user_ids = [m.user_id for m in members]
        users = db.query(User).filter(User.id.in_(member_user_ids)).all()
        user_name_map = {u.id: (u.nickname or u.name) for u in users}

        member_balances = [
            {
                "user_id":     m.user_id,
                "user_name":   user_name_map.get(m.user_id, f"User {m.user_id}"),
                "role":        m.role.value,
                "total_paid":  round(paid_by_map.get(m.user_id, 0), 2),
                "total_share": round(share_map.get(m.user_id, 0), 2),
                "net_balance": round(net_balances.get(m.user_id, 0), 2),
            }
            for m in members
        ]
    
        return {
            "group_id":              group.id,
            "group_name":            group.name,
            "status":                group.status.value,
            "total_members":         len(members),
            "member_count":          len(members),
            "admin_count":           admin_count,
            "total_expenses":        round(total_amount, 2),
            "expense_count":         len(expenses),
            "pending_settlements":   pending_settlements,
            "pending_join_requests": pending_join_requests,
            "invite_code_present":   invite_code_present,
            "caller_role":           membership.role.value,
            "member_balances":       member_balances,
        }

    elif name == "calculate_group_settlement":
        group_id = arguments["group_id"]
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        try:
            assert_member(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        net_balances = compute_net_balances(db, group_id)
        transactions = simplify_debts(net_balances)

        db.query(SettlementRecord).filter(
            SettlementRecord.group_id == group_id,
            SettlementRecord.status == SettlementStatus.pending,
        ).delete()

        records = []
        for t in transactions:
            record = SettlementRecord(
                group_id=group_id,
                from_user_id=t.from_user_id,
                to_user_id=t.to_user_id,
                amount=t.amount,
            )
            db.add(record)
            records.append({"from_user_id": t.from_user_id, "to_user_id": t.to_user_id, "amount": t.amount})

        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] calculate_group_settlement DB commit failed group_id={group_id}")
            return {"error": "Database error while calculating settlements"}

        log.info(f"[Tool] calculate_group_settlement group_id={group_id} tx_count={len(records)}")
        return {
            "group_id":          group_id,
            "transaction_count": len(records),
            "settlements":       records,
        }

    elif name == "simplify_debts":
        group_id = arguments["group_id"]
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        try:
            assert_member(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        net_balances = compute_net_balances(db, group_id)
        transactions = simplify_debts(net_balances)
        return {
            "group_id":    group_id,
            "settlements": [
                {"from_user_id": t.from_user_id, "to_user_id": t.to_user_id, "amount": t.amount}
                for t in transactions
            ],
        }

    elif name == "get_member_balance":
        group_id   = arguments["group_id"]
        target_uid = arguments["user_id"]

        try:
            assert_member(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        net_balances = compute_net_balances(db, group_id)
        balance = net_balances.get(target_uid, 0.0)
        return {
            "group_id":    group_id,
            "user_id":     target_uid,
            "net_balance": round(balance, 2),
            "status":      "owed" if balance > 0 else ("owes" if balance < 0 else "settled"),
        }

    elif name == "archive_group":
        group_id = arguments["group_id"]
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}
        if group.status == GroupStatus.archived:
            return {"error": "Group is already archived"}

        try:
            assert_owner(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        group.status      = GroupStatus.archived
        group.archived_at = datetime.utcnow()
        _write_audit(db, group_id, user_id, "group_archived")
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] archive_group DB commit failed group_id={group_id}")
            return {"error": "Database error while archiving group"}

        log.info(f"[Tool] archive_group group_id={group_id} by user_id={user_id}")
        return {"success": True, "group_id": group_id, "archived_at": group.archived_at.isoformat()}

    elif name == "list_group_expenses":
        group_id = arguments["group_id"]

        try:
            assert_member(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        q = db.query(GroupExpense).filter(GroupExpense.group_id == group_id)
        if arguments.get("category"):
            q = q.filter(GroupExpense.category == ExpenseCategory(arguments["category"]))
        if arguments.get("paid_by"):
            q = q.filter(GroupExpense.paid_by == arguments["paid_by"])
        if arguments.get("month"):
            q = q.filter(extract("month", GroupExpense.date) == arguments["month"])
        if arguments.get("year"):
            q = q.filter(extract("year", GroupExpense.date) == arguments["year"])

        expenses = q.order_by(GroupExpense.date.desc()).all()
        return {"group_id": group_id, "expenses": [_group_expense_dict(e) for e in expenses]}

    # ── V3 new tools ──────────────────────────────────────────────────────────

    elif name == "get_invite_code":
        group_id = arguments["group_id"]
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        try:
            assert_admin(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        try:
            code = _ensure_invite_code(db, group)
        except Exception:
            return {"error": "Failed to retrieve invite code"}
        return {"group_id": group_id, "invite_code": code}

    elif name == "regenerate_invite_code":
        group_id = arguments["group_id"]
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        try:
            assert_admin(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        new_code = generate_invite_code()
        old_code = getattr(group, "invite_code", None)
        try:
            group.invite_code = new_code
        except AttributeError:
            return {"error": "invite_code column not available — run database migration"}

        _write_audit(
            db, group_id, user_id, "invite_code_regenerated",
            detail=f"old={old_code} new={new_code}",
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] regenerate_invite_code DB commit failed group_id={group_id}")
            return {"error": "Database error while regenerating invite code"}

        log.info(f"[Tool] regenerate_invite_code group_id={group_id} new_code={new_code} by user_id={user_id}")
        return {"group_id": group_id, "invite_code": new_code}

    elif name == "request_group_join":
        invite_code = arguments["invite_code"].upper().strip()
        log.info(f"[Tool] request_group_join user_id={user_id} invite_code={invite_code}")

        try:
            GroupJoinRequest = _get_join_request_model()
        except RuntimeError as e:
            return {"error": str(e)}

        group = get_group_by_code(db, invite_code)
        if not group:
            return {"error": "Invalid invite code"}
        if group.status == GroupStatus.archived:
            return {"error": "This group is archived and not accepting new members"}

        # already a member?
        existing_membership = db.query(GroupMember).filter(
            GroupMember.group_id == group.id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if existing_membership:
            return {"error": "You are already a member of this group"}

        # duplicate pending request?
        existing_request = db.query(GroupJoinRequest).filter(
            GroupJoinRequest.group_id == group.id,
            GroupJoinRequest.user_id == user_id,
            GroupJoinRequest.status == "pending",
        ).first()
        if existing_request:
            return {"error": "You already have a pending join request for this group"}

        jr = GroupJoinRequest(
            group_id=group.id,
            user_id=user_id,
            status="pending",
        )
        db.add(jr)
        _write_audit(db, group.id, user_id, "join_requested", target_user_id=user_id)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] request_group_join DB commit failed user_id={user_id} group_id={group.id}")
            return {"error": "Database error while submitting join request"}

        db.refresh(jr)
        log.info(f"[Tool] request_group_join created join_request_id={jr.id} group_id={group.id} user_id={user_id}")
        return {
            "success":         True,
            "join_request_id": jr.id,
            "group_id":        group.id,
            "group_name":      group.name,
            "status":          "pending",
        }

    elif name == "approve_join_request":
        group_id        = arguments["group_id"]
        join_request_id = arguments["join_request_id"]
        log.info(f"[Tool] approve_join_request group_id={group_id} jr_id={join_request_id} caller={user_id}")

        try:
            GroupJoinRequest = _get_join_request_model()
        except RuntimeError as e:
            return {"error": str(e)}

        try:
            assert_admin(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        jr = db.query(GroupJoinRequest).filter(
            GroupJoinRequest.id == join_request_id,
            GroupJoinRequest.group_id == group_id,
        ).first()
        if not jr:
            return {"error": "Join request not found"}
        if jr.status != "pending":
            return {"error": f"Join request is already {jr.status}"}

        jr.status      = JoinRequestStatus.approved
        jr.approved_at = datetime.utcnow()
        jr.approved_by = user_id

        # create or re-activate membership
        existing = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == jr.user_id,
        ).first()
        if existing:
            existing.is_active = True
        else:
            db.add(GroupMember(group_id=group_id, user_id=jr.user_id, role=GroupMemberRole.member))

        _write_audit(db, group_id, user_id, "join_approved", target_user_id=jr.user_id)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] approve_join_request DB commit failed group_id={group_id} jr_id={join_request_id}")
            return {"error": "Database error while approving join request"}

        log.info(f"[Tool] approve_join_request approved user_id={jr.user_id} group_id={group_id}")
        return {"success": True, "user_id": jr.user_id, "group_id": group_id, "status": "approved"}

    elif name == "reject_join_request":
        group_id        = arguments["group_id"]
        join_request_id = arguments["join_request_id"]
        note            = arguments.get("note")
        log.info(f"[Tool] reject_join_request group_id={group_id} jr_id={join_request_id} caller={user_id}")

        try:
            GroupJoinRequest = _get_join_request_model()
        except RuntimeError as e:
            return {"error": str(e)}

        try:
            assert_admin(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        jr = db.query(GroupJoinRequest).filter(
            GroupJoinRequest.id == join_request_id,
            GroupJoinRequest.group_id == group_id,
        ).first()
        if not jr:
            return {"error": "Join request not found"}
        if jr.status != "pending":
            return {"error": f"Join request is already {jr.status}"}

        jr.status      = JoinRequestStatus.rejected
        jr.approved_at = datetime.utcnow()   # reusing approved_at as "resolved_at"
        jr.approved_by = user_id

        _write_audit(db, group_id, user_id, "join_rejected", target_user_id=jr.user_id, detail=note)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] reject_join_request DB commit failed group_id={group_id} jr_id={join_request_id}")
            return {"error": "Database error while rejecting join request"}

        log.info(f"[Tool] reject_join_request rejected user_id={jr.user_id} group_id={group_id}")
        return {"success": True, "user_id": jr.user_id, "group_id": group_id, "status": "rejected"}

    elif name == "list_join_requests":
        group_id       = arguments["group_id"]
        status_filter  = arguments.get("status")
        log.debug(f"[Tool] list_join_requests group_id={group_id} status={status_filter} caller={user_id}")

        try:
            GroupJoinRequest = _get_join_request_model()
        except RuntimeError as e:
            return {"error": str(e)}

        try:
            assert_admin(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        q = db.query(GroupJoinRequest).filter(GroupJoinRequest.group_id == group_id)
        if status_filter:
            q = q.filter(GroupJoinRequest.status == status_filter)
        requests = q.order_by(GroupJoinRequest.requested_at.desc()).all()
        return {
            "group_id": group_id,
            "join_requests": [_join_request_dict(jr) for jr in requests],
        }

    elif name == "change_member_role":
        group_id  = arguments["group_id"]
        target_id = arguments["user_id"]
        new_role  = arguments["new_role"]
        log.info(f"[Tool] change_member_role group_id={group_id} target={target_id} new_role={new_role} caller={user_id}")

        if new_role not in ("admin", "member"):
            return {"error": "new_role must be 'admin' or 'member'"}

        try:
            assert_owner(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        target = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_id,
            GroupMember.is_active == True,
        ).first()
        if not target:
            return {"error": "Target member not found"}
        if target.role == GroupMemberRole.owner:
            return {"error": "Cannot change the role of the owner; use transfer_ownership instead"}
        if target.user_id == user_id:
            return {"error": "Owner cannot change their own role"}

        old_role     = target.role.value
        target.role  = GroupMemberRole(new_role)
        action       = "member_promoted" if new_role == "admin" else "member_demoted"
        _write_audit(db, group_id, user_id, action, target_user_id=target_id,
                     detail=f"{old_role} → {new_role}")
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] change_member_role DB commit failed group_id={group_id}")
            return {"error": "Database error while changing member role"}

        log.info(f"[Tool] change_member_role group_id={group_id} user_id={target_id} {old_role} → {new_role}")
        return {"success": True, "user_id": target_id, "old_role": old_role, "new_role": new_role}

    elif name == "transfer_ownership":
        group_id         = arguments["group_id"]
        new_owner_uid    = arguments["new_owner_user_id"]
        log.info(f"[Tool] transfer_ownership group_id={group_id} new_owner={new_owner_uid} caller={user_id}")

        try:
            assert_owner(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        if new_owner_uid == user_id:
            return {"error": "You are already the owner"}

        new_owner_membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == new_owner_uid,
            GroupMember.is_active == True,
        ).first()
        if not new_owner_membership:
            return {"error": "Target user is not an active member of this group"}

        current_owner = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        ).first()

        current_owner.role       = GroupMemberRole.admin
        new_owner_membership.role = GroupMemberRole.owner
        _write_audit(
            db, group_id, user_id, "ownership_transferred",
            target_user_id=new_owner_uid,
            detail=f"from={user_id} to={new_owner_uid}",
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] transfer_ownership DB commit failed group_id={group_id}")
            return {"error": "Database error while transferring ownership"}

        log.info(f"[Tool] transfer_ownership group_id={group_id} from={user_id} to={new_owner_uid}")
        return {"success": True, "new_owner_user_id": new_owner_uid, "previous_owner_user_id": user_id}

    elif name == "deactivate_member":
        group_id  = arguments["group_id"]
        target_id = arguments["user_id"]
        log.info(f"[Tool] deactivate_member group_id={group_id} target={target_id} caller={user_id}")

        try:
            assert_admin(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        target = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_id,
            GroupMember.is_active == True,
        ).first()
        if not target:
            return {"error": "Active member not found"}
        if target.role == GroupMemberRole.owner:
            return {"error": "Cannot deactivate the group owner"}

        target.is_active = False
        _write_audit(db, group_id, user_id, "member_deactivated", target_user_id=target_id)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] deactivate_member DB commit failed group_id={group_id}")
            return {"error": "Database error while deactivating member"}

        log.info(f"[Tool] deactivate_member deactivated user_id={target_id} group_id={group_id}")
        return {"success": True, "user_id": target_id, "is_active": False}

    elif name == "reactivate_member":
        group_id  = arguments["group_id"]
        target_id = arguments["user_id"]
        log.info(f"[Tool] reactivate_member group_id={group_id} target={target_id} caller={user_id}")

        try:
            assert_admin(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        target = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_id,
        ).first()
        if not target:
            return {"error": "Member record not found"}
        if target.is_active:
            return {"error": "Member is already active"}

        target.is_active = True
        _write_audit(db, group_id, user_id, "member_reactivated", target_user_id=target_id)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] reactivate_member DB commit failed group_id={group_id}")
            return {"error": "Database error while reactivating member"}

        log.info(f"[Tool] reactivate_member reactivated user_id={target_id} group_id={group_id}")
        return {"success": True, "user_id": target_id, "is_active": True}

    elif name == "get_group_audit_log":
        group_id = arguments["group_id"]
        limit    = arguments.get("limit", 50)
        log.debug(f"[Tool] get_group_audit_log group_id={group_id} limit={limit} caller={user_id}")

        try:
            GroupAuditLog = _get_audit_log_model()
        except RuntimeError as e:
            return {"error": str(e)}

        try:
            assert_member(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        entries = (
            db.query(GroupAuditLog)
            .filter(GroupAuditLog.group_id == group_id)
            .order_by(GroupAuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "group_id": group_id,
            "audit_log": [_audit_log_dict(e) for e in entries],
        }

    elif name == "unarchive_group":
        group_id = arguments["group_id"]
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}
        if group.status != GroupStatus.archived:
            return {"error": "Group is not archived"}

        try:
            assert_owner(db, group_id, user_id)
        except HTTPException as e:
            return {"error": e.detail}

        group.status      = GroupStatus.active
        group.archived_at = None
        _write_audit(db, group_id, user_id, "group_unarchived")
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Tool] unarchive_group DB commit failed group_id={group_id}")
            return {"error": "Database error while unarchiving group"}

        log.info(f"[Tool] unarchive_group group_id={group_id} by user_id={user_id}")
        return {"success": True, "group_id": group_id, "status": "active"}

    elif name == "list_my_groups":
        log.debug(f"[Tool] list_my_groups user_id={user_id}")
        memberships = db.query(GroupMember).filter(
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).all()
        group_ids = [m.group_id for m in memberships]
        groups = db.query(Group).filter(Group.id.in_(group_ids)).all() if group_ids else []
        return {"groups": [_group_dict(g) for g in groups]}

    return {"error": f"Unknown tool: {name}"}





# ─────────────────────────────────────────────────────────────────────────────
# SERIALIZATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _expense_dict(e) -> dict:
    return {
        "id": e.id, "user_id": e.user_id, "amount": e.amount,
        "category": e.category, "date": str(e.date), "description": e.description,
        "tags": e.tags, "is_recurring": e.is_recurring, "payment_method": e.payment_method,
    }

def _group_dict(g) -> dict:
    return {
        "id": g.id, "name": g.name, "description": g.description,
        "group_type": g.group_type.value, "status": g.status.value,
        "created_by": g.created_by, "created_at": g.created_at.isoformat(),
        "invite_code": getattr(g, "invite_code", None),
    }

def _group_expense_dict(e, shares: list = None) -> dict:
    base = {
        "id": e.id, "group_id": e.group_id, "title": e.title,
        "amount": e.amount, "category": e.category.value,
        "paid_by": e.paid_by, "split_type": e.split_type.value,
        "date": str(e.date), "description": e.description,
        "is_settled": e.is_settled, "created_at": e.created_at.isoformat(),
    }
    if shares:
        base["splits"] = shares
    elif hasattr(e, "participants") and e.participants:
        base["splits"] = [
            {"user_id": p.user_id, "share_value": p.share_value, "share_amount": p.share_amount}
            for p in e.participants
        ]
    return base

def _join_request_dict(jr) -> dict:
    return {
        "id":           jr.id,
        "group_id":     jr.group_id,
        "user_id":      jr.user_id,
        "status":       jr.status,
        "requested_at": jr.requested_at.isoformat() if jr.requested_at else None,
        "resolved_at":  jr.approved_at.isoformat() if jr.approved_at else None,
        "resolved_by":  jr.approved_by,
        "note":         None,  # column doesn't exist in db.py
    }

def _audit_log_dict(entry) -> dict:
    return {
        "id":             entry.id,
        "group_id":       entry.group_id,
        "actor_user_id":  entry.actor_user_id,
        "action":         entry.action,
        "target_user_id": getattr(entry, "target_user_id", None),
        "detail":         getattr(entry, "detail", None),
        "created_at":     entry.created_at.isoformat() if entry.created_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# OAUTH DISCOVERY & AUTH
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/.well-known/oauth-protected-resource")
def oauth_protected_resource(request: Request):
    base = str(request.base_url).rstrip("/")
    return {"resource": base, "authorization_servers": [base]}


@app.get("/.well-known/oauth-authorization-server")
def oauth_authorization_server(request: Request):
    base = str(request.base_url).rstrip("/")
    return {
        "issuer":                                base,
        "authorization_endpoint":                f"{base}/oauth/authorize",
        "token_endpoint":                        f"{base}/oauth/token",
        "registration_endpoint":                 f"{base}/register",
        "response_types_supported":              ["code"],
        "grant_types_supported":                 ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported":      ["S256", "plain"],
        "scopes_supported":                      ["mcp"],
    }


@app.post("/register")
async def oauth_register(request: Request):
    body = await request.json()
    client_id     = secrets.token_urlsafe(16)
    client_secret = secrets.token_urlsafe(32)
    store_client(client_id, client_secret, body.get("redirect_uris", []))
    log.info(f"[OAuth] New client registered: client_id={client_id}")
    return {
        "client_id":     client_id, "client_secret": client_secret,
        "redirect_uris": body.get("redirect_uris", []),
        "grant_types":   ["authorization_code"], "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


@app.get("/oauth/authorize")
async def oauth_authorize(
    request: Request, client_id: str = "", redirect_uri: str = "", state: str = "",
    code_challenge: str = "", code_challenge_method: str = "S256",
    scope: str = "mcp", response_type: str = "code",
):
    log.info(f"[OAuth] Authorize request: client_id={client_id}")
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Expense Tracker — Sign In</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
        .card {{ background: white; border-radius: 16px; padding: 40px; width: 380px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); }}
        .logo {{ font-size: 36px; text-align: center; margin-bottom: 8px; }}
        h2 {{ text-align: center; color: #111; font-size: 20px; margin-bottom: 4px; }}
        .subtitle {{ text-align: center; color: #666; font-size: 14px; margin-bottom: 28px; }}
        label {{ display: block; font-size: 13px; font-weight: 600; color: #444; margin-bottom: 6px; }}
        input {{ width: 100%; padding: 10px 14px; border: 1.5px solid #ddd; border-radius: 8px; font-size: 14px; margin-bottom: 16px; outline: none; transition: border 0.2s; }}
        input:focus {{ border-color: #4f46e5; }}
        .btn-row {{ display: flex; gap: 10px; margin-top: 8px; }}
        button {{ flex: 1; padding: 11px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; border: none; transition: opacity 0.2s; }}
        button:hover {{ opacity: 0.88; }}
        .allow {{ background: #4f46e5; color: white; }}
        .deny  {{ background: #f3f4f6; color: #374151; }}
        .register-link {{ text-align: center; margin-top: 20px; font-size: 13px; color: #666; }}
        .register-link a {{ color: #4f46e5; text-decoration: none; font-weight: 600; }}
        .divider {{ border: none; border-top: 1px solid #e5e7eb; margin: 20px 0; }}
    </style>
</head>
<body>
<div class="card">
    <div class="logo">💸</div>
    <h2>Expense Tracker</h2>
    <p class="subtitle">Sign in to allow <strong>Claude</strong> to access your expenses</p>
    <hr class="divider">
    <form method="post" action="/oauth/login">
        <input type="hidden" name="client_id"             value="{client_id}">
        <input type="hidden" name="redirect_uri"          value="{redirect_uri}">
        <input type="hidden" name="state"                 value="{state}">
        <input type="hidden" name="code_challenge"        value="{code_challenge}">
        <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
        <label>Email</label>
        <input type="email" name="email" placeholder="you@example.com" required autofocus>
        <label>Password</label>
        <input type="password" name="password" placeholder="••••••••" required>
        <div class="btn-row">
            <button class="allow" type="submit" name="action" value="allow">✅ Sign In & Allow</button>
            <button class="deny"  type="submit" name="action" value="deny">❌ Deny</button>
        </div>
    </form>
    <p class="register-link">No account? <a href="/register-user?redirect_uri={urllib.parse.quote(redirect_uri)}&client_id={client_id}&state={state}&code_challenge={code_challenge}&code_challenge_method={code_challenge_method}">Create one</a></p>
</div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/oauth/login")
async def oauth_login(
    client_id: str = Form(...), redirect_uri: str = Form(...), state: str = Form(""),
    code_challenge: str = Form(""), code_challenge_method: str = Form("S256"),
    action: str = Form(...), email: str = Form(""), password: str = Form(""),
):
    if action == "deny":
        log.info(f"[OAuth] Login denied by user: email={email}")
        params = urllib.parse.urlencode({"error": "access_denied", "state": state})
        return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=302)

    db = next(get_db())
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            log.warning(f"[OAuth] Login failed: email={email}")
            error_html = f"""<!DOCTYPE html><html><head><title>Sign In</title>
            <style>* {{box-sizing:border-box;margin:0;padding:0}} body{{font-family:'Segoe UI',sans-serif;background:#f0f2f5;display:flex;align-items:center;justify-content:center;min-height:100vh}}
            .card{{background:white;border-radius:16px;padding:40px;width:380px;box-shadow:0 4px 24px rgba(0,0,0,0.1)}}
            .logo{{font-size:36px;text-align:center;margin-bottom:8px}} h2{{text-align:center;color:#111;font-size:20px;margin-bottom:4px}}
            .subtitle{{text-align:center;color:#666;font-size:14px;margin-bottom:28px}}
            label{{display:block;font-size:13px;font-weight:600;color:#444;margin-bottom:6px}}
            input{{width:100%;padding:10px 14px;border:1.5px solid #ddd;border-radius:8px;font-size:14px;margin-bottom:16px;outline:none}}
            .error{{background:#fee2e2;color:#dc2626;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px}}
            .btn-row{{display:flex;gap:10px;margin-top:8px}} button{{flex:1;padding:11px;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;border:none}}
            .allow{{background:#4f46e5;color:white}} .deny{{background:#f3f4f6;color:#374151}}
            .divider{{border:none;border-top:1px solid #e5e7eb;margin:20px 0}}</style></head>
            <body><div class="card"><div class="logo">💸</div><h2>Expense Tracker</h2>
            <p class="subtitle">Sign in to allow <strong>Claude</strong> to access your expenses</p>
            <hr class="divider"><div class="error">❌ Invalid email or password.</div>
            <form method="post" action="/oauth/login">
            <input type="hidden" name="client_id" value="{client_id}">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <input type="hidden" name="state" value="{state}">
            <input type="hidden" name="code_challenge" value="{code_challenge}">
            <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
            <label>Email</label><input type="email" name="email" value="{email}" required>
            <label>Password</label><input type="password" name="password" required>
            <div class="btn-row">
            <button class="allow" type="submit" name="action" value="allow">✅ Sign In & Allow</button>
            <button class="deny" type="submit" name="action" value="deny">❌ Deny</button>
            </div></form></div></body></html>"""
            return HTMLResponse(content=error_html, status_code=200)

        code = secrets.token_urlsafe(32)
        store_auth_code(code, user.id, client_id, redirect_uri, code_challenge, code_challenge_method)
        log.info(f"[OAuth] Login successful: user_id={user.id} email={email}")
        params = urllib.parse.urlencode({"code": code, "state": state})
        return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=302)
    except Exception:
        log.exception(f"[OAuth] Unexpected error during login: email={email}")
        raise
    finally:
        db.close()


@app.get("/register-user")
async def register_user_page(
    redirect_uri: str = "", client_id: str = "", state: str = "",
    code_challenge: str = "", code_challenge_method: str = "S256", error: str = "",
):
    error_html = f'<div class="error">❌ {error}</div>' if error else ""
    html = f"""<!DOCTYPE html>
<html><head><title>Create Account</title>
<style>* {{box-sizing:border-box;margin:0;padding:0}} body{{font-family:'Segoe UI',sans-serif;background:#f0f2f5;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}
.card{{background:white;border-radius:16px;padding:40px;width:420px;box-shadow:0 4px 24px rgba(0,0,0,0.1)}}
.logo{{font-size:36px;text-align:center;margin-bottom:8px}} h2{{text-align:center;color:#111;font-size:20px;margin-bottom:4px}}
.subtitle{{text-align:center;color:#666;font-size:14px;margin-bottom:24px}}
label{{display:block;font-size:13px;font-weight:600;color:#444;margin-bottom:5px}}
input{{width:100%;padding:10px 14px;border:1.5px solid #ddd;border-radius:8px;font-size:14px;margin-bottom:14px;outline:none;transition:border 0.2s}}
input:focus{{border-color:#4f46e5}} .error{{background:#fee2e2;color:#dc2626;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:14px}}
.optional{{color:#9ca3af;font-weight:400}} button{{width:100%;padding:12px;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;border:none;background:#4f46e5;color:white;margin-top:4px}}
button:hover{{opacity:0.88}} .login-link{{text-align:center;margin-top:18px;font-size:13px;color:#666}}
.login-link a{{color:#4f46e5;text-decoration:none;font-weight:600}} .divider{{border:none;border-top:1px solid #e5e7eb;margin:18px 0}}</style></head>
<body><div class="card"><div class="logo">💸</div><h2>Create Account</h2>
<p class="subtitle">Sign up to use Expense Tracker with Claude</p><hr class="divider">
{error_html}
<form method="post" action="/register-user">
<input type="hidden" name="redirect_uri" value="{redirect_uri}">
<input type="hidden" name="client_id" value="{client_id}">
<input type="hidden" name="state" value="{state}">
<input type="hidden" name="code_challenge" value="{code_challenge}">
<input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
<label>Full Name</label><input type="text" name="name" placeholder="John Doe" required>
<label>Nickname <span class="optional">(optional)</span></label><input type="text" name="nickname" placeholder="Johnny">
<label>Email</label><input type="email" name="email" placeholder="you@example.com" required>
<label>Phone <span class="optional">(optional)</span></label><input type="tel" name="phone" placeholder="+91 9999999999">
<label>Password</label><input type="password" name="password" placeholder="Min 8 characters" required minlength="8">
<button type="submit">🚀 Create Account & Continue</button></form>
<p class="login-link">Already have an account? <a href="/oauth/authorize?client_id={client_id}&redirect_uri={urllib.parse.quote(redirect_uri)}&state={state}&code_challenge={code_challenge}&code_challenge_method={code_challenge_method}">Sign in</a></p>
</div></body></html>"""
    return HTMLResponse(content=html)


@app.post("/register-user")
async def register_user_submit(
    name: str = Form(...), email: str = Form(...), password: str = Form(...),
    nickname: str = Form(""), phone: str = Form(""),
    redirect_uri: str = Form(...), client_id: str = Form(...), state: str = Form(""),
    code_challenge: str = Form(""), code_challenge_method: str = Form("S256"),
):
    db = next(get_db())
    try:
        if db.query(User).filter(User.email == email).first():
            log.warning(f"[Auth] Registration failed — email already registered: {email}")
            error_params = urllib.parse.urlencode({
                "redirect_uri": redirect_uri, "client_id": client_id, "state": state,
                "code_challenge": code_challenge, "code_challenge_method": code_challenge_method,
                "error": "Email already registered.",
            })
            return RedirectResponse(url=f"/register-user?{error_params}", status_code=302)
        if len(password) < 8:
            error_params = urllib.parse.urlencode({
                "redirect_uri": redirect_uri, "client_id": client_id, "state": state,
                "code_challenge": code_challenge, "code_challenge_method": code_challenge_method,
                "error": "Password must be at least 8 characters.",
            })
            return RedirectResponse(url=f"/register-user?{error_params}", status_code=302)
        user = User(
            name=name, nickname=nickname or None, email=email,
            phone=phone or None, hashed_password=hash_password(password),
        )
        db.add(user)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[Auth] DB commit failed during user registration: email={email}")
            raise
        db.refresh(user)
        log.info(f"[Auth] New user registered: user_id={user.id} email={email}")
        code = secrets.token_urlsafe(32)
        store_auth_code(code, user.id, client_id, redirect_uri, code_challenge, code_challenge_method)
        params = urllib.parse.urlencode({"code": code, "state": state})
        return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=302)
    except Exception:
        log.exception(f"[Auth] Unexpected error during registration: email={email}")
        raise
    finally:
        db.close()


# ─── Token Endpoint ───────────────────────────────────────────────────────────

@app.post("/oauth/token")
async def oauth_token(request: Request):
    content_type = request.headers.get("content-type", "")
    raw_body     = await request.body()
    if "application/json" in content_type:
        body = json.loads(raw_body)
    else:
        form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
        body = {k: v[0] for k, v in form.items()}

    grant_type = body.get("grant_type")
    code       = body.get("code")
    log.info(f"[OAuth] Token request: grant_type={grant_type}")

    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail={"error": "unsupported_grant_type"})

    code_data = get_auth_code(code)
    if not code_data:
        log.warning(f"[OAuth] Token exchange failed — invalid code")
        raise HTTPException(status_code=400, detail={"error": "invalid_grant"})
    if datetime.utcnow() > code_data["expires_at"]:
        delete_auth_code(code)
        log.warning(f"[OAuth] Token exchange failed — code expired")
        raise HTTPException(status_code=400, detail={"error": "invalid_grant", "error_description": "code expired"})

    access_token = secrets.token_urlsafe(32)
    store_access_token(access_token, code_data["user_id"], code_data["client_id"])
    delete_auth_code(code)
    log.info(f"[OAuth] Access token issued: user_id={code_data['user_id']}")
    return {"access_token": access_token, "token_type": "bearer", "expires_in": 86400, "scope": "mcp"}


# ─── Token Validation ─────────────────────────────────────────────────────────

def _get_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return None

def _validate_token(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    data = get_access_token(token)
    if not data:
        return None
    if datetime.utcnow() > data["expires_at"]:
        delete_access_token(token)
        log.info(f"[OAuth] Expired token deleted for user_id={data.get('user_id')}")
        return None
    return data["user_id"]


# ─── MCP Endpoints ────────────────────────────────────────────────────────────

async def _handle_mcp(msg: dict, user_id: int) -> dict:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params", {})
    log.debug(f"[MCP] method={method} id={msg_id} user_id={user_id}")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo":      {"name": "expense-tracker", "version": "3.0.0"},
            "capabilities":    {"tools": {}},
        }}
    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": MCP_TOOLS}}
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        t0     = time.perf_counter()
        result = run_tool(tool_name, arguments, user_id)
        elapsed = (time.perf_counter() - t0) * 1000
        log.info(f"[MCP] tools/call name={tool_name} user_id={user_id} [{elapsed:.1f}ms]")
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
        }}
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


@app.post("/")
async def root_post(request: Request):
    token   = _get_token(request)
    user_id = _validate_token(token)
    if not user_id:
        log.warning("[MCP] Unauthorized POST to /")
        raise HTTPException(
            status_code=401, detail="Unauthorized",
            headers={"WWW-Authenticate": 'Bearer realm="expense-tracker"'},
        )
    body = await request.json()
    return await _handle_mcp(body, user_id)


@app.get("/")
async def root_get(request: Request):
    token   = _get_token(request)
    user_id = _validate_token(token)
    if user_id:
        async def event_stream():
            yield _sse({"jsonrpc": "2.0", "method": "notifications/initialized",
                        "params": {"serverInfo": {"name": "expense-tracker", "version": "3.0.0"},
                                   "capabilities": {"tools": {}}}})
            async for chunk in request.stream():
                if not chunk:
                    continue
                try:
                    msg      = json.loads(chunk)
                    response = await _handle_mcp(msg, user_id)
                    if response:
                        yield _sse(response)
                except Exception:
                    log.exception("[MCP] SSE stream error")
                    yield _sse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Internal error"}, "id": None})
        return StreamingResponse(
            event_stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return {"status": "ok", "message": "Expense Tracker API V3 running"}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# REST ROUTES — Personal Expenses (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=payload.name, nickname=payload.nickname, email=payload.email,
        phone=payload.phone, hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] create_user DB commit failed email={payload.email}")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(user)
    log.info(f"[REST] create_user user_id={user.id} email={user.email}")
    return user


@app.post("/expenses", response_model=ExpenseOut, status_code=201)
def create_expense_rest(payload: ExpenseCreate, db: Session = Depends(get_db)):
    expense = Expense(**payload.model_dump(), user_id=1)
    db.add(expense)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception("[REST] create_expense DB commit failed")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(expense)
    log.info(f"[REST] create_expense expense_id={expense.id}")
    return expense


@app.get("/expenses", response_model=list[ExpenseOut])
def list_expenses_rest(
    category: Optional[str] = None, payment_method: Optional[str] = None,
    is_recurring: Optional[bool] = None, month: Optional[int] = None,
    year: Optional[int] = None, db: Session = Depends(get_db),
):
    q = db.query(Expense)
    if category:        q = q.filter(Expense.category == category)
    if payment_method:  q = q.filter(Expense.payment_method == payment_method)
    if is_recurring is not None: q = q.filter(Expense.is_recurring == is_recurring)
    if month:           q = q.filter(extract("month", Expense.date) == month)
    if year:            q = q.filter(extract("year", Expense.date) == year)
    return q.order_by(Expense.date.desc()).all()


@app.get("/expenses/{expense_id}", response_model=ExpenseOut)
def get_expense_rest(expense_id: int, db: Session = Depends(get_db)):
    e = db.query(Expense).filter(Expense.id == expense_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Expense not found")
    return e


@app.put("/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense_rest(expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)):
    e = db.query(Expense).filter(Expense.id == expense_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Expense not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] update_expense DB commit failed expense_id={expense_id}")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(e)
    return e


@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense_rest(expense_id: int, db: Session = Depends(get_db)):
    e = db.query(Expense).filter(Expense.id == expense_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(e)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] delete_expense DB commit failed expense_id={expense_id}")
        raise HTTPException(status_code=500, detail="Database error")


@app.get("/summary")
def summary(db: Session = Depends(get_db)):
    expenses = db.query(Expense).all()
    total    = sum(e.amount for e in expenses)
    by_category, by_payment = {}, {}
    for e in expenses:
        by_category[e.category] = by_category.get(e.category, 0) + e.amount
        if e.payment_method:
            by_payment[e.payment_method] = by_payment.get(e.payment_method, 0) + e.amount
    return {
        "total": round(total, 2), "count": len(expenses),
        "by_category":       {k: round(v, 2) for k, v in by_category.items()},
        "by_payment_method": {k: round(v, 2) for k, v in by_payment.items()},
    }


# ─────────────────────────────────────────────────────────────────────────────
# REST ROUTES — Groups V2 (backward-compatible)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/groups", response_model=GroupOut, status_code=201)
def create_group_rest(payload: GroupCreate, db: Session = Depends(get_db)):
    caller_id   = 1
    invite_code = generate_invite_code()
    group = Group(
        name=payload.name,
        description=payload.description,
        group_type=payload.group_type,
        created_by=caller_id,
    )
    try:
        group.invite_code = invite_code
    except AttributeError:
        log.warning("[REST] create_group — invite_code column not available yet")

    db.add(group)
    db.flush()
    db.add(GroupMember(group_id=group.id, user_id=caller_id, role=GroupMemberRole.owner))
    for mid in payload.member_user_ids:
        if mid != caller_id:
            if not db.query(User).filter(User.id == mid).first():
                db.rollback()
                raise HTTPException(status_code=404, detail=f"User {mid} not found")
            db.add(GroupMember(group_id=group.id, user_id=mid, role=GroupMemberRole.member))

    _write_audit(db, group.id, caller_id, "group_created", detail=f"name={group.name!r}")
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] create_group DB commit failed name={payload.name!r}")
        raise HTTPException(status_code=500, detail="Database error while creating group")
    db.refresh(group)
    log.info(f"[REST] create_group group_id={group.id} name={group.name!r} invite_code={invite_code}")
    return group


@app.get("/groups", response_model=list[GroupOut])
def list_groups_rest(db: Session = Depends(get_db)):
    # V3: in production this would filter to caller's groups via token; stub uses user_id=1
    caller_id   = 1
    memberships = db.query(GroupMember).filter(
        GroupMember.user_id == caller_id,
        GroupMember.is_active == True,
    ).all()
    group_ids = [m.group_id for m in memberships]
    if not group_ids:
        return []
    return db.query(Group).filter(Group.id.in_(group_ids)).order_by(Group.created_at.desc()).all()


@app.get("/groups/{group_id}", response_model=GroupOut)
def get_group_rest(group_id: int, db: Session = Depends(get_db)):
    g = db.query(Group).filter(Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    return g


@app.get("/groups/{group_id}/members", response_model=list[GroupMemberOut])
def list_group_members_rest(group_id: int, db: Session = Depends(get_db)):
    return (
        db.query(GroupMember)
        .filter(GroupMember.group_id == group_id, GroupMember.is_active == True)
        .all()
    )


@app.post("/groups/{group_id}/members", status_code=201)
def add_member_rest(group_id: int, user_id: int, db: Session = Depends(get_db)):
    group = _assert_active_group(db, group_id)
    if not db.query(User).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id, GroupMember.user_id == user_id
    ).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="User already a member")
        existing.is_active = True
        _write_audit(db, group_id, user_id, "member_reactivated", target_user_id=user_id)
        try:
            db.commit()
        except Exception:
            db.rollback()
            log.exception(f"[REST] add_member reactivate DB commit failed group_id={group_id}")
            raise HTTPException(status_code=500, detail="Database error")
        return {"message": "Member re-added"}
    db.add(GroupMember(group_id=group_id, user_id=user_id, role=GroupMemberRole.member))
    _write_audit(db, group_id, user_id, "member_added", target_user_id=user_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] add_member DB commit failed group_id={group_id}")
        raise HTTPException(status_code=500, detail="Database error")
    log.info(f"[REST] add_member user_id={user_id} group_id={group_id}")
    return {"message": "Member added"}


@app.delete("/groups/{group_id}/members/{user_id}", status_code=204)
def remove_member_rest(group_id: int, user_id: int, db: Session = Depends(get_db)):
    _assert_active_group(db, group_id)
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id,
        GroupMember.is_active == True,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == GroupMemberRole.owner:
        raise HTTPException(status_code=400, detail="Cannot remove group owner")
    member.is_active = False
    _write_audit(db, group_id, user_id, "member_removed", target_user_id=user_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] remove_member DB commit failed group_id={group_id} user_id={user_id}")
        raise HTTPException(status_code=500, detail="Database error")
    log.info(f"[REST] remove_member user_id={user_id} group_id={group_id}")


@app.post("/groups/{group_id}/expenses", response_model=GroupExpenseOut, status_code=201)
def add_group_expense_rest(group_id: int, payload: GroupExpenseCreate, db: Session = Depends(get_db)):
    _assert_active_group(db, group_id)
    try:
        shares = compute_split_shares(
            total_amount=payload.amount,
            split_type=payload.split_type,
            participant_user_ids=payload.participant_user_ids,
            participants=payload.participants,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    expense = GroupExpense(
        group_id=group_id, title=payload.title, amount=payload.amount,
        category=payload.category, paid_by=payload.paid_by,
        split_type=payload.split_type, date=payload.date, description=payload.description,
    )
    db.add(expense)
    db.flush()
    for s in shares:
        db.add(ExpenseParticipant(
            expense_id=expense.id, user_id=s["user_id"],
            share_value=s["share_value"], share_amount=s["share_amount"],
        ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] add_group_expense DB commit failed group_id={group_id}")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(expense)
    log.info(f"[REST] add_group_expense expense_id={expense.id} group_id={group_id} amount={expense.amount}")
    return expense


@app.get("/groups/{group_id}/expenses", response_model=list[GroupExpenseOut])
def list_group_expenses_rest(
    group_id: int,
    category: Optional[str] = None,
    paid_by: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(GroupExpense).filter(GroupExpense.group_id == group_id)
    if category:
        q = q.filter(GroupExpense.category == ExpenseCategory(category))
    if paid_by:
        q = q.filter(GroupExpense.paid_by == paid_by)
    if month:
        q = q.filter(extract("month", GroupExpense.date) == month)
    if year:
        q = q.filter(extract("year", GroupExpense.date) == year)
    return q.order_by(GroupExpense.date.desc()).all()


@app.get("/groups/{group_id}/expenses/{expense_id}", response_model=GroupExpenseOut)
def get_group_expense_rest(group_id: int, expense_id: int, db: Session = Depends(get_db)):
    e = db.query(GroupExpense).filter(
        GroupExpense.id == expense_id, GroupExpense.group_id == group_id
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Expense not found")
    return e


@app.get("/groups/{group_id}/dashboard", response_model=GroupDashboard)
def group_dashboard_rest(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    expenses     = db.query(GroupExpense).filter(GroupExpense.group_id == group_id).all()
    total_amount = sum(e.amount for e in expenses)

    pending = db.query(SettlementRecord).filter(
        SettlementRecord.group_id == group_id,
        SettlementRecord.status == SettlementStatus.pending,
    ).count()

    net_balances = compute_net_balances(db, group_id)
    paid_map:  dict = defaultdict(float)
    share_map: dict = defaultdict(float)
    for e in expenses:
        paid_map[e.paid_by] += e.amount
        for p in e.participants:
            share_map[p.user_id] += p.share_amount

    members = db.query(GroupMember).filter(
        GroupMember.group_id == group_id, GroupMember.is_active == True
    ).all()

    member_balances = [
        MemberBalance(
            user_id=m.user_id,
            total_paid=round(paid_map.get(m.user_id, 0), 2),
            total_share=round(share_map.get(m.user_id, 0), 2),
            net_balance=round(net_balances.get(m.user_id, 0), 2),
        )
        for m in members
    ]

    return GroupDashboard(
        group_id=group.id, group_name=group.name, status=group.status,
        total_members=len(members), total_expenses=round(total_amount, 2),
        expense_count=len(expenses), pending_settlements=pending,
        member_balances=member_balances,
    )


@app.post("/groups/{group_id}/settlements/calculate", response_model=list[SettlementRecordOut])
def calculate_settlements_rest(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    net_balances = compute_net_balances(db, group_id)
    transactions = simplify_debts(net_balances)

    db.query(SettlementRecord).filter(
        SettlementRecord.group_id == group_id,
        SettlementRecord.status == SettlementStatus.pending,
    ).delete()

    records = []
    for t in transactions:
        r = SettlementRecord(
            group_id=group_id, from_user_id=t.from_user_id,
            to_user_id=t.to_user_id, amount=t.amount,
        )
        db.add(r)
        records.append(r)

    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] calculate_settlements DB commit failed group_id={group_id}")
        raise HTTPException(status_code=500, detail="Database error")

    for r in records:
        db.refresh(r)
    log.info(f"[REST] calculate_settlements group_id={group_id} tx_count={len(records)}")
    return records


@app.get("/groups/{group_id}/settlements", response_model=list[SettlementRecordOut])
def list_settlements_rest(group_id: int, db: Session = Depends(get_db)):
    return (
        db.query(SettlementRecord)
        .filter(SettlementRecord.group_id == group_id)
        .order_by(SettlementRecord.created_at.desc())
        .all()
    )


@app.patch("/groups/{group_id}/settlements/{settlement_id}/settle", response_model=SettlementRecordOut)
def mark_settled_rest(group_id: int, settlement_id: int, db: Session = Depends(get_db)):
    r = db.query(SettlementRecord).filter(
        SettlementRecord.id == settlement_id,
        SettlementRecord.group_id == group_id,
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Settlement record not found")
    if r.status == SettlementStatus.settled:
        raise HTTPException(status_code=400, detail="Already settled")
    r.status     = SettlementStatus.settled
    r.settled_at = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] mark_settled DB commit failed settlement_id={settlement_id}")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(r)
    log.info(f"[REST] mark_settled settlement_id={settlement_id} group_id={group_id}")
    return r


@app.post("/groups/{group_id}/archive", response_model=GroupOut)
def archive_group_rest(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.status == GroupStatus.archived:
        raise HTTPException(status_code=400, detail="Group already archived")
    group.status      = GroupStatus.archived
    group.archived_at = datetime.utcnow()
    _write_audit(db, group_id, group.created_by, "group_archived")
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] archive_group DB commit failed group_id={group_id}")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(group)
    log.info(f"[REST] archive_group group_id={group_id}")
    return group


# ─────────────────────────────────────────────────────────────────────────────
# REST ROUTES — V3 New Endpoints
# ─────────────────────────────────────────────────────────────────────────────

# ── Invite codes ──────────────────────────────────────────────────────────────

@app.get("/groups/{group_id}/invite-code")
def get_invite_code_rest(group_id: int, db: Session = Depends(get_db)):
    """Get (or auto-generate) the invite code for a group. Requires admin/owner."""
    caller_id = 1  # replace with token auth in production
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    assert_admin(db, group_id, caller_id)
    try:
        code = _ensure_invite_code(db, group)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to retrieve invite code")
    return {"group_id": group_id, "invite_code": code}


@app.post("/groups/{group_id}/invite-code/regenerate", response_model=RegenerateInviteResponse)
def regenerate_invite_code_rest(group_id: int, db: Session = Depends(get_db)):
    """Regenerate the invite code (invalidates the old one). Requires admin/owner."""
    caller_id = 1
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    assert_admin(db, group_id, caller_id)

    new_code = generate_invite_code()
    old_code = getattr(group, "invite_code", None)
    try:
        group.invite_code = new_code
    except AttributeError:
        raise HTTPException(status_code=500, detail="invite_code column not available — run database migration")

    _write_audit(db, group_id, caller_id, "invite_code_regenerated",
                 detail=f"old={old_code} new={new_code}")
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] regenerate_invite_code DB commit failed group_id={group_id}")
        raise HTTPException(status_code=500, detail="Database error")

    log.info(f"[REST] regenerate_invite_code group_id={group_id} new_code={new_code}")
    return RegenerateInviteResponse(group_id=group_id, invite_code=new_code)


@app.get("/groups/join/{invite_code}")
def lookup_group_by_code_rest(invite_code: str, db: Session = Depends(get_db)):
    """Look up a group by invite code (returns limited public info)."""
    group = get_group_by_code(db, invite_code.upper().strip())
    if not group:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")
    return {
        "group_id":    group.id,
        "group_name":  group.name,
        "group_type":  group.group_type.value,
        "status":      group.status.value,
        "description": group.description,
    }


# ── Join requests ─────────────────────────────────────────────────────────────

@app.post("/groups/join", status_code=201)
def request_join_rest(payload: JoinByCodeRequest, db: Session = Depends(get_db)):
    """Submit a join request using an invite code."""
    caller_id   = 1
    invite_code = payload.invite_code.upper().strip()
    log.info(f"[REST] request_join user_id={caller_id} invite_code={invite_code}")

    try:
        GroupJoinRequest = _get_join_request_model()
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))

    group = get_group_by_code(db, invite_code)
    if not group:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    if group.status == GroupStatus.archived:
        raise HTTPException(status_code=400, detail="Group is archived")

    existing_membership = db.query(GroupMember).filter(
        GroupMember.group_id == group.id,
        GroupMember.user_id == caller_id,
        GroupMember.is_active == True,
    ).first()
    if existing_membership:
        raise HTTPException(status_code=400, detail="Already a member of this group")

    existing_request = db.query(GroupJoinRequest).filter(
        GroupJoinRequest.group_id == group.id,
        GroupJoinRequest.user_id == caller_id,
        GroupJoinRequest.status == "pending",
    ).first()
    if existing_request:
        raise HTTPException(status_code=400, detail="Pending join request already exists")

    jr = GroupJoinRequest(group_id=group.id, user_id=caller_id, status="pending")
    db.add(jr)
    _write_audit(db, group.id, caller_id, "join_requested", target_user_id=caller_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] request_join DB commit failed group_id={group.id}")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(jr)
    log.info(f"[REST] request_join created jr_id={jr.id} group_id={group.id}")
    return {"join_request_id": jr.id, "group_id": group.id, "status": "pending"}


@app.get("/groups/{group_id}/join-requests", response_model=list[JoinRequestOut])
def list_join_requests_rest(
    group_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List join requests. Requires admin/owner."""
    caller_id = 1
    assert_admin(db, group_id, caller_id)
    try:
        GroupJoinRequest = _get_join_request_model()
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))

    q = db.query(GroupJoinRequest).filter(GroupJoinRequest.group_id == group_id)
    if status:
        q = q.filter(GroupJoinRequest.status == status)
    return q.order_by(GroupJoinRequest.requested_at.desc()).all()


@app.post("/groups/{group_id}/join-requests/{join_request_id}/approve", response_model=JoinRequestOut)
def approve_join_request_rest(group_id: int, join_request_id: int, db: Session = Depends(get_db)):
    """Approve a pending join request. Requires admin/owner."""
    caller_id = 1
    assert_admin(db, group_id, caller_id)
    try:
        GroupJoinRequest = _get_join_request_model()
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))

    jr = db.query(GroupJoinRequest).filter(
        GroupJoinRequest.id == join_request_id,
        GroupJoinRequest.group_id == group_id,
    ).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Join request not found")
    if jr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Join request is already {jr.status}")

    jr.status      = "approved"
    jr.resolved_at = datetime.utcnow()
    jr.resolved_by = caller_id

    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id, GroupMember.user_id == jr.user_id
    ).first()
    if existing:
        existing.is_active = True
    else:
        db.add(GroupMember(group_id=group_id, user_id=jr.user_id, role=GroupMemberRole.member))

    _write_audit(db, group_id, caller_id, "join_approved", target_user_id=jr.user_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] approve_join_request DB commit failed jr_id={join_request_id}")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(jr)
    log.info(f"[REST] approve_join_request jr_id={join_request_id} group_id={group_id} user_id={jr.user_id}")
    return jr


@app.post("/groups/{group_id}/join-requests/{join_request_id}/reject", response_model=JoinRequestOut)
def reject_join_request_rest(
    group_id: int, join_request_id: int,
    note: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Reject a pending join request. Requires admin/owner."""
    caller_id = 1
    assert_admin(db, group_id, caller_id)
    try:
        GroupJoinRequest = _get_join_request_model()
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))

    jr = db.query(GroupJoinRequest).filter(
        GroupJoinRequest.id == join_request_id,
        GroupJoinRequest.group_id == group_id,
    ).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Join request not found")
    if jr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Join request is already {jr.status}")

    jjr.status      = JoinRequestStatus.rejected   # or JoinRequestStatus.rejected
    jr.approved_at = datetime.utcnow()
    jr.approved_by = caller_id

    _write_audit(db, group_id, caller_id, "join_rejected", target_user_id=jr.user_id, detail=note)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] reject_join_request DB commit failed jr_id={join_request_id}")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(jr)
    log.info(f"[REST] reject_join_request jr_id={join_request_id} group_id={group_id}")
    return jr


# ── Roles & ownership ─────────────────────────────────────────────────────────

@app.patch("/groups/{group_id}/members/{user_id}/role")
def change_member_role_rest(
    group_id: int, user_id: int, payload: RoleChangeRequest, db: Session = Depends(get_db)
):
    """Promote or demote a member. Only owner can call this."""
    caller_id = 1
    assert_owner(db, group_id, caller_id)

    if payload.new_role not in ("admin", "member"):
        raise HTTPException(status_code=422, detail="new_role must be 'admin' or 'member'")

    target = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id,
        GroupMember.is_active == True,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Active member not found")
    if target.role == GroupMemberRole.owner:
        raise HTTPException(status_code=400, detail="Cannot change owner role; use transfer_ownership")
    if target.user_id == caller_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    old_role    = target.role.value
    target.role = GroupMemberRole(payload.new_role)
    action      = "member_promoted" if payload.new_role == "admin" else "member_demoted"
    _write_audit(db, group_id, caller_id, action, target_user_id=user_id,
                 detail=f"{old_role} → {payload.new_role}")
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] change_member_role DB commit failed group_id={group_id}")
        raise HTTPException(status_code=500, detail="Database error")

    log.info(f"[REST] change_member_role group_id={group_id} user_id={user_id} {old_role} → {payload.new_role}")
    return {"user_id": user_id, "old_role": old_role, "new_role": payload.new_role}


@app.post("/groups/{group_id}/transfer-ownership")
def transfer_ownership_rest(
    group_id: int, payload: TransferOwnershipRequest, db: Session = Depends(get_db)
):
    """Transfer ownership to another active member. Only current owner can call."""
    caller_id     = 1
    new_owner_uid = payload.new_owner_user_id
    assert_owner(db, group_id, caller_id)

    if new_owner_uid == caller_id:
        raise HTTPException(status_code=400, detail="You are already the owner")

    new_owner_membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == new_owner_uid,
        GroupMember.is_active == True,
    ).first()
    if not new_owner_membership:
        raise HTTPException(status_code=404, detail="Target user is not an active member")

    current_owner_membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == caller_id,
    ).first()

    current_owner_membership.role  = GroupMemberRole.admin
    new_owner_membership.role      = GroupMemberRole.owner
    _write_audit(db, group_id, caller_id, "ownership_transferred",
                 target_user_id=new_owner_uid,
                 detail=f"from={caller_id} to={new_owner_uid}")
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] transfer_ownership DB commit failed group_id={group_id}")
        raise HTTPException(status_code=500, detail="Database error")

    log.info(f"[REST] transfer_ownership group_id={group_id} from={caller_id} to={new_owner_uid}")
    return {"success": True, "new_owner_user_id": new_owner_uid, "previous_owner_user_id": caller_id}


# ── Membership deactivate / reactivate ────────────────────────────────────────

@app.patch("/groups/{group_id}/members/{user_id}/deactivate")
def deactivate_member_rest(group_id: int, user_id: int, db: Session = Depends(get_db)):
    """Deactivate a member. Requires admin/owner. Cannot deactivate the owner."""
    caller_id = 1
    assert_admin(db, group_id, caller_id)

    target = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id,
        GroupMember.is_active == True,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Active member not found")
    if target.role == GroupMemberRole.owner:
        raise HTTPException(status_code=400, detail="Cannot deactivate the group owner")

    target.is_active = False
    _write_audit(db, group_id, caller_id, "member_deactivated", target_user_id=user_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] deactivate_member DB commit failed group_id={group_id} user_id={user_id}")
        raise HTTPException(status_code=500, detail="Database error")

    log.info(f"[REST] deactivate_member group_id={group_id} user_id={user_id}")
    return {"user_id": user_id, "is_active": False}


@app.patch("/groups/{group_id}/members/{user_id}/reactivate")
def reactivate_member_rest(group_id: int, user_id: int, db: Session = Depends(get_db)):
    """Reactivate a deactivated member. Requires admin/owner."""
    caller_id = 1
    assert_admin(db, group_id, caller_id)

    target = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Member record not found")
    if target.is_active:
        raise HTTPException(status_code=400, detail="Member is already active")

    target.is_active = True
    _write_audit(db, group_id, caller_id, "member_reactivated", target_user_id=user_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] reactivate_member DB commit failed group_id={group_id} user_id={user_id}")
        raise HTTPException(status_code=500, detail="Database error")

    log.info(f"[REST] reactivate_member group_id={group_id} user_id={user_id}")
    return {"user_id": user_id, "is_active": True}


# ── Audit log ─────────────────────────────────────────────────────────────────

@app.get("/groups/{group_id}/audit-log", response_model=list[AuditLogOut])
def get_audit_log_rest(
    group_id: int, limit: int = 50, db: Session = Depends(get_db)
):
    """Get audit log entries for a group. Requires member access."""
    caller_id = 1
    assert_member(db, group_id, caller_id)
    try:
        GroupAuditLog = _get_audit_log_model()
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))

    entries = (
        db.query(GroupAuditLog)
        .filter(GroupAuditLog.group_id == group_id)
        .order_by(GroupAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return entries


# ── Unarchive ─────────────────────────────────────────────────────────────────

@app.post("/groups/{group_id}/unarchive", response_model=GroupOut)
def unarchive_group_rest(group_id: int, db: Session = Depends(get_db)):
    """Unarchive a group. Requires owner role."""
    caller_id = 1
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.status != GroupStatus.archived:
        raise HTTPException(status_code=400, detail="Group is not archived")
    assert_owner(db, group_id, caller_id)

    group.status      = GroupStatus.active
    group.archived_at = None
    _write_audit(db, group_id, caller_id, "group_unarchived")
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.exception(f"[REST] unarchive_group DB commit failed group_id={group_id}")
        raise HTTPException(status_code=500, detail="Database error")
    db.refresh(group)
    log.info(f"[REST] unarchive_group group_id={group_id}")
    return group


# ── My groups (private visibility) ───────────────────────────────────────────

@app.get("/my/groups", response_model=list[GroupOut])
def list_my_groups_rest(db: Session = Depends(get_db)):
    """List all groups the caller is an active member of."""
    caller_id   = 1
    memberships = db.query(GroupMember).filter(
        GroupMember.user_id == caller_id,
        GroupMember.is_active == True,
    ).all()
    group_ids = [m.group_id for m in memberships]
    if not group_ids:
        return []
    return db.query(Group).filter(Group.id.in_(group_ids)).order_by(Group.created_at.desc()).all()


# ─────────────────────────────────────────────────────────────────────────────
# Frontend mount (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

from frontend import mount_frontend
mount_frontend(app)