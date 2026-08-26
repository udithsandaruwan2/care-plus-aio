# Production OTP & payments gate

Demo / thesis bar uses `OTP_DUMMY=true` and `PAYMENT_PROVIDER=mock` (Stripe demo UI + mock confirm). Flip these only after [e2e-acceptance.md](../e2e-acceptance.md) is green.

## Real OTP email

1. Set `OTP_ENABLED=true`, `OTP_DUMMY=false`.
2. Configure Django email (`EMAIL_HOST`, credentials, or SES). Console backend is fine for local smoke only.
3. Confirm `/otp` UI works without a visible demo code.
4. Verify hire / pay / records still require OTP when enabled.

## PayHere (Sri Lanka primary)

1. Set `PAYMENT_PROVIDER=payhere`, merchant id/secret, sandbox flag, HTTPS `PAYHERE_NOTIFY_URL`.
2. Set `PAYHERE_RETURN_URL` / `PAYHERE_CANCEL_URL` to your deployed order success/failed pages.
3. Order pay page posts a form to PayHere when credentials are present (`stub: false`).
4. Keep mock confirm disabled in production (`MOCK_PAYMENT_CONFIRM_ENABLED=false`).

## Load / security smoke

- See [load-concurrency.md](load-concurrency.md) for `/voice/turn/` and care-request concurrency.
- Confirm admin routes redirect non-admin users (`RequireRole`).
- Confirm voice never charges (Pay stays manual / provider redirect only).
