"""ReviewReply AI — FastAPI web application."""
import os
from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import secrets
import time
import sentry_sdk

from app.config import SECRET_KEY, ANTHROPIC_API_KEY, DEBUG, ADMIN_BACKDOOR_TOKEN, SENTRY_DSN, REDIS_URL
from app.database import (
    init_db, get_user, get_businesses, get_reviews, count_reviews,
    create_business, add_review, save_response, save_response_with_flags, approve_response,
    get_notification_prefs, save_notification_pref,
    get_team_members, create_team_invite, attach_member_user, remove_team_member,
    add_audit, count_responses_this_month, get_dead_letters,
    add_comment, get_comments_by_review_ids, get_tags_by_review_ids, get_top_tags,
)
from app.ai_responder import generate_response
from app.notifications import send_notifications
from app.task_queue import enqueue as task_enqueue
from app.rate_limit import check_generate, check_publish, check_ip
from app.database import get_dead_letters
from app.celery_app import REDIS_URL, RESULT_URL, celery_app
from app.celery_tasks import send_notification, generate_one
from app.bulk_tasks import generate_bulk_task
from app.logger import setup_logging, logger
from app.task_status import get_task_status
from starlette.responses import JSONResponse

app = FastAPI(title="ReviewReply AI", docs_url="/docs" if DEBUG else None)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.05)

setup_logging()

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def ensure_csrf_token(request):
    """Get or create a CSRF token stored in the session."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        request.session["csrf_token"] = token
    return token


templates.env.globals["csrf_token"] = ensure_csrf_token

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Svelte frontend (built static files)
frontend_dist = Path(__file__).parent.parent / "frontend_dist"
if frontend_dist.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

# Simple in-memory rate limiting per IP (best-effort)
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    if not check_ip(ip):
        return HTMLResponse("Rate limit exceeded", status_code=429)
    try:
        response = await call_next(request)
    except Exception as e:
        print(f"[error] {request.url} {e}")
        raise
    return response


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


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf(request: Request, token: str):
    session_token = request.session.get("csrf_token")
    if not session_token or not token or token != session_token:
        raise HTTPException(status_code=400, detail="CSRF validation failed")


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
    if role in ("staff", "suggest"):
        return RedirectResponse("/dashboard", status_code=302)
    from app.stripe_billing import create_checkout_session
    url = create_checkout_session(user["email"], user["id"], plan)
    return RedirectResponse(url, status_code=302)


@app.get("/billing/success")
async def billing_success(request: Request, session_id: str = ""):
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/tasks/{task_id}")
async def task_status(task_id: str):
    if not REDIS_URL:
        raise HTTPException(status_code=503, detail="Task tracking unavailable without Redis backend")
    return JSONResponse(get_task_status(task_id))


@app.get("/billing/portal")
async def billing_portal(request: Request):
    user, account_id, role = get_account_context(request)
    if not user or not user.get("stripe_customer_id") or role in ("staff", "suggest"):
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


# --- Admin OTP login ---

import random


@app.get("/admin-otp", response_class=HTMLResponse)
async def admin_otp_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_otp.html", context={"step": "request"})


@app.post("/admin-otp/request")
async def admin_otp_request(request: Request, email: str = Form(...), csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    email = email.strip().lower()
    if email not in [e.lower() for e in ADMIN_EMAILS]:
        raise HTTPException(status_code=403, detail="Not authorized")
    code = f"{random.randint(0, 999999):06d}"
    if REDIS_URL:
        from app.rate_limit import _redis_client
        if _redis_client:
            _redis_client.setex(f"otp:{email}", 600, code)
    else:
        request.session[f"otp_{email}"] = code
    try:
        from app.email_service import send_email
        send_email(email, "Your admin code", f"<p>Your admin login code: <b>{code}</b></p><p>Expires in 10 minutes.</p>")
    except Exception:
        pass
    return templates.TemplateResponse(request=request, name="admin_otp.html", context={"step": "verify", "email": email})


@app.post("/admin-otp/verify")
async def admin_otp_verify(request: Request, email: str = Form(...), code: str = Form(...), csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    email = email.strip().lower()
    stored = None
    if REDIS_URL:
        from app.rate_limit import _redis_client
        if _redis_client:
            stored = _redis_client.get(f"otp:{email}")
            stored = stored.decode() if stored else None
    else:
        stored = request.session.get(f"otp_{email}")
    if not stored or stored != code:
        raise HTTPException(status_code=403, detail="Invalid code")
    # consume
    if REDIS_URL:
        from app.rate_limit import _redis_client
        if _redis_client:
            _redis_client.delete(f"otp:{email}")
    else:
        request.session.pop(f"otp_{email}", None)

    from app.database import create_user
    user_id = create_user(email=email, name=email.split("@")[0], google_id=f"admin_{email}")
    request.session["user_id"] = user_id
    request.session["account_id"] = user_id
    request.session["role"] = "owner"
    return RedirectResponse("/admin", status_code=302)


# --- Dashboard ---

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    businesses = get_businesses(account_id)
    current_business = None
    reviews = []
    page = int(request.query_params.get("page", 1))
    per_page = 20
    status_filter = request.query_params.get("status") or "needs_action"
    rating_filter = request.query_params.get("rating")
    search = request.query_params.get("q", "").strip() or None
    responses_used = count_responses_this_month(account_id)
    plan = user.get("subscription_plan") or "starter"
    status = user.get("subscription_status") or "trial"
    plan_limit = 50 if plan == "starter" else None
    responses_left = None if plan_limit is None else max(plan_limit - responses_used, 0)
    trial_days_left = None
    if status == "trial" and user.get("trial_ends_at"):
        from datetime import datetime as dt
        try:
            trial_end = dt.fromisoformat(user["trial_ends_at"])
            trial_days_left = max((trial_end - dt.utcnow()).days, 0)
        except Exception:
            pass

    business_id = request.query_params.get("business_id")
    if businesses:
        if business_id:
            current_business = next((b for b in businesses if str(b["id"]) == business_id), businesses[0])
        else:
            current_business = businesses[0]
        total = count_reviews(current_business["id"])
        offset = (page - 1) * per_page
        reviews = get_reviews(
            current_business["id"],
            limit=per_page,
            offset=offset,
            status=status_filter,
            rating_filter=rating_filter,
            search=search,
        )
        review_ids = [r["id"] for r in reviews]
        comments = get_comments_by_review_ids(review_ids)
        review_tags = get_tags_by_review_ids(review_ids)
        total_pages = max(1, (total + per_page - 1) // per_page)
        # Insights
        from app.database import db_connection
        with db_connection() as conn:
            approved = conn.execute("""
                SELECT COUNT(*) as c FROM responses resp
                JOIN reviews r ON resp.review_id = r.id
                JOIN businesses b ON r.business_id = b.id
                WHERE b.id = ? AND resp.status='approved'
            """, (current_business["id"],)).fetchone()["c"]
            published = conn.execute("""
                SELECT COUNT(*) as c FROM responses resp
                JOIN reviews r ON resp.review_id = r.id
                JOIN businesses b ON r.business_id = b.id
                WHERE b.id = ? AND resp.status='approved' AND resp.published_at != ''
            """, (current_business["id"],)).fetchone()["c"]
            avg_ttr_row = conn.execute("""
                SELECT AVG(strftime('%s', resp.published_at) - strftime('%s', r.created_at)) as s
                FROM responses resp
                JOIN reviews r ON resp.review_id = r.id
                JOIN businesses b ON r.business_id = b.id
                WHERE b.id = ? AND resp.published_at != ''
            """, (current_business["id"],)).fetchone()
            avg_ttr = avg_ttr_row["s"] if avg_ttr_row and avg_ttr_row["s"] else None
            approve_ready = conn.execute("""
                SELECT COUNT(*) as c FROM responses resp
                JOIN reviews r ON resp.review_id = r.id
                WHERE r.business_id=? AND (resp.status IS NULL OR resp.status != 'approved') AND r.rating >= 4 AND resp.ai_response IS NOT NULL
            """, (current_business["id"],)).fetchone()["c"]
            publish_ready = conn.execute("""
                SELECT COUNT(*) as c FROM responses resp
                JOIN reviews r ON resp.review_id = r.id
                JOIN businesses b ON r.business_id = b.id
                WHERE r.business_id=? AND resp.status='approved' AND r.google_review_id != '' AND b.google_location_id != ''
            """, (current_business["id"],)).fetchone()["c"]
            # simple 7-day counts
            weekly = conn.execute("""
                SELECT strftime('%Y-%m-%d', r.created_at) as d, COUNT(*) as c
                FROM reviews r WHERE r.business_id=? AND r.created_at >= date('now','-7 day')
                GROUP BY d ORDER BY d ASC
            """, (current_business["id"],)).fetchall()
            weekly_labels = [w["d"][5:] for w in weekly]
            weekly_data = [w["c"] for w in weekly]
            rating_recent = conn.execute("""
                SELECT AVG(rating) as a FROM reviews WHERE business_id=? AND created_at >= date('now','-30 day')
            """, (current_business["id"],)).fetchone()["a"]
            rating_prev = conn.execute("""
                SELECT AVG(rating) as a FROM reviews WHERE business_id=? AND created_at BETWEEN date('now','-60 day') AND date('now','-30 day')
            """, (current_business["id"],)).fetchone()["a"]
            rating_delta = round(rating_recent - rating_prev, 2) if rating_recent and rating_prev else None
            publish_rate = conn.execute("""
                SELECT COUNT(*) as c FROM responses WHERE status='published' AND created_at >= date('now','-7 day')
            """, ()).fetchone()["c"]
            ttr_7d = conn.execute("""
                SELECT AVG(strftime('%s', resp.published_at) - strftime('%s', r.created_at)) as s
                FROM responses resp JOIN reviews r ON resp.review_id=r.id
                WHERE resp.published_at != '' AND resp.created_at >= date('now','-7 day')
            """, ()).fetchone()["s"]
            activity = conn.execute("""
                SELECT action, meta, created_at FROM audit_log
                WHERE account_id=? ORDER BY created_at DESC LIMIT 10
            """, (account_id,)).fetchall()
            top_tags = get_top_tags(current_business["id"])
    else:
        comments = {}
        review_tags = {}
        top_tags = []
        total_pages = 1
        total = 0
        approved = 0
        published = 0
        avg_ttr = None
        approve_ready = 0
        publish_ready = 0
        weekly_labels = []
        weekly_data = []
        rating_delta = None
        publish_rate = 0
        ttr_7d = None
        activity = []

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "user": user,
        "role": role,
        "businesses": businesses,
        "current_business": current_business,
        "reviews": reviews,
        "page": page,
        "total_pages": total_pages,
        "total_reviews": total,
        "approved_reviews": approved,
        "published_reviews": published,
        "avg_ttr": avg_ttr,
        "status_filter": status_filter or "all",
        "rating_filter": rating_filter or "all",
        "search": search or "",
        "responses_used": responses_used,
        "responses_left": responses_left,
        "plan_limit": plan_limit,
        "trial_days_left": trial_days_left,
        "plan": plan,
        "status": status,
        "approve_ready": approve_ready,
        "publish_ready": publish_ready,
        "weekly_labels": weekly_labels,
        "weekly_data": weekly_data,
        "rating_delta": rating_delta,
        "publish_rate": publish_rate,
        "ttr_7d": ttr_7d,
        "activity": activity,
        "comments": comments,
        "review_tags": review_tags,
        "top_tags": top_tags if businesses else [],
    })


# --- Business Management ---

@app.post("/business/add")
async def add_business(
    request: Request,
    csrf_token: str = Form(...),
    name: str = Form(...),
    business_type: str = Form(...),
    location: str = Form(...),
    tone: str = Form("friendly and professional"),
):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role in ("staff", "suggest"):
        raise HTTPException(status_code=403, detail="Only owners/admins can add businesses")
    verify_csrf(request, csrf_token)
    biz_id = create_business(account_id, name, business_type, location, tone)
    add_audit(account_id, user["id"], "business.add", "business", biz_id, name)
    return RedirectResponse("/dashboard", status_code=302)


# --- Review Management ---

@app.post("/review/add")
async def add_review_manual(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(...),
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
    verify_csrf(request, csrf_token)
    new_id = add_review(business_id, author, rating, text)
    add_audit(account_id, user["id"], "review.add", "review", new_id, f"rating={rating}")
    payload = {"business_name": biz["name"], "author": author, "rating": rating, "text": text}
    if REDIS_URL:
        send_notification.delay(account_id, "new_review", payload)
    else:
        task_enqueue(send_notifications, account_id, "new_review", payload)
    return RedirectResponse(f"/dashboard?business_id={business_id}", status_code=302)


# --- Google Business Sync ---

@app.post("/business/{business_id}/sync")
async def sync_reviews(request: Request, business_id: int, background_tasks: BackgroundTasks, csrf_token: str = Form(...)):
    """Pull latest reviews from Google Business Profile."""
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role in ("staff", "suggest"):
        raise HTTPException(status_code=403, detail="Not allowed for your role")

    access_token = user.get("google_access_token", "")
    if not access_token:
        return RedirectResponse(f"/dashboard?business_id={business_id}&error=no_google", status_code=302)

    from app.database import db_connection
    with db_connection() as conn:
        biz = conn.execute("SELECT * FROM businesses WHERE id=? AND user_id=?", (business_id, account_id)).fetchone()
    if not biz or not biz["google_location_id"]:
        return RedirectResponse(f"/dashboard?business_id={business_id}&error=no_location", status_code=302)
    verify_csrf(request, csrf_token)

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
            add_audit(account_id, user["id"], "review.sync", "review", None, f"rating={rev['rating']}")
            payload = {
                "business_name": biz["name"],
                "author": rev["author"],
                "rating": rev["rating"],
                "text": rev["text"],
            }
            if REDIS_URL:
                send_notification.delay(account_id, "new_review", payload)
            else:
                task_enqueue(send_notifications, account_id, "new_review", payload)

    return RedirectResponse(f"/dashboard?business_id={business_id}&synced={imported}", status_code=302)


@app.post("/response/{response_id}/publish")
async def publish_response(request: Request, response_id: int, csrf_token: str = Form(...)):
    """Publish an approved response to Google."""
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role in ("staff", "suggest"):
        raise HTTPException(status_code=403, detail="You cannot publish with this role")
    verify_csrf(request, csrf_token)
    if not check_publish(user["id"]):
        return HTMLResponse("Rate limit exceeded for publish", status_code=429)

    # Offload publish to Celery
    if REDIS_URL:
        from app.publish_celery import publish_response_task
        task = publish_response_task.delay(account_id, user["id"], response_id, user.get("google_refresh_token", ""), user.get("google_access_token", ""))
        return RedirectResponse(f"/dashboard?task={task.id}", status_code=302)
    else:
        from app.publish_task import publish_response_task_sync
        task_enqueue(lambda: publish_response_task_sync(account_id, user["id"], response_id, user.get("google_refresh_token", ""), user.get("google_access_token", "")))
        return RedirectResponse("/dashboard?pub=queued", status_code=302)


@app.get("/business/connect-google")
async def connect_google_business(request: Request):
    """After Google OAuth, fetch user's business locations and let them pick one."""
    user, account_id, role = get_account_context(request)
    if not user or not user.get("google_access_token") or role in ("staff", "suggest"):
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
    if not user or role in ("staff", "suggest"):
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    verify_csrf(request, form.get("csrf_token", ""))

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
async def generate_ai_response(request: Request, review_id: int, background_tasks: BackgroundTasks, csrf_token: str = Form(...)):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    verify_csrf(request, csrf_token)
    if not check_generate(user["id"]):
        return HTMLResponse("Rate limit exceeded for generate", status_code=429)
    # Plan enforcement
    plan = user.get("subscription_plan") or "starter"
    status = user.get("subscription_status") or "trial"
    if plan == "starter":
        used = count_responses_this_month(account_id)
        if used >= 50:
            return RedirectResponse("/pricing?limit_reached=1", status_code=302)

    # Check subscription / trial
    from datetime import datetime as dt
    sub_status = user.get("subscription_status", "trial")
    if sub_status == "trial" and user.get("trial_ends_at"):
        try:
            trial_end = dt.fromisoformat(user["trial_ends_at"])
            if dt.utcnow() > trial_end:
                return RedirectResponse("/pricing?expired=1", status_code=302)
        except Exception:
            pass
    elif sub_status not in ("trial", "active"):
        return RedirectResponse("/pricing?expired=1", status_code=302)

    from app.database import db_connection  # noqa
    with db_connection() as conn:
        review = conn.execute("""
            SELECT r.*, b.name as business_name, b.type as business_type,
                   b.location, b.tone, b.owner_name, b.id as business_id,
                   b.auto_approve_high, b.banned_phrases, b.signoff_library, b.brand_facts,
                   b.brand_hours, b.brand_services, b.brand_geo, b.brand_usp, b.allowed_phrases,
                   b.auto_rule_1_2, b.auto_rule_3, b.auto_rule_4_5, b.quiet_hours, b.sla_hours_neg
            FROM reviews r JOIN businesses b ON r.business_id = b.id
            WHERE r.id = ? AND b.user_id = ?
        """, (review_id, account_id)).fetchone()

    if not review:
        raise HTTPException(status_code=404)

    # Offload generation to Celery/worker
    if REDIS_URL:
        task = generate_one.delay(account_id, review_id)
        return RedirectResponse(f"/dashboard?business_id={review['business_id']}&task={task.id}", status_code=302)
    else:
        t = task_enqueue(lambda: generate_one(account_id, review_id))
        return RedirectResponse(f"/dashboard?business_id={review['business_id']}&gen=queued", status_code=302)


@app.post("/review/{review_id}/comment")
async def comment_on_review(request: Request, review_id: int, csrf_token: str = Form(...), text: str = Form(...)):
    """Add an internal comment on a review (collaboration)."""
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    verify_csrf(request, csrf_token)
    text = (text or "").strip()
    if not text:
        return RedirectResponse("/dashboard", status_code=302)

    from app.database import db_connection
    with db_connection() as conn:
        row = conn.execute("""
            SELECT r.id, r.business_id FROM reviews r
            JOIN businesses b ON r.business_id = b.id
            WHERE r.id = ? AND b.user_id = ?
        """, (review_id, account_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404)

    add_comment(review_id, user["id"], text)
    add_audit(account_id, user["id"], "comment.add", "review", review_id, "")
    return RedirectResponse(f"/dashboard?business_id={row['business_id']}", status_code=302)


@app.post("/review/{review_id}/generate-all")
async def generate_all_responses(request: Request, review_id: int, background_tasks: BackgroundTasks, csrf_token: str = Form(...)):
    """Generate AI responses for all reviews without one."""
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    verify_csrf(request, csrf_token)

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

    # Enqueue bulk generation (Celery if available)
    review_ids = [r["id"] for r in reviews_without]
    if review_ids:
        if REDIS_URL:
            task = generate_bulk_task.delay(account_id, review_ids, auto_approve=True)
            return RedirectResponse(f"/dashboard?business_id={business_id}&task={task.id}", status_code=302)
        else:
            task_enqueue(lambda: generate_bulk_task(account_id, review_ids, auto_approve=True))

    return RedirectResponse(f"/dashboard?business_id={business_id}&gen=queued", status_code=302)


@app.post("/responses/bulk-approve")
async def bulk_approve(request: Request, business_id: int = Form(...), csrf_token: str = Form(...)):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    verify_csrf(request, csrf_token)
    if role in ("staff", "suggest"):
        raise HTTPException(status_code=403)
    from app.database import db_connection
    with db_connection() as conn:
        rows = conn.execute("""
            SELECT resp.id FROM responses resp
            JOIN reviews r ON resp.review_id = r.id
            JOIN businesses b ON r.business_id = b.id
            WHERE r.business_id=? AND b.user_id=? AND (resp.status IS NULL OR resp.status!='approved') AND r.rating>=4 AND resp.ai_response IS NOT NULL
        """, (business_id, account_id)).fetchall()
    for row in rows:
        approve_response(row["id"], "")
        add_audit(account_id, user["id"], "response.bulk_approve", "response", row["id"], "")
    return RedirectResponse(f"/dashboard?business_id={business_id}&bulk=approved", status_code=302)


@app.post("/responses/bulk-publish")
async def bulk_publish(request: Request, business_id: int = Form(...), csrf_token: str = Form(...)):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    verify_csrf(request, csrf_token)
    if role in ("staff", "suggest"):
        raise HTTPException(status_code=403)
    from app.database import db_connection
    with db_connection() as conn:
        rows = conn.execute("""
            SELECT resp.id FROM responses resp
            JOIN reviews r ON resp.review_id = r.id
            JOIN businesses b ON r.business_id = b.id
            WHERE r.business_id=? AND b.user_id=? AND resp.status='approved' AND r.google_review_id!='' AND b.google_location_id!=''
        """, (business_id, account_id)).fetchall()
    if REDIS_URL:
        from app.publish_celery import publish_response_task
        task_ids = []
        for row in rows:
            task = publish_response_task.delay(account_id, user["id"], row["id"], user.get("google_refresh_token", ""), user.get("google_access_token", ""))
            task_ids.append(task.id)
            add_audit(account_id, user["id"], "response.bulk_publish", "response", row["id"], "")
        tid = task_ids[0] if task_ids else ""
        return RedirectResponse(f"/dashboard?business_id={business_id}&task={tid}", status_code=302)
    else:
        from app.publish_task import publish_response_task_sync
        for row in rows:
            task_enqueue(lambda: publish_response_task_sync(account_id, user["id"], row["id"], user.get("google_refresh_token", ""), user.get("google_access_token", "")))
            add_audit(account_id, user["id"], "response.bulk_publish", "response", row["id"], "")
        return RedirectResponse(f"/dashboard?business_id={business_id}&bulk=published", status_code=302)


@app.post("/response/{response_id}/approve")
async def approve(request: Request, response_id: int, background_tasks: BackgroundTasks):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role in ("staff", "suggest"):
        raise HTTPException(status_code=403, detail="You cannot approve with this role")

    form = await request.form()
    verify_csrf(request, form.get("csrf_token", ""))
    edited = form.get("edited_response", "")
    approve_response(response_id, edited)
    add_audit(account_id, user["id"], "response.approve", "response", response_id, "")

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

    payload = {"business_id": business_id}
    if REDIS_URL:
        send_notification_task.delay(account_id, "approved", payload)
    else:
        task_enqueue(send_notifications, account_id, "approved", payload)

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
    csrf_token: str = Form(...),
    name: str = Form(...),
    business_type: str = Form(...),
    location: str = Form(...),
    tone: str = Form("friendly and professional"),
    owner_name: str = Form(""),
    auto_approve_high: int = Form(0),
    banned_phrases: str = Form(""),
    signoff_library: str = Form(""),
    brand_facts: str = Form(""),
    brand_hours: str = Form(""),
    brand_services: str = Form(""),
    brand_geo: str = Form(""),
    brand_usp: str = Form(""),
    allowed_phrases: str = Form(""),
    auto_rule_1_2: str = Form("draft"),
    auto_rule_3: str = Form("draft"),
    auto_rule_4_5: str = Form("approve"),
    quiet_hours: str = Form(""),
    sla_hours_neg: int = Form(24),
):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role in ("staff", "suggest"):
        raise HTTPException(status_code=403)
    verify_csrf(request, csrf_token)
    from app.database import db_connection
    with db_connection() as conn:
        conn.execute(
            """UPDATE businesses SET name=?, type=?, location=?, tone=?, owner_name=?, auto_approve_high=?, banned_phrases=?, signoff_library=?, brand_facts=?,
               brand_hours=?, brand_services=?, brand_geo=?, brand_usp=?, allowed_phrases=?,
               auto_rule_1_2=?, auto_rule_3=?, auto_rule_4_5=?, quiet_hours=?, sla_hours_neg=?
               WHERE id=? AND user_id=?""",
            (name, business_type, location, tone, owner_name, int(auto_approve_high), banned_phrases, signoff_library, brand_facts,
             brand_hours, brand_services, brand_geo, brand_usp, allowed_phrases,
             auto_rule_1_2, auto_rule_3, auto_rule_4_5, quiet_hours, int(sla_hours_neg), business_id, account_id)
        )
    add_audit(account_id, user["id"], "business.update", "business", business_id, "")
    return RedirectResponse("/settings", status_code=302)


@app.post("/settings/notifications")
async def update_notifications(request: Request):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if role in ("staff", "suggest"):
        raise HTTPException(status_code=403)
    form = await request.form()
    verify_csrf(request, form.get("csrf_token", ""))
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

    add_audit(account_id, user["id"], "notifications.update", "account", account_id, "")
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
async def onboarding_step1(request: Request, csrf_token: str = Form(...), name: str = Form(...), business_type: str = Form(...), location: str = Form(...)):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    verify_csrf(request, csrf_token)
    business_id = create_business(account_id, name, business_type, location)
    request.session["onboarding_business_id"] = business_id
    return templates.TemplateResponse(request=request, name="onboarding.html", context={"user": user, "step": 2})


@app.post("/onboarding/step2")
async def onboarding_step2(request: Request, csrf_token: str = Form(...), tone: str = Form(...), owner_name: str = Form("")):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    verify_csrf(request, csrf_token)
    business_id = request.session.get("onboarding_business_id")
    if business_id:
        from app.database import db_connection
        with db_connection() as conn:
            conn.execute("UPDATE businesses SET tone=?, owner_name=? WHERE id=?", (tone, owner_name, business_id))
    return templates.TemplateResponse(request=request, name="onboarding.html", context={"user": user, "step": 3})


@app.post("/onboarding/step3")
async def onboarding_step3(request: Request, csrf_token: str = Form(...), author: str = Form("Customer"), rating: int = Form(...), text: str = Form(...)):
    user, account_id, role = get_account_context(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    verify_csrf(request, csrf_token)
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
    form = await request.form()
    verify_csrf(request, form.get("csrf_token", ""))
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
    if user_role in ("staff", "suggest"):
        raise HTTPException(status_code=403)
    form = await request.form()
    verify_csrf(request, form.get("csrf_token", ""))
    create_team_invite(account_id, email, role)
    try:
        from app.email_service import send_email
        send_email(email, f"You're invited to ReviewReply AI ({role})", f"<p>{user['email']} invited you to collaborate on review replies.</p><p>Sign up with this email to join.</p>")
    except Exception:
        pass
    add_audit(account_id, user["id"], "team.invite", "user", None, email)
    return RedirectResponse("/team", status_code=302)


@app.post("/team/remove/{member_id}")
async def team_remove(request: Request, member_id: int):
    user, account_id, role = get_account_context(request)
    if not user or role in ("staff", "suggest"):
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    verify_csrf(request, form.get("csrf_token", ""))
    remove_team_member(account_id, member_id)
    add_audit(account_id, user["id"], "team.remove", "membership", member_id, "")
    return RedirectResponse("/team", status_code=302)


# --- Profile ---

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request=request, name="profile.html", context={"user": user})


@app.post("/profile")
async def profile_update(request: Request, csrf_token: str = Form(...), name: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    verify_csrf(request, csrf_token)
    from app.database import db_connection
    with db_connection() as conn:
        conn.execute("UPDATE users SET name=?, updated_at=datetime('now') WHERE id=?", (name, user["id"]))
    return RedirectResponse("/profile", status_code=302)


@app.post("/profile/delete")
async def profile_delete(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    verify_csrf(request, form.get("csrf_token", ""))
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

        # Audit log
        audit_log = [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 50").fetchall()]

    # Dead letter queue
    dead_letters = get_dead_letters()

    stats = {
        "total_users": total_users, "active_trials": active_trials,
        "paying_customers": paying, "mrr": mrr,
        "total_businesses": total_businesses, "total_reviews": total_reviews,
        "total_responses": total_responses, "approved_responses": approved,
        "open_tickets": open_tickets,
    }

    return templates.TemplateResponse(request=request, name="admin.html", context={
        "user": user, "stats": stats, "tickets": tickets, "users": users_list,
        "audit_log": audit_log, "dead_letters": dead_letters,
    })


# --- Admin API: logs, health, debug (secret token) ---

import logging
import io

_log_buffer = io.StringIO()
_log_handler = logging.StreamHandler(_log_buffer)
_log_handler.setLevel(logging.WARNING)
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger().addHandler(_log_handler)
logging.getLogger("uvicorn.error").addHandler(_log_handler)


@app.get("/api/health")
async def health():
    """Public health check for Railway."""
    return {"status": "ok", "version": "1.0"}


@app.get("/api/debug/logs")
async def debug_logs(request: Request, token: str = "", lines: int = 50):
    """Get recent error/warning logs. Requires admin token or admin session."""
    from app.config import ADMIN_EMAILS
    DEBUG_TOKEN = os.environ.get("DEBUG_TOKEN", "rr-debug-2026")
    user = get_current_user(request)
    is_admin = user and user["email"] in ADMIN_EMAILS
    is_token = token == DEBUG_TOKEN

    if not is_admin and not is_token:
        raise HTTPException(status_code=404)

    log_content = _log_buffer.getvalue()
    log_lines = log_content.strip().split("\n") if log_content.strip() else []

    from app.database import db_connection, _fetchall, _fetchone, USE_PG
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        recent_errors = _fetchall(conn, f"SELECT * FROM audit_log WHERE action LIKE '%%error%%' ORDER BY created_at DESC LIMIT {p}", (lines,))
        db_stats = {
            "users": _fetchone(conn, "SELECT COUNT(*) as c FROM users")["c"],
            "businesses": _fetchone(conn, "SELECT COUNT(*) as c FROM businesses")["c"],
            "reviews": _fetchone(conn, "SELECT COUNT(*) as c FROM reviews")["c"],
            "responses": _fetchone(conn, "SELECT COUNT(*) as c FROM responses")["c"],
        }

    dead = get_dead_letters()

    # Google API diagnostics
    google_diag = {}
    with db_connection() as conn:
        u = _fetchone(conn, "SELECT id, email, google_access_token, google_refresh_token FROM users LIMIT 1")
        if u:
            tok = u["google_access_token"] or ""
            google_diag["has_access_token"] = bool(tok)
            google_diag["has_refresh_token"] = bool(u["google_refresh_token"])
            google_diag["token_preview"] = tok[:20] + "..." if tok else "none"
            if tok:
                try:
                    r = requests.get(
                        "https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
                        headers={"Authorization": f"Bearer {tok}"},
                        timeout=10,
                    )
                    google_diag["accounts_status"] = r.status_code
                    google_diag["accounts_response"] = r.json()
                except Exception as e:
                    google_diag["accounts_error"] = str(e)

    return {
        "status": "ok",
        "db": db_stats,
        "recent_logs": log_lines[-lines:],
        "dead_letters": dead[-10:],
        "audit_errors": recent_errors,
        "google_diag": google_diag,
    }


@app.get("/api/debug/db")
async def debug_db(request: Request, token: str = "", table: str = "users", limit: int = 10):
    """Peek at DB tables. Admin only."""
    from app.config import ADMIN_EMAILS, SECRET_KEY
    user = get_current_user(request)
    is_admin = user and user["email"] in ADMIN_EMAILS
    is_token = token == SECRET_KEY
    if not is_admin and not is_token:
        raise HTTPException(status_code=404)

    allowed = {"users", "businesses", "reviews", "responses", "support_tickets", "audit_log", "team_memberships"}
    if table not in allowed:
        return {"error": f"table must be one of {allowed}"}

    from app.database import db_connection
    with db_connection() as conn:
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()]
    return {"table": table, "count": len(rows), "rows": rows}
