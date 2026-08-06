"""误差评估指标：MAE / RMSE / MAPE / R²。

用法：
    from eval_metrics import metrics_report
    rep = metrics_report(y_true, y_pred)   # → dict + 打印
"""
from __future__ import annotations

import numpy as np


def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(yhat))))


def rmse(y, yhat):
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(yhat)) ** 2)))


def mape(y, yhat, eps=1e-9):
    y, yhat = np.asarray(y), np.asarray(yhat)
    return float(np.mean(np.abs((y - yhat) / (np.abs(y) + eps))) * 100)


def r2(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return float(1 - ss_res / (ss_tot + 1e-12))


def metrics_report(y, yhat, name="模型"):
    rep = {"mae": mae(y, yhat), "rmse": rmse(y, yhat), "mape": mape(y, yhat), "r2": r2(y, yhat)}
    print(f"[{name}] MAE={rep['mae']:.4f} RMSE={rep['rmse']:.4f} "
          f"MAPE={rep['mape']:.2f}% R²={rep['r2']:.4f}")
    return rep
