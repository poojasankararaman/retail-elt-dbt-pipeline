.PHONY: setup data load build day2 docs lint clean all

PY ?= python
DBT = cd retail && dbt

setup:
	$(PY) -m pip install -r requirements.txt

# Day 1: generate synthetic Olist-shaped data, load raw, build models
data:
	$(PY) ingestion/generate_sample_data.py --n-orders 5000 --seed 42 --day 1 --out data/raw

load:
	$(PY) ingestion/load_raw.py --mode replace

build:
	$(DBT) build --profiles-dir .

# Day 2: new orders arrive and some customers move -> exercises incremental model + SCD2 snapshot
day2:
	$(PY) ingestion/generate_sample_data.py --n-orders 800 --seed 43 --day 2 --out data/raw
	$(PY) ingestion/load_raw.py --mode append
	$(DBT) build --profiles-dir .
	$(DBT) snapshot --profiles-dir .

docs:
	$(DBT) docs generate --profiles-dir .
	$(DBT) docs serve --profiles-dir .

lint:
	ruff check ingestion dags

clean:
	rm -rf retail/target retail/logs retail.duckdb data/raw/*.csv

all: data load build
