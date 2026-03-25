# ReviewReply AI — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web-based SaaS where UK small businesses see their Google reviews, get AI-generated responses, and publish them — all from a simple dashboard.

**Architecture:** FastAPI backend with Jinja2 templates (server-rendered HTML, no SPA). SQLite for MVP storage. Google OAuth for user auth + Google Business Profile API for reviews. Claude API for response generation. Stripe Checkout for payments. Docker for deployment.

**Tech Stack:** Python 3.14, FastAPI, Jinja2, SQLite, Anthropic Claude API, Google OAuth2, Google Business Profile API, Stripe, Docker, Tailwind CSS (CDN)

---

## File Structure

```
reviewbot/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env
├── app/
│   ├── main.py              # FastAPI app, routes, startup
│   ├── config.py             # Settings from env
│   ├── database.py           # SQLite models + connection
│   ├── auth.py               # Google OAuth flow
│   ├── google_reviews.py     # Google Business Profile API client
│   ├── ai_responder.py       # Claude response generation (exists, keep)
│   ├── stripe_billing.py     # Stripe checkout + webhook
│   ├── templates/
│   │   ├── base.html         # Layout with nav, Tailwind
│   │   ├── landing.html      # Public landing page
│   │   ├── dashboard.html    # Main review dashboard
│   │   ├── settings.html     # Business settings, tone config
│   │   ├── pricing.html      # Pricing page
│   │   └── login.html        # Login page
│   └── static/
│       └── logo.svg          # Simple logo
└── tests/
    ├── test_ai_responder.py
    ├── test_database.py
    └── test_routes.py
```

---

## Chunk 1: Core Backend

### Task 1: Config + Database

**Files:**
- Create: `app/config.py`
- Create: `app/database.py`

- [ ] **Step 1: Create config.py**

```python
# app/config.py — loads all settings from .env
```

- [ ] **Step 2: Create database.py with SQLite models**

Tables: `users`, `businesses`, `reviews`, `responses`

- [ ] **Step 3: Test database creates tables**

Run: `python -c "from app.database import init_db; init_db()"`

- [ ] **Step 4: Commit**

### Task 2: FastAPI App Skeleton + Landing Page

**Files:**
- Create: `app/main.py`
- Create: `app/templates/base.html`
- Create: `app/templates/landing.html`

- [ ] **Step 1: Create FastAPI app with Jinja2**
- [ ] **Step 2: Create base.html with Tailwind CDN**
- [ ] **Step 3: Create landing.html — hero, features, CTA, pricing**
- [ ] **Step 4: Test: `uvicorn app.main:app` → visit localhost:8000**
- [ ] **Step 5: Commit**

### Task 3: Google OAuth Login

**Files:**
- Create: `app/auth.py`
- Create: `app/templates/login.html`

- [ ] **Step 1: Implement Google OAuth2 flow**

`/auth/google` → redirect to Google → `/auth/callback` → create user → set session cookie

- [ ] **Step 2: Create login page**
- [ ] **Step 3: Test OAuth flow locally**
- [ ] **Step 4: Commit**

### Task 4: Dashboard + Review Display

**Files:**
- Create: `app/templates/dashboard.html`
- Modify: `app/main.py` — add dashboard route

- [ ] **Step 1: Create dashboard route (requires auth)**
- [ ] **Step 2: Create dashboard.html — shows reviews + AI responses**
- [ ] **Step 3: Add mock data for testing**
- [ ] **Step 4: Test: login → see dashboard with mock reviews**
- [ ] **Step 5: Commit**

---

## Chunk 2: Google Reviews + AI Integration

### Task 5: Google Business Profile API Client

**Files:**
- Create: `app/google_reviews.py`

- [ ] **Step 1: Implement fetch_locations() — get user's business locations**
- [ ] **Step 2: Implement fetch_reviews() — get reviews for a location**
- [ ] **Step 3: Implement post_reply() — publish a reply to a review**
- [ ] **Step 4: Test with mock data**
- [ ] **Step 5: Commit**

### Task 6: AI Response Generation Integration

**Files:**
- Modify: `app/ai_responder.py` (already exists)
- Modify: `app/main.py` — add generate + approve routes

- [ ] **Step 1: Add route POST /reviews/{id}/generate — generates AI response**
- [ ] **Step 2: Add route POST /reviews/{id}/approve — publishes response via Google API**
- [ ] **Step 3: Add route POST /reviews/{id}/edit — save edited response**
- [ ] **Step 4: Add "Generate All" button for batch generation**
- [ ] **Step 5: Test full flow: see review → generate → edit → approve**
- [ ] **Step 6: Commit**

### Task 7: Settings Page

**Files:**
- Create: `app/templates/settings.html`
- Modify: `app/main.py` — add settings routes

- [ ] **Step 1: Create settings page — business name, type, tone selector**
- [ ] **Step 2: Save settings to database**
- [ ] **Step 3: Test: change tone → generate response → verify tone changes**
- [ ] **Step 4: Commit**

---

## Chunk 3: Payments + Docker + Deploy

### Task 8: Stripe Billing

**Files:**
- Create: `app/stripe_billing.py`
- Create: `app/templates/pricing.html`

- [ ] **Step 1: Create pricing page with two plans (£19/£39)**
- [ ] **Step 2: Implement Stripe Checkout session creation**
- [ ] **Step 3: Implement Stripe webhook for subscription events**
- [ ] **Step 4: Add subscription check middleware — free trial 7 days, then require payment**
- [ ] **Step 5: Test with Stripe test mode**
- [ ] **Step 6: Commit**

### Task 9: Docker Setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Update: `requirements.txt`

- [ ] **Step 1: Create Dockerfile (python:3.14-slim, install deps, run uvicorn)**
- [ ] **Step 2: Create docker-compose.yml (app + volumes for SQLite)**
- [ ] **Step 3: Test: `docker compose up --build` → visit localhost:8000**
- [ ] **Step 4: Commit**

### Task 10: Landing Page Polish

**Files:**
- Modify: `app/templates/landing.html`

- [ ] **Step 1: Add sections: Hero, Problem, Solution, How it works, Pricing, FAQ, CTA**
- [ ] **Step 2: Add social proof / stats section**
- [ ] **Step 3: Mobile responsive check**
- [ ] **Step 4: Commit**
