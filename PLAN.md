# ReviewBot — AI Review Responder for UK Small Businesses

## Продукт

Бизнес получает отзыв на Google → AI пишет профессиональный ответ в тоне бизнеса → владелец одобряет одной кнопкой → ответ публикуется.

## Целевая аудитория

UK small businesses которые получают отзывы но не отвечают:
- Рестораны, кафе, пабы
- Парикмахерские, барбершопы, салоны
- Сантехники, электрики, строители (tradesmen)
- Стоматологии, клиники
- Отели, B&B
- Автосервисы
- Фитнес-студии

## Монетизация

| План | Цена | Что входит |
|------|------|-----------|
| Starter | £19/мес | До 50 ответов, 1 локация |
| Pro | £39/мес | Безлимит, tone of voice, 3 локации |
| Agency | £79/мес | 10 локаций, white-label dashboard |

## Почему это работает

1. Google ранжирует бизнесы выше если они отвечают на отзывы
2. 90% малых бизнесов не отвечают — лень, нет времени, не знают что писать
3. Плохой ответ на негативный отзыв хуже чем молчание — AI делает это правильно
4. ROI очевидный: £19/мес → лучший рейтинг → больше клиентов

## Техническая архитектура

```
Google Business API
       ↓
   [Webhook: новый отзыв]
       ↓
   Python Backend (FastAPI)
       ↓
   Claude API → генерация ответа
       ↓
   Telegram Bot / Web Dashboard
   → владелец видит: отзыв + предложенный ответ
   → жмёт ✅ Approve или ✏️ Edit
       ↓
   Google Business API → публикация ответа
```

## Стек

- **Backend:** Python, FastAPI
- **AI:** Claude API (Anthropic) — для генерации ответов
- **Database:** PostgreSQL (Supabase бесплатный tier)
- **Auth:** Google OAuth (для подключения Google Business)
- **Notifications:** Telegram Bot (MVP) → Web Dashboard (v2)
- **Payments:** Stripe Checkout + подписки
- **Hosting:** Railway / Render (бесплатный tier для MVP)
- **Landing:** простой HTML (у нас уже есть шаблон)

## План разработки

### День 1 — Ядро
- [ ] Настроить Google Business API (OAuth + доступ к отзывам)
- [ ] Написать сервис получения новых отзывов
- [ ] Написать AI генератор ответов (Claude API)
- [ ] Telegram бот: отправка отзыва + ответа владельцу
- [ ] Кнопки Approve / Edit / Skip в боте

### День 2 — Полный цикл
- [ ] Публикация одобренного ответа через Google API
- [ ] Настройка tone of voice (формальный/дружелюбный/профессиональный)
- [ ] Хранение истории отзывов и ответов (PostgreSQL)
- [ ] Обработка негативных отзывов (другой промпт, более осторожный)
- [ ] Периодическая проверка новых отзывов (cron / scheduler)

### День 3 — Лендинг + Оплата
- [ ] Landing page (HTML, объяснение продукта, CTA)
- [ ] Stripe Checkout интеграция (подписка £19/£39)
- [ ] Onboarding flow: зарегался → подключил Google → готово
- [ ] Deploy всего на Railway/Render

### День 4 — Запуск
- [ ] FB рекламная кампания (£10-20/день)
- [ ] Таргет: UK small business owners, restaurant owners, salon owners
- [ ] 2-3 варианта креатива для A/B тестирования
- [ ] Мониторинг конверсий

## Промпт для генерации ответов

```
You are a professional review response assistant for {business_name},
a {business_type} in {location}.

Tone: {tone} (friendly / professional / warm)

Rules:
- Thank the reviewer by name if available
- Address specific points they mentioned
- Keep it 2-4 sentences
- Never be defensive on negative reviews
- On negative reviews: apologize, offer to resolve, invite to contact directly
- On positive reviews: express genuine gratitude, mention what they enjoyed
- Never use generic phrases like "We value your feedback"
- Sound human, not corporate

Review ({rating} stars):
"{review_text}"

Write a response:
```

## Конкурентный анализ

Существующие решения дорогие ($99-299/мес) и рассчитаны на агентства.
Наша ниша: **дешёвый, простой инструмент для одного бизнеса за £19/мес.**
Не нужен dashboard, не нужен enterprise onboarding — подключил Google, получаешь ответы в Telegram.

## Ключевые метрики

- CAC (стоимость привлечения клиента) — цель < £30
- MRR (monthly recurring revenue) — цель £500 за первый месяц (25 клиентов)
- Churn — цель < 10% в месяц
- LTV — при £19/мес и 10% churn = £190
