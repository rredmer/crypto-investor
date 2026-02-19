import { api } from "./client";

export interface MLModel {
  model_id: string;
  symbol: string;
  timeframe: string;
  exchange: string;
  created_at: string;
  metrics?: Record<string, number>;
  feature_importance?: Record<string, number>;
}

export interface MLPrediction {
  model_id: string;
  symbol: string;
  predictions: Array<{
    timestamp: string;
    prediction: number;
    probability?: number;
  }>;
}

export const mlApi = {
  train: (data: { symbol?: string; timeframe?: string; exchange?: string; test_ratio?: number }) =>
    api.post<{ job_id: string; status: string }>("/ml/train/", data),
  listModels: () => api.get<MLModel[]>("/ml/models/"),
  getModel: (modelId: string) => api.get<MLModel>(`/ml/models/${modelId}/`),
  predict: (data: { model_id: string; symbol?: string; timeframe?: string; exchange?: string; bars?: number }) =>
    api.post<MLPrediction>("/ml/predict/", data),
};
