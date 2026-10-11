// The time left before a moment the core gives (a community goal's expiry, ADR 0032): counted
// here, so that it stays right between two pushes of the live view.
import { t, type Language } from "./i18n";

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "ends in 2 d 4 h", "ends in 3 h 05 min", "ends in 12 min", or "ended". */
export function timeLeft(until: string, now: number, language: Language): string {
  const left = Date.parse(until) - now;
  if (Number.isNaN(left)) return "";
  if (left <= 0) return t(language, "countdown.ended");
  const days = Math.floor(left / DAY);
  const hours = Math.floor((left % DAY) / HOUR);
  const minutes = Math.floor((left % HOUR) / MINUTE);
  const time =
    days > 0
      ? t(language, "countdown.days", { days, hours })
      : hours > 0
        ? t(language, "countdown.hours", { hours, minutes: String(minutes).padStart(2, "0") })
        : t(language, "countdown.minutes", { minutes });
  return t(language, "countdown.endsIn", { time });
}
