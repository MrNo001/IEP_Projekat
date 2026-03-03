FROM node:20-alpine AS solc

WORKDIR /src
RUN npm install -g solc@0.8.19
COPY contracts/Payment.sol ./Payment.sol
RUN rm -rf /src/out && mkdir -p /src/out
RUN solcjs --optimize --abi --bin Payment.sol -o /src/out
RUN node -e "const fs=require('fs'); const abiPath='/src/out/Payment_sol_Payment.abi'; const binPath='/src/out/Payment_sol_Payment.bin'; const abi=JSON.parse(fs.readFileSync(abiPath,'utf8')); const bin=fs.readFileSync(binPath,'utf8').trim(); fs.writeFileSync('/src/Payment.artifact.json', JSON.stringify({abi, bin:'0x'+bin}));"

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=solc /src/Payment.artifact.json /app/contracts/Payment.artifact.json

CMD ["python", "app.py"]


