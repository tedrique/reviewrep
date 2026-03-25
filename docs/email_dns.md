# Email deliverability (Postmark or SES)

## Required DNS for your sender domain

### SPF
```
v=spf1 include:spf.mtasv.net include:amazonses.com ~all
```

### DKIM (choose one provider)
- **Postmark**: add the two CNAMEs provided by Postmark for your server token.
- **SES**: in AWS SES, verify your domain and add the three DKIM CNAMEs SES gives you.

### Return-Path (for SES bounce tracking)
Add the MX/CNAME that SES provides when setting up a custom MAIL FROM domain.

## Environment variables
- `FROM_EMAIL` / `FROM_NAME`
- Postmark: `POSTMARK_TOKEN`
- SES: `SES_ACCESS_KEY`, `SES_SECRET_KEY`, `SES_REGION`

## Sending priority
1. Postmark (if token set)
2. SES (if keys set)
3. Direct SMTP fallback (best-effort, can hit spam)

## Test
- Use https://www.mail-tester.com/ to verify SPF/DKIM/DMARC.
- Send a real message from the app and confirm it lands in Inbox, not Spam.
