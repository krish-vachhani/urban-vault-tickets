/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base path for API calls, e.g. "/api/v1" (served through the same origin). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
