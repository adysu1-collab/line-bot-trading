from pathlib import Path
import glob
import json
import polars as pl

# 指向你在 GCP 上的實際資料夾路徑
cleaned_dir = Path.home() / "shioaji_bot/data_clean"
parquet_files = glob.glob(str(cleaned_dir / "cleaned_aligned_*.parquet"))

paired_1min_records = []

for file_path in parquet_files:
    raw_date = Path(file_path).stem.split("_")[-1]
    formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date
    
    df = pl.read_parquet(file_path)
    
    if len(df) > 0 and "txf_close" in df.columns:
        df_valid = (
            df.drop_nulls(subset=["txf_close", "close"])
            .with_columns(pl.col("ts").cast(pl.Datetime("ns")))
        )
        
        df_1min = (
            df_valid
            .group_by_dynamic("ts", every="1m")
            .agg([
                pl.col("close").last().alias("etf_close"),
                pl.col("txf_close").last().alias("tx_close")
            ])
            .drop_nulls()
        )
        
        for row in df_1min.iter_rows(named=True):
            time_str = str(row["ts"]).split(" ")[1] if " " in str(row["ts"]) else str(row["ts"])
            paired_1min_records.append({
                "date": formatted_date,
                "time": time_str[:5],
                "etf_close": float(row["etf_close"]),
                "tx_close": float(row["tx_close"])
            })

output_json_path = Path("api/paired_1min_history.json")
output_json_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_json_path, "w", encoding="utf-8") as f:
    json.dump(paired_1min_records, f, ensure_ascii=False)

print(f"成功產出 1 分 K 歷史資料！共產出 {len(paired_1min_records)} 筆紀錄。")
