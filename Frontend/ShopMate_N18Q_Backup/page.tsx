"use client";

import {
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  ShopMateApiError,
  createShopMateChat,
  loadShopMateSession,
  loginToShopMate,
  logoutFromShopMate,
  registerShopMateAccount,
  selectShopMateChat,
  sendShopMateMessage,
  type WorkspaceData,
} from "@/lib/shopmate-api";

import {
  normalizeShopMateWorkspace,
  type ShopMateMessage,
} from "@/lib/shopmate-workspace";

type AuthenticationMode = "login" | "register";

const TOKEN_STORAGE_KEY = "shopmate_auth_token";

const welcomeMessage: ShopMateMessage = {
  role: "assistant",
  content:
    "Hello! I’m ShopMate, your personalized shopping assistant. Tell me what clothing, footwear, fashion, or beauty product you are looking for. You can include your budget, preferred brand, size, colour, occasion, or travel plans.",
};

function getReadableError(error: unknown): string {
  if (error instanceof ShopMateApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "An unexpected ShopMate error occurred.";
}

function formatScore(value: number | null): string {
  if (value === null) {
    return "";
  }

  const percentage =
    value >= 0 && value <= 1
      ? value * 100
      : value;

  return `${Math.round(percentage)}%`;
}

export default function HomePage() {
  const [token, setToken] =
    useState<string | null>(null);

  const [workspaceData, setWorkspaceData] =
    useState<WorkspaceData | null>(null);

  const [authenticationMode, setAuthenticationMode] =
    useState<AuthenticationMode>("login");

  const [initializing, setInitializing] =
    useState(true);

  const [busy, setBusy] =
    useState(false);

  const [errorMessage, setErrorMessage] =
    useState("");

  const [loginIdentity, setLoginIdentity] =
    useState("");

  const [loginPassword, setLoginPassword] =
    useState("");

  const [registerUsername, setRegisterUsername] =
    useState("");

  const [registerDisplayName, setRegisterDisplayName] =
    useState("");

  const [registerEmail, setRegisterEmail] =
    useState("");

  const [registerPassword, setRegisterPassword] =
    useState("");

  const [
    registerConfirmPassword,
    setRegisterConfirmPassword,
  ] = useState("");

  const [messageInput, setMessageInput] =
    useState("");

  const [pendingUserMessage, setPendingUserMessage] =
    useState("");

  const conversationRef =
    useRef<HTMLDivElement | null>(null);

  const workspace = useMemo(
    () =>
      normalizeShopMateWorkspace(
        workspaceData ?? {},
      ),
    [workspaceData],
  );

  const selectedChatTitle =
    workspace.chats.find(
      (chat) =>
        chat.id === workspace.selectedChatId,
    )?.title ?? "Shopping Assistant";

  const displayedMessages = useMemo(() => {
    const storedMessages =
      workspace.messages.length > 0
        ? workspace.messages
        : [welcomeMessage];

    if (!pendingUserMessage) {
      return storedMessages;
    }

    return [
      ...storedMessages,
      {
        role: "user" as const,
        content: pendingUserMessage,
      },
    ];
  }, [
    workspace.messages,
    pendingUserMessage,
  ]);

  useEffect(() => {
    const savedToken =
      window.localStorage.getItem(
        TOKEN_STORAGE_KEY,
      );

    if (!savedToken) {
      setInitializing(false);
      return;
    }

    loadShopMateSession(savedToken)
      .then((response) => {
        setToken(savedToken);
        setWorkspaceData(response.workspace);
      })
      .catch(() => {
        window.localStorage.removeItem(
          TOKEN_STORAGE_KEY,
        );

        setToken(null);
        setWorkspaceData(null);
      })
      .finally(() => {
        setInitializing(false);
      });
  }, []);

  useEffect(() => {
    const conversationElement =
      conversationRef.current;

    if (!conversationElement) {
      return;
    }

    conversationElement.scrollTo({
      top: conversationElement.scrollHeight,
      behavior: "smooth",
    });
  }, [
    displayedMessages,
    workspace.products,
    busy,
  ]);

  async function handleLogin(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setBusy(true);
    setErrorMessage("");

    try {
      const response = await loginToShopMate({
        login_identity: loginIdentity.trim(),
        password: loginPassword,
      });

      window.localStorage.setItem(
        TOKEN_STORAGE_KEY,
        response.token,
      );

      setToken(response.token);
      setWorkspaceData(response.workspace);
      setLoginPassword("");
    } catch (error) {
      setErrorMessage(
        getReadableError(error),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRegistration(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setBusy(true);
    setErrorMessage("");

    try {
      const response =
        await registerShopMateAccount({
          username: registerUsername.trim(),
          display_name:
            registerDisplayName.trim() ||
            undefined,
          email:
            registerEmail.trim() ||
            undefined,
          password: registerPassword,
          confirm_password:
            registerConfirmPassword,
        });

      window.localStorage.setItem(
        TOKEN_STORAGE_KEY,
        response.token,
      );

      setToken(response.token);
      setWorkspaceData(response.workspace);
      setRegisterPassword("");
      setRegisterConfirmPassword("");
    } catch (error) {
      setErrorMessage(
        getReadableError(error),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    if (!token) {
      return;
    }

    setBusy(true);
    setErrorMessage("");

    try {
      await logoutFromShopMate(token);
    } catch {
      // The local token is cleared even when the server
      // session has already expired.
    } finally {
      window.localStorage.removeItem(
        TOKEN_STORAGE_KEY,
      );

      setToken(null);
      setWorkspaceData(null);
      setMessageInput("");
      setPendingUserMessage("");
      setBusy(false);
    }
  }

  async function handleNewChat() {
    if (!token || busy) {
      return;
    }

    setBusy(true);
    setErrorMessage("");

    try {
      const response =
        await createShopMateChat(token);

      setWorkspaceData(
        response.workspace,
      );
    } catch (error) {
      setErrorMessage(
        getReadableError(error),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSelectChat(
    chatId: number,
  ) {
    if (!token || busy) {
      return;
    }

    if (chatId === workspace.selectedChatId) {
      return;
    }

    setBusy(true);
    setErrorMessage("");

    try {
      const response =
        await selectShopMateChat(
          token,
          chatId,
        );

      setWorkspaceData(
        response.workspace,
      );
    } catch (error) {
      setErrorMessage(
        getReadableError(error),
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitMessage(
    requestedMessage: string,
  ) {
    if (!token || busy) {
      return;
    }

    const cleanedMessage =
      requestedMessage.trim();

    if (!cleanedMessage) {
      return;
    }

    setBusy(true);
    setErrorMessage("");
    setMessageInput("");
    setPendingUserMessage(cleanedMessage);

    try {
      let activeChatId =
        workspace.selectedChatId;

      if (activeChatId === null) {
        const newChatResponse =
          await createShopMateChat(token);

        setWorkspaceData(
          newChatResponse.workspace,
        );

        const newWorkspace =
          normalizeShopMateWorkspace(
            newChatResponse.workspace,
          );

        activeChatId =
          newWorkspace.selectedChatId;
      }

      if (activeChatId === null) {
        throw new Error(
          "ShopMate could not create an active chat.",
        );
      }

      const response =
        await sendShopMateMessage(
          token,
          {
            chat_id: activeChatId,
            message_text: cleanedMessage,
            top_n: 10,
          },
        );

      setWorkspaceData(
        response.workspace,
      );
    } catch (error) {
      setErrorMessage(
        getReadableError(error),
      );
    } finally {
      setPendingUserMessage("");
      setBusy(false);
    }
  }

  function handleMessageSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    void submitMessage(messageInput);
  }

  if (initializing) {
    return (
      <main className="shopmate-loading-screen">
        <div className="shopmate-loading-logo">
          S
        </div>

        <h1>ShopMate</h1>
        <p>Connecting to your shopping workspace…</p>
      </main>
    );
  }

  if (!token) {
    return (
      <main className="shopmate-auth-page">
        <section className="shopmate-auth-brand">
          <div className="shopmate-auth-logo">
            S
          </div>

          <h1>ShopMate</h1>

          <p className="shopmate-auth-powered">
            Powered by Amazon 2023 Data
          </p>

          <h2>
            Personalized fashion and shopping
            recommendations
          </h2>

          <p className="shopmate-auth-description">
            Search clothing, footwear, fashion,
            apparel, and beauty products using your
            preferences, budget, conversation history,
            and contextual requirements.
          </p>

          <div className="shopmate-auth-feature">
            ✓ Persistent user profile and chats
          </div>

          <div className="shopmate-auth-feature">
            ✓ Explainable hybrid recommendations
          </div>

          <div className="shopmate-auth-feature">
            ✓ Conditional travel and weather context
          </div>
        </section>

        <section className="shopmate-auth-panel">
          <div className="shopmate-auth-card">
            <div className="shopmate-auth-tabs">
              <button
                type="button"
                className={
                  authenticationMode === "login"
                    ? "active"
                    : ""
                }
                onClick={() => {
                  setAuthenticationMode("login");
                  setErrorMessage("");
                }}
              >
                Login
              </button>

              <button
                type="button"
                className={
                  authenticationMode === "register"
                    ? "active"
                    : ""
                }
                onClick={() => {
                  setAuthenticationMode("register");
                  setErrorMessage("");
                }}
              >
                Create Account
              </button>
            </div>

            {errorMessage && (
              <div className="shopmate-error">
                {errorMessage}
              </div>
            )}

            {authenticationMode === "login" ? (
              <form
                className="shopmate-auth-form"
                onSubmit={handleLogin}
              >
                <h2>Welcome back</h2>

                <p>
                  Log in to access your saved chats and
                  personalized recommendations.
                </p>

                <label>
                  Username or email
                  <input
                    value={loginIdentity}
                    required
                    autoComplete="username"
                    onChange={(event) =>
                      setLoginIdentity(
                        event.target.value,
                      )
                    }
                  />
                </label>

                <label>
                  Password
                  <input
                    type="password"
                    value={loginPassword}
                    required
                    autoComplete="current-password"
                    onChange={(event) =>
                      setLoginPassword(
                        event.target.value,
                      )
                    }
                  />
                </label>

                <button
                  type="submit"
                  className="shopmate-auth-submit"
                  disabled={busy}
                >
                  {busy
                    ? "Logging in…"
                    : "Login to ShopMate"}
                </button>
              </form>
            ) : (
              <form
                className="shopmate-auth-form"
                onSubmit={handleRegistration}
              >
                <h2>Create your account</h2>

                <p>
                  Your account stores profile
                  preferences, chats, and recommendation
                  history.
                </p>

                <label>
                  Username
                  <input
                    value={registerUsername}
                    required
                    minLength={3}
                    autoComplete="username"
                    onChange={(event) =>
                      setRegisterUsername(
                        event.target.value,
                      )
                    }
                  />
                </label>

                <label>
                  Display name
                  <input
                    value={registerDisplayName}
                    autoComplete="name"
                    onChange={(event) =>
                      setRegisterDisplayName(
                        event.target.value,
                      )
                    }
                  />
                </label>

                <label>
                  Email
                  <input
                    type="email"
                    value={registerEmail}
                    autoComplete="email"
                    onChange={(event) =>
                      setRegisterEmail(
                        event.target.value,
                      )
                    }
                  />
                </label>

                <label>
                  Password
                  <input
                    type="password"
                    value={registerPassword}
                    required
                    minLength={8}
                    autoComplete="new-password"
                    onChange={(event) =>
                      setRegisterPassword(
                        event.target.value,
                      )
                    }
                  />
                </label>

                <label>
                  Confirm password
                  <input
                    type="password"
                    value={
                      registerConfirmPassword
                    }
                    required
                    minLength={8}
                    autoComplete="new-password"
                    onChange={(event) =>
                      setRegisterConfirmPassword(
                        event.target.value,
                      )
                    }
                  />
                </label>

                <button
                  type="submit"
                  className="shopmate-auth-submit"
                  disabled={busy}
                >
                  {busy
                    ? "Creating account…"
                    : "Create ShopMate Account"}
                </button>
              </form>
            )}
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="shopmate-app">
      <aside className="shopmate-sidebar">
        <div className="shopmate-brand">
          <div className="shopmate-brand-row">
            <div className="shopmate-brand-logo">
              S
            </div>

            <div className="shopmate-brand-name">
              ShopMate
            </div>
          </div>

          <div className="shopmate-powered">
            Powered by Amazon 2023 Data
          </div>
        </div>

        <div className="shopmate-sidebar-content">
          <button
            type="button"
            className="shopmate-sidebar-button new-chat-button"
            onClick={() => {
              void handleNewChat();
            }}
            disabled={busy}
          >
            <span className="sidebar-icon">＋</span>
            New Chat
          </button>

          <div className="sidebar-section-title">
            QUICK ACTIONS
          </div>

          <button
            type="button"
            className="shopmate-sidebar-button"
            disabled={busy}
            onClick={() => {
              void submitMessage(
                "Show me popular and highly rated fashion products.",
              );
            }}
          >
            <span className="sidebar-icon">✣</span>
            Popular Fashion
          </button>

          <button
            type="button"
            className="shopmate-sidebar-button"
            disabled={busy}
            onClick={() => {
              void submitMessage(
                "Show me the available clothing, footwear, fashion, and beauty categories.",
              );
            }}
          >
            <span className="sidebar-icon">▦</span>
            Browse Categories
          </button>

          <div className="sidebar-section-title recent-title">
            RECENT CHATS
          </div>

          <div className="recent-chat-list">
            {workspace.chats.length > 0 ? (
              workspace.chats.map((chat) => (
                <button
                  type="button"
                  key={chat.id}
                  className={
                    workspace.selectedChatId ===
                    chat.id
                      ? "recent-chat active"
                      : "recent-chat"
                  }
                  disabled={busy}
                  onClick={() => {
                    void handleSelectChat(chat.id);
                  }}
                >
                  <span className="recent-chat-icon">
                    ◯
                  </span>

                  <span className="recent-chat-text">
                    {chat.title}
                  </span>
                </button>
              ))
            ) : (
              <div className="shopmate-empty-chats">
                Your saved chats will appear here.
              </div>
            )}
          </div>
        </div>

        <div className="shopmate-account">
          <div className="account-avatar">
            {workspace.displayName
              .charAt(0)
              .toUpperCase()}
          </div>

          <div className="account-copy">
            <div className="account-name">
              {workspace.displayName}
            </div>

            <div className="account-status">
              Personal account
            </div>
          </div>

          <button
            type="button"
            className="account-menu"
            onClick={() => {
              void handleLogout();
            }}
            disabled={busy}
            title="Log out"
          >
            ↪
          </button>
        </div>
      </aside>

      <section className="shopmate-main">
        <header className="shopmate-topbar">
          <button
            type="button"
            className="topbar-back"
            onClick={() => {
              void handleNewChat();
            }}
            disabled={busy}
            aria-label="Start new chat"
          >
            ‹
          </button>

          <div className="topbar-title">
            {selectedChatTitle}
          </div>

          <div className="topbar-spacer" />
        </header>

        <div
          ref={conversationRef}
          className="shopmate-conversation"
        >
          <div className="conversation-inner">
            {errorMessage && (
              <div className="shopmate-error workspace-error">
                {errorMessage}
              </div>
            )}

            {displayedMessages.map(
              (message, index) => (
                <div
                  key={`${message.role}-${index}-${message.content.slice(0, 20)}`}
                  className={
                    message.role === "user"
                      ? "message-row user-row"
                      : "message-row assistant-row"
                  }
                >
                  {message.role ===
                    "assistant" && (
                    <div className="message-avatar assistant-avatar">
                      S
                    </div>
                  )}

                  <div
                    className={
                      message.role === "user"
                        ? "message-bubble user-bubble"
                        : "message-bubble assistant-bubble"
                    }
                  >
                    {message.content}
                  </div>

                  {message.role === "user" && (
                    <div className="message-avatar user-avatar">
                      {workspace.displayName
                        .charAt(0)
                        .toUpperCase()}
                    </div>
                  )}
                </div>
              ),
            )}

            {busy && pendingUserMessage && (
              <div className="message-row assistant-row">
                <div className="message-avatar assistant-avatar">
                  S
                </div>

                <div className="message-bubble assistant-bubble shopmate-thinking">
                  Finding suitable products from the
                  Amazon 2023 catalogue…
                </div>
              </div>
            )}

            {workspace.statusText && (
              <div className="shopmate-workspace-status">
                {workspace.statusText}
              </div>
            )}

            {workspace.weatherVisible &&
              workspace.weatherText && (
                <section className="shopmate-weather-panel">
                  <strong>
                    Travel and weather context
                  </strong>

                  <p>{workspace.weatherText}</p>
                </section>
              )}

            {workspace.products.length > 0 && (
              <section className="recommendation-section">
                <div className="recommendation-heading">
                  <div>
                    <h2>Recommended for you</h2>

                    <p>
                      Real products from your processed
                      Amazon catalogue
                    </p>
                  </div>

                  <span>
                    {workspace.products.length} products
                  </span>
                </div>

                <div className="product-grid">
                  {workspace.products.map(
                    (product, index) => (
                      <article
                        className="product-card"
                        key={`${product.productId}-${index}`}
                      >
                        <div className="product-image-wrap">
                          {product.imageUrl ? (
                            <img
                              src={product.imageUrl}
                              alt={product.title}
                              className="product-image"
                            />
                          ) : (
                            <div className="product-image-placeholder">
                              Product image
                            </div>
                          )}
                        </div>

                        <div className="product-information">
                          <div className="product-brand">
                            {product.brand}
                          </div>

                          <h3 className="product-title">
                            {product.title}
                          </h3>

                          {product.category && (
                            <div className="product-category">
                              {product.category}
                            </div>
                          )}

                          {(product.ratingText ||
                            product.reviewCountText) && (
                            <div className="product-rating">
                              <span className="rating-star">
                                ★
                              </span>

                              <strong>
                                {product.ratingText}
                              </strong>

                              {product.reviewCountText && (
                                <span>
                                  (
                                  {
                                    product.reviewCountText
                                  }
                                  )
                                </span>
                              )}
                            </div>
                          )}

                          <div className="product-tags">
                            {product.matchScore !==
                              null && (
                              <span>
                                Match{" "}
                                {formatScore(
                                  product.matchScore,
                                )}
                              </span>
                            )}

                            {product.trustScore !==
                              null && (
                              <span>
                                Trust{" "}
                                {formatScore(
                                  product.trustScore,
                                )}
                              </span>
                            )}

                            {product.tags.map((tag) => (
                              <span key={tag}>
                                {tag}
                              </span>
                            ))}
                          </div>

                          {product.explanation && (
                            <p className="product-explanation">
                              {product.explanation}
                            </p>
                          )}

                          <div className="product-footer">
                            <div className="product-price">
                              {product.priceText}
                            </div>

                            {product.purchaseUrl && (
                              <a
                                href={
                                  product.purchaseUrl
                                }
                                target="_blank"
                                rel="noreferrer"
                              >
                                View product
                              </a>
                            )}
                          </div>
                        </div>
                      </article>
                    ),
                  )}
                </div>

                <p className="historical-price-note">
                  Prices and catalogue information are
                  historical Amazon 2023 data and may not
                  represent current availability or prices.
                </p>
              </section>
            )}

            {workspace.products.length === 0 &&
              workspace.productCardsHtml && (
                <section
                  className="shopmate-html-card-fallback"
                  dangerouslySetInnerHTML={{
                    __html:
                      workspace.productCardsHtml,
                  }}
                />
              )}
          </div>
        </div>

        <footer className="shopmate-composer-shell">
          <form
            className="shopmate-composer"
            onSubmit={handleMessageSubmit}
          >
            <textarea
              value={messageInput}
              rows={2}
              disabled={busy}
              placeholder="Ask for clothing, shoes, fashion, apparel, or beauty products..."
              onChange={(event) =>
                setMessageInput(
                  event.target.value,
                )
              }
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey
                ) {
                  event.preventDefault();
                  void submitMessage(
                    messageInput,
                  );
                }
              }}
            />

            <button
              type="submit"
              className="composer-send"
              disabled={
                busy ||
                !messageInput.trim()
              }
              aria-label="Send message"
            >
              ➤
            </button>
          </form>

          <div className="shopmate-dataset-note">
            ShopMate uses historical Amazon 2023
            product data for personalized
            recommendations
          </div>
        </footer>
      </section>
    </main>
  );
}
