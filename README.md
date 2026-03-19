# crypto-kdj-alert

Python service for 7x24 monitoring of BTC/ETH USDT perpetual futures using KDJ cross signals on 5 minute candles, with Feishu and Telegram alerts.

## Features

- Monitors one or more symbols and intervals from env config.
- Uses `Binance Futures` as primary source and `OKX Swap` as backup.
- Calculates KDJ with `N=26`, `K smoothing=20`, `D smoothing=9`.
- Sends alerts when `J` crosses above or below `K`.
- Supports Feishu webhook and Telegram bot delivery.
- Includes Docker and systemd deployment examples.

## Strategy Definition

- Market: USDT perpetual futures
- Interval: configurable, for example `5m,15m`
- Bullish alert: previous candle `J <= K`, current candle `J > K`
- Bearish alert: previous candle `J >= K`, current candle `J < K`
- Alerts are deduplicated per signal per candle

## Quick Start

1. Create a virtual environment and install dependencies.
2. Copy `.env.example` to `.env`.
3. Fill in `FEISHU_WEBHOOK`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`.
4. Start the service.

```powershell
cd D:\crypto-kdj-alert
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python -m app.main
```

## Config Notes

- `INTERVALS=5m,15m` means the service evaluates both 5-minute and 15-minute closed candles.
- `POLL_SECONDS=1` means the service checks every second for a newly closed candle on each configured interval.
- `STATE_FILE=logs/alert_state.json` persists the last J/K relation so restarts do not resend the same unchanged state.
- `PRIMARY_FAIL_THRESHOLD=3` switches traffic to OKX after three consecutive Binance failures.
- `PRIMARY_RECOVER_PROBE_SECONDS=60` probes Binance every 60 seconds while running on backup.

## Deployment

### Docker

```powershell
cd D:\crypto-kdj-alert
docker compose -f deploy\docker\docker-compose.yml up -d --build
```

### systemd

Copy [deploy/systemd/crypto-kdj-alert.service](deploy/systemd/crypto-kdj-alert.service) to `/etc/systemd/system/` and adjust paths for your Linux server.
