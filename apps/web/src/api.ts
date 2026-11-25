type ValidationIssue = {
  instancePath?: string;
  keyword?: string;
  message?: string;
  params?: { type?: string; missingProperty?: string; additionalProperty?: string };
  loc?: (string | number)[];
  msg?: string;
};

function validationMessage(details: unknown): string | undefined {
  const list = Array.isArray(details) ? details : (details as { detail?: unknown } | null)?.detail;
  if (!Array.isArray(list)) return;
  const issue = (list as ValidationIssue[]).find(
    (item) =>
      (item?.message || item?.msg) &&
      item.keyword !== 'anyOf' &&
      !(item.keyword === 'type' && item.params?.type === 'null'),
  );
  if (!issue) return;

  const path =
    issue.loc?.filter((part) => part !== 'body').join('.') ??
    issue.instancePath?.split('/').slice(1).join('.');
  const property = issue.params?.missingProperty ?? issue.params?.additionalProperty;
  const field = [path, property].filter(Boolean).join('.');
  if (issue.keyword === 'required') return `${field} is required.`;
  if (issue.keyword === 'additionalProperties') return `${field} is not supported.`;
  const message = issue.message ?? issue.msg;
  return field ? `${field}: ${message}` : message;
}

export async function api<T = any>(path: string, body?: unknown, method?: string): Promise<T> {
  const response = await fetch('/api' + path, {
    method: method || (body === undefined ? 'GET' : 'POST'),
    headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = response.status === 422 ? validationMessage(data.details) : undefined;
    throw new Error(detail ?? (data.error || 'Request failed'));
  }
  return data;
}
