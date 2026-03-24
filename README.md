# E-store backend (IEP project)

This repository implements a multi-service **online store** backend with **JWT authentication**, **MySQL** persistence, and **Ethereum (Ganache)** payment flows using a Solidity `Payment` contract. It was developed as a **university project** for the course **Infrastruktura za elektronsko poslovanje** — in English: **Infrastructure for Electronic Business**.

For the full assignment wording, constraints, and grading criteria, see **`IEP_Projekat_2025.pdf`** (course project specification).

---

## What’s in the stack

- **Authentication service** (Flask): user registration, login, JWT issuance, account deletion.
- **Store service** (Flask): same codebase, different **`SERVICE_MODE`** — exposes **owner**, **customer**, **courier**, or **product statistics** APIs; also includes a **blockchain helper** API under `/blockchain`.
- **MySQL** (two databases: auth + store).
- **Ganache** local chain for development.
- **Adminer** for browsing databases (optional).

---

## Repository layout

```
IEP_Projekat/
├── docker-compose.yml          # All services, ports, env
├── authentication/
│   ├── authentication.py       # Auth Flask app (entrypoint)
│   ├── models.py
│   ├── config.py
│   ├── Dockerfile
│   └── requirements.txt
├── store/
│   ├── app.py                  # Store Flask app (entrypoint)
│   ├── auth.py                 # JWT + role checks
│   ├── blockchain.py           # Web3 helpers
│   ├── contract.py             # Deploy / interact with Payment contract
│   ├── models.py
│   ├── config.py
│   ├── routes/
│   │   ├── owner.py            # Owner blueprint
│   │   ├── customer.py         # Customer blueprint
│   │   ├── courier.py          # Courier blueprint
│   │   ├── product_stats.py    # Stats blueprint (prefix /product_stats)
│   │   └── blockchain_interface.py
│   ├── contracts/              # Payment.sol, ABI, compile script
│   ├── Dockerfile
│   └── requirements.txt
├── tests/                      # Automated tests & helpers
└── README.md
```

The store app **registers blueprints based on `SERVICE_MODE`**: `owner`, `customer`, `courier`, `stats`, or `all` (owner + customer + courier together).

---

## How to run

### Prerequisites

- Docker and Docker Compose

### Start everything

```bash
docker compose up -d
```

Rebuild images after code changes:

```bash
docker compose up -d --build
```

Stop and remove containers; add **`-v`** to wipe MySQL volumes:

```bash
docker compose down
docker compose down -v
```

### Service URLs and ports

| Service        | Port | Notes                                      |
|----------------|------|--------------------------------------------|
| Authentication | 5000 | JWT auth API                               |
| Owner store    | 5001 | Owner role routes                            |
| Customer store | 5002 | Customer role routes + blockchain helpers |
| Courier store  | 5003 | Courier role routes                        |
| Stats store    | 5004 | Extended product statistics (`/product_stats`) |
| Adminer        | 8080 | DB UI                                      |
| Ganache        | 8545 | JSON-RPC                                   |

Health checks:

- Authentication: `GET http://localhost:5000/`
- Store (any mode): `GET http://localhost:5002/` (or 5001 / 5003 / 5004)

---

## Authentication

Protected store endpoints expect a JWT from the auth service:

```http
Authorization: Bearer <accessToken>
```

Obtain a token with `POST /login` on port **5000** (see below). The JWT must include the `roles` claim expected by each route (`owner`, `customer`, or `courier`).

---

## API overview

Base URLs below use the **default compose ports**. Replace the host/port if you run services differently.

### Authentication service (`http://localhost:5000`)

| Method | Path                 | Auth | Description |
|--------|----------------------|------|-------------|
| GET    | `/`                  | No   | Health                                      |
| POST   | `/register_customer` | No | Register a customer                         |
| POST   | `/register_courier`  | No   | Register a courier                          |
| POST   | `/login`             | No   | JSON: `email`, `password` → `accessToken`   |
| POST   | `/delete`            | JWT  | Delete the authenticated user               |
| POST   | `/__reset`           | No*  | Drop/recreate auth DB + seed owner (dev)    |

\* `__reset` is only active when `ALLOW_RESET=1`; optional header `X-Reset-Token` if `RESET_TOKEN` is set (compose uses `dev`).

### Store — common to modes that mount the blueprint

**Owner** (`http://localhost:5001` in compose):

| Method | Path                    | Role   | Description |
|--------|-------------------------|--------|-------------|
| POST   | `/update`               | owner  | Multipart CSV: categories\|..., name, price |
| GET    | `/product_statistics`   | owner  | Per-product sold / waiting counts           |
| GET    | `/category_statistics`  | owner  | Category names sorted by sold quantity      |

**Customer** (`http://localhost:5002`):

| Method | Path                 | Role     | Description |
|--------|----------------------|----------|-------------|
| GET    | `/search`            | customer | Query: `name`, `category` (category id → `Category{id}`) |
| POST   | `/order`             | customer | Create order; blockchain mode requires `address` |
| GET    | `/status`            | customer | List customer’s orders                      |
| POST   | `/delivered`         | customer | Mark order complete (`PENDING` → `COMPLETE`) |
| POST   | `/generate_invoice` | customer | Payment / invoice payload for blockchain  |

**Courier** (`http://localhost:5003`):

| Method | Path               | Role    | Description |
|--------|--------------------|---------|-------------|
| GET    | `/orders_to_deliver` | courier | Orders in `CREATED`                       |
| POST   | `/pick_up_order`   | courier | Pick up order; blockchain checks payment    |

**Product statistics** (`http://localhost:5004`, prefix `/product_stats`, owner role):

| Method | Path                      | Description |
|--------|---------------------------|-------------|
| GET    | `/product_stats/summary`   | Per-product sold/waiting, revenue, avg price |
| GET    | `/product_stats/top_sold`  | Query: `limit` (default 5, max 50)          |
| GET    | `/product_stats/top_revenue` | Query: `limit`                            |

### Blockchain helper API (on each store container that runs the store app)

Prefix: **`/blockchain`** (e.g. customer service: `http://localhost:5002/blockchain/...`).

| Method | Path                         | Description |
|--------|------------------------------|-------------|
| GET    | `/blockchain/owner`          | Derive owner address from `OWNER_PRIVATE_KEY` |
| GET    | `/blockchain/test-accounts`  | Ganache + owner + addresses seen on orders, with balances |
| GET    | `/blockchain/accounts`       | List Ganache accounts and balances           |
| GET    | `/blockchain/balance`        | Query: `address`                             |
| POST   | `/blockchain/account`        | Create account; optional fund from Ganache index |
| POST   | `/blockchain/send`           | Send wei (`from_private_key`, `to_address`, `value_wei`) |
| GET    | `/blockchain/transaction/<tx_hash>` | Transaction + receipt summary        |

### Dev-only database reset (store)

| Method | Path        | Notes |
|--------|-------------|-------|
| POST   | `/__reset`  | Same pattern as auth: `ALLOW_RESET`, optional `X-Reset-Token` |

---

## Example: blockchain helpers (customer service on 5002)

```bash
curl http://localhost:5002/blockchain/accounts

curl "http://localhost:5002/blockchain/balance?address=0xYourAddress"

curl -X POST http://localhost:5002/blockchain/account \
  -H "Content-Type: application/json" \
  -d '{"fund_from_account_index": 0, "fund_wei": 1000000000000000000}'

curl -X POST http://localhost:5002/blockchain/send \
  -H "Content-Type: application/json" \
  -d '{"from_private_key": "0x...", "to_address": "0x...", "value_wei": 1000}'

curl http://localhost:5002/blockchain/transaction/0xTxHash
```

---

## Adminer (database UI)

Open **http://localhost:8080**.

**Authentication database**

- Server: `auth-mysql`
- User: `auth_user` / Password: `auth_password`
- Database: `auth_db`

**Store database**

- Server: `store-mysql`
- User: `store_user` / Password: `store_password`
- Database: `store_db`

Root on both MySQL containers: `root` / `rootpassword`.

---

## Docker Compose tips

```bash
docker compose ps
docker compose logs -f
docker compose logs -f owner
docker compose restart customer
```

---

## Tests

The `tests/` directory contains level-based test scripts and helpers. Install dependencies from `tests/requirements.txt` and run using the project’s `run.ps1` / `run.sh` as appropriate for your environment.

---

## License / course use

Academic project for **Infrastructure for Electronic Business**; see **`IEP_Projekat_2025.pdf`** for official requirements and context.
