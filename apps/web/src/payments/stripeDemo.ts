/** Dummy Stripe test-card rules. Card PAN never leaves the browser. */

const DECLINES: Record<string, string> = {
  '4000000000000002': 'Your card was declined.',
  '4000000000009995': 'Your card has insufficient funds.',
  '4000000000000069': 'Your card has expired.',
};

export function digitsOnly(value: string): string {
  return value.replace(/\D/g, '');
}

export function formatCardNumber(value: string): string {
  return digitsOnly(value)
    .slice(0, 16)
    .replace(/(\d{4})(?=\d)/g, '$1 ');
}

export function formatExpiry(value: string): string {
  const d = digitsOnly(value).slice(0, 4);
  if (d.length <= 2) return d;
  return `${d.slice(0, 2)} / ${d.slice(2)}`;
}

export function luhnOk(num: string): boolean {
  const digits = digitsOnly(num);
  if (digits.length < 13 || digits.length > 19) return false;
  let sum = 0;
  let alt = false;
  for (let i = digits.length - 1; i >= 0; i -= 1) {
    let n = Number(digits[i]);
    if (alt) {
      n *= 2;
      if (n > 9) n -= 9;
    }
    sum += n;
    alt = !alt;
  }
  return sum % 10 === 0;
}

export function expiryValid(mmYy: string): boolean {
  const d = digitsOnly(mmYy);
  if (d.length !== 4) return false;
  const month = Number(d.slice(0, 2));
  const year = 2000 + Number(d.slice(2));
  if (month < 1 || month > 12) return false;
  const now = new Date();
  const exp = new Date(year, month, 0, 23, 59, 59);
  return exp >= now;
}

export type CardCheck = { ok: true } | { ok: false; message: string; decline?: boolean };

export function validateDemoCard(input: {
  number: string;
  expiry: string;
  cvc: string;
  name: string;
}): CardCheck {
  const number = digitsOnly(input.number);
  const cvc = digitsOnly(input.cvc);
  const name = input.name.trim();
  if (!name) return { ok: false, message: 'Enter the name on the card.' };
  if (number.length < 13) return { ok: false, message: 'Your card number is incomplete.' };
  if (!luhnOk(number)) return { ok: false, message: 'Your card number is invalid.' };
  if (!expiryValid(input.expiry)) {
    return { ok: false, message: "Your card's expiration date is incomplete." };
  }
  if (cvc.length < 3) return { ok: false, message: "Your card's security code is incomplete." };
  const decline = DECLINES[number];
  if (decline) return { ok: false, message: decline, decline: true };
  return { ok: true };
}
