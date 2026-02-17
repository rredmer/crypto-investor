import { api } from "./client";
import type {
  DataSourceConfig,
  DataSourceConfigCreate,
  ExchangeConfig,
  ExchangeConfigCreate,
  ExchangeTestResult,
} from "../types";

export const exchangeConfigsApi = {
  list: () => api.get<ExchangeConfig[]>("/exchange-configs/"),
  get: (id: number) => api.get<ExchangeConfig>(`/exchange-configs/${id}/`),
  create: (data: ExchangeConfigCreate) =>
    api.post<ExchangeConfig>("/exchange-configs/", data),
  update: (id: number, data: Partial<ExchangeConfigCreate>) =>
    api.put<ExchangeConfig>(`/exchange-configs/${id}/`, data),
  delete: (id: number) => api.delete<void>(`/exchange-configs/${id}/`),
  test: (id: number) =>
    api.post<ExchangeTestResult>(`/exchange-configs/${id}/test/`),
};

export const dataSourcesApi = {
  list: () => api.get<DataSourceConfig[]>("/data-sources/"),
  get: (id: number) => api.get<DataSourceConfig>(`/data-sources/${id}/`),
  create: (data: DataSourceConfigCreate) =>
    api.post<DataSourceConfig>("/data-sources/", data),
  update: (id: number, data: Partial<DataSourceConfigCreate>) =>
    api.put<DataSourceConfig>(`/data-sources/${id}/`, data),
  delete: (id: number) => api.delete<void>(`/data-sources/${id}/`),
};
