export type UnknownRecord = Record<string, unknown>;

export interface ShopMateChat {
  id: number;
  title: string;
}

export interface ShopMateMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ShopMateProduct {
  productId: string;
  title: string;
  brand: string;
  category: string;
  priceText: string;
  ratingText: string;
  reviewCountText: string;
  matchScore: number | null;
  trustScore: number | null;
  explanation: string;
  imageUrl: string;
  purchaseUrl: string;
  tags: string[];
}

export interface NormalizedWorkspace {
  selectedChatId: number | null;
  chats: ShopMateChat[];
  messages: ShopMateMessage[];
  products: ShopMateProduct[];
  productCardsHtml: string;
  displayName: string;
  statusText: string;
  weatherText: string;
  weatherVisible: boolean;
}

function isRecord(
  value: unknown,
): value is UnknownRecord {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function toText(
  value: unknown,
): string | null {
  if (typeof value === "string") {
    const cleanedValue = value.trim();

    return cleanedValue || null;
  }

  if (
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }

  return null;
}

function toNumber(
  value: unknown,
): number | null {
  if (
    typeof value === "number" &&
    Number.isFinite(value)
  ) {
    return value;
  }

  if (typeof value === "string") {
    const cleanedValue = value.trim();

    if (!cleanedValue) {
      return null;
    }

    const parsedValue = Number(cleanedValue);

    if (Number.isFinite(parsedValue)) {
      return parsedValue;
    }
  }

  return null;
}

function getRecordValue(
  record: UnknownRecord,
  candidateKeys: string[],
): unknown {
  const normalizedCandidates = new Set(
    candidateKeys.map((key) => key.toLowerCase()),
  );

  for (const [key, value] of Object.entries(record)) {
    if (
      normalizedCandidates.has(
        key.toLowerCase(),
      )
    ) {
      return value;
    }
  }

  return undefined;
}

export function findWorkspaceValue(
  value: unknown,
  candidateKeys: string[],
): unknown {
  const normalizedCandidates = new Set(
    candidateKeys.map((key) => key.toLowerCase()),
  );

  function visit(
    currentValue: unknown,
    visited: Set<object>,
  ): unknown {
    if (isRecord(currentValue)) {
      if (visited.has(currentValue)) {
        return undefined;
      }

      visited.add(currentValue);

      for (
        const [key, nestedValue]
        of Object.entries(currentValue)
      ) {
        if (
          normalizedCandidates.has(
            key.toLowerCase(),
          ) &&
          nestedValue !== null &&
          nestedValue !== undefined
        ) {
          return nestedValue;
        }
      }

      for (
        const nestedValue
        of Object.values(currentValue)
      ) {
        const foundValue = visit(
          nestedValue,
          visited,
        );

        if (foundValue !== undefined) {
          return foundValue;
        }
      }
    }

    if (Array.isArray(currentValue)) {
      for (const item of currentValue) {
        const foundValue = visit(
          item,
          visited,
        );

        if (foundValue !== undefined) {
          return foundValue;
        }
      }
    }

    return undefined;
  }

  return visit(value, new Set<object>());
}

function normalizeChats(
  workspace: unknown,
): ShopMateChat[] {
  const rawChats = findWorkspaceValue(
    workspace,
    [
      "chat_choices",
      "sidebar_chat_choices",
      "chat_sessions",
      "recent_chats",
      "chats",
    ],
  );

  if (!Array.isArray(rawChats)) {
    return [];
  }

  const chats: ShopMateChat[] = [];

  for (const rawChat of rawChats) {
    if (Array.isArray(rawChat)) {
      const firstValue = rawChat[0];
      const secondValue = rawChat[1];

      const chatId =
        toNumber(secondValue) ??
        toNumber(firstValue);

      if (chatId === null) {
        continue;
      }

      const chatTitle =
        toText(firstValue) ??
        toText(secondValue) ??
        `Chat ${chatId}`;

      chats.push({
        id: Math.trunc(chatId),
        title: chatTitle,
      });

      continue;
    }

    if (!isRecord(rawChat)) {
      continue;
    }

    const chatId = toNumber(
      getRecordValue(
        rawChat,
        [
          "chat_id",
          "id",
          "session_id",
          "value",
        ],
      ),
    );

    if (chatId === null) {
      continue;
    }

    const chatTitle =
      toText(
        getRecordValue(
          rawChat,
          [
            "chat_title",
            "title",
            "label",
            "name",
          ],
        ),
      ) ?? `Chat ${chatId}`;

    chats.push({
      id: Math.trunc(chatId),
      title: chatTitle,
    });
  }

  const uniqueChats = new Map<
    number,
    ShopMateChat
  >();

  for (const chat of chats) {
    uniqueChats.set(chat.id, chat);
  }

  return [...uniqueChats.values()];
}

function normalizeMessages(
  workspace: unknown,
): ShopMateMessage[] {
  const rawMessages = findWorkspaceValue(
    workspace,
    [
      "chatbot_messages",
      "chat_messages",
      "loaded_messages",
      "message_history",
      "chat_history",
      "messages",
      "history",
    ],
  );

  if (!Array.isArray(rawMessages)) {
    return [];
  }

  const messages: ShopMateMessage[] = [];

  for (const rawMessage of rawMessages) {
    if (Array.isArray(rawMessage)) {
      const userMessage = toText(
        rawMessage[0],
      );

      const assistantMessage = toText(
        rawMessage[1],
      );

      if (userMessage) {
        messages.push({
          role: "user",
          content: userMessage,
        });
      }

      if (assistantMessage) {
        messages.push({
          role: "assistant",
          content: assistantMessage,
        });
      }

      continue;
    }

    if (!isRecord(rawMessage)) {
      continue;
    }

    const rawRole = (
      toText(
        getRecordValue(
          rawMessage,
          [
            "role",
            "message_role",
            "sender",
            "author",
          ],
        ),
      ) ?? ""
    ).toLowerCase();

    const content = toText(
      getRecordValue(
        rawMessage,
        [
          "content",
          "message_text",
          "text",
          "message",
        ],
      ),
    );

    if (!content) {
      continue;
    }

    const role: "user" | "assistant" =
      rawRole.includes("user") ||
      rawRole.includes("human")
        ? "user"
        : "assistant";

    messages.push({
      role,
      content,
    });
  }

  return messages;
}

function normalizeTags(
  value: unknown,
): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => toText(item))
      .filter(
        (item): item is string =>
          item !== null,
      )
      .slice(0, 6);
  }

  const textValue = toText(value);

  if (!textValue) {
    return [];
  }

  return textValue
    .split(/[,|;]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 6);
}

function formatPrice(
  record: UnknownRecord,
): string {
  const explicitDisplay = toText(
    getRecordValue(
      record,
      [
        "historical_price_display",
        "price_display",
        "display_price",
        "price_text",
      ],
    ),
  );

  if (explicitDisplay) {
    return explicitDisplay;
  }

  const numericPrice = toNumber(
    getRecordValue(
      record,
      [
        "historical_price",
        "price",
        "product_price",
      ],
    ),
  );

  if (numericPrice === null) {
    return "Historical price unavailable";
  }

  return `$${numericPrice.toFixed(2)}`;
}

function formatRating(
  record: UnknownRecord,
): string {
  const explicitDisplay = toText(
    getRecordValue(
      record,
      [
        "rating_display",
        "display_rating",
        "rating_text",
      ],
    ),
  );

  if (explicitDisplay) {
    return explicitDisplay;
  }

  const numericRating = toNumber(
    getRecordValue(
      record,
      [
        "average_rating",
        "rating",
        "matched_average_rating",
      ],
    ),
  );

  if (numericRating === null) {
    return "";
  }

  return numericRating.toFixed(1);
}

function normalizeProducts(
  workspace: unknown,
): ShopMateProduct[] {
  const rawProducts = findWorkspaceValue(
    workspace,
    [
      "product_cards",
      "recommendation_cards",
      "card_records",
      "latest_recommendations",
      "loaded_recommendations",
      "recommendations",
      "cards",
    ],
  );

  if (!Array.isArray(rawProducts)) {
    return [];
  }

  const products: ShopMateProduct[] = [];

  for (const rawProduct of rawProducts) {
    if (!isRecord(rawProduct)) {
      continue;
    }

    const productId =
      toText(
        getRecordValue(
          rawProduct,
          [
            "product_id",
            "asin",
            "parent_asin",
            "id",
          ],
        ),
      ) ?? "";

    const title =
      toText(
        getRecordValue(
          rawProduct,
          [
            "title",
            "product_title",
            "name",
          ],
        ),
      ) ?? "Product";

    const brand =
      toText(
        getRecordValue(
          rawProduct,
          [
            "brand",
            "product_brand",
          ],
        ),
      ) ?? "Unknown brand";

    const category =
      toText(
        getRecordValue(
          rawProduct,
          [
            "category",
            "product_category",
            "category_label",
            "main_category",
          ],
        ),
      ) ?? "";

    const reviewCount =
      toText(
        getRecordValue(
          rawProduct,
          [
            "review_count_display",
            "rating_number",
            "review_count",
            "matched_review_count",
          ],
        ),
      ) ?? "";

    const matchScore = toNumber(
      getRecordValue(
        rawProduct,
        [
          "match_score",
          "product_match_score",
        ],
      ),
    );

    const trustScore = toNumber(
      getRecordValue(
        rawProduct,
        [
          "trust_score",
          "product_trust_score",
        ],
      ),
    );

    const explanation =
      toText(
        getRecordValue(
          rawProduct,
          [
            "explanation",
            "recommendation_explanation",
            "reason",
            "why_recommended",
          ],
        ),
      ) ?? "";

    const imageUrl =
      toText(
        getRecordValue(
          rawProduct,
          [
            "image_url",
            "product_image_url",
            "image",
          ],
        ),
      ) ?? "";

    const purchaseUrl =
      toText(
        getRecordValue(
          rawProduct,
          [
            "purchase_link",
            "amazon_url",
            "product_url",
            "buy_link",
            "url",
          ],
        ),
      ) ?? "";

    const tags = normalizeTags(
      getRecordValue(
        rawProduct,
        [
          "tags",
          "matched_attributes",
          "attributes",
          "features",
        ],
      ),
    );

    products.push({
      productId,
      title,
      brand,
      category,
      priceText: formatPrice(rawProduct),
      ratingText: formatRating(rawProduct),
      reviewCountText: reviewCount,
      matchScore,
      trustScore,
      explanation,
      imageUrl,
      purchaseUrl,
      tags,
    });
  }

  return products;
}

export function normalizeShopMateWorkspace(
  workspace: unknown,
): NormalizedWorkspace {
  const chats = normalizeChats(workspace);

  const selectedChatValue =
    findWorkspaceValue(
      workspace,
      [
        "selected_chat_id",
        "current_chat_id",
        "active_chat_id",
        "chat_id",
      ],
    );

  const selectedChatNumber = toNumber(
    selectedChatValue,
  );

  const productCardsHtml =
    toText(
      findWorkspaceValue(
        workspace,
        [
          "product_cards_html",
          "cards_html",
          "recommendation_html",
          "rendered_cards",
        ],
      ),
    ) ?? "";

  const statusText =
    toText(
      findWorkspaceValue(
        workspace,
        [
          "status_text",
          "status_message",
          "workspace_status",
          "response_status",
        ],
      ),
    ) ?? "";

  const weatherText =
    toText(
      findWorkspaceValue(
        workspace,
        [
          "weather_status",
          "weather_text",
          "weather_summary",
          "weather_message",
        ],
      ),
    ) ?? "";

  const explicitWeatherVisible =
    findWorkspaceValue(
      workspace,
      [
        "weather_visible",
        "show_weather",
      ],
    );

  const weatherVisible =
    explicitWeatherVisible === true ||
    (
      typeof explicitWeatherVisible === "string" &&
      explicitWeatherVisible.toLowerCase() === "true"
    ) ||
    Boolean(weatherText);

  const displayName =
    toText(
      findWorkspaceValue(
        workspace,
        [
          "display_name",
          "account_name",
          "username",
          "user_name",
        ],
      ),
    ) ?? "ShopMate User";

  return {
    selectedChatId:
      selectedChatNumber !== null
        ? Math.trunc(selectedChatNumber)
        : chats[0]?.id ?? null,
    chats,
    messages: normalizeMessages(workspace),
    products: normalizeProducts(workspace),
    productCardsHtml,
    displayName,
    statusText,
    weatherText,
    weatherVisible,
  };
}
