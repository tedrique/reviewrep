"""
AI Review Responder — generates professional review responses using Claude.
"""
import anthropic


SYSTEM_PROMPT = """You are a professional review response assistant for {business_name}, a {business_type} in {location}.

Tone: {tone}

Rules:
- Thank the reviewer by name if available
- Address specific points they mentioned
- Keep it 2-4 sentences, natural and concise
- Never be defensive on negative reviews
- On negative reviews (1-2 stars): apologize sincerely, acknowledge the issue, offer to resolve, invite them to contact directly
- On mixed reviews (3 stars): thank them, acknowledge the positive, address concerns
- On positive reviews (4-5 stars): express genuine gratitude, mention what they enjoyed, invite them back
- Never use generic phrases like "We value your feedback" or "Your satisfaction is our priority"
- Sound like a real human, not a corporate template
- Use British English spelling (colour, favourite, realise)
- Do not use emojis unless the business tone is "casual"
- Sign off with the business name or owner name if provided"""


def generate_response(
    review_text: str,
    rating: int,
    author: str,
    business_name: str,
    business_type: str,
    location: str,
    tone: str = "friendly and professional",
    api_key: str = "",
    owner_name: str = "",
    banned_phrases: str = "",
    signoff_library: str = "",
    brand_facts: str = "",
) -> str:
    """Generate an AI response to a review using Claude."""

    client = anthropic.Anthropic(api_key=api_key)

    system = SYSTEM_PROMPT.format(
        business_name=business_name,
        business_type=business_type,
        location=location,
        tone=tone,
    )

    if owner_name:
        system += f"\nSign off as: {owner_name}"
    if banned_phrases:
        system += f"\nNever use these phrases: {banned_phrases}"
    if signoff_library:
        system += f"\nPick a natural sign-off from: {signoff_library}"
    if brand_facts:
        system += f"\nBrand facts to weave in when relevant: {brand_facts}"

    user_msg = f"""Review by {author} ({rating} star{'s' if rating != 1 else ''}):
"{review_text}"

Write a response:"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    return response.content[0].text.strip()


def generate_response_batch(
    reviews: list[dict],
    business_config: dict,
    api_key: str,
) -> list[dict]:
    """Generate responses for multiple reviews."""
    results = []
    for review in reviews:
        try:
            response = generate_response(
                review_text=review["text"],
                rating=review["rating"],
                author=review["author"],
                business_name=business_config["name"],
                business_type=business_config["type"],
                location=business_config["location"],
                tone=business_config.get("tone", "friendly and professional"),
                api_key=api_key,
                owner_name=business_config.get("owner_name", ""),
                banned_phrases=business_config.get("banned_phrases", ""),
                signoff_library=business_config.get("signoff_library", ""),
                brand_facts=business_config.get("brand_facts", ""),
            )
            results.append({
                **review,
                "ai_response": response,
                "status": "pending_approval",
            })
        except Exception as e:
            results.append({
                **review,
                "ai_response": f"Error: {e}",
                "status": "error",
            })
    return results
