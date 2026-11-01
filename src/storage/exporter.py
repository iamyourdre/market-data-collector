"""
Exporter module to serialize collected market data into clean JSON and CSV formats.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from ..collectors.base import CollectionResult

logger = logging.getLogger(__name__)


def clean_nan(val: Any) -> Any:
    """Helper to convert NaN and numpy types to JSON-safe Python types."""
    if val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if np.isnan(val) or np.isinf(val):
            return None
        return round(float(val), 8)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    return val


def format_collection_result_json(result: CollectionResult) -> Dict[str, Any]:
    """Format CollectionResult into clean, structured JSON format."""
    df = result.df_merged
    cfg = result.config

    # Summary Statistics
    close_series = df["close"].dropna()
    start_price = float(close_series.iloc[0]) if not close_series.empty else 0.0
    latest_price = float(close_series.iloc[-1]) if not close_series.empty else 0.0
    price_change_pct = (
        ((latest_price - start_price) / start_price * 100) if start_price > 0 else 0.0
    )

    summary_stats = {
        "start_price": round(start_price, 4),
        "latest_price": round(latest_price, 4),
        "highest_price": round(float(df["high"].max()), 4) if not df.empty else 0.0,
        "lowest_price": round(float(df["low"].min()), 4) if not df.empty else 0.0,
        "price_change_pct": round(price_change_pct, 2),
        "total_volume": round(float(df["volume"].sum()), 4) if "volume" in df.columns else 0.0,
        "latest_rsi": (
            clean_nan(df[f"rsi_{cfg.indicators.rsi_period}"].iloc[-1])
            if f"rsi_{cfg.indicators.rsi_period}" in df.columns and not df.empty
            else None
        ),
        "latest_funding_rate": (
            clean_nan(result.raw_funding_rates[-1]["funding_rate"])
            if result.raw_funding_rates
            else None
        ),
        "latest_open_interest": (
            clean_nan(result.raw_open_interest[-1]["open_interest"])
            if result.raw_open_interest
            else None
        ),
    }

    # Format records
    records = []
    for _, row in df.iterrows():
        record = {
            "timestamp": int(row["timestamp"]),
            "datetime": row.get("datetime", ""),
            "open": clean_nan(row["open"]),
            "high": clean_nan(row["high"]),
            "low": clean_nan(row["low"]),
            "close": clean_nan(row["close"]),
            "volume": clean_nan(row.get("volume")),
            "quote_volume": clean_nan(row.get("quote_volume")),
            "indicators": {
                f"rsi_{cfg.indicators.rsi_period}": clean_nan(
                    row.get(f"rsi_{cfg.indicators.rsi_period}")
                ),
                "macd": {
                    "line": clean_nan(row.get("macd_line")),
                    "signal": clean_nan(row.get("macd_signal")),
                    "hist": clean_nan(row.get("macd_hist")),
                },
            },
            "derivatives": {
                "funding_rate": clean_nan(row.get("funding_rate")),
                "funding_settled": clean_nan(row.get("funding_settled")),
                "open_interest": clean_nan(row.get("open_interest")),
                "open_interest_usd": clean_nan(row.get("open_interest_usd")),
            },
        }

        # Add EMA values
        for period in cfg.indicators.ema_periods:
            record["indicators"][f"ema_{period}"] = clean_nan(row.get(f"ema_{period}"))

        if "trades_count" in row and not pd.isna(row["trades_count"]):
            record["trades_count"] = int(row["trades_count"])

        records.append(record)

    output = {
        "metadata": {
            "symbol": result.symbol,
            "exchange": result.exchange,
            "timeframe": result.timeframe,
            "period_days": cfg.days,
            "start_time": result.start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": result.end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_candles": len(records),
            "total_funding_events": len(result.raw_funding_rates),
            "total_oi_records": len(result.raw_open_interest),
            "indicators_config": {
                "rsi_period": cfg.indicators.rsi_period,
                "macd": {
                    "fast": cfg.indicators.macd_fast,
                    "slow": cfg.indicators.macd_slow,
                    "signal": cfg.indicators.macd_signal,
                },
                "ema_periods": cfg.indicators.ema_periods,
            },
            "summary_stats": summary_stats,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "data": records,
        "raw_series": {
            "funding_rates": result.raw_funding_rates,
            "open_interest": result.raw_open_interest,
        },
    }

    return output


def export_data(
    result: CollectionResult,
    output_path: Optional[str] = None,
    export_csv: bool = False,
) -> Dict[str, str]:
    """
    Export collection result to JSON (and optional CSV).
    Returns dictionary with saved file paths.
    """
    output_dir = Path(result.config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base_name = f"{result.symbol}_{result.timeframe}_{result.exchange}_{result.config.days}d"

    if output_path:
        json_file = Path(output_path)
    else:
        json_file = output_dir / f"{base_name}.json"

    # Export JSON
    data_dict = format_collection_result_json(result)
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2)
    logger.info(f"Saved JSON data to {json_file} ({json_file.stat().st_size / 1024:.1f} KB)")

    saved_paths = {"json": str(json_file)}

    # Export CSV if requested
    if export_csv or result.config.export_csv:
        csv_file = json_file.with_suffix(".csv")
        result.df_merged.to_csv(csv_file, index=False)
        saved_paths["csv"] = str(csv_file)
        logger.info(f"Saved CSV data to {csv_file}")

    return saved_paths
