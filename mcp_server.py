# import asyncio
# import json
# from typing import Optional
# from sqlalchemy import extract
# from db import Expense, SessionLocal, init_db

# from mcp.server import Server
# from mcp.server.stdio import stdio_server
# from mcp import types

# init_db()

# app = Server("expense-tracker")


# def get_db():
#     db = SessionLocal()
#     try:
#         return db
#     except Exception:
#         db.close()
#         raise


# def expense_to_dict(e) -> dict:
#     return {
#         "id": e.id,
#         "amount": e.amount,
#         "category": e.category,
#         "date": str(e.date),
#         "description": e.description,
#         "tags": e.tags,
#         "is_recurring": e.is_recurring,
#         "payment_method": e.payment_method,
#     }


# # ─── Tool Definitions ─────────────────────────────────────────────────────────

# @app.list_tools()
# async def list_tools() -> list[types.Tool]:
#     return [
#         types.Tool(
#             name="create_expense",
#             description="Create a new expense record.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "amount":         {"type": "number",  "description": "Expense amount in INR"},
#                     "category":       {"type": "string",  "description": "Category: Food, Transport, Shopping, Health, Utilities, Entertainment, Other"},
#                     "date":           {"type": "string",  "description": "Date in YYYY-MM-DD format"},
#                     "description":    {"type": "string",  "description": "Optional description"},
#                     "tags":           {"type": "string",  "description": "Comma-separated tags e.g. 'lunch,office'"},
#                     "is_recurring":   {"type": "boolean", "description": "True if recurring expense"},
#                     "payment_method": {"type": "string",  "description": "Cash, Credit Card, Debit Card, UPI, Net Banking, Other"},
#                 },
#                 "required": ["amount", "category", "date"],
#             },
#         ),
#         types.Tool(
#             name="list_expenses",
#             description="List all expenses with optional filters.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "category":       {"type": "string",  "description": "Filter by category"},
#                     "payment_method": {"type": "string",  "description": "Filter by payment method"},
#                     "is_recurring":   {"type": "boolean", "description": "Filter by recurring flag"},
#                     "month":          {"type": "integer", "description": "Filter by month (1-12)"},
#                     "year":           {"type": "integer", "description": "Filter by year e.g. 2024"},
#                 },
#             },
#         ),
#         types.Tool(
#             name="get_expense",
#             description="Get a single expense by ID.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "expense_id": {"type": "integer", "description": "Expense ID"},
#                 },
#                 "required": ["expense_id"],
#             },
#         ),
#         types.Tool(
#             name="update_expense",
#             description="Update an existing expense by ID. Only provided fields are updated.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "expense_id":     {"type": "integer", "description": "Expense ID to update"},
#                     "amount":         {"type": "number",  "description": "New amount"},
#                     "category":       {"type": "string",  "description": "New category"},
#                     "date":           {"type": "string",  "description": "New date YYYY-MM-DD"},
#                     "description":    {"type": "string",  "description": "New description"},
#                     "tags":           {"type": "string",  "description": "New tags"},
#                     "is_recurring":   {"type": "boolean", "description": "New recurring flag"},
#                     "payment_method": {"type": "string",  "description": "New payment method"},
#                 },
#                 "required": ["expense_id"],
#             },
#         ),
#         types.Tool(
#             name="delete_expense",
#             description="Delete an expense by ID.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "expense_id": {"type": "integer", "description": "Expense ID to delete"},
#                 },
#                 "required": ["expense_id"],
#             },
#         ),
#         types.Tool(
#             name="get_summary",
#             description="Get total expenses, count, breakdown by category and payment method.",
#             inputSchema={"type": "object", "properties": {}},
#         ),
#     ]


# # ─── Tool Handlers ────────────────────────────────────────────────────────────

# @app.call_tool()
# async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

#     if name == "create_expense":
#         db = get_db()
#         try:
#             expense = Expense(
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
#             result = expense_to_dict(expense)
#         finally:
#             db.close()

#     elif name == "list_expenses":
#         db = get_db()
#         try:
#             q = db.query(Expense)
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
#             result = [expense_to_dict(e) for e in q.order_by(Expense.date.desc()).all()]
#         finally:
#             db.close()

#     elif name == "get_expense":
#         db = get_db()
#         try:
#             expense = db.query(Expense).filter(Expense.id == arguments["expense_id"]).first()
#             result = expense_to_dict(expense) if expense else {"error": "Expense not found"}
#         finally:
#             db.close()

#     elif name == "update_expense":
#         db = get_db()
#         try:
#             expense = db.query(Expense).filter(Expense.id == arguments["expense_id"]).first()
#             if not expense:
#                 result = {"error": "Expense not found"}
#             else:
#                 for field in ["amount", "category", "date", "description", "tags", "is_recurring", "payment_method"]:
#                     if field in arguments:
#                         setattr(expense, field, arguments[field])
#                 db.commit()
#                 db.refresh(expense)
#                 result = expense_to_dict(expense)
#         finally:
#             db.close()

#     elif name == "delete_expense":
#         db = get_db()
#         try:
#             expense = db.query(Expense).filter(Expense.id == arguments["expense_id"]).first()
#             if not expense:
#                 result = {"error": "Expense not found"}
#             else:
#                 db.delete(expense)
#                 db.commit()
#                 result = {"success": True, "deleted_id": arguments["expense_id"]}
#         finally:
#             db.close()

#     elif name == "get_summary":
#         db = get_db()
#         try:
#             expenses = db.query(Expense).all()
#             total = sum(e.amount for e in expenses)
#             by_category: dict = {}
#             by_payment: dict = {}
#             for e in expenses:
#                 by_category[e.category] = by_category.get(e.category, 0) + e.amount
#                 if e.payment_method:
#                     by_payment[e.payment_method] = by_payment.get(e.payment_method, 0) + e.amount
#             result = {
#                 "total": round(total, 2),
#                 "count": len(expenses),
#                 "by_category": {k: round(v, 2) for k, v in by_category.items()},
#                 "by_payment_method": {k: round(v, 2) for k, v in by_payment.items()},
#             }
#         finally:
#             db.close()

#     else:
#         result = {"error": f"Unknown tool: {name}"}

#     return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# # ─── Entry point ──────────────────────────────────────────────────────────────

# async def main():
#     async with stdio_server() as (read_stream, write_stream):
#         await app.run(read_stream, write_stream, app.create_initialization_options())


# if __name__ == "__main__":
#     asyncio.run(main())


import asyncio
import json
from collections import defaultdict
from typing import Optional, List
from datetime import date

from sqlalchemy import extract
from db import (
    Expense, User, SessionLocal, init_db,
    Group, GroupMember, GroupExpense, ExpenseParticipant, SettlementRecord,
    GroupType, GroupMemberRole, SplitType, GroupStatus, ExpenseCategory, SettlementStatus,
)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

init_db()

app = Server("expense-tracker")

# ─── Default user for stdio server (no OAuth in stdio mode) ───────────────────
# In stdio mode there is no HTTP auth layer; we default to user_id=1.
# Override by setting EXPENSE_USER_ID in the environment if needed.
import os
DEFAULT_USER_ID: int = int(os.environ.get("EXPENSE_USER_ID", 1))


def get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


# ─── Serialisation helpers ────────────────────────────────────────────────────

def _expense_dict(e) -> dict:
    return {
        "id": e.id,
        "user_id": e.user_id,
        "amount": e.amount,
        "category": e.category,
        "date": str(e.date),
        "description": e.description,
        "tags": e.tags,
        "is_recurring": e.is_recurring,
        "payment_method": e.payment_method,
    }


def _group_dict(g) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "group_type": g.group_type.value,
        "status": g.status.value,
        "created_by": g.created_by,
        "created_at": g.created_at.isoformat(),
    }


def _group_expense_dict(e, shares: list = None) -> dict:
    base = {
        "id": e.id,
        "group_id": e.group_id,
        "title": e.title,
        "amount": e.amount,
        "category": e.category.value,
        "paid_by": e.paid_by,
        "split_type": e.split_type.value,
        "date": str(e.date),
        "description": e.description,
        "is_settled": e.is_settled,
        "created_at": e.created_at.isoformat(),
    }
    if shares:
        base["splits"] = shares
    elif hasattr(e, "participants") and e.participants:
        base["splits"] = [
            {
                "user_id": p.user_id,
                "share_value": p.share_value,
                "share_amount": p.share_amount,
            }
            for p in e.participants
        ]
    return base


# ─── Split & debt logic (mirrored from main.py) ───────────────────────────────

def compute_split_shares(
    total_amount: float,
    split_type: SplitType,
    participant_user_ids: Optional[List[int]],
    participants: Optional[list],          # list of dicts {user_id, share_value}
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
        total_pct = sum(p["share_value"] for p in participants)
        if abs(total_pct - 100.0) > 0.01:
            raise ValueError(f"Percentages must sum to 100, got {total_pct}")
        return [
            {
                "user_id": p["user_id"],
                "share_value": p["share_value"],
                "share_amount": round(total_amount * p["share_value"] / 100, 2),
            }
            for p in participants
        ]

    if split_type == SplitType.fixed:
        total_fixed = sum(p["share_value"] for p in participants)
        if abs(total_fixed - total_amount) > 0.01:
            raise ValueError(f"Fixed amounts must sum to {total_amount}, got {total_fixed}")
        return [
            {
                "user_id": p["user_id"],
                "share_value": p["share_value"],
                "share_amount": round(p["share_value"], 2),
            }
            for p in participants
        ]

    if split_type == SplitType.by_days:
        total_days = sum(p["share_value"] for p in participants)
        if total_days <= 0:
            raise ValueError("Total days must be > 0")
        return [
            {
                "user_id": p["user_id"],
                "share_value": p["share_value"],
                "share_amount": round(total_amount * p["share_value"] / total_days, 2),
            }
            for p in participants
        ]

    if split_type == SplitType.custom:
        return [
            {
                "user_id": p["user_id"],
                "share_value": None,
                "share_amount": round(p["share_value"], 2),
            }
            for p in participants
        ]

    raise ValueError(f"Unknown split_type: {split_type}")


def compute_net_balances(db, group_id: int) -> dict:
    balances: dict[int, float] = defaultdict(float)
    expenses = db.query(GroupExpense).filter(GroupExpense.group_id == group_id).all()
    for expense in expenses:
        balances[expense.paid_by] += expense.amount
        for p in expense.participants:
            balances[p.user_id] -= p.share_amount
    return dict(balances)


def _simplify_debts(net_balances: dict) -> list:
    creditors = sorted(
        [(uid, bal) for uid, bal in net_balances.items() if bal > 0.001],
        key=lambda x: x[1],
    )
    debtors = sorted(
        [(uid, -bal) for uid, bal in net_balances.items() if bal < -0.001],
        key=lambda x: x[1],
    )
    transactions = []
    i, j = len(creditors) - 1, len(debtors) - 1
    creditors = list(creditors)
    debtors = list(debtors)
    while i >= 0 and j >= 0:
        cred_uid, cred_amt = creditors[i]
        debt_uid, debt_amt = debtors[j]
        settled = min(cred_amt, debt_amt)
        transactions.append(
            {"from_user_id": debt_uid, "to_user_id": cred_uid, "amount": round(settled, 2)}
        )
        creditors[i] = (cred_uid, round(cred_amt - settled, 2))
        debtors[j] = (debt_uid, round(debt_amt - settled, 2))
        if creditors[i][1] < 0.001:
            i -= 1
        if debtors[j][1] < 0.001:
            j -= 1
    return transactions


# ─── Tool Definitions ─────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Personal expense tools ────────────────────────────────────────────
        types.Tool(
            name="create_expense",
            description="Create a new personal expense record for the authenticated user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount":         {"type": "number",  "description": "Expense amount in INR"},
                    "category":       {"type": "string",  "description": "Food, Transport, Shopping, Health, Utilities, Entertainment, Other"},
                    "date":           {"type": "string",  "description": "Date in YYYY-MM-DD format"},
                    "description":    {"type": "string",  "description": "Optional description"},
                    "tags":           {"type": "string",  "description": "Comma-separated tags e.g. 'lunch,office'"},
                    "is_recurring":   {"type": "boolean", "description": "True if recurring expense"},
                    "payment_method": {"type": "string",  "description": "Cash, Credit Card, Debit Card, UPI, Net Banking, Other"},
                },
                "required": ["amount", "category", "date"],
            },
        ),
        types.Tool(
            name="list_expenses",
            description="List personal expenses for the authenticated user with optional filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category":       {"type": "string"},
                    "payment_method": {"type": "string"},
                    "is_recurring":   {"type": "boolean"},
                    "month":          {"type": "integer", "description": "Filter by month (1-12)"},
                    "year":           {"type": "integer", "description": "Filter by year e.g. 2024"},
                },
            },
        ),
        types.Tool(
            name="get_expense",
            description="Get a single personal expense by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "expense_id": {"type": "integer", "description": "Expense ID"},
                },
                "required": ["expense_id"],
            },
        ),
        types.Tool(
            name="update_expense",
            description="Update an existing personal expense by ID. Only provided fields are updated.",
            inputSchema={
                "type": "object",
                "properties": {
                    "expense_id":     {"type": "integer", "description": "Expense ID to update"},
                    "amount":         {"type": "number"},
                    "category":       {"type": "string"},
                    "date":           {"type": "string",  "description": "YYYY-MM-DD"},
                    "description":    {"type": "string"},
                    "tags":           {"type": "string"},
                    "is_recurring":   {"type": "boolean"},
                    "payment_method": {"type": "string"},
                },
                "required": ["expense_id"],
            },
        ),
        types.Tool(
            name="delete_expense",
            description="Delete a personal expense by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "expense_id": {"type": "integer", "description": "Expense ID to delete"},
                },
                "required": ["expense_id"],
            },
        ),
        types.Tool(
            name="get_summary",
            description="Get total spend, count, breakdown by category and payment method for the authenticated user.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_profile",
            description="Get the authenticated user's profile.",
            inputSchema={"type": "object", "properties": {}},
        ),

        # ── Group tools ───────────────────────────────────────────────────────
        types.Tool(
            name="create_group",
            description="Create a new expense group. The authenticated user becomes the owner.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name":            {"type": "string", "description": "Group name, e.g. 'Goa Trip'"},
                    "description":     {"type": "string", "description": "Optional description"},
                    "group_type":      {"type": "string", "enum": ["family","friends","trip","office","roommates","event","other"]},
                    "member_user_ids": {"type": "array",  "items": {"type": "integer"}, "description": "Additional member user IDs to add on creation"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="add_group_member",
            description="Add a user to a group. Requires admin or owner role.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {"type": "integer"},
                    "user_id":  {"type": "integer", "description": "User to add"},
                },
                "required": ["group_id", "user_id"],
            },
        ),
        types.Tool(
            name="remove_group_member",
            description="Remove a member from a group. Requires admin or owner role.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {"type": "integer"},
                    "user_id":  {"type": "integer", "description": "User to remove"},
                },
                "required": ["group_id", "user_id"],
            },
        ),
        types.Tool(
            name="add_group_expense",
            description=(
                "Add an expense to a group. Supports equal, percentage, fixed, by_days, and custom splits. "
                "For equal split supply participant_user_ids. "
                "For percentage/fixed/by_days/custom supply participants array with user_id and share_value."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id":             {"type": "integer"},
                    "title":                {"type": "string"},
                    "amount":               {"type": "number"},
                    "category":             {"type": "string", "enum": ["food","travel","hotel","fuel","entertainment","shopping","miscellaneous"]},
                    "paid_by":              {"type": "integer", "description": "user_id of who paid"},
                    "split_type":           {"type": "string", "enum": ["equal","percentage","fixed","by_days","custom"]},
                    "date":                 {"type": "string", "description": "YYYY-MM-DD"},
                    "description":          {"type": "string"},
                    "participant_user_ids": {"type": "array", "items": {"type": "integer"}, "description": "For equal split only"},
                    "participants": {
                        "type": "array",
                        "description": "For percentage/fixed/by_days/custom",
                        "items": {
                            "type": "object",
                            "properties": {
                                "user_id":     {"type": "integer"},
                                "share_value": {"type": "number", "description": "% / days / INR depending on split_type"},
                            },
                            "required": ["user_id", "share_value"],
                        },
                    },
                },
                "required": ["group_id", "title", "amount", "paid_by", "split_type", "date"],
            },
        ),
        types.Tool(
            name="get_group_summary",
            description="Get the dashboard summary for a group: total expenses, member balances, pending settlements.",
            inputSchema={
                "type": "object",
                "properties": {"group_id": {"type": "integer"}},
                "required": ["group_id"],
            },
        ),
        types.Tool(
            name="calculate_group_settlement",
            description="Calculate and persist the simplified debt transactions for a group. Returns the minimum set of payments needed.",
            inputSchema={
                "type": "object",
                "properties": {"group_id": {"type": "integer"}},
                "required": ["group_id"],
            },
        ),
        types.Tool(
            name="simplify_debts",
            description="Return the simplified debt graph for a group without persisting. Use for preview before confirming.",
            inputSchema={
                "type": "object",
                "properties": {"group_id": {"type": "integer"}},
                "required": ["group_id"],
            },
        ),
        types.Tool(
            name="get_member_balance",
            description="Get the net balance of a specific member in a group.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {"type": "integer"},
                    "user_id":  {"type": "integer"},
                },
                "required": ["group_id", "user_id"],
            },
        ),
        types.Tool(
            name="archive_group",
            description="Archive a group (locks it from new expenses). Requires owner role.",
            inputSchema={
                "type": "object",
                "properties": {"group_id": {"type": "integer"}},
                "required": ["group_id"],
            },
        ),
        types.Tool(
            name="list_group_expenses",
            description="List all expenses in a group with optional filters.",
            inputSchema={
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
        ),
    ]


# ─── Tool Handlers ────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    user_id = DEFAULT_USER_ID
    db = get_db()
    try:
        result = _run_tool(name, arguments, user_id, db)
    finally:
        db.close()

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


def _run_tool(name: str, arguments: dict, user_id: int, db) -> dict:  # noqa: C901

    # ── Personal expense tools ────────────────────────────────────────────────

    if name == "create_expense":
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
        db.commit()
        db.refresh(expense)
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
        db.commit()
        db.refresh(e)
        return _expense_dict(e)

    elif name == "delete_expense":
        e = db.query(Expense).filter(
            Expense.id == arguments["expense_id"],
            Expense.user_id == user_id,
        ).first()
        if not e:
            return {"error": "Expense not found"}
        db.delete(e)
        db.commit()
        return {"success": True, "deleted_id": arguments["expense_id"]}

    elif name == "get_summary":
        expenses = db.query(Expense).filter(Expense.user_id == user_id).all()
        total = sum(e.amount for e in expenses)
        by_cat: dict = {}
        by_pay: dict = {}
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
            "id": user.id,
            "name": user.name,
            "nickname": user.nickname,
            "email": user.email,
            "phone": user.phone,
        }

    # ── Group tools ───────────────────────────────────────────────────────────

    elif name == "create_group":
        group = Group(
            name=arguments["name"],
            description=arguments.get("description"),
            group_type=GroupType(arguments.get("group_type", "other")),
            created_by=user_id,
        )
        db.add(group)
        db.flush()

        # creator is always owner
        db.add(GroupMember(group_id=group.id, user_id=user_id, role=GroupMemberRole.owner))

        for mid in arguments.get("member_user_ids", []):
            if mid != user_id:
                member_exists = db.query(User).filter(User.id == mid).first()
                if not member_exists:
                    db.rollback()
                    return {"error": f"User {mid} not found"}
                db.add(GroupMember(group_id=group.id, user_id=mid, role=GroupMemberRole.member))

        db.commit()
        db.refresh(group)
        return _group_dict(group)

    elif name == "add_group_member":
        group_id       = arguments["group_id"]
        target_user_id = arguments["user_id"]

        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}
        if group.status == GroupStatus.archived:
            return {"error": "Group is archived"}

        caller = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if not caller or caller.role not in (GroupMemberRole.owner, GroupMemberRole.admin):
            return {"error": "Admin or owner permission required"}

        existing = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_user_id,
        ).first()
        if existing:
            if existing.is_active:
                return {"error": "User is already a member"}
            existing.is_active = True
            db.commit()
            return {"success": True, "message": "Member re-added", "user_id": target_user_id}

        target = db.query(User).filter(User.id == target_user_id).first()
        if not target:
            return {"error": f"User {target_user_id} not found"}

        db.add(GroupMember(group_id=group_id, user_id=target_user_id, role=GroupMemberRole.member))
        db.commit()
        return {"success": True, "message": "Member added", "user_id": target_user_id}

    elif name == "remove_group_member":
        group_id       = arguments["group_id"]
        target_user_id = arguments["user_id"]

        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        caller = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if not caller or caller.role not in (GroupMemberRole.owner, GroupMemberRole.admin):
            return {"error": "Admin or owner permission required"}

        target = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_user_id,
            GroupMember.is_active == True,
        ).first()
        if not target:
            return {"error": "Member not found or already removed"}
        if target.role == GroupMemberRole.owner:
            return {"error": "Cannot remove the group owner"}

        target.is_active = False
        db.commit()
        return {"success": True, "message": "Member removed", "user_id": target_user_id}

    elif name == "add_group_expense":
        group_id = arguments["group_id"]

        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}
        if group.status == GroupStatus.archived:
            return {"error": "Group is archived"}

        membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if not membership:
            return {"error": "Not a member of this group"}

        split_type = SplitType(arguments["split_type"])

        try:
            shares = compute_split_shares(
                total_amount=arguments["amount"],
                split_type=split_type,
                participant_user_ids=arguments.get("participant_user_ids"),
                participants=arguments.get("participants"),   # already plain dicts from JSON
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

        db.commit()
        db.refresh(expense)
        return _group_expense_dict(expense, shares)

    elif name == "get_group_summary":
        group_id = arguments["group_id"]

        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if not membership:
            return {"error": "Not a member of this group"}

        expenses = db.query(GroupExpense).filter(GroupExpense.group_id == group_id).all()
        total_amount = sum(e.amount for e in expenses)

        pending_settlements = db.query(SettlementRecord).filter(
            SettlementRecord.group_id == group_id,
            SettlementRecord.status == SettlementStatus.pending,
        ).count()

        net_balances = compute_net_balances(db, group_id)

        paid_by_map: dict[int, float] = defaultdict(float)
        share_map:   dict[int, float] = defaultdict(float)
        for e in expenses:
            paid_by_map[e.paid_by] += e.amount
            for p in e.participants:
                share_map[p.user_id] += p.share_amount

        members = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.is_active == True,
        ).all()

        member_uids = [m.user_id for m in members]
        users_q = db.query(User).filter(User.id.in_(member_uids)).all()
        uid_to_name = {u.id: (u.nickname or u.name) for u in users_q}

        member_balances = [
            {
                "user_id":     m.user_id,
                "user_name":   uid_to_name.get(m.user_id, f"User {m.user_id}"),
                "role":        m.role.value,
                "total_paid":  round(paid_by_map.get(m.user_id, 0), 2),
                "total_share": round(share_map.get(m.user_id, 0), 2),
                "net_balance": round(net_balances.get(m.user_id, 0), 2),
            }
            for m in members
        ]

        return {
            "group_id":            group.id,
            "group_name":          group.name,
            "status":              group.status.value,
            "total_members":       len(members),
            "total_expenses":      round(total_amount, 2),
            "expense_count":       len(expenses),
            "pending_settlements": pending_settlements,
            "member_balances":     member_balances,
        }

    elif name == "calculate_group_settlement":
        group_id = arguments["group_id"]

        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if not membership:
            return {"error": "Not a member of this group"}

        net_balances = compute_net_balances(db, group_id)
        transactions = _simplify_debts(net_balances)

        # wipe existing pending settlements before re-calculating
        db.query(SettlementRecord).filter(
            SettlementRecord.group_id == group_id,
            SettlementRecord.status == SettlementStatus.pending,
        ).delete()

        for t in transactions:
            db.add(SettlementRecord(
                group_id=group_id,
                from_user_id=t["from_user_id"],
                to_user_id=t["to_user_id"],
                amount=t["amount"],
            ))

        db.commit()
        return {
            "group_id":          group_id,
            "transaction_count": len(transactions),
            "settlements":       transactions,
        }

    elif name == "simplify_debts":
        group_id = arguments["group_id"]

        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return {"error": "Group not found"}

        membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if not membership:
            return {"error": "Not a member of this group"}

        net_balances = compute_net_balances(db, group_id)
        transactions = _simplify_debts(net_balances)
        return {"group_id": group_id, "settlements": transactions}

    elif name == "get_member_balance":
        group_id    = arguments["group_id"]
        target_uid  = arguments["user_id"]

        membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if not membership:
            return {"error": "Not a member of this group"}

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

        caller = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if not caller or caller.role != GroupMemberRole.owner:
            return {"error": "Only the owner can archive a group"}

        from datetime import datetime
        group.status      = GroupStatus.archived
        group.archived_at = datetime.utcnow()
        db.commit()
        return {"success": True, "group_id": group_id, "archived_at": group.archived_at.isoformat()}

    elif name == "list_group_expenses":
        group_id = arguments["group_id"]

        membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.is_active == True,
        ).first()
        if not membership:
            return {"error": "Not a member of this group"}

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
        return {
            "group_id": group_id,
            "expenses": [_group_expense_dict(e) for e in expenses],
        }

    return {"error": f"Unknown tool: {name}"}


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())