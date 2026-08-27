export type JsonObject = Record<string, unknown>;

export type WorkspaceData = JsonObject;

export interface HealthResponse {
  success: boolean;
  service: string;
  backend_restored: boolean;
  controller_count: number;
  database_connected: boolean;
}

export interface AuthenticationResponse {
  success: boolean;
  token: string;
  user_id: number;
  workspace: WorkspaceData;
}

export interface SessionResponse {
  success: boolean;
  user_id: number;
  workspace: WorkspaceData | null;
}

export interface WorkspaceResponse {
  success: boolean;
  workspace: WorkspaceData;
}

export interface LogoutResponse {
  success: boolean;
  message: string;
}

export interface RegisterInput {
  display_name: string;
  email: string;
  password: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface MessageInput {
  chat_id: number;
  message_text: string;
  top_n?: number;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_SHOPMATE_API_URL ??
  "http://127.0.0.1:8000";

export class ShopMateApiError extends Error {
  readonly status: number;
  readonly details: unknown;

  constructor(
    message: string,
    status: number,
    details: unknown = null,
  ) {
    super(message);
    this.name = "ShopMateApiError";
    this.status = status;
    this.details = details;
  }
}

function getErrorMessage(
  responseBody: unknown,
  fallbackMessage: string,
): string {
  if (
    typeof responseBody === "object" &&
    responseBody !== null
  ) {
    const record = responseBody as JsonObject;
    const detail = record.detail;

    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (
            typeof item === "object" &&
            item !== null
          ) {
            const message = (item as JsonObject).msg;

            if (typeof message === "string") {
              return message;
            }
          }

          return null;
        })
        .filter(
          (message): message is string =>
            message !== null,
        );

      if (messages.length > 0) {
        return messages.join(" ");
      }
    }

    const message = record.message;

    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }

  return fallbackMessage;
}

async function shopmateRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);

  headers.set("Accept", "application/json");

  if (
    options.body !== undefined &&
    options.body !== null
  ) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}${path}`,
      {
        ...options,
        headers,
        cache: "no-store",
      },
    );
  } catch (error) {
    throw new ShopMateApiError(
      "The ShopMate Python backend is not reachable. Keep the notebook kernel and FastAPI bridge running.",
      0,
      error,
    );
  }

  let responseBody: unknown = null;

  const contentType =
    response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      responseBody = await response.json();
    } catch {
      responseBody = null;
    }
  } else {
    try {
      responseBody = await response.text();
    } catch {
      responseBody = null;
    }
  }

  if (!response.ok) {
    throw new ShopMateApiError(
      getErrorMessage(
        responseBody,
        `ShopMate API request failed with status ${response.status}.`,
      ),
      response.status,
      responseBody,
    );
  }

  return responseBody as T;
}

export function checkShopMateHealth(): Promise<HealthResponse> {
  return shopmateRequest<HealthResponse>(
    "/api/health",
  );
}

export function registerShopMateAccount(
  input: RegisterInput,
): Promise<AuthenticationResponse> {
  return shopmateRequest<AuthenticationResponse>(
    "/api/auth/register",
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function loginToShopMate(
  input: LoginInput,
): Promise<AuthenticationResponse> {
  return shopmateRequest<AuthenticationResponse>(
    "/api/auth/login",
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function loadShopMateSession(
  token: string,
): Promise<SessionResponse> {
  return shopmateRequest<SessionResponse>(
    "/api/session",
    {
      method: "GET",
    },
    token,
  );
}

export function logoutFromShopMate(
  token: string,
): Promise<LogoutResponse> {
  return shopmateRequest<LogoutResponse>(
    "/api/auth/logout",
    {
      method: "POST",
    },
    token,
  );
}

export function createShopMateChat(
  token: string,
): Promise<WorkspaceResponse> {
  return shopmateRequest<WorkspaceResponse>(
    "/api/chats/create",
    {
      method: "POST",
    },
    token,
  );
}

export function selectShopMateChat(
  token: string,
  chatId: number,
): Promise<WorkspaceResponse> {
  return shopmateRequest<WorkspaceResponse>(
    "/api/chats/select",
    {
      method: "POST",
      body: JSON.stringify({
        chat_id: chatId,
      }),
    },
    token,
  );
}

export function renameShopMateChat(
  token: string,
  chatId: number,
  newTitle: string,
): Promise<WorkspaceResponse> {
  return shopmateRequest<WorkspaceResponse>(
    "/api/chats/rename",
    {
      method: "POST",
      body: JSON.stringify({
        chat_id: chatId,
        new_title: newTitle,
      }),
    },
    token,
  );
}

export function deleteShopMateChat(
  token: string,
  chatId: number,
): Promise<WorkspaceResponse> {
  return shopmateRequest<WorkspaceResponse>(
    "/api/chats/delete",
    {
      method: "POST",
      body: JSON.stringify({
        chat_id: chatId,
      }),
    },
    token,
  );
}

export function searchShopMateChats(
  token: string,
  query: string,
  currentChatId?: number | null,
): Promise<WorkspaceResponse> {
  const searchParameters = new URLSearchParams();

  searchParameters.set("query", query);

  if (currentChatId !== null && currentChatId !== undefined) {
    searchParameters.set(
      "current_chat_id",
      String(currentChatId),
    );
  }

  return shopmateRequest<WorkspaceResponse>(
    `/api/chats/search?${searchParameters.toString()}`,
    {
      method: "GET",
    },
    token,
  );
}

export function sendShopMateMessage(
  token: string,
  input: MessageInput,
): Promise<WorkspaceResponse> {
  return shopmateRequest<WorkspaceResponse>(
    "/api/messages",
    {
      method: "POST",
      body: JSON.stringify({
        chat_id: input.chat_id,
        message_text: input.message_text,
        top_n: input.top_n ?? 10,
      }),
    },
    token,
  );
}
