import { AlertCircle, Copy } from "lucide-react";

import { ApiError } from "../api/client";

interface ApiErrorNoticeProps {
  error: unknown;
  onRetry?: () => void;
}

export function ApiErrorNotice({ error, onRetry }: ApiErrorNoticeProps) {
  const apiError = error instanceof ApiError ? error : undefined;
  const message = error instanceof Error ? error.message : "Не удалось выполнить запрос";

  return (
    <div className="error-notice" role="alert">
      <AlertCircle aria-hidden="true" />
      <div>
        <strong>{message}</strong>
        {apiError?.requestId && (
          <button
            className="request-id"
            type="button"
            onClick={() => navigator.clipboard.writeText(apiError.requestId ?? "")}
            title="Скопировать идентификатор запроса"
          >
            Запрос: {apiError.requestId} <Copy size={14} aria-hidden="true" />
          </button>
        )}
      </div>
      {onRetry && <button className="button button--secondary" type="button" onClick={onRetry}>Повторить</button>}
    </div>
  );
}
