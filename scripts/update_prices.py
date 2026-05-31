import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZIP_URL = "https://files.ember-energy.org/public-downloads/price/outputs/european_wholesale_electricity_price_data_hourly.zip"
TARGET_CSV = ROOT / "prices" / "all_countries.csv"
BUILD_SCRIPT = ROOT / "scripts" / "build_negative_prices.py"


def find_all_countries_csv(zip_file):
    matches = [
        name
        for name in zip_file.namelist()
        if Path(name).name.lower() == "all_countries.csv"
    ]
    if not matches:
        raise FileNotFoundError("all_countries.csv was not found inside the downloaded ZIP")
    return matches[0]


def download_file(url, destination):
    with urllib.request.urlopen(url, timeout=120) as response:
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def main():
    TARGET_CSV.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="energyprices-update-") as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / "prices.zip"
        extracted_csv = temp_path / "all_countries.csv"

        print(f"Downloading {ZIP_URL}")
        download_file(ZIP_URL, zip_path)
        print(f"Downloaded {zip_path.stat().st_size:,} bytes")

        with zipfile.ZipFile(zip_path) as zip_file:
            source_name = find_all_countries_csv(zip_file)
            print(f"Extracting {source_name}")
            with zip_file.open(source_name) as source, extracted_csv.open("wb") as target:
                shutil.copyfileobj(source, target)

        if extracted_csv.stat().st_size == 0:
            raise ValueError("Downloaded CSV is empty; keeping the existing local file")

        backup_path = TARGET_CSV.with_suffix(".csv.bak")
        if TARGET_CSV.exists():
            shutil.copy2(TARGET_CSV, backup_path)
            print(f"Backup written to {backup_path}")

        shutil.move(str(extracted_csv), TARGET_CSV)
        print(f"Updated {TARGET_CSV}")

    print("Rebuilding dashboard data")
    subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT, check=True)
    print("Update complete")


if __name__ == "__main__":
    main()
