"""Regression Explorer API - CSV ingestion and leak-resistant cross-validated model comparison."""
from __future__ import annotations

import io
import ipaddress
import itertools
import json
import math
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import BayesianRidge, ElasticNet, Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

MAX_BYTES = 3 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLS = 80
MAX_FEATURES = 12
MAX_SUBSETS = 400
DEFAULT_URL = 'https://raw.githubusercontent.com/Avik-Jain/100-Days-Of-ML-Code/master/datasets/50_Startups.csv'

app = FastAPI(title='Regression Explorer API', version='1.0.0')
origins = [s.strip() for s in os.getenv('ALLOWED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000').split(',') if s.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET','POST'], allow_headers=['*'])

class UrlRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2048)

class TrainRequest(BaseModel):
    dataset_id: str = 'ignored'  # Browser resends CSV; no server-side dataset storage
    csv_text: str
    target: str
    features: list[str]
    test_size: float = Field(default=0.2, ge=0.1, le=0.4)
    max_features: int = Field(default=5, ge=1, le=5)
    random_state: int = Field(default=42, ge=0, le=1_000_000)


def parse_csv(blob: bytes | str) -> pd.DataFrame:
    if isinstance(blob, str):
        blob = blob.encode('utf-8')
    if len(blob) > MAX_BYTES:
        raise HTTPException(413, 'CSV exceeds 3 MB limit')
    try:
        df = pd.read_csv(io.BytesIO(blob), encoding='utf-8-sig')
    except Exception as exc:
        raise HTTPException(422, f'Unable to read CSV: {exc}') from exc
    if not 12 <= len(df) <= MAX_ROWS:
        raise HTTPException(422, f'Dataset must contain 12-{MAX_ROWS} rows')
    if df.shape[1] < 2 or df.shape[1] > MAX_COLS:
        raise HTTPException(422, 'Dataset must contain 2-80 columns')
    if not df.columns.is_unique:
        raise HTTPException(422, 'Duplicate column names are not supported')
    return df


def metadata(df):
    return {'rows': len(df), 'columns': list(df.columns),
            'preview': json.loads(df.head(8).to_json(orient='records')),
            'numeric_columns': [c for c in df if pd.api.types.is_numeric_dtype(df[c])],
            'missing': {k: int(v) for k, v in df.isna().sum().items()}}


def validate_public_url(url: str):
    p = urlparse(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise HTTPException(400, 'Use a public HTTPS URL without custom port or credentials')
    host = p.hostname
    if host.lower() in {'localhost'} or host.lower().endswith(('.local', '.internal')):
        raise HTTPException(400, 'Local/internal hosts are not allowed')
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses:
            raise ValueError('No IPs')
        for addr in addresses:
            ip = ipaddress.ip_address(addr[4][0])
            if not ip.is_global:
                raise ValueError('Non-public IP address')
    except (OSError, ValueError) as exc:
        raise HTTPException(400, f'Invalid or non-public host: {exc}') from exc


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.post('/api/dataset/url')
def csv_from_url(req: UrlRequest):
    validate_public_url(req.url)
    try:
        # Redirects off; trust_env=False avoids environment proxies.
        with httpx.Client(follow_redirects=False, timeout=12, trust_env=False) as client:
            with client.stream('GET', req.url) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise HTTPException(413, 'CSV exceeds 3 MB limit')
    except httpx.HTTPError as exc:
        raise HTTPException(400, f'Failed to fetch URL: {exc}') from exc
    df = parse_csv(bytes(data))
    return {'csv_text': bytes(data).decode('utf-8-sig'), **metadata(df)}


@app.post('/api/dataset/upload')
async def csv_upload(file: UploadFile = File(...)):
    try:
        data = await file.read(MAX_BYTES + 1)
        df = parse_csv(data)
        return {'csv_text': data.decode('utf-8-sig'), **metadata(df)}
    except UnicodeDecodeError as exc:
        raise HTTPException(422, 'Only UTF-8 CSV files are supported') from exc
    finally:
        await file.close()


def make_preprocessor(numeric, categorical):
    transformers = []
    if numeric:
        transformers.append(('numeric', Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scale', StandardScaler()),
        ]), numeric))
    if categorical:
        transformers.append(('category', Pipeline([
            ('imputer', SimpleImputer(strategy='most_frequent')),
            ('ohe', OneHotEncoder(handle_unknown='ignore', drop='first')),
        ]), categorical))
    return ColumnTransformer(transformers, sparse_threshold=0)


MODEL_GRIDS = {
    'LinearRegression': [(LinearRegression, {})],
    'Ridge': [(Ridge, {'alpha': a}) for a in (0.01, 0.1, 1.0, 10.0, 100.0)],
    'Lasso': [(Lasso, {'alpha': a, 'max_iter': 10000}) for a in (0.1, 1.0, 10.0, 100.0, 1000.0)],
    'ElasticNet': [(ElasticNet, {'alpha': a, 'l1_ratio': ratio, 'max_iter': 10000}) for a in (0.01, 0.1, 1.0) for ratio in (0.2, 0.5, 0.8)],
    'BayesianRidge': [(BayesianRidge, {'tol': t}) for t in (1e-3, 1e-5)],
}


@app.post('/api/train')
def train(req: TrainRequest):
    df = parse_csv(req.csv_text)
    if req.target not in df or not req.features or len(set(req.features)) != len(req.features):
        raise HTTPException(422, 'Choose a valid target and unique input features')
    if req.target in req.features or any(f not in df for f in req.features):
        raise HTTPException(422, 'Invalid input features')
    if len(req.features) > MAX_FEATURES:
        raise HTTPException(422, f'Select at most {MAX_FEATURES} features')
    subset_count = sum(math.comb(len(req.features), k) for k in range(1, min(req.max_features, len(req.features)) + 1))
    if subset_count > MAX_SUBSETS:
        raise HTTPException(422, f'Too many subsets ({subset_count}); reduce feature count or max features (limit {MAX_SUBSETS})')

    y = pd.to_numeric(df[req.target], errors='coerce')
    valid = y.notna()
    if valid.sum() < 12:
        raise HTTPException(422, 'Target must be numeric with at least 12 valid values')
    X = df.loc[valid, req.features].copy()
    y = y.loc[valid]
    # only numerical or moderate-cardinality categorical columns
    numeric = [c for c in req.features if pd.api.types.is_numeric_dtype(X[c])]
    categorical = [c for c in req.features if c not in numeric]
    for c in categorical:
        distinct = X[c].nunique(dropna=True)
        if distinct > 25 or distinct == 0:
            raise HTTPException(422, f'{c}: categorical column needs 1-25 nonempty categories')
    for c in numeric:
        if X[c].notna().sum() == 0:
            raise HTTPException(422, f'{c}: all numeric values are missing')
    for c in categorical:
        X[c] = X[c].fillna('__MISSING__').astype(str)

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=req.test_size, random_state=req.random_state)
    folds = min(5, max(2, len(Xtr) // 6))
    cv = KFold(n_splits=folds, shuffle=True, random_state=req.random_state)
    all_rows = []
    best_rows = []
    predictions = []
    for method, grid in MODEL_GRIDS.items():
        for k in range(1, min(req.max_features, len(req.features)) + 1):
            candidates = []
            for subset in itertools.combinations(req.features, k):
                subset = list(subset)
                num = [c for c in subset if c in numeric]
                cat = [c for c in subset if c in categorical]
                best = None
                for estimator_cls, params in grid:
                    pipe = Pipeline([
                        ('preprocess', make_preprocessor(num, cat)),
                        ('regressor', estimator_cls(**params))
                    ])
                    try:
                        scores = cross_val_score(pipe, Xtr[subset], ytr, cv=cv,
                                                 scoring='neg_root_mean_squared_error', error_score='raise')
                        cv_rmse = float(-scores.mean())
                    except (ValueError, TypeError) as exc:
                        raise HTTPException(422, f'Modeling failed for {subset}: {exc}') from exc
                    if best is None or cv_rmse < best['cv_rmse']:
                        best = {'model': pipe, 'params': params, 'cv_rmse': cv_rmse}
                best['model'].fit(Xtr[subset], ytr)
                preds = best['model'].predict(Xte[subset])
                row = {'method': method, 'number_of_features': k, 'features': subset,
                       'parameters': {p: v for p, v in best['params'].items() if p != 'max_iter'},
                       'cv_rmse': round(best['cv_rmse'], 4),
                       'rmse': round(float(np.sqrt(mean_squared_error(yte, preds))), 4),
                       'r2': round(float(r2_score(yte, preds)), 6),
                       'mae': round(float(mean_absolute_error(yte, preds)), 4)}
                candidates.append((row, best['model'], preds))
                all_rows.append(row)
            # Important: select with train CV only. Held-out metrics never used to select features.
            chosen, fitted, chosen_preds = min(candidates, key=lambda item: item[0]['cv_rmse'])
            best_rows.append(chosen)
            for idx, actual, predicted in zip(Xte.index, yte.to_numpy(), chosen_preds):
                predictions.append({'method': method, 'number_of_features': k, 'row_index': int(idx),
                                    'actual': round(float(actual), 5), 'predicted': round(float(predicted), 5),
                                    'residual': round(float(actual - predicted), 5)})
    overall = min(best_rows, key=lambda r: r['cv_rmse'])
    return {'dataset': {'rows': len(X), 'train_rows': len(Xtr), 'test_rows': len(Xte), 'target': req.target,
                        'features': req.features, 'cv_folds': folds, 'total_subsets': subset_count,
                        'total_experiments': len(all_rows)},
            'best_per_count': best_rows, 'all_subsets': all_rows, 'predictions': predictions,
            'best_overall': overall}
