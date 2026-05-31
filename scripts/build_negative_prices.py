import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "prices" / "all_countries.csv"
OUTPUT_JSON = ROOT / "data" / "negative_prices.json"
OUTPUT_JS = ROOT / "data" / "negative_prices.js"


def parse_local_datetime(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV}")

    countries = {}
    months_by_country = defaultdict(set)
    negative_by_day = defaultdict(lambda: defaultdict(int))
    negative_by_hour = defaultdict(lambda: defaultdict(int))
    consecutive_by_day = defaultdict(lambda: defaultdict(int))
    current_negative_streak = defaultdict(int)
    observed_days_by_month = defaultdict(set)
    total_observations = 0
    total_negative = 0
    skipped_rows = 0

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            country = row["Country"].strip()
            iso3 = row["ISO3 Code"].strip()
            try:
                local_dt = parse_local_datetime(row["Datetime (Local)"].strip())
                price = float(row["Price (EUR/MWhe)"])
            except (KeyError, TypeError, ValueError):
                skipped_rows += 1
                continue

            month_key = local_dt.strftime("%Y-%m")
            day_key = str(local_dt.day)
            date_key = local_dt.strftime("%Y-%m-%d")

            countries[country] = iso3
            months_by_country[country].add(month_key)
            observed_days_by_month[(country, month_key)].add(day_key)
            total_observations += 1

            if price < 0:
                negative_by_day[(country, month_key)][day_key] += 1
                negative_by_hour[(country, month_key)][str(local_dt.hour)] += 1
                current_negative_streak[(country, date_key)] += 1
                consecutive_by_day[(country, month_key)][day_key] = max(
                    consecutive_by_day[(country, month_key)][day_key],
                    current_negative_streak[(country, date_key)],
                )
                total_negative += 1
            else:
                current_negative_streak[(country, date_key)] = 0

    series = {}
    for country, months in months_by_country.items():
        series[country] = {}
        for month_key in sorted(months):
            year, month = map(int, month_key.split("-"))
            if month == 12:
                next_month = datetime(year + 1, 1, 1)
            else:
                next_month = datetime(year, month + 1, 1)
            current_month = datetime(year, month, 1)
            days_in_month = (next_month - current_month).days

            days = []
            cumulative = 0
            counts = negative_by_day[(country, month_key)]
            hourly_counts = negative_by_hour[(country, month_key)]
            consecutive_counts = consecutive_by_day[(country, month_key)]
            for day in range(1, days_in_month + 1):
                negatives = counts.get(str(day), 0)
                cumulative += negatives
                days.append(
                    {
                        "day": day,
                        "negativePrices": negatives,
                        "maxConsecutiveNegativePrices": consecutive_counts.get(str(day), 0),
                        "otherNegativePrices": max(
                            0,
                            negatives - consecutive_counts.get(str(day), 0),
                        ),
                        "cumulativeNegativePrices": cumulative,
                    }
                )

            observed_days = len(observed_days_by_month[(country, month_key)])
            series[country][month_key] = {
                "days": days,
                "daysInMonth": days_in_month,
                "observedDays": observed_days,
                "isCompleteMonth": observed_days == days_in_month,
                "hourlyNegativePrices": [
                    hourly_counts.get(str(hour), 0)
                    for hour in range(24)
                ],
                "totalNegativePrices": cumulative,
                "daysWithNegativePrices": sum(1 for item in days if item["negativePrices"] > 0),
                "maxConsecutiveNegativePrices": max(
                    (item["maxConsecutiveNegativePrices"] for item in days),
                    default=0,
                ),
            }

    payload = {
        "source": str(INPUT_CSV.relative_to(ROOT)).replace("\\", "/"),
        "generatedFromRows": total_observations,
        "skippedRows": skipped_rows,
        "totalNegativePrices": total_negative,
        "countries": [
            {
                "name": country,
                "iso3": countries[country],
                "months": sorted(months_by_country[country]),
            }
            for country in sorted(countries)
        ],
        "series": series,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    with OUTPUT_JS.open("w", encoding="utf-8") as handle:
        handle.write("window.NEGATIVE_PRICE_DATA = ")
        json.dump(payload, handle, ensure_ascii=False)
        handle.write(";\n")

    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_JS}")
    print(f"Rows processed: {total_observations:,}")
    print(f"Rows skipped: {skipped_rows:,}")
    print(f"Negative prices: {total_negative:,}")


if __name__ == "__main__":
    main()
