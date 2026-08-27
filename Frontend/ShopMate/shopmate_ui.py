"""
ShopMate — Personalized Shopping Assistant UI (Gradio)
======================================================

A clean, ChatGPT-style UI for a personalized shopping assistant.

Layout:
    ┌────────────────┬─────────────────────────────────┐
    │                │  Chat messages                  │
    │   Sidebar      │  ...                            │
    │   - New chat   │                                 │
    │   - Recent     │  Product cards (grid)           │
    │   - Account    │  ─────────────────────────      │
    │                │  Message composer               │
    └────────────────┴─────────────────────────────────┘

HOW TO PLUG IN YOUR RECOMMENDATION ENGINE
-----------------------------------------
Find the function marked `# TODO: PLUG YOUR BACKEND` below
(section 1) and replace its body with a call to your own code:

    answer_user_query(user_message, chat_history)
        -> returns (assistant_text: str, products: list[dict])

Each product dict should have:
    {
        "title": str,
        "brand": str,
        "price": float,
        "rating": float,          # 0..5
        "review_count": int,
        "image_url": str,         # optional; emoji fallback used if missing
        "category": str,          # optional
        "tags": list[str],        # optional
        "description": str,       # optional (shown on card)
        "url": str,               # optional (View button)
    }

Run:
    pip install gradio
    python shopmate_ui.py
"""

from __future__ import annotations

import html
from typing import List, Dict, Tuple, Any

import gradio as gr


# =========================================================
# 1. BACKEND ADAPTERS — replace with YOUR recommender
# =========================================================

def answer_user_query(
    user_message: str,
    chat_history: List[Dict[str, str]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    TODO: PLUG YOUR BACKEND HERE.

    Call your recommendation engine + (optional) LLM here.
    Return a tuple:
        (assistant_reply_text, list_of_product_dicts)
    """
    # ---- DEMO STUB (delete when you plug your engine) --------------
    demo_products = [
        {
            "title": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
            "brand": "Sony",
            "price": 349.99,
            "rating": 4.6,
            "review_count": 18432,
            "category": "Electronics",
            "tags": ["wireless", "premium", "noise-cancelling"],
            "description": "Industry-leading noise cancellation, 30h battery.",
            "image_url": "",
        },
        {
            "title": "Apple AirPods Pro (2nd Gen)",
            "brand": "Apple",
            "price": 199.0,
            "rating": 4.7,
            "review_count": 42210,
            "category": "Electronics",
            "tags": ["earbuds", "apple", "anc"],
            "description": "Active Noise Cancellation, Spatial Audio, USB-C.",
            "image_url": "",
        },
        {
            "title": "Bose QuietComfort Earbuds II",
            "brand": "Bose",
            "price": 249.0,
            "rating": 4.4,
            "review_count": 8210,
            "category": "Electronics",
            "tags": ["earbuds", "noise-cancelling"],
            "description": "World-class ANC in a compact form factor.",
            "image_url": "",
        },
        {
            "title": "Sennheiser Momentum 4 Wireless",
            "brand": "Sennheiser",
            "price": 279.95,
            "rating": 4.5,
            "review_count": 5210,
            "category": "Electronics",
            "tags": ["headphones", "wireless", "premium"],
            "description": "Audiophile sound with 60h battery life.",
            "image_url": "",
        },
    ]
    reply = (
        f"Here are a few great picks based on **\"{user_message}\"**. "
        "I focused on top-rated options at different price points — let me "
        "know your budget or preferred brand and I'll narrow it down."
    )
    return reply, demo_products
    # ----------------------------------------------------------------


def get_trending_products() -> List[Dict[str, Any]]:
    """TODO: PLUG YOUR BACKEND — return trending products list."""
    _, prods = answer_user_query("trending", [])
    return prods


def get_categories() -> List[str]:
    """TODO: PLUG YOUR BACKEND — return category names."""
    return [
        "Electronics",
        "Home & Kitchen",
        "Books",
        "Fashion",
        "Beauty",
        "Toys & Games",
        "Sports & Outdoors",
    ]


# =========================================================
# 2. HTML RENDERING HELPERS
# =========================================================

EMOJI_BY_CATEGORY = {
    "Electronics": "🎧",
    "Home & Kitchen": "🍳",
    "Books": "📘",
    "Fashion": "👟",
    "Clothing": "👟",
    "Beauty": "🧴",
    "Beauty & Personal Care": "🧴",
    "Toys": "🎮",
    "Toys & Games": "🎮",
    "Sports & Outdoors": "🏋️",
    "Pet Supplies": "🐾",
    "Office Products": "🖱️",
}


def _safe(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def render_product_card(p: Dict[str, Any]) -> str:
    """Render one product as an HTML card."""
    title = _safe(p.get("title", "Untitled"))
    brand = _safe(p.get("brand", ""))
    price = p.get("price", 0.0)
    rating = float(p.get("rating", 0.0) or 0.0)
    reviews = int(p.get("review_count", 0) or 0)
    category = p.get("category", "")
    desc = _safe(p.get("description", ""))
    url = p.get("url", "")
    image_url = p.get("image_url", "")
    tags = p.get("tags", []) or []

    # Image or emoji fallback
    if image_url:
        image_html = (
            f'<div class="sm-card-img">'
            f'<img src="{_safe(image_url)}" alt="{title}" loading="lazy"/>'
            f"</div>"
        )
    else:
        emoji = EMOJI_BY_CATEGORY.get(category, "📦")
        image_html = f'<div class="sm-card-img sm-card-img-emoji">{emoji}</div>'

    stars = "★" * int(round(rating)) + "☆" * (5 - int(round(rating)))
    tags_html = "".join(
        f'<span class="sm-tag">{_safe(t)}</span>' for t in tags[:3]
    )
    brand_line = f'<div class="sm-card-brand">{brand}</div>' if brand else ""
    desc_html = f'<div class="sm-card-desc">{desc}</div>' if desc else ""
    button_html = (
        f'<a class="sm-card-btn" href="{_safe(url)}" target="_blank" rel="noopener">View</a>'
        if url
        else '<button class="sm-card-btn" type="button">View</button>'
    )

    return f"""
    <article class="sm-card">
      {image_html}
      <div class="sm-card-body">
        {brand_line}
        <div class="sm-card-title">{title}</div>
        <div class="sm-card-meta">
          <span class="sm-stars">{stars}</span>
          <span class="sm-rating">{rating:.1f}</span>
          <span class="sm-reviews">({reviews:,})</span>
        </div>
        {desc_html}
        <div class="sm-card-tags">{tags_html}</div>
        <div class="sm-card-footer">
          <div class="sm-card-price">${float(price):.2f}</div>
          {button_html}
        </div>
      </div>
    </article>
    """


def render_product_grid(products: List[Dict[str, Any]]) -> str:
    if not products:
        return (
            '<div class="sm-empty">'
            "💡 Ask me anything — I'll show product recommendations here."
            "</div>"
        )
    cards = "\n".join(render_product_card(p) for p in products)
    header = (
        f'<div class="sm-grid-header">'
        f"<span class='sm-grid-title'>Recommended for you</span>"
        f"<span class='sm-grid-count'>{len(products)} products</span>"
        f"</div>"
    )
    return f'{header}<div class="sm-grid">{cards}</div>'


# =========================================================
# 3. CSS — minimal, targeted, no !important abuse
# =========================================================

SHOPMATE_CSS = """
:root {
  --sm-primary: #5b5bf6;
  --sm-primary-dark: #4a4ae0;
  --sm-primary-light: #eeeeff;
  --sm-bg: #f6f7fb;
  --sm-panel: #ffffff;
  --sm-border: #e5e7eb;
  --sm-text: #111827;
  --sm-muted: #6b7280;
  --sm-soft: #9ca3af;
}

.gradio-container {
  max-width: 1400px !important;
  background: var(--sm-bg);
}

/* --- Sidebar --- */
#sm-sidebar {
  background: var(--sm-panel);
  border: 1px solid var(--sm-border);
  border-radius: 16px;
  padding: 18px 14px;
  min-height: 620px;
}
#sm-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 4px 6px 14px 6px;
  border-bottom: 1px solid var(--sm-border);
  margin-bottom: 14px;
}
#sm-brand .sm-logo {
  width: 36px; height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6d6dfa, #a56dfa);
  color: #fff; font-size: 20px;
  display: grid; place-items: center;
}
#sm-brand .sm-brand-name {
  font-weight: 700; font-size: 17px; color: var(--sm-text);
  line-height: 1.1;
}
#sm-brand .sm-brand-sub {
  font-size: 11px; color: var(--sm-muted);
}
.sm-section-label {
  font-size: 11px; letter-spacing: 0.08em;
  color: var(--sm-soft); font-weight: 600;
  margin: 14px 4px 6px 4px; text-transform: uppercase;
}
#sm-sidebar .sm-side-btn button {
  width: 100%;
  justify-content: flex-start;
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  color: var(--sm-text);
  font-weight: 500;
  padding: 10px 12px;
  border-radius: 10px;
}
#sm-sidebar .sm-side-btn button:hover {
  background: var(--sm-primary-light);
  border-color: #dcdcfa;
}
#sm-new-chat button {
  background: var(--sm-primary);
  color: #fff;
  font-weight: 600;
  border-radius: 10px;
  padding: 10px 14px;
}
#sm-new-chat button:hover { background: var(--sm-primary-dark); }

#sm-recent-list .form { border: none; background: transparent; }
#sm-recent-list label {
  display: block;
  padding: 8px 10px;
  border-radius: 8px;
  color: var(--sm-text);
  font-size: 13px;
  cursor: pointer;
}
#sm-recent-list label:hover { background: var(--sm-primary-light); }
#sm-recent-list input[type="radio"] { display: none; }

#sm-account {
  margin-top: 16px; padding-top: 14px;
  border-top: 1px solid var(--sm-border);
  display: flex; align-items: center; gap: 10px;
}
#sm-account .sm-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: var(--sm-primary); color: #fff;
  display: grid; place-items: center; font-weight: 700;
}
#sm-account .sm-account-name { font-size: 13px; font-weight: 600; }
#sm-account .sm-account-sub { font-size: 11px; color: var(--sm-muted); }

/* --- Main column --- */
#sm-main {
  background: var(--sm-panel);
  border: 1px solid var(--sm-border);
  border-radius: 16px;
  padding: 0;
  overflow: hidden;
  min-height: 620px;
}
#sm-topbar {
  padding: 14px 20px;
  border-bottom: 1px solid var(--sm-border);
  display: flex; align-items: center; justify-content: space-between;
  background: #fff;
}
#sm-topbar .sm-title { font-weight: 700; font-size: 16px; color: var(--sm-text); }
#sm-topbar .sm-sub { font-size: 12px; color: var(--sm-muted); }

#sm-chat { border: none; box-shadow: none; background: transparent; }
#sm-chat .message-wrap { padding: 4px 20px; }

/* --- Product grid --- */
#sm-products {
  padding: 6px 20px 20px 20px;
  max-height: 480px;
  overflow-y: auto;
}
.sm-grid-header {
  display: flex; justify-content: space-between; align-items: center;
  margin: 10px 0 12px 0;
}
.sm-grid-title { font-weight: 700; color: var(--sm-text); font-size: 15px; }
.sm-grid-count { color: var(--sm-muted); font-size: 12px; }
.sm-empty {
  padding: 40px 20px; text-align: center;
  color: var(--sm-muted); font-size: 14px;
  border: 1px dashed var(--sm-border); border-radius: 14px;
  background: #fafbff;
}
.sm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}
.sm-card {
  background: #fff;
  border: 1px solid var(--sm-border);
  border-radius: 14px;
  padding: 12px;
  display: flex; flex-direction: column;
  transition: box-shadow .15s, transform .15s, border-color .15s;
}
.sm-card:hover {
  box-shadow: 0 8px 24px rgba(91, 91, 246, 0.12);
  border-color: #c9c9fa;
  transform: translateY(-1px);
}
.sm-card-img {
  height: 110px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f1f3fb, #e8eaf6);
  display: grid; place-items: center;
  overflow: hidden;
  margin-bottom: 10px;
}
.sm-card-img-emoji { font-size: 48px; }
.sm-card-img img { max-width: 100%; max-height: 100%; object-fit: contain; }
.sm-card-brand { font-size: 11px; color: var(--sm-muted); margin-bottom: 2px; }
.sm-card-title {
  font-size: 13px; font-weight: 600; color: var(--sm-text);
  line-height: 1.35;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; min-height: 34px;
}
.sm-card-meta {
  display: flex; align-items: center; gap: 6px;
  margin-top: 6px; font-size: 12px;
}
.sm-stars { color: #f59e0b; letter-spacing: 1px; font-size: 11px; }
.sm-rating { font-weight: 600; color: var(--sm-text); }
.sm-reviews { color: var(--sm-muted); }
.sm-card-desc {
  font-size: 12px; color: var(--sm-muted);
  margin-top: 6px; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.sm-card-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.sm-tag {
  font-size: 10px; padding: 2px 8px;
  background: #f3f4f6; color: #4b5563;
  border-radius: 999px;
}
.sm-card-footer {
  margin-top: 10px; padding-top: 10px;
  border-top: 1px solid #f1f2f6;
  display: flex; align-items: center; justify-content: space-between;
}
.sm-card-price { font-weight: 700; font-size: 16px; color: var(--sm-text); }
.sm-card-btn {
  background: var(--sm-primary); color: #fff;
  border: none; border-radius: 8px;
  padding: 6px 14px; font-size: 12px; font-weight: 600;
  cursor: pointer; text-decoration: none; display: inline-block;
}
.sm-card-btn:hover { background: var(--sm-primary-dark); }

/* --- Composer --- */
#sm-composer {
  padding: 14px 20px;
  border-top: 1px solid var(--sm-border);
  background: #fff;
}
#sm-composer .sm-input textarea {
  border-radius: 14px;
  border: 1px solid var(--sm-border);
  padding: 12px 14px;
  font-size: 14px;
  background: #fbfcff;
}
#sm-composer .sm-input textarea:focus {
  border-color: var(--sm-primary);
  background: #fff;
  outline: none;
}
#sm-send button {
  background: var(--sm-primary);
  color: #fff;
  border-radius: 14px;
  padding: 12px 22px;
  font-weight: 600;
  border: none;
}
#sm-send button:hover { background: var(--sm-primary-dark); }

.sm-hint {
  text-align: center; color: var(--sm-soft);
  font-size: 11px; margin-top: 6px;
}

/* --- Suggestion chips --- */
#sm-suggestions { padding: 6px 20px 0 20px; }
#sm-suggestions .sm-chip button {
  background: #fff; border: 1px solid var(--sm-border);
  color: var(--sm-text); font-size: 12px;
  padding: 6px 12px; border-radius: 999px;
}
#sm-suggestions .sm-chip button:hover {
  border-color: var(--sm-primary); background: var(--sm-primary-light);
}

footer { display: none !important; }
"""


# =========================================================
# 4. CHAT HANDLERS
# =========================================================

INITIAL_GREETING = {
    "role": "assistant",
    "content": (
        "Hi! I'm **ShopMate** 🛍️ — your personalized shopping assistant "
        "powered by Amazon 2023 data.\n\n"
        "Tell me what you're looking for (e.g. *\"noise-cancelling headphones "
        "under $250\"*, *\"a gift for a coffee lover\"*, *\"skincare for dry skin\"*) "
        "and I'll find the best matches for you."
    ),
}


def on_send(message: str, history: List[Dict[str, str]]):
    """Handle a user message. Returns (history, products_html, input_reset)."""
    message = (message or "").strip()
    if not message:
        return history, gr.update(), ""

    history = list(history) + [{"role": "user", "content": message}]
    reply_text, products = answer_user_query(message, history)
    history.append({"role": "assistant", "content": reply_text})
    return history, render_product_grid(products), ""


def on_suggestion(prompt: str, history: List[Dict[str, str]]):
    return on_send(prompt, history)


def on_new_chat():
    return [INITIAL_GREETING], render_product_grid([]), ""


def on_trending(history: List[Dict[str, str]]):
    prods = get_trending_products()
    history = list(history) + [
        {"role": "user", "content": "Show me trending products"},
        {
            "role": "assistant",
            "content": "Here are the trending products right now — top-rated across categories:",
        },
    ]
    return history, render_product_grid(prods), ""


def on_categories(history: List[Dict[str, str]]):
    cats = get_categories()
    reply = "**Available categories:**\n\n" + "\n".join(f"• {c}" for c in cats)
    history = list(history) + [
        {"role": "user", "content": "Browse categories"},
        {"role": "assistant", "content": reply},
    ]
    return history, gr.update(), ""


# =========================================================
# 5. BUILD THE INTERFACE
# =========================================================

def build_ui() -> gr.Blocks:
    with gr.Blocks(
        title="ShopMate — Personalized Shopping AI",
        css=SHOPMATE_CSS,
        theme=gr.themes.Soft(
            primary_hue="indigo",
            neutral_hue="slate",
            font=("Inter", "system-ui", "sans-serif"),
        ),
    ) as demo:

        gr.HTML(
            """
            <div style="padding: 14px 4px 8px 4px;">
              <div style="font-size:22px;font-weight:800;color:#111827;">
                ShopMate <span style="color:#5b5bf6;">·</span>
                <span style="font-weight:500;color:#6b7280;font-size:16px;">
                  Personalized Shopping AI
                </span>
              </div>
              <div style="color:#6b7280;font-size:13px;margin-top:2px;">
                A ChatGPT-style assistant that recommends from the Amazon 2023 catalog.
              </div>
            </div>
            """
        )

        with gr.Row(equal_height=False):
            # -------- SIDEBAR --------
            with gr.Column(scale=1, min_width=260, elem_id="sm-sidebar"):
                gr.HTML(
                    """
                    <div id="sm-brand">
                      <div class="sm-logo">🛍️</div>
                      <div>
                        <div class="sm-brand-name">ShopMate</div>
                        <div class="sm-brand-sub">Powered by Amazon 2023 data</div>
                      </div>
                    </div>
                    """
                )

                new_chat_btn = gr.Button(
                    "＋  New Chat", elem_id="sm-new-chat"
                )

                gr.HTML('<div class="sm-section-label">Quick Actions</div>')
                trending_btn = gr.Button(
                    "🔥  Trending Products", elem_classes=["sm-side-btn"]
                )
                categories_btn = gr.Button(
                    "🗂️  Browse Categories", elem_classes=["sm-side-btn"]
                )

                gr.HTML('<div class="sm-section-label">Recent Chats</div>')
                recent = gr.Radio(
                    choices=["Current session"],
                    value="Current session",
                    label="",
                    show_label=False,
                    elem_id="sm-recent-list",
                    interactive=True,
                )

                gr.HTML(
                    """
                    <div id="sm-account">
                      <div class="sm-avatar">U</div>
                      <div>
                        <div class="sm-account-name">Guest User</div>
                        <div class="sm-account-sub">Local session</div>
                      </div>
                    </div>
                    """
                )

            # -------- MAIN COLUMN --------
            with gr.Column(scale=3, elem_id="sm-main"):
                gr.HTML(
                    """
                    <div id="sm-topbar">
                      <div>
                        <div class="sm-title">Shopping Assistant</div>
                        <div class="sm-sub">Ask anything — get personalized picks</div>
                      </div>
                      <div class="sm-sub">🟢 Online</div>
                    </div>
                    """
                )

                chatbot = gr.Chatbot(
                    value=[INITIAL_GREETING],
                    type="messages",
                    elem_id="sm-chat",
                    height=340,
                    show_label=False,
                    show_copy_button=True,
                    bubble_full_width=False,
                    avatar_images=(None, None),
                )

                # Suggestion chips
                with gr.Row(elem_id="sm-suggestions"):
                    s1 = gr.Button(
                        "Noise cancelling headphones under $300",
                        elem_classes=["sm-chip"], size="sm",
                    )
                    s2 = gr.Button(
                        "Gift for a coffee lover",
                        elem_classes=["sm-chip"], size="sm",
                    )
                    s3 = gr.Button(
                        "Home gym essentials",
                        elem_classes=["sm-chip"], size="sm",
                    )

                products_html = gr.HTML(
                    render_product_grid([]), elem_id="sm-products"
                )

                with gr.Column(elem_id="sm-composer"):
                    with gr.Row():
                        msg = gr.Textbox(
                            placeholder="Ask about products, get recommendations…",
                            lines=1,
                            max_lines=4,
                            show_label=False,
                            elem_classes=["sm-input"],
                            scale=8,
                            autofocus=True,
                        )
                        send_btn = gr.Button(
                            "Send ➤", elem_id="sm-send", scale=1, variant="primary"
                        )
                    gr.HTML(
                        '<div class="sm-hint">'
                        "ShopMate uses Amazon 2023 product data for personalized recommendations."
                        "</div>"
                    )

        # -------- EVENTS --------
        send_btn.click(
            on_send,
            inputs=[msg, chatbot],
            outputs=[chatbot, products_html, msg],
        )
        msg.submit(
            on_send,
            inputs=[msg, chatbot],
            outputs=[chatbot, products_html, msg],
        )

        new_chat_btn.click(
            on_new_chat, inputs=None, outputs=[chatbot, products_html, msg]
        )
        trending_btn.click(
            on_trending, inputs=[chatbot], outputs=[chatbot, products_html, msg]
        )
        categories_btn.click(
            on_categories, inputs=[chatbot], outputs=[chatbot, products_html, msg]
        )

        for chip in (s1, s2, s3):
            chip.click(
                on_suggestion,
                inputs=[chip, chatbot],
                outputs=[chatbot, products_html, msg],
            )

    return demo


# =========================================================
# 6. LAUNCH
# =========================================================

if __name__ == "__main__":
    ui = build_ui()
    ui.queue()
    ui.launch(inbrowser=True, share=False)
