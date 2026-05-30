# MCP Expense Tracker

A full-stack expense tracking application built on the Model Context Protocol (MCP), featuring personal expense management, collaborative group expense sharing, invite-code based group membership, role-based access control, settlements, and audit logs.

## Features

### Personal Expense Tracking

* Add, edit, and delete expenses
* Categorize expenses
* Multiple payment methods
* Recurring expenses
* Tags and descriptions
* Dashboard analytics

### Group Expense Management

* Create and manage expense groups
* Automatic invite code generation
* Join groups via invite codes
* Join request approval workflow
* Multiple split methods
* Settlement calculations
* Group balance tracking

### Access Control

* Owner, Admin, and Member roles
* Multi-admin support
* Role management
* Group privacy controls

### Audit & Monitoring

* Group activity audit logs
* Membership change tracking
* Administrative action history

### Authentication

* OAuth 2.0 with PKCE
* Secure session handling
* MCP-compatible authentication flow

## Tech Stack

### Backend

* Python 3.11+
* FastAPI
* SQLAlchemy
* PostgreSQL
* MCP (Model Context Protocol)

### Frontend

* Bootstrap 5
* Bootstrap Icons
* HTML/CSS
* JavaScript

## Installation

### Clone Repository

```bash
git clone https://github.com/DP132/mcp_expense_tracker.git
cd mcp_expense_tracker
```

### Create Virtual Environment

```bash
python -m venv mcp_env
```

### Activate Environment

Windows:

```bash
mcp_env\Scripts\activate
```

Linux / macOS:

```bash
source mcp_env/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment



### Run Application

```bash
uvicorn backend:app --reload --port 8001
```

Open:

```text
http://localhost:8001/app
```

## Project Structure

```text
mcp_expense_tracker/
│
├── backend.py
├── frontend.py
├── db.py
├── mcp_server.py
├── requirements.txt
├── README.md
│
├── models/
├── services/
├── static/
└── templates/
```

## Core Functionality

* Expense Tracking
* Group Expense Splitting
* Invite Code System
* Join Approval Workflow
* Role-Based Access Control
* Settlement Management
* Audit Logging
* OAuth Authentication
* MCP Tool Integration

## Future Improvements

* Email notifications
* Expense attachments
* Budget planning
* Mobile application
* Advanced analytics
* Export reports


