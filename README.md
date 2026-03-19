## Docker Compose

```bash
# Start all services (foreground)
docker-compose up

# Start all services in background
docker-compose up -d

# Stop all services
docker-compose down

# Stop and remove volumes (resets DB data)
docker-compose down -v

# Build/rebuild images and start
docker-compose up -d --build

# List running services
docker-compose ps

# View logs (all services)
docker-compose logs -f

# View logs for a specific service
docker-compose logs -f owner
docker-compose logs -f authentication

# Restart a service
docker-compose restart owner

# Start only specific services (e.g. DBs + ganache)
docker-compose up -d auth-mysql store-mysql ganache

```

curl http://localhost:5002/blockchain/accounts

# Balance of an address
curl "http://localhost:5002/blockchain/balance?address=0xYourAddress"

# Create account (optionally funded)
curl -X POST http://localhost:5002/blockchain/account -H "Content-Type: application/json" -d '{"fund_from_account_index": 0, "fund_wei": 1000000000000000000}'

# Send wei
curl -X POST http://localhost:5002/blockchain/send -H "Content-Type: application/json" -d '{"from_private_key": "0x...", "to_address": "0x...", "value_wei": 1000}'

# Inspect a tx
curl http://localhost:5002/blockchain/transaction/0xTxHash



## Docker (single container)

docker build - build image from dockerfile
docker run - create and run a new container from image
docker start - start one or more stopped containers
docker rename - rename container
docker stop - stop container
docker rm - remove container

docker container - manage containers

docker image - manage images


Reset routes:
    localhost:500x/__reset (POST)

Adminer:
    Server (auth DB): mysql
    Username: auth_user
    Password: auth_password
    Database: auth_db
    or
    Server (store DB): store-mysql
    Username: store_user
    Password: store_password
    Database: store_db
    Root also exists for both DB containers:
    Username: root
    Password: rootpassword