"""Generate synthetic, Olist-shaped retail data with realistic mess.

Why synthetic? It makes the repo runnable in one command with no downloads.
To use the real Olist dataset instead, drop its CSVs into data/raw/ using the same
file names/columns (see README) and skip this script.

Day 1 : full snapshot of customers, products, orders, items, payments.
Day 2 : new orders arrive, some existing customers move (city/state change),
        and some day-1 orders get a status update. Used to exercise the
        incremental model and the SCD2 snapshot.

Intentional data problems (so the dbt tests have something to catch):
  * exact duplicate order rows
  * mixed-case / padded order_status values
  * delivered timestamp earlier than purchase timestamp
  * order_items whose order_id does not exist (orphans)
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

STATES = {
    "SP": ["Sao Paulo", "Campinas", "Santos"],
    "RJ": ["Rio de Janeiro", "Niteroi"],
    "MG": ["Belo Horizonte", "Uberlandia"],
    "RS": ["Porto Alegre", "Caxias do Sul"],
    "BA": ["Salvador", "Feira de Santana"],
}
CATEGORIES = ["electronics", "home", "toys", "sports", "beauty", "books", "garden", "auto"]
PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]
STATUS_WEIGHTS = [
    ("delivered", 0.80),
    ("shipped", 0.08),
    ("processing", 0.05),
    ("canceled", 0.04),
    ("invoiced", 0.03),
]


def pick_status(rng: random.Random) -> str:
    r, acc = rng.random(), 0.0
    for status, w in STATUS_WEIGHTS:
        acc += w
        if r <= acc:
            return status
    return "delivered"


def messy_case(rng: random.Random, status: str) -> str:
    roll = rng.random()
    if roll < 0.04:
        return status.upper()
    if roll < 0.07:
        return f" {status.capitalize()} "
    return status


def random_location(rng: random.Random) -> tuple[str, str]:
    state = rng.choice(list(STATES))
    return rng.choice(STATES[state]), state


def make_customers(rng: random.Random, day: int, n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        city, state = random_location(rng)
        rows.append({"customer_id": f"c{day}_{i:05d}", "city": city, "state": state})
    return pd.DataFrame(rows)


def make_products(rng: random.Random, n: int) -> pd.DataFrame:
    rows = [
        {
            "product_id": f"p{i:04d}",
            "category": rng.choice(CATEGORIES),
            "weight_g": rng.randint(50, 20000),
            "list_price": round(rng.uniform(5, 800), 2),
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows)


def make_orders(
    rng: random.Random,
    day: int,
    n_orders: int,
    customer_ids: list[str],
    products: pd.DataFrame,
    start: datetime,
    span_days: int,
):
    orders, items, payments = [], [], []
    price_by_product = dict(zip(products["product_id"], products["list_price"], strict=True))
    product_ids = list(price_by_product)

    for i in range(n_orders):
        order_id = f"o{day}_{i:06d}"
        purchased = start + timedelta(
            days=rng.randint(0, span_days - 1), seconds=rng.randint(0, 86399)
        )
        status = pick_status(rng)
        delivered = None
        if status == "delivered":
            delivered = purchased + timedelta(days=rng.randint(2, 25))
            if rng.random() < 0.01:  # bad data: delivered before purchase
                delivered = purchased - timedelta(days=rng.randint(1, 5))

        orders.append(
            {
                "order_id": order_id,
                "customer_id": rng.choice(customer_ids),
                "order_status": messy_case(rng, status),
                "order_purchase_timestamp": purchased.isoformat(sep=" "),
                "order_delivered_timestamp": delivered.isoformat(sep=" ") if delivered else None,
            }
        )

        total = 0.0
        for item_no in range(1, rng.choice([1, 1, 1, 2, 2, 3]) + 1):
            pid = rng.choice(product_ids)
            price = round(price_by_product[pid] * rng.uniform(0.85, 1.1), 2)
            freight = round(rng.uniform(4, 40), 2)
            total += price + freight
            items.append(
                {
                    "order_id": order_id,
                    "order_item_id": item_no,
                    "product_id": pid,
                    "price": price,
                    "freight_value": freight,
                }
            )
        if status != "canceled":
            payments.append(
                {
                    "order_id": order_id,
                    "payment_type": rng.choice(PAYMENT_TYPES),
                    "payment_value": round(total, 2),
                }
            )

    orders_df = pd.DataFrame(orders)
    # bad data: exact duplicate order rows
    dupes = orders_df.sample(frac=0.02, random_state=rng.randint(0, 10_000))
    orders_df = pd.concat([orders_df, dupes], ignore_index=True)

    items_df = pd.DataFrame(items)
    # bad data: orphan order items
    orphans = items_df.sample(frac=0.005, random_state=rng.randint(0, 10_000)).copy()
    orphans["order_id"] = [f"ghost_{day}_{i:05d}" for i in range(len(orphans))]
    items_df = pd.concat([items_df, orphans], ignore_index=True)

    return orders_df, items_df, pd.DataFrame(payments)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--n-orders", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--day", type=int, default=1, choices=[1, 2])
    ap.add_argument("--out", type=Path, default=Path("data/raw"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    base = datetime(2025, 1, 1)
    if args.day == 1:
        customers = make_customers(rng, 1, 1500)
        products = make_products(rng, 200)
        orders, items, payments = make_orders(
            rng, 1, args.n_orders, list(customers["customer_id"]), products, base, 365
        )
    else:
        prev_customers_path = out / "customers.csv"
        prev_products_path = out / "products.csv"
        if not prev_customers_path.exists() or not prev_products_path.exists():
            raise SystemExit("Run day 1 first (make data load build) before generating day 2.")
        prev_customers = pd.read_csv(prev_customers_path)
        products = pd.read_csv(prev_products_path)

        # ~3% of existing customers move -> SCD2 history
        movers = prev_customers.sample(frac=0.03, random_state=args.seed).copy()
        for idx in movers.index:
            city, state = random_location(rng)
            movers.at[idx, "city"], movers.at[idx, "state"] = city, state
        new_customers = make_customers(rng, 2, 200)
        customers = pd.concat([movers, new_customers], ignore_index=True)

        all_ids = list(prev_customers["customer_id"]) + list(new_customers["customer_id"])
        orders, items, payments = make_orders(
            rng, 2, args.n_orders, all_ids, products, base + timedelta(days=365), 30
        )
        products = products.iloc[0:0]  # no product changes on day 2 (header only)

    customers.to_csv(out / "customers.csv", index=False)
    products.to_csv(out / "products.csv", index=False)
    orders.to_csv(out / "orders.csv", index=False)
    items.to_csv(out / "order_items.csv", index=False)
    payments.to_csv(out / "payments.csv", index=False)

    print(
        f"day {args.day}: customers={len(customers)} products={len(products)} "
        f"orders={len(orders)} items={len(items)} payments={len(payments)} -> {out}"
    )


if __name__ == "__main__":
    main()
