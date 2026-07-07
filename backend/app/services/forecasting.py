import os
import datetime
import joblib
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from typing import List, Tuple, Dict, Any

from app.models import Centre, Drug, StockLog, FootfallLog, BedStatus, StaffAttendance

# Define paths for saving models
MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "models"))
os.makedirs(MODELS_DIR, exist_ok=True)

FOOTFALL_MODEL_PATH = os.path.join(MODELS_DIR, "footfall_model.joblib")
CONSUMPTION_MODEL_PATH = os.path.join(MODELS_DIR, "consumption_model.joblib")
BED_MODEL_PATH = os.path.join(MODELS_DIR, "bed_model.joblib")
METADATA_PATH = os.path.join(MODELS_DIR, "metadata.joblib")

# Category Mappings
TIER_MAP = {"rural": 0, "urban": 1, "tribal": 2}
TYPE_MAP = {"PHC": 0, "CHC": 1}

def get_centre_features(centre: Centre) -> Dict[str, Any]:
    return {
        "population_served": centre.population_served,
        "centre_type_code": TYPE_MAP.get(centre.type, 0),
        "tier_code": TIER_MAP.get(centre.tier_classification, 0)
    }

def _add_lag_features(df: pd.DataFrame, value_col: str, group_col: str) -> pd.DataFrame:
    """Add lag-1, lag-7, rolling mean/std features for time-series accuracy improvement."""
    df = df.sort_values([group_col, "date_ordinal"]).copy()
    grouped = df.groupby(group_col)[value_col]
    df["lag_1"] = grouped.shift(1).fillna(df[value_col].median())
    df["lag_7"] = grouped.shift(7).fillna(df[value_col].median())
    df["rolling_mean_7"] = grouped.transform(lambda x: x.rolling(7, min_periods=1).mean())
    df["rolling_std_7"] = grouped.transform(lambda x: x.rolling(7, min_periods=1).std().fillna(0))
    return df

def retrain_models(db: Session) -> Dict[str, Any]:
    """
    Trains pooled models across all centres for footfall, stock consumption, and bed demand.
    Uses enhanced features (lags, rolling stats, month, weekend) and tuned hyperparameters
    for improved accuracy. Reports cross-validated RMSE alongside train RMSE.
    """
    print("Fetching logs for retraining (enhanced model v2)...")
    
    # 1. Fetch Centres to map their properties
    centres = db.query(Centre).all()
    centre_map = {c.id: get_centre_features(c) for c in centres}

    # ----------------------------------------------------
    # Model A: Footfall Forecasting (Enhanced)
    # ----------------------------------------------------
    footfall_logs = db.query(FootfallLog).all()
    if not footfall_logs:
        raise ValueError("Cannot train footfall model: No footfall logs in database.")

    ff_data = []
    for log in footfall_logs:
        c_feats = centre_map.get(log.centre_id, {"population_served": 10000, "centre_type_code": 0, "tier_code": 0})
        dt = log.timestamp
        is_monsoon = 6 <= dt.month <= 8
        ff_data.append({
            "centre_id": log.centre_id,
            "population_served": c_feats["population_served"],
            "centre_type_code": c_feats["centre_type_code"],
            "tier_code": c_feats["tier_code"],
            "day_of_week": dt.weekday(),
            "day_of_year": dt.timetuple().tm_yday,
            "month": dt.month,
            "is_weekend": 1 if dt.weekday() >= 5 else 0,
            "is_monsoon": 1 if is_monsoon else 0,
            "date_ordinal": dt.toordinal(),
            "count": log.count
        })

    df_ff = pd.DataFrame(ff_data)
    df_ff = _add_lag_features(df_ff, "count", "centre_id")

    FF_FEATURES = ["population_served", "centre_type_code", "tier_code", "day_of_week",
                   "day_of_year", "month", "is_weekend", "is_monsoon",
                   "lag_1", "lag_7", "rolling_mean_7", "rolling_std_7"]
    X_ff = df_ff[FF_FEATURES]
    y_ff = df_ff["count"]

    ff_model = GradientBoostingRegressor(
        n_estimators=200, learning_rate=0.08, max_depth=5,
        subsample=0.8, min_samples_leaf=5, random_state=42
    )
    ff_model.fit(X_ff, y_ff)
    ff_train_rmse = float(np.sqrt(np.mean((ff_model.predict(X_ff) - y_ff) ** 2)))
    # Cross-validated RMSE (honest out-of-sample accuracy)
    ff_cv_scores = cross_val_score(ff_model, X_ff, y_ff, cv=5, scoring="neg_root_mean_squared_error")
    ff_cv_rmse = float(-ff_cv_scores.mean())
    print(f"Footfall Model trained. Train RMSE: {ff_train_rmse:.2f}, CV RMSE: {ff_cv_rmse:.2f}")

    # ----------------------------------------------------
    # Model B: Drug Consumption Forecasting (Enhanced)
    # ----------------------------------------------------
    stock_logs = db.query(StockLog).filter(StockLog.quantity_change < 0).all()
    if not stock_logs:
        raise ValueError("Cannot train consumption model: No stock consumption logs in database.")

    ff_daily = db.query(
        FootfallLog.centre_id,
        func.strftime("%Y-%m-%d", FootfallLog.timestamp).label("date"),
        func.sum(FootfallLog.count).label("count")
    ).group_by(FootfallLog.centre_id, "date").all()
    ff_daily_map = {(item.centre_id, item.date): item.count for item in ff_daily}

    cons_data = []
    for log in stock_logs:
        c_feats = centre_map.get(log.centre_id, {"population_served": 10000, "centre_type_code": 0, "tier_code": 0})
        dt = log.timestamp
        date_str = dt.strftime("%Y-%m-%d")
        
        footfall_on_day = ff_daily_map.get((log.centre_id, date_str), 0)
        if footfall_on_day == 0:
            footfall_on_day = 80 if c_feats["centre_type_code"] == 1 else 25

        is_monsoon = 6 <= dt.month <= 8
        cons_data.append({
            "centre_id": log.centre_id,
            "population_served": c_feats["population_served"],
            "centre_type_code": c_feats["centre_type_code"],
            "tier_code": c_feats["tier_code"],
            "drug_id": log.drug_id,
            "day_of_week": dt.weekday(),
            "month": dt.month,
            "is_weekend": 1 if dt.weekday() >= 5 else 0,
            "is_monsoon": 1 if is_monsoon else 0,
            "footfall": footfall_on_day,
            "date_ordinal": dt.toordinal(),
            "consumption": abs(log.quantity_change)
        })

    df_cons = pd.DataFrame(cons_data)
    df_cons = _add_lag_features(df_cons, "consumption", "centre_id")

    CONS_FEATURES = ["population_served", "centre_type_code", "tier_code", "drug_id",
                     "day_of_week", "month", "is_weekend", "is_monsoon", "footfall",
                     "lag_1", "lag_7", "rolling_mean_7", "rolling_std_7"]
    X_cons = df_cons[CONS_FEATURES]
    y_cons = df_cons["consumption"]

    cons_model = GradientBoostingRegressor(
        n_estimators=200, learning_rate=0.08, max_depth=5,
        subsample=0.8, min_samples_leaf=5, random_state=42
    )
    cons_model.fit(X_cons, y_cons)
    cons_train_rmse = float(np.sqrt(np.mean((cons_model.predict(X_cons) - y_cons) ** 2)))
    cons_cv_scores = cross_val_score(cons_model, X_cons, y_cons, cv=5, scoring="neg_root_mean_squared_error")
    cons_cv_rmse = float(-cons_cv_scores.mean())
    print(f"Consumption Model trained. Train RMSE: {cons_train_rmse:.2f}, CV RMSE: {cons_cv_rmse:.2f}")

    # ----------------------------------------------------
    # Model C: Bed Occupancy Forecasting (Enhanced)
    # ----------------------------------------------------
    bed_logs = db.query(BedStatus).all()
    if not bed_logs:
        raise ValueError("Cannot train bed model: No bed status logs in database.")

    bed_data = []
    for log in bed_logs:
        c_feats = centre_map.get(log.centre_id, {"population_served": 10000, "centre_type_code": 0, "tier_code": 0})
        dt = log.timestamp
        date_str = dt.strftime("%Y-%m-%d")
        
        footfall_on_day = ff_daily_map.get((log.centre_id, date_str), 0)
        if footfall_on_day == 0:
            footfall_on_day = 80 if c_feats["centre_type_code"] == 1 else 25

        bed_data.append({
            "centre_id": log.centre_id,
            "centre_type_code": c_feats["centre_type_code"],
            "population_served": c_feats["population_served"],
            "total_beds": log.total_beds,
            "footfall": footfall_on_day,
            "day_of_week": dt.weekday(),
            "month": dt.month,
            "is_weekend": 1 if dt.weekday() >= 5 else 0,
            "date_ordinal": dt.toordinal(),
            "occupied_beds": log.occupied_beds
        })

    df_bed = pd.DataFrame(bed_data)
    df_bed = _add_lag_features(df_bed, "occupied_beds", "centre_id")

    BED_FEATURES = ["centre_type_code", "population_served", "total_beds", "footfall",
                    "day_of_week", "month", "is_weekend",
                    "lag_1", "lag_7", "rolling_mean_7", "rolling_std_7"]
    X_bed = df_bed[BED_FEATURES]
    y_bed = df_bed["occupied_beds"]

    bed_model = GradientBoostingRegressor(
        n_estimators=200, learning_rate=0.08, max_depth=4,
        subsample=0.8, min_samples_leaf=5, random_state=42
    )
    bed_model.fit(X_bed, y_bed)
    bed_train_rmse = float(np.sqrt(np.mean((bed_model.predict(X_bed) - y_bed) ** 2)))
    bed_cv_scores = cross_val_score(bed_model, X_bed, y_bed, cv=5, scoring="neg_root_mean_squared_error")
    bed_cv_rmse = float(-bed_cv_scores.mean())
    print(f"Bed Occupancy Model trained. Train RMSE: {bed_train_rmse:.2f}, CV RMSE: {bed_cv_rmse:.2f}")

    # Save models to disk
    joblib.dump(ff_model, FOOTFALL_MODEL_PATH)
    joblib.dump(cons_model, CONSUMPTION_MODEL_PATH)
    joblib.dump(bed_model, BED_MODEL_PATH)

    metadata = {
        "last_trained": datetime.datetime.utcnow().isoformat(),
        "footfall_model_train_rmse": ff_train_rmse,
        "footfall_model_cv_rmse": ff_cv_rmse,
        "consumption_model_train_rmse": cons_train_rmse,
        "consumption_model_cv_rmse": cons_cv_rmse,
        "bed_model_train_rmse": bed_train_rmse,
        "bed_model_cv_rmse": bed_cv_rmse,
        # Keep backward-compatible keys
        "footfall_model_rmse": ff_cv_rmse,
        "consumption_model_rmse": cons_cv_rmse,
        "bed_model_rmse": bed_cv_rmse,
    }
    joblib.dump(metadata, METADATA_PATH)
    print("All enhanced models (v2) saved to models/ directory.")
    return metadata

# ----------------------------------------------------
# Inference & Rollout Simulation
# ----------------------------------------------------

def load_models():
    """Helper to check and load joblib models."""
    if not (os.path.exists(FOOTFALL_MODEL_PATH) and os.path.exists(CONSUMPTION_MODEL_PATH) and os.path.exists(BED_MODEL_PATH)):
        return None, None, None, None
    try:
        ff = joblib.load(FOOTFALL_MODEL_PATH)
        cons = joblib.load(CONSUMPTION_MODEL_PATH)
        bed = joblib.load(BED_MODEL_PATH)
        meta = joblib.load(METADATA_PATH)
        return ff, cons, bed, meta
    except:
        return None, None, None, None

def _get_recent_values(db: Session, centre_id: int, model_type: str, n: int = 7) -> List[float]:
    """Fetch the most recent n values for lag/rolling features at inference time."""
    if model_type == "footfall":
        rows = db.query(FootfallLog.count).filter_by(centre_id=centre_id)\
            .order_by(FootfallLog.timestamp.desc()).limit(n).all()
        return [float(r.count) for r in reversed(rows)]
    elif model_type == "beds":
        rows = db.query(BedStatus.occupied_beds).filter_by(centre_id=centre_id)\
            .order_by(BedStatus.timestamp.desc()).limit(n).all()
        return [float(r.occupied_beds) for r in reversed(rows)]
    elif model_type == "consumption":
        rows = db.query(StockLog.quantity_change).filter_by(centre_id=centre_id)\
            .filter(StockLog.quantity_change < 0)\
            .order_by(StockLog.timestamp.desc()).limit(n).all()
        return [abs(float(r.quantity_change)) for r in reversed(rows)]
    return []

def forecast_footfall_next_7_days(centre_id: int, db: Session) -> List[float]:
    ff_model, _, _, _ = load_models()
    centre = db.query(Centre).filter_by(id=centre_id).first()
    
    if not centre:
        return [0.0] * 7

    # If models are not trained yet, return a simple baseline
    if ff_model is None:
        base = 80.0 if centre.type == "CHC" else 25.0
        return [float(round(base + np.sin(i)*5)) for i in range(7)]

    c_feats = get_centre_features(centre)
    now = datetime.datetime.utcnow()

    # Get recent footfall history for lag features
    recent = _get_recent_values(db, centre_id, "footfall", 7)
    if not recent:
        recent = [25.0 if centre.type == "PHC" else 80.0] * 7

    predictions = []
    running_history = list(recent)  # will extend as we predict

    for i in range(7):
        target_date = now + datetime.timedelta(days=i)
        is_monsoon = 6 <= target_date.month <= 8

        lag_1 = running_history[-1] if len(running_history) >= 1 else np.median(recent)
        lag_7 = running_history[-7] if len(running_history) >= 7 else np.median(recent)
        window = running_history[-7:] if len(running_history) >= 7 else running_history
        rolling_mean = float(np.mean(window))
        rolling_std = float(np.std(window)) if len(window) > 1 else 0.0

        features = pd.DataFrame([{
            "population_served": c_feats["population_served"],
            "centre_type_code": c_feats["centre_type_code"],
            "tier_code": c_feats["tier_code"],
            "day_of_week": target_date.weekday(),
            "day_of_year": target_date.timetuple().tm_yday,
            "month": target_date.month,
            "is_weekend": 1 if target_date.weekday() >= 5 else 0,
            "is_monsoon": 1 if is_monsoon else 0,
            "lag_1": lag_1,
            "lag_7": lag_7,
            "rolling_mean_7": rolling_mean,
            "rolling_std_7": rolling_std,
        }])
        
        pred = ff_model.predict(features)[0]
        # Sundays are emergency-only, so scale down to 10%
        if target_date.weekday() == 6:
            pred = pred * 0.1
        pred = float(round(max(0.0, pred), 1))
        predictions.append(pred)
        running_history.append(pred)

    return predictions

def forecast_beds_next_7_days(centre_id: int, predicted_footfall: List[float], db: Session) -> List[float]:
    _, _, bed_model, _ = load_models()
    centre = db.query(Centre).filter_by(id=centre_id).first()
    if not centre:
        return [0.0] * 7

    total_beds = 30 if centre.type == "CHC" else 6

    if bed_model is None:
        return [float(round(total_beds * 0.4 + (f/10.0))) for f in predicted_footfall]

    c_feats = get_centre_features(centre)
    now = datetime.datetime.utcnow()

    # Get recent bed history for lag features
    recent = _get_recent_values(db, centre_id, "beds", 7)
    if not recent:
        recent = [total_beds * 0.4] * 7

    predictions = []
    running_history = list(recent)
    
    for i in range(7):
        target_date = now + datetime.timedelta(days=i)
        lag_1 = running_history[-1] if len(running_history) >= 1 else np.median(recent)
        lag_7 = running_history[-7] if len(running_history) >= 7 else np.median(recent)
        window = running_history[-7:] if len(running_history) >= 7 else running_history
        rolling_mean = float(np.mean(window))
        rolling_std = float(np.std(window)) if len(window) > 1 else 0.0

        features = pd.DataFrame([{
            "centre_type_code": c_feats["centre_type_code"],
            "population_served": c_feats["population_served"],
            "total_beds": total_beds,
            "footfall": predicted_footfall[i],
            "day_of_week": target_date.weekday(),
            "month": target_date.month,
            "is_weekend": 1 if target_date.weekday() >= 5 else 0,
            "lag_1": lag_1,
            "lag_7": lag_7,
            "rolling_mean_7": rolling_mean,
            "rolling_std_7": rolling_std,
        }])
        
        pred = bed_model.predict(features)[0]
        pred = float(round(min(float(total_beds), max(0.0, pred)), 1))
        predictions.append(pred)
        running_history.append(pred)

    return predictions

def forecast_days_to_stockout(
    centre_id: int,
    drug_id: int,
    current_stock: int,
    predicted_footfall_7: List[float],
    db: Session
) -> Tuple[float, float, float, str]:
    """
    Executes a 30-day rollout simulation of daily inventory consumption.
    Uses enhanced Gradient Boosting predictions with lag/rolling features for improved accuracy.
    """
    _, cons_model, _, meta = load_models()
    centre = db.query(Centre).filter_by(id=centre_id).first()
    drug = db.query(Drug).filter_by(id=drug_id).first()

    if not centre or not drug:
        return 99.0, 99.0, 99.0, "Invalid centre/drug ID."

    # If stock is already out
    if current_stock <= 0:
        return 0.0, 0.0, 0.0, "Stock is currently depleted (0 units)."

    # If model is not loaded, fall back to historical daily average consumption
    if cons_model is None or meta is None:
        # Fallback extrapolation
        thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        total_consumed = db.query(func.sum(StockLog.quantity_change)).filter(
            StockLog.centre_id == centre_id,
            StockLog.drug_id == drug_id,
            StockLog.quantity_change < 0,
            StockLog.timestamp >= thirty_days_ago
        ).scalar() or 0
        avg_daily = abs(total_consumed) / 30.0
        
        if avg_daily <= 0:
            return 99.0, 99.0, 99.0, "No historical consumption observed in last 30 days. Forecasting engine inactive."
            
        predicted = current_stock / avg_daily
        return (
            round(predicted, 1),
            round(max(0.0, predicted * 0.7), 1),
            round(predicted * 1.3, 1),
            f"Extrapolated from historical daily average consumption ({avg_daily:.1f} units/day). ML models not loaded."
        )

    # We run 3 simulations (expected, lower, upper stockout days)
    rmse = meta["consumption_model_rmse"]
    c_feats = get_centre_features(centre)
    now = datetime.datetime.utcnow()

    # Get recent consumption history for lag features
    recent_cons = _get_recent_values(db, centre_id, "consumption", 7)
    if not recent_cons:
        recent_cons = [5.0] * 7

    # We repeat footfall over 30 days (cycling the 7-day predicted footfall list)
    def simulate(offset_factor: float) -> float:
        stock = float(current_stock)
        running_history = list(recent_cons)

        for d in range(1, 31):
            target_date = now + datetime.timedelta(days=d)
            is_monsoon = 6 <= target_date.month <= 8
            
            # Retrieve predicted footfall for this future day
            footfall_val = predicted_footfall_7[d % 7]

            lag_1 = running_history[-1] if len(running_history) >= 1 else np.median(recent_cons)
            lag_7 = running_history[-7] if len(running_history) >= 7 else np.median(recent_cons)
            window = running_history[-7:] if len(running_history) >= 7 else running_history
            rolling_mean = float(np.mean(window))
            rolling_std = float(np.std(window)) if len(window) > 1 else 0.0
            
            features = pd.DataFrame([{
                "population_served": c_feats["population_served"],
                "centre_type_code": c_feats["centre_type_code"],
                "tier_code": c_feats["tier_code"],
                "drug_id": drug_id,
                "day_of_week": target_date.weekday(),
                "month": target_date.month,
                "is_weekend": 1 if target_date.weekday() >= 5 else 0,
                "is_monsoon": 1 if is_monsoon else 0,
                "footfall": footfall_val,
                "lag_1": lag_1,
                "lag_7": lag_7,
                "rolling_mean_7": rolling_mean,
                "rolling_std_7": rolling_std,
            }])
            
            pred_cons = cons_model.predict(features)[0]
            # Add prediction offset to capture uncertainty:
            # - For lower stockout days (fastest depletion), we use high consumption (offset = +1.96 * RMSE)
            # - For upper stockout days (slowest depletion), we use low consumption (offset = -1.96 * RMSE)
            final_cons = max(0.0, pred_cons + (offset_factor * rmse))
            
            stock -= final_cons
            running_history.append(final_cons)
            if stock <= 0:
                return float(d)
        return 99.0  # safe (exceeds 30 days)

    expected_days = simulate(offset_factor=0.0)
    lower_days = simulate(offset_factor=1.96)    # High consumption -> fast stockout
    upper_days = simulate(offset_factor=-1.96)   # Low consumption -> slow stockout

    # Safety limits
    if lower_days > expected_days:
        lower_days = expected_days
    if upper_days < expected_days:
        upper_days = expected_days

    reasoning = (
        f"Simulated using enhanced Gradient Boosting v2 (CV-RMSE: {rmse:.1f} units) with lag/rolling features. "
        f"Expected daily consumption averages {round(current_stock / expected_days, 1) if expected_days < 99 else 0.0:.1f} units/day over the forecast period. "
        f"Uncertainty limits evaluated at 95% confidence interval boundaries."
    )

    return round(expected_days, 1), round(lower_days, 1), round(upper_days, 1), reasoning

