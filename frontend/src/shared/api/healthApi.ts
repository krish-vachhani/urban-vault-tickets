import { apiClient } from "./axiosClient";

export type ApiHealth = {
  status: "ok" | "unavailable";
  database: "ok" | "unreachable";
};

export const healthQueryKey = ["health"] as const;

export async function getApiHealth(): Promise<ApiHealth> {
  const response = await apiClient.get<ApiHealth>("/health/");
  return response.data;
}
