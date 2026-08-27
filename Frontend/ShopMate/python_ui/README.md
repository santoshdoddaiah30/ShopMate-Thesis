# ShopMate — Gradio UI (Python)

A clean, ChatGPT-style personalized shopping UI built with Gradio.
Layout matches the polished Next.js version: **sidebar + chat + product-card grid + composer**.

## Why this is better than the previous Gradio attempt

Your previous code fought Gradio's built-in styles with hundreds of `!important`
overrides, which is why the layout broke. This version:

- Uses **Gradio's native layout primitives** (`gr.Row`, `gr.Column`, `scale=`) instead of forcing widths with CSS
- Uses a **single `gr.HTML` block** to render the product grid — reliable across Gradio 4.x and 5.x
- Uses **`type="messages"`** (the modern chat format that avoids deprecation warnings)
- Has **minimal, targeted CSS** — no width/height wars with Gradio's shadow DOM
- Ships a **working demo stub** so you can run it immediately and verify the layout, then plug in your engine

## Install & Run

```bash
pip install gradio
python shopmate_ui.py
```

The app opens at `http://localhost:7860`.

## Plug in YOUR recommendation engine

Open `shopmate_ui.py` and find the two functions in section **1. BACKEND ADAPTERS**:

### `answer_user_query(user_message, chat_history)`

Replace the demo stub with a call to your engine. It must return a tuple:

```python
def answer_user_query(user_message, chat_history):
    # Call YOUR functions here:
    reply_text = my_llm.generate(user_message, chat_history)   # your LLM call
    products   = my_recommender.recommend(user_message, top_n=8)  # your recommender

    # Normalize each product to the dict shape below:
    products = [
        {
            "title": p["title"],
            "brand": p.get("brand", ""),
            "price": float(p["price"]),
            "rating": float(p.get("average_rating", 0)),
            "review_count": int(p.get("rating_number", 0)),
            "category": p.get("main_category", ""),
            "tags": p.get("categories", []),
            "description": p.get("description", ""),
            "image_url": p.get("image_url", ""),  # optional
            "url": p.get("url", ""),              # optional
        }
        for p in products
    ]
    return reply_text, products
```

### `get_trending_products()` and `get_categories()`

Optional — used by the sidebar Quick Action buttons. Return a list of the same
product dicts / a list of category name strings.

## Field mapping for Amazon Reviews 2023 (McAuley Lab)

If you're using the raw Amazon 2023 metadata JSONL, map fields like:

| Amazon 2023 field | UI field       |
| ----------------- | -------------- |
| `title`           | `title`        |
| `store`           | `brand`        |
| `price`           | `price`        |
| `average_rating`  | `rating`       |
| `rating_number`   | `review_count` |
| `main_category`   | `category`     |
| `categories`      | `tags`         |
| `description`     | `description`  |
| `images[0].large` | `image_url`    |

## Customizing the look

- **Colors** — edit the `:root` CSS variables at the top of `SHOPMATE_CSS`
  (`--sm-primary`, `--sm-bg`, etc.)
- **Card layout** — edit `render_product_card()` — it's just an HTML string
- **Sidebar sections** — add more `gr.Button` widgets inside the `#sm-sidebar` column

## Optional: connect the "Recent Chats" list to your persistence layer

The demo shows a single "Current session" radio. If you have per-user chat
persistence (like your `persistent_workspace_controller`), replace the `recent`
Radio's `choices` with your list of chat titles and wire its `.change` event
to load the selected chat into `chatbot`.
