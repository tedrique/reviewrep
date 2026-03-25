from datetime import time, datetime

DEFAULT_RULES = {
    "1_2": "draft",
    "3": "draft",
    "4_5": "approve",
}


def parse_rule(biz: dict, rating: int, plan: str) -> str:
    if rating <= 2:
        rule = biz.get("auto_rule_1_2") or DEFAULT_RULES["1_2"]
    elif rating == 3:
        rule = biz.get("auto_rule_3") or DEFAULT_RULES["3"]
    else:
        rule = biz.get("auto_rule_4_5") or DEFAULT_RULES["4_5"]

    if plan == "starter" and rule == "publish" and rating < 5:
        return "approve"
    return rule


def quiet_hours_blocked(biz: dict, rating: int) -> bool:
    qh = (biz.get("quiet_hours") or "").strip()
    if not qh:
        return False
    if rating <= 1:
        return False  # urgent
    try:
        start_s, end_s = qh.split("-")
        start = datetime.strptime(start_s, "%H:%M").time()
        end = datetime.strptime(end_s, "%H:%M").time()
        now_t = datetime.utcnow().time()
        if start < end:
            return start <= now_t <= end
        else:  # spans midnight
            return now_t >= start or now_t <= end
    except Exception:
        return False
