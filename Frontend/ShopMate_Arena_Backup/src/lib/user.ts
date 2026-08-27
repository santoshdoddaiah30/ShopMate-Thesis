// A very lightweight "session": store a user id in a cookie via the client.
// Real apps would use auth; for a demo, an anonymous UUID is enough.
export const USER_COOKIE = "shopper_uid";

export function getOrCreateClientUserId(): string {
  if (typeof document === "undefined") return "anon";
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${USER_COOKIE}=`));
  if (match) return decodeURIComponent(match.split("=")[1]);
  const uid =
    "u_" +
    Math.random().toString(36).slice(2, 10) +
    Date.now().toString(36).slice(-4);
  const oneYear = 60 * 60 * 24 * 365;
  document.cookie = `${USER_COOKIE}=${encodeURIComponent(uid)}; path=/; max-age=${oneYear}; SameSite=Lax`;
  return uid;
}
