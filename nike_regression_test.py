import json
import re
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
USERNAME = "final184ff4a9"
PASSWORD = "ColdStart!123"
REQUEST_TEXT = "Show me Nike shoes under $100."

# Exact footwear evidence used by the application's semantic category-safety
# layer. The regression test must recognise valid footwear labels such as
# sandals, slides, trainers, runners, and sneakers.
FOOTWEAR_EVIDENCE = (
    "shoe",
    "shoes",
    "sneaker",
    "sneakers",
    "sandal",
    "sandals",
    "slide",
    "slides",
    "boot",
    "boots",
    "slipper",
    "slippers",
    "loafer",
    "loafers",
    "flat",
    "flats",
    "clog",
    "clogs",
    "trainer",
    "trainers",
    "runner",
    "running",
    "walking",
    "footwear",
    "moccasin",
    "moccasins",
    "pump",
    "pumps",
    "heel",
    "heels",
    "oxford",
    "oxfords",
    "cleat",
    "cleats",
    "flip flop",
    "flip flops",
)


def semantic_phrase_present(text_value, phrase_value):
    """Match a complete, case-insensitive word or phrase."""
    normalised_text = str(text_value or "").casefold()
    normalised_phrase = str(phrase_value or "").casefold()

    if not normalised_text or not normalised_phrase:
        return False

    return bool(
        re.search(
            r"(?<![a-z0-9])"
            + re.escape(normalised_phrase)
            + r"(?![a-z0-9])",
            normalised_text,
        )
    )


def product_has_footwear_evidence(product):
    """Validate final-card footwear evidence without changing app behaviour."""
    searchable_product_text = " ".join(
        str(product.get(field, "") or "")
        for field in (
            "title",
            "category",
            "categories",
            "request_search_text",
        )
    )

    return any(
        semantic_phrase_present(searchable_product_text, phrase)
        for phrase in FOOTWEAR_EVIDENCE
    )


def find_numeric_prices_by_product_id(value, price_by_product_id=None):
    """Collect only numeric persisted-card prices from the API payload."""
    if price_by_product_id is None:
        price_by_product_id = {}

    if isinstance(value, dict):
        product_id = value.get("product_id") or value.get("asin")
        price_value = value.get("price")

        if (
            product_id is not None
            and isinstance(price_value, (int, float))
            and not isinstance(price_value, bool)
        ):
            price_by_product_id[str(product_id)] = float(price_value)

        for child in value.values():
            find_numeric_prices_by_product_id(child, price_by_product_id)

    elif isinstance(value, list):
        for child in value:
            find_numeric_prices_by_product_id(child, price_by_product_id)

    return price_by_product_id

def api(method, path, payload=None, token=None, timeout=240):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None if payload is None else json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        BASE + path,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {body}") from error


def find_first(value, keys):
    if isinstance(value, dict):
        for key in keys:
            if value.get(key) not in (None, ""):
                return value[key]

        for child in value.values():
            found = find_first(child, keys)
            if found not in (None, ""):
                return found

    elif isinstance(value, list):
        for child in value:
            found = find_first(child, keys)
            if found not in (None, ""):
                return found

    return None


def find_products(value):
    if isinstance(value, dict):
        cards = value.get("product_cards")

        if isinstance(cards, list):
            return cards

        for child in value.values():
            products = find_products(child)
            if products:
                return products

    elif isinstance(value, list):
        for child in value:
            products = find_products(child)
            if products:
                return products

    return []


print("Logging in...")

status, login = api(
    "POST",
    "/api/auth/login",
    {
        "login_identity": USERNAME,
        "password": PASSWORD,
    },
)

print("Login HTTP status:", status)

token = login["token"]


print("Creating fresh chat...")

status, created = api(
    "POST",
    "/api/chats/create",
    {},
    token,
)

workspace = created["workspace"]
chat_id = int(workspace["selected_chat_id"])

print("Chat ID:", chat_id)


print("Sending Nike request...")
print("This may take a while. Please wait.")

started = time.perf_counter()

status, result = api(
    "POST",
    "/api/messages",
    {
        "chat_id": chat_id,
        "message_text": REQUEST_TEXT,
        "top_n": 10,
    },
    token,
)

elapsed = time.perf_counter() - started


products = find_products(result)

assistant_message = find_first(
    result,
    [
        "assistant_message",
        "display_message",
        "message",
    ],
) or ""


nike_valid = bool(products) and all(
    "nike" in (
        str(product.get("brand", ""))
        + " "
        + str(product.get("title", ""))
    ).casefold()
    for product in products
)


shoes_valid = bool(products) and all(
    product_has_footwear_evidence(product)
    for product in products
)


numeric_prices_by_product_id = find_numeric_prices_by_product_id(result)

known_prices = [
    numeric_prices_by_product_id[str(product.get("product_id") or product.get("asin"))]
    for product in products
    if str(product.get("product_id") or product.get("asin"))
    in numeric_prices_by_product_id
]


prices_valid = (
    len(known_prices) == len(products)
    and all(price <= 100 for price in known_prices)
)


historical_display_unchanged = bool(products) and all(
    isinstance(product.get("price"), str)
    and "historical" in product["price"].casefold()
    for product in products
)


outfit_mode = bool(
    find_first(
        result,
        [
            "outfit_request",
            "outfit_grouped_cards",
        ],
    )
)


ordinary_mode = not outfit_mode


passed = (
    status == 200
    and ordinary_mode
    and nike_valid
    and shoes_valid
    and prices_valid
)


print()
print("=" * 80)
print("NIKE REGRESSION RESULT")
print("=" * 80)

print("HTTP status:", status)
print(f"Runtime: {elapsed:.2f} seconds")
print("Chat ID:", chat_id)

print()
print("Assistant message:")
print(assistant_message)

print()
print("Returned products:")

for product in products:
    print(
        "- title="
        + repr(product.get("title"))
        + " | brand="
        + repr(product.get("brand"))
        + " | category="
        + repr(
            product.get("category")
            or product.get("categories")
        )
        + " | price="
        + repr(product.get("price"))
    )


print()
print("Ordinary mode:", ordinary_mode)
print("Nike preserved:", nike_valid)
print("Shoes preserved:", shoes_valid)
print("Known prices <= $100:", prices_valid)
print("Historical display unchanged:", historical_display_unchanged)
print("PASS:", passed)


if not passed:
    print()
    print("RAW RESPONSE:")
    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )

