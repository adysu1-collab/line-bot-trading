from pathlib import Path
import glob
import json
import polars as pl

# 指向你在 GCP 上的實際資料夾路徑
cleaned_dir = Path.home() / "shioaji_bot/data_clean"
parquet_files = sorted(glob.glob(str(cleaned_dir / "cleaned_aligned_*.parquet")))

output_json_path = Path("api/paired_1min_history.json")
output_json_path.parent.mkdir(parents=True, exist_ok=True)

# 1. 先載入既有的 api/paired_1min_history.json（保留歷史補齊資料）
existing_records = []
if output_json_path.exists():
    with open(output_json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        if isinstance(loaded, list):
            existing_records = loaded

# 2. 從 GCP data_clean 產出最新 1 分 K 紀錄
new_records = []

for file_path in parquet_files:
    raw_date = Path(file_path).stem.split("_")[-1]
    formatted_date = (
        f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        if len(raw_date) == 8
        else raw_date
    )

    df = pl.read_parquet(file_path)

    if len(df) > 0 and "txf_close" in df.columns and "close" in df.columns:
        df_valid = (
            df.drop_nulls(subset=["txf_close", "close"])
            .with_columns(pl.col("ts").cast(pl.Datetime("ns")))
        )

        df_1min = (
            df_valid
            .group_by_dynamic("ts", every="1m")
            .agg([
                pl.col("close").last().alias("etf_close"),
                pl.col("txf_close").last().alias("tx_close"),
            ])
            .drop_nulls()
        )

        for row in df_1min.iter_rows(named=True):
            ts_str = str(row["ts"])
            time_str = ts_str.split(" ")[1] if " " in ts_str else ts_str
            rec_date = formatted_date
            if len(ts_str) >= 10 and ts_str[4] == "-" and ts_str[7] == "-":
                rec_date = ts_str[:10]

            new_records.append({
                "date": rec_date,
                "time": time_str[:5],
                "etf_close": float(row["etf_close"]),
                "tx_close": float(row["tx_close"]),
            })

# 3. 依 (date, time) 合併去重（新資料覆蓋同分鐘舊資料）
merged_map: dict[tuple[str, str], dict] = {}

for rec in existing_records:
    if "date" in rec and "time" in rec:
        merged_map[(str(rec["date"]), str(rec["time"])[:5])] = {
            "date": str(rec["date"]),
            "time": str(rec["time"])[:5],
            "etf_close": float(rec["etf_close"]),
            "tx_close": float(rec["tx_close"]),
        }

for rec in new_records:
    merged_map[(rec["date"], rec["time"])] = rec

merged_records = [
    merged_map[k]
    for k in sorted(merged_map.keys(), key=lambda x: (x[0], x[1]))
]

# 4. 寫回 api/paired_1min_history.json
with open(output_json_path, "w", encoding="utf-8") as f:
    json.dump(merged_records, f, ensure_ascii=False)

all_dates = sorted({r["date"] for r in merged_records})
min_date = all_dates[0] if all_dates else "無"
max_date = all_dates[-1] if all_dates else "無"

print(
    f"成功更新 1 分 K 歷史資料！既有 {len(existing_records)} 筆、"
    f"本次掃描 {len(new_records)} 筆，合併後共 {len(merged_records)} 筆 "
    f"（共 {len(all_dates)} 個交易日：{min_date} ~ {max_date}）。"
)
