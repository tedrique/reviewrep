"""ReviewReply AI — FastAPI web application."""
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path

from app.config import SECRET_KEY, ANTHROPIC_API_KEY, DEBUG
from app.database import (
    init_db, get_user, get_businesses, get_reviews,
    create_business, add_review, save_response, approve_response,
    get_notification_prefs, save_notification_pref,
    get_team_members, create_team_invite, attach_member_user, remove_team_member,
)
from app.ai_responder import generate_response
from app.notifications import send_notifications

app = FastAPI(title="ReviewReply AI", docs_url="/docs" if DEBUG else None)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def startup():
    init_db()


# --- Helpers ---

def get_current_user(request: Request) -> dict | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user(user_id)


def get_account_context(request: Request) -> tuple[dict | None, int | None, str]:
    """Return (user, account_id, role). Account_id is the owner account whose data we're viewing."""
    user = get_current_user(request)
    if not user:
        return None, None, ""
    account_id = request.session.get("account_id") or user["id"]
    role = request.session.get("role") or "owner"
    request.session["account_id"] = account_id
    request.session["role"] = role
    return user, account_id, role


def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


# --- Public Routes ---

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request=request, name="landing.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(request=request, name="pricing.html", context={"user": user})


# --- Google OAuth ---

@app.get("/auth/google")
async def google_login(request: Request):
    from app.auth import get_login_url
    return RedirectResponse(get_login_url(), status_code=302)


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse("/login", status_code=302)
    from app.auth import exchange_code, get_user_info
    from app.database import create_user
    try:
        tokens = exchange_code(code)
        user_info = get_user_info(tokens["access_token"])
        user_id = create_user(
            email=user_info.get("email", ""),
            name=user_info.get("name", ""),
            google_id=user_info.get("id", ""),
            access_token=tokens.get("access_token", ""),
            refresh_token=tokens.get("refresh_token", ""),
        )
        request.session["user_id"] = user_id
        # Link to team invitation if one exists
        invite = attach_member_user(user_info.get("email", ""), user_id)
        if invite:
            request.session["account_id"] = invite["account_id"]
            request.session["role"] = invite["role"]
        else:
            request.session["account_id"] = user_id
            request.session["role"] = "owner"
        try:
            from app.email_service import send_welcome_email
            send_welcome_email(to=user_info["email"], name=user_info.get("name", ""))
        except Exception:
            pass
        # Check if user has businesses — if not, go to onboarding
        businesses = get_businesses(user_id)
        if not businesses:
            return RedirectResponse("/onboarding", status_code=302)
        return RedirectResponse("/dashboard", status_code=302)
    except Exception as e:
        print(f"OAuth error: {e}")
        return RedirectResponse("/login", status_code=302)


# --- Stripe Billing ---

@app.get("/billing/checkout/{plan}")
async def billing_checkout(request: Request, plan: str):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role == "staff":
        return RedirectResponse("/dashboard", status_code=302)
    from app.stripe_billing import create_checkout_session
    url = create_checkout_session(user["email"], user["id"], plan)
    return RedirectResponse(url, status_code=302)


@app.get("/billing/success")
async def billing_success(request: Request, session_id: str = ""):
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/billing/portal")
async def billing_portal(request: Request):
    user, account_id, role = get_account_context(request)
    if not user or not user.get("stripe_customer_id") or role == "staff":
        return RedirectResponse("/pricing", status_code=302)
    from app.stripe_billing import create_portal_session
    url = create_portal_session(user["stripe_customer_id"])
    return RedirectResponse(url, status_code=302)


@app.post("/billing/webhook")
async def billing_webhook(request: Request):
    from app.config import STRIPE_WEBHOOK_SECRET
    from app.stripe_billing import handle_webhook_event
    from app.database import db_connection
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if not STRIPE_WEBHOOK_SECRET:
        return {"status": "no webhook secret configured"}
    result = handle_webhook_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    if not result:
        return {"status": "ignored"}
    if result["event"] == "checkout_completed":
        with db_connection() as conn:
            conn.execute(
                "UPDATE users SET subscription_status='active', subscription_plan=?, stripe_customer_id=? WHERE id=?",
                (result["plan"], result["customer_id"], result["user_id"])
            )
    elif result["event"] == "subscription_cancelled":
        with db_connection() as conn:
            conn.execute(
                "UPDATE users SET subscription_status='cancelled' WHERE stripe_customer_id=?",
                (result["customer_id"],)
            )
    return {"status": "ok"}


# --- Admin backdoor login (hidden, not linked anywhere) ---

@app.get("/admin-login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_login.html")


@app.post("/admin-login")
async def demo_login(request: Request, email: str = Form(...), name: str = Form(...)):
    from app.database import create_user, db_connection

    # Check if user already exists
    with db_connection() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()

    user_id = create_user(email=email, name=name, google_id=f"demo_{email}")
    request.session["user_id"] = user_id
    request.session["account_id"] = user_id
    request.session["role"] = "owner"

    if existing:
        # Returning user — go straight to dashboard
        return RedirectResponse("/dashboard", status_code=302)

    # New user — send welcome email and start onboarding
    try:
        from app.email_service import send_welcome_email
        send_welcome_email(to=email, name=name)
    except Exception:
        pass

    return RedirectResponse("/onboarding", status_code=302)


# --- Dashboard ---

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    businesses = get_businesses(account_id)
    current_business = None
    reviews = []

    business_id = request.query_params.get("business_id")
    if businesses:
        if business_id:
            current_business = next((b for b in businesses if str(b["id"]) == business_id), businesses[0])
        else:
            current_business = businesses[0]
        reviews = get_reviews(current_business["id"])

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "user": user,
        "role": role,
        "businesses": businesses,
        "current_business": current_business,
        "reviews": reviews,
    })


# --- Business Management ---

@app.post("/business/add")
async def add_business(
    request: Request,
    name: str = Form(...),
    business_type: str = Form(...),
    location: str = Form(...),
    tone: str = Form("friendly and professional"),
):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role == "staff":
        raise HTTPException(status_code=403, detail="Staff cannot add businesses")
    create_business(account_id, name, business_type, location, tone)
    return RedirectResponse("/dashboard", status_code=302)


# --- Review Management ---

@app.post("/review/add")
async def add_review_manual(
    request: Request,
    business_id: int = Form(...),
    author: str = Form("Customer"),
    rating: int = Form(...),
    text: str = Form(...),
):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    from app.database import db_connection
    with db_connection() as conn:
        biz = conn.execute("SELECT * FROM businesses WHERE id = ? AND user_id = ?", (business_id, account_id)).fetchone()
        if not biz:
            raise HTTPException(status_code=403)
    add_review(business_id, author, rating, text)
    try:
        send_notifications(account_id, "new_review", {
            "business_name": biz["name"],
            "author": author,
            "rating": rating,
            "text": text,
        })
    except Exception:
        pass
    return RedirectResponse(f"/dashboard?business_id={business_id}", status_code=302)


# --- Google Business Sync ---

@app.post("/business/{business_id}/sync")
async def sync_reviews(request: Request, business_id: int):
    """Pull latest reviews from Google Business Profile."""
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    access_token = user.get("google_access_token", "")
    if not access_token:
        return RedirectResponse(f"/dashboard?business_id={business_id}&error=no_google", status_code=302)

    from app.database import db_connection
    with db_connection() as conn:
        biz = conn.execute("SELECT * FROM businesses WHERE id=? AND user_id=?", (business_id, account_id)).fetchone()
        if not biz or not biz["google_location_id"]:
            return RedirectResponse(f"/dashboard?business_id={business_id}&error=no_location", status_code=302)

    # Refresh token if needed
    from app.google_reviews import get_reviews as fetch_google_reviews, refresh_access_token
    from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

    if user.get("google_refresh_token"):
        new_token = refresh_access_token(user["google_refresh_token"], GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
        if new_token:
            access_token = new_token
            with db_connection() as conn:
                conn.execute("UPDATE users SET google_access_token=? WHERE id=?", (new_token, user["id"]))

    reviews = fetch_google_reviews(access_token, biz["google_location_id"])

    # Import new reviews
    imported = 0
    for rev in reviews:
        if rev["has_reply"]:
            continue
        with db_connection() as conn:
            exists = conn.execute("SELECT id FROM reviews WHERE google_review_id=? AND business_id=?",
                                  (rev["google_review_id"], business_id)).fetchone()
        if not exists and rev["text"]:
            add_review(business_id, rev["author"], rev["rating"], rev["text"],
                       google_review_id=rev["google_review_id"], review_time=rev["time"])
            imported += 1
            try:
                send_notifications(account_id, "new_review", {
                    "business_name": biz["name"],
                    "author": rev["author"],
                    "rating": rev["rating"],
                    "text": rev["text"],
                })
            except Exception:
                pass

    return RedirectResponse(f"/dashboard?business_id={business_id}&synced={imported}", status_code=302)


@app.post("/response/{response_id}/publish")
async def publish_response(request: Request, response_id: int):
    """Publish an approved response to Google."""
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    from app.database import db_connection
    with db_connection() as conn:
        row = conn.execute("""
            SELECT resp.*, r.google_review_id, r.business_id, b.google_location_id
            FROM responses resp
            JOIN reviews r ON resp.review_id = r.id
            JOIN businesses b ON r.business_id = b.id
            WHERE resp.id = ? AND b.user_id = ?
        """, (response_id, account_id)).fetchone()

    if not row or not row["google_review_id"] or not row["google_location_id"]:
        return RedirectResponse("/dashboard", status_code=302)

    reply_text = row["edited_response"] or row["ai_response"]
    review_name = f"{row['google_location_id']}/reviews/{row['google_review_id']}"

    from app.google_reviews import post_reply, refresh_access_token
    from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

    access_token = user.get("google_access_token", "")
    if user.get("google_refresh_token"):
        new_token = refresh_access_token(user["google_refresh_token"], GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
        if new_token:
            access_token = new_token

    success = post_reply(access_token, review_name, reply_text)
    if success:
        with db_connection() as conn:
            conn.execute("UPDATE responses SET status='published' WHERE id=?", (response_id,))

    return RedirectResponse(f"/dashboard?business_id={row['business_id']}", status_code=302)


@app.get("/business/connect-google")
async def connect_google_business(request: Request):
    """After Google OAuth, fetch user's business locations and let them pick one."""
    user, account_id, role = get_account_context(request)
    if not user or not user.get("google_access_token") or role == "staff":
        return RedirectResponse("/auth/google", status_code=302)

    from app.google_reviews import get_accounts, get_locations, refresh_access_token
    from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

    access_token = user["google_access_token"]
    if user.get("google_refresh_token"):
        new_token = refresh_access_token(user["google_refresh_token"], GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
        if new_token:
            access_token = new_token

    accounts = get_accounts(access_token)
    all_locations = []
    for acc in accounts:
        locs = get_locations(access_token, acc["name"])
        for loc in locs:
            all_locations.append({
                "name": loc.get("name", ""),
                "title": loc.get("title", loc.get("locationName", "Unknown")),
                "address": loc.get("storefrontAddress", {}).get("addressLines", [""])[0] if loc.get("storefrontAddress") else "",
            })

    return templates.TemplateResponse(request=request, name="connect_google.html", context={
        "user": user, "locations": all_locations,
    })


@app.post("/business/link-location")
async def link_google_location(request: Request, location_name: str = Form(...), location_title: str = Form("")):
    """Link a Google Business location to a ReviewRep business."""
    user, account_id, role = get_account_context(request)
    if not user or role == "staff":
        return RedirectResponse("/login", status_code=302)

    from app.database import db_connection
    businesses = get_businesses(account_id)

    if businesses:
        with db_connection() as conn:
            conn.execute("UPDATE businesses SET google_location_id=? WHERE id=?",
                         (location_name, businesses[0]["id"]))
    else:
        create_business(account_id, location_title or "My Business", "other", "", "friendly and professional")
        businesses = get_businesses(account_id)
        with db_connection() as conn:
            conn.execute("UPDATE businesses SET google_location_id=? WHERE id=?",
                         (location_name, businesses[0]["id"]))

    return RedirectResponse("/dashboard", status_code=302)


@app.post("/review/{review_id}/generate")
async def generate_ai_response(request: Request, review_id: int):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    from app.database import db_connection
    with db_connection() as conn:
        review = conn.execute("""
            SELECT r.*, b.name as business_name, b.type as business_type,
                   b.location, b.tone, b.owner_name, b.id as business_id,
                   b.auto_approve_high, b.banned_phrases, b.signoff_library, b.brand_facts
            FROM reviews r JOIN businesses b ON r.business_id = b.id
            WHERE r.id = ? AND b.user_id = ?
        """, (review_id, account_id)).fetchone()

    if not review:
        raise HTTPException(status_code=404)

    ai_response = generate_response(
        review_text=review["text"],
        rating=review["rating"],
        author=review["author"],
        business_name=review["business_name"],
        business_type=review["business_type"],
        location=review["location"],
        tone=review["tone"],
        api_key=ANTHROPIC_API_KEY,
        owner_name=review["owner_name"] or "",
        banned_phrases=review["banned_phrases"] or "",
        signoff_library=review["signoff_library"] or "",
        brand_facts=review["brand_facts"] or "",
    )

    response_id = save_response(review_id, ai_response)
    if review["auto_approve_high"] and review["rating"] >= 4:
        approve_response(response_id, ai_response)
        try:
            send_notifications(account_id, "approved", {
                "business_name": review["business_name"],
                "rating": review["rating"],
                "author": review["author"],
            })
        except Exception:
            pass
    else:
        try:
            send_notifications(account_id, "draft_ready", {
                "business_name": review["business_name"],
                "rating": review["rating"],
                "author": review["author"],
            })
        except Exception:
            pass
    return RedirectResponse(f"/dashboard?business_id={review['business_id']}", status_code=302)


@app.post("/review/{review_id}/generate-all")
async def generate_all_responses(request: Request, review_id: int):
    """Generate AI responses for all reviews without one."""
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # Get business_id from the review
    from app.database import db_connection
    with db_connection() as conn:
        review = conn.execute("SELECT business_id FROM reviews WHERE id = ?", (review_id,)).fetchone()
        if not review:
            raise HTTPException(status_code=404)
        business_id = review["business_id"]

        # Get all reviews without responses
        reviews_without = conn.execute("""
            SELECT r.*, b.name as business_name, b.type as business_type,
                   b.location, b.tone, b.owner_name,
                   b.auto_approve_high, b.banned_phrases, b.signoff_library, b.brand_facts
            FROM reviews r
            JOIN businesses b ON r.business_id = b.id
            LEFT JOIN responses resp ON resp.review_id = r.id
            WHERE r.business_id = ? AND b.user_id = ? AND resp.id IS NULL
        """, (business_id, account_id)).fetchall()

    for rev in reviews_without:
        try:
            ai_response = generate_response(
                review_text=rev["text"],
                rating=rev["rating"],
                author=rev["author"],
                business_name=rev["business_name"],
                business_type=rev["business_type"],
                location=rev["location"],
                tone=rev["tone"],
                api_key=ANTHROPIC_API_KEY,
                owner_name=rev["owner_name"] or "",
                banned_phrases=rev["banned_phrases"] or "",
                signoff_library=rev["signoff_library"] or "",
                brand_facts=rev["brand_facts"] or "",
            )
            resp_id = save_response(rev["id"], ai_response)
            if rev["auto_approve_high"] and rev["rating"] >= 4:
                approve_response(resp_id, ai_response)
                try:
                    send_notifications(account_id, "approved", {
                        "business_name": rev["business_name"],
                        "rating": rev["rating"],
                        "author": rev["author"],
                    })
                except Exception:
                    pass
        except Exception:
            continue

    return RedirectResponse(f"/dashboard?business_id={business_id}", status_code=302)


@app.post("/response/{response_id}/approve")
async def approve(request: Request, response_id: int):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    edited = form.get("edited_response", "")
    approve_response(response_id, edited)

    # Check if this is the first ever approve (onboarding) → show welcome
    from app.database import db_connection
    with db_connection() as conn:
        total_approved = conn.execute(
            "SELECT COUNT(*) as c FROM responses resp JOIN reviews r ON resp.review_id = r.id JOIN businesses b ON r.business_id = b.id WHERE b.user_id = ? AND resp.status = 'approved'",
            (account_id,)
        ).fetchone()["c"]
        if total_approved == 1:
            return RedirectResponse("/welcome", status_code=302)

    # Get business_id for redirect
    with db_connection() as conn:
        row = conn.execute("""
            SELECT r.business_id FROM responses resp
            JOIN reviews r ON resp.review_id = r.id
            JOIN businesses b ON r.business_id = b.id
            WHERE resp.id = ? AND b.user_id = ?
        """, (response_id, account_id)).fetchone()
    business_id = row["business_id"] if row else ""

    try:
        send_notifications(account_id, "approved", {
            "business_id": business_id,
        })
    except Exception:
        pass

    return RedirectResponse(f"/dashboard?business_id={business_id}", status_code=302)


# --- Settings ---

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    businesses = get_businesses(account_id)
    notifications = get_notification_prefs(account_id)
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "user": user, "role": role, "businesses": businesses, "notifications": notifications,
    })


@app.post("/settings/business/{business_id}")
async def update_business(
    request: Request,
    business_id: int,
    name: str = Form(...),
    business_type: str = Form(...),
    location: str = Form(...),
    tone: str = Form("friendly and professional"),
    owner_name: str = Form(""),
    auto_approve_high: int = Form(0),
    banned_phrases: str = Form(""),
    signoff_library: str = Form(""),
    brand_facts: str = Form(""),
):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role == "staff":
        raise HTTPException(status_code=403)
    from app.database import db_connection
    with db_connection() as conn:
        conn.execute(
            """UPDATE businesses SET name=?, type=?, location=?, tone=?, owner_name=?, auto_approve_high=?, banned_phrases=?, signoff_library=?, brand_facts=?
               WHERE id=? AND user_id=?""",
            (name, business_type, location, tone, owner_name, int(auto_approve_high), banned_phrases, signoff_library, brand_facts, business_id, account_id)
        )
    return RedirectResponse("/settings", status_code=302)


@app.post("/settings/notifications")
async def update_notifications(request: Request):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role == "staff":
        raise HTTPException(status_code=403)
    form = await request.form()
    events = form.getlist("events")
    events_str = ",".join(events) if events else "new_review,draft_ready,approved"
    email_target = form.get("email_target", "").strip()
    slack_webhook = form.get("slack_webhook", "").strip()
    telegram_target = form.get("telegram_target", "").strip()  # format: token:chat_id

    if email_target:
        save_notification_pref(account_id, "email", email_target, events_str)
    if slack_webhook:
        save_notification_pref(account_id, "slack", slack_webhook, events_str)
    if telegram_target:
        save_notification_pref(account_id, "telegram", telegram_target, events_str)

    return RedirectResponse("/settings", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


# --- Legal Pages ---

@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(request=request, name="terms.html", context={"user": user})


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(request=request, name="privacy.html", context={"user": user})


@app.get("/cookies", response_class=HTMLResponse)
async def cookies(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(request=request, name="cookies.html", context={"user": user})


# --- Email Verification ---

@app.get("/verify-email")
async def verify_email(request: Request, token: str = ""):
    if not token:
        return RedirectResponse("/login", status_code=302)
    from app.database import db_connection
    with db_connection() as conn:
        user = conn.execute("SELECT id FROM users WHERE email_token = ?", (token,)).fetchone()
        if user:
            conn.execute("UPDATE users SET email_verified = 1, email_token = '' WHERE id = ?", (user["id"],))
    return RedirectResponse("/dashboard", status_code=302)


# --- Onboarding ---

@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding(request: Request):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    businesses = get_businesses(account_id)
    step = 1 if not businesses else 3
    return templates.TemplateResponse(request=request, name="onboarding.html", context={"user": user, "step": step})


@app.post("/onboarding/step1")
async def onboarding_step1(request: Request, name: str = Form(...), business_type: str = Form(...), location: str = Form(...)):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    business_id = create_business(account_id, name, business_type, location)
    request.session["onboarding_business_id"] = business_id
    return templates.TemplateResponse(request=request, name="onboarding.html", context={"user": user, "step": 2})


@app.post("/onboarding/step2")
async def onboarding_step2(request: Request, tone: str = Form(...), owner_name: str = Form("")):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    business_id = request.session.get("onboarding_business_id")
    if business_id:
        from app.database import db_connection
        with db_connection() as conn:
            conn.execute("UPDATE businesses SET tone=?, owner_name=? WHERE id=?", (tone, owner_name, business_id))
    return templates.TemplateResponse(request=request, name="onboarding.html", context={"user": user, "step": 3})


@app.post("/onboarding/step3")
async def onboarding_step3(request: Request, author: str = Form("Customer"), rating: int = Form(...), text: str = Form(...)):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    businesses = get_businesses(account_id)
    if not businesses:
        return RedirectResponse("/onboarding", status_code=302)
    business = businesses[0]
    review_id = add_review(business["id"], author, rating, text)
    ai_resp = generate_response(
        review_text=text, rating=rating, author=author,
        business_name=business["name"], business_type=business["type"],
        location=business["location"], tone=business["tone"],
        api_key=ANTHROPIC_API_KEY, owner_name=business.get("owner_name", ""),
    )
    save_response(review_id, ai_resp)
    return RedirectResponse(f"/dashboard?business_id={business['id']}", status_code=302)


@app.get("/welcome", response_class=HTMLResponse)
async def welcome_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request=request, name="welcome.html", context={"user": user})


# --- Help & Support ---

@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(request=request, name="help.html", context={"user": user})


@app.get("/support", response_class=HTMLResponse)
async def support_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(request=request, name="support.html", context={"user": user, "sent": False})


@app.post("/support")
async def support_submit(request: Request, email: str = Form(...), subject: str = Form(...), message: str = Form(...)):
    user = get_current_user(request)
    from app.database import db_connection
    with db_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS support_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT, subject TEXT, message TEXT, status TEXT DEFAULT 'open', created_at TEXT DEFAULT (datetime('now')))")
        conn.execute("INSERT INTO support_tickets (user_id, email, subject, message) VALUES (?, ?, ?, ?)",
                     (user["id"] if user else None, email, subject, message))
    try:
        from app.email_service import send_email
        send_email("stan.evodek@gmail.com", f"[Support] {subject} — {email}", f"<p>From: {email}</p><p>{message}</p>")
    except Exception:
        pass
    return templates.TemplateResponse(request=request, name="support.html", context={"user": user, "sent": True})


# --- Team ---

@app.get("/team", response_class=HTMLResponse)
async def team_page(request: Request):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    team_members = get_team_members(account_id)
    return templates.TemplateResponse(request=request, name="team.html", context={"user": user, "role": role, "team_members": team_members})


@app.post("/team/invite")
async def team_invite(request: Request, email: str = Form(...), role: str = Form("staff")):
    user, account_id, user_role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user_role == "staff":
        raise HTTPException(status_code=403)
    create_team_invite(account_id, email, role)
    try:
        from app.email_service import send_email
        send_email(email, f"You're invited to ReviewReply AI ({role})", f"<p>{user['email']} invited you to collaborate on review replies.</p><p>Sign up with this email to join.</p>")
    except Exception:
        pass
    return RedirectResponse("/team", status_code=302)


@app.post("/team/remove/{member_id}")
async def team_remove(request: Request, member_id: int):
    user, account_id, role = get_account_context(request)
    if not user or role == "staff":
        return RedirectResponse("/login", status_code=302)
    remove_team_member(account_id, member_id)
    return RedirectResponse("/team", status_code=302)


# --- Profile ---

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request=request, name="profile.html", context={"user": user})


@app.post("/profile")
async def profile_update(request: Request, name: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    from app.database import db_connection
    with db_connection() as conn:
        conn.execute("UPDATE users SET name=?, updated_at=datetime('now') WHERE id=?", (name, user["id"]))
    return RedirectResponse("/profile", status_code=302)


@app.post("/profile/delete")
async def profile_delete(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    from app.database import db_connection
    with db_connection() as conn:
        conn.execute("DELETE FROM responses WHERE review_id IN (SELECT id FROM reviews WHERE business_id IN (SELECT id FROM businesses WHERE user_id=?))", (user["id"],))
        conn.execute("DELETE FROM reviews WHERE business_id IN (SELECT id FROM businesses WHERE user_id=?)", (user["id"],))
        conn.execute("DELETE FROM businesses WHERE user_id=?", (user["id"],))
        conn.execute("DELETE FROM users WHERE id=?", (user["id"],))
    request.session.clear()
    return RedirectResponse("/", status_code=302)


# --- Admin Panel (hidden, only for ADMIN_EMAILS) ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    from app.config import ADMIN_EMAILS
    user = get_current_user(request)
    if not user or user["email"] not in ADMIN_EMAILS:
        raise HTTPException(status_code=404)

    from app.database import db_connection
    with db_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        active_trials = conn.execute("SELECT COUNT(*) as c FROM users WHERE subscription_status='trial'").fetchone()["c"]
        paying = conn.execute("SELECT COUNT(*) as c FROM users WHERE subscription_status='active'").fetchone()["c"]
        total_businesses = conn.execute("SELECT COUNT(*) as c FROM businesses").fetchone()["c"]
        total_reviews = conn.execute("SELECT COUNT(*) as c FROM reviews").fetchone()["c"]
        total_responses = conn.execute("SELECT COUNT(*) as c FROM responses").fetchone()["c"]
        approved = conn.execute("SELECT COUNT(*) as c FROM responses WHERE status='approved'").fetchone()["c"]

        starter_count = conn.execute("SELECT COUNT(*) as c FROM users WHERE subscription_status='active' AND subscription_plan='starter'").fetchone()["c"]
        pro_count = conn.execute("SELECT COUNT(*) as c FROM users WHERE subscription_status='active' AND subscription_plan='pro'").fetchone()["c"]
        mrr = starter_count * 19 + pro_count * 39

        conn.execute("CREATE TABLE IF NOT EXISTS support_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT, subject TEXT, message TEXT, status TEXT DEFAULT 'open', created_at TEXT DEFAULT (datetime('now')))")
        open_tickets = conn.execute("SELECT COUNT(*) as c FROM support_tickets WHERE status='open'").fetchone()["c"]
        tickets = [dict(r) for r in conn.execute("SELECT * FROM support_tickets ORDER BY created_at DESC LIMIT 20").fetchall()]
        users_list = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]

    stats = {
        "total_users": total_users, "active_trials": active_trials,
        "paying_customers": paying, "mrr": mrr,
        "total_businesses": total_businesses, "total_reviews": total_reviews,
        "total_responses": total_responses, "approved_responses": approved,
        "open_tickets": open_tickets,
    }

    return templates.TemplateResponse(request=request, name="admin.html", context={
        "user": user, "stats": stats, "tickets": tickets, "users": users_list,
    })
