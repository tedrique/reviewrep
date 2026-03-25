"""Stripe billing — checkout sessions and webhook handling."""
import stripe
from app.config import STRIPE_SECRET_KEY, STRIPE_PRICE_STARTER, STRIPE_PRICE_PRO, APP_URL

stripe.api_key = STRIPE_SECRET_KEY


def create_checkout_session(user_email: str, user_id: int, plan: str = "starter") -> str:
    price_id = STRIPE_PRICE_STARTER if plan == "starter" else STRIPE_PRICE_PRO

    session = stripe.checkout.Session.create(
        customer_email=user_email,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{APP_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{APP_URL}/pricing",
        metadata={"user_id": str(user_id), "plan": plan},
    )
    return session.url


def create_portal_session(customer_id: str) -> str:
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{APP_URL}/dashboard",
    )
    return session.url


def handle_webhook_event(payload: bytes, sig_header: str, webhook_secret: str) -> dict | None:
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception:
        return None

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        return {
            "event": "checkout_completed",
            "user_id": int(session["metadata"].get("user_id", 0)),
            "plan": session["metadata"].get("plan", "starter"),
            "customer_id": session.get("customer", ""),
            "subscription_id": session.get("subscription", ""),
        }

    if event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        return {
            "event": "subscription_cancelled",
            "customer_id": sub.get("customer", ""),
        }

    return None
