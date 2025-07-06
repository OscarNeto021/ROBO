#!/usr/bin/env python3
"""Treinamento de modelos de ML a partir de ticks (streaming).

Este script carrega dados de ticks em chunks e realiza amostragem
reservoir ou carrega todos os dados, gera features simples e treina
modelos clássicos de machine learning.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Iterator, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


def parse_args() -> argparse.Namespace:
    """Lê argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description="Treina modelos de ML com ticks")
    parser.add_argument("--symbol", required=True, help="Símbolo do ativo")
    parser.add_argument("--days", type=int, default=30, help="Número de dias")
    parser.add_argument(
        "--max-samples",
        type=int,
        default=100_000,
        help="Máximo de amostras (0 para todas)",
    )
    parser.add_argument(
        "--tmp-dir",
        default="tmp",
        help="Diretório temporário para dados de ticks",
    )
    parser.add_argument("--verbose", action="store_true", help="Modo verboso")
    return parser.parse_args()


def _load_prices(
    symbol: str,
    tmp_dir: str,
    days: int,
) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
    """Carrega ticks em chunks de 1 milhão."""

    path = Path(tmp_dir) / f"{symbol}_ticks.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    start_ts = None
    if days > 0:
        end_ts = pd.Timestamp.utcnow().timestamp()
        start_ts = end_ts - days * 86_400

    columns = ["timestamp", "price"]
    for chunk in pd.read_parquet(path, columns=columns, chunksize=1_000_000):
        if start_ts is not None:
            chunk = chunk[chunk["timestamp"] >= start_ts]
        yield chunk["price"].to_numpy(dtype=np.float32), chunk["timestamp"].to_numpy(
            dtype=np.float64
        )


def _generate_chunk_features(
    prices: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Gera features e labels para um vetor de preços."""
    if prices.size < 12:
        return (
            np.array([], dtype=np.float32),
            np.array([], dtype=np.float32),
            np.array([], dtype=np.float32),
            np.array([], dtype=np.int8),
        )

    ret1 = prices[10:-1] - prices[9:-2]
    ret5 = prices[10:-1] - prices[5:-6]
    ret10 = prices[10:-1] - prices[:-11]
    labels = (prices[11:] > prices[10:-1]).astype(np.int8)
    return ret1, ret5, ret10, labels


def _reservoir_sampling(
    reservoir: List[Tuple[float, float, float, float]],
    new_rows: Iterator[Tuple[float, float, float, float]],
    max_samples: int,
    start_index: int,
) -> int:
    """Atualiza o reservoir com Algorithm R."""
    n = start_index
    for row in new_rows:
        n += 1
        if len(reservoir) < max_samples:
            reservoir.append(row)
        else:
            j = np.random.randint(0, n)
            if j < max_samples:
                reservoir[j] = row
    return n


def main() -> None:
    args = parse_args()
    start = time.time()
    tmp_dir = Path(args.tmp_dir)

    reservoir: List[Tuple[float, float, float, int]] = []
    frames: List[pd.DataFrame] = []
    count = 0
    prev_prices = np.array([], dtype=np.float32)

    for prices, ticks in _load_prices(args.symbol, args.tmp_dir, args.days):
        if prev_prices.size:
            prices = np.concatenate([prev_prices, prices])
        ret1, ret5, ret10, labels = _generate_chunk_features(prices)
        if labels.size == 0:
            prev_prices = prices[-11:]
            continue
        ticks_feat = ticks[10:-1]
        data = zip(ticks_feat, ret1, ret5, ret10, labels)
        if args.max_samples > 0:
            count = _reservoir_sampling(reservoir, data, args.max_samples, count)
        else:
            df = pd.DataFrame(
                {
                    "tick": ticks_feat,
                    "ret1": ret1,
                    "ret5": ret5,
                    "ret10": ret10,
                    "target": labels,
                }
            )
            frames.append(df)
        prev_prices = prices[-11:]
        if args.verbose:
            print(f"🔄 Chunk processado, linhas coletadas: {count}")

    if args.max_samples > 0:
        full_df = pd.DataFrame(
            reservoir, columns=["tick", "ret1", "ret5", "ret10", "target"]
        )
    else:
        full_df = pd.concat(frames, ignore_index=True)

    full_df.dropna(axis=1, how="all", inplace=True)

    features = full_df[["ret1", "ret5", "ret10"]]
    target = full_df["target"]

    print(f"📊  Dataset final: {len(full_df)} linhas, {features.shape[1]} features")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    auc = cross_val_score(
        GradientBoostingClassifier(random_state=42),
        X_scaled,
        target,
        cv=cv,
        scoring="roc_auc",
    ).mean()
    print(f"🔁 CV AUC {auc:.4f}")

    X_train, X_val, y_train, y_val = train_test_split(
        X_scaled, target, test_size=0.2, random_state=42, stratify=target
    )

    print("🧠 Treinando ...")

    rf_model = RandomForestClassifier(n_estimators=300, random_state=42)
    rf_model.fit(X_train, y_train)
    print("✔️ RF ...")

    gbm_model = GradientBoostingClassifier(random_state=42)
    gbm_model.fit(X_train, y_train)
    print("✔️ GBM ...")

    lr_model = LogisticRegression(max_iter=1000)
    lr_model.fit(X_train, y_train)
    print("✔️ LR ...")

    xgb_model = XGBClassifier(
        n_estimators=300,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        random_state=42,
    )
    try:
        from xgboost import callback

        xgb_model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[callback.EarlyStopping(rounds=50, save_best=True)],
            verbose=False,
        )
    except (TypeError, ImportError):
        print("⚠️  XGB sem callback EarlyStopping → treinando sem ES")
        xgb_model.fit(X_train, y_train)
    print("✔️ XGB ...")

    model_id = uuid.uuid4().hex[:8]
    model_path = tmp_dir / f"model_{model_id}.pkl"
    joblib.dump(
        {
            "scaler": scaler,
            "rf": rf_model,
            "gbm": gbm_model,
            "lr": lr_model,
            "xgb": xgb_model,
        },
        model_path,
    )

    elapsed = time.time() - start
    print(
        f"✅ Modelo salvo: {model_id}  |  🧠  Treino concluído em {time.strftime('%H:%M:%S', time.gmtime(elapsed))}"
    )

    shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrompido pelo usuário", file=sys.stderr)
        sys.exit(1)
