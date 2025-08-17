# RebullOS Telegram Bot

Bot Telegram untuk mengontrol `reinstall.sh` dari [rebullos](https://github.com/xyzval/rebullos).

## Instalasi Cepat

```bash
git clone https://github.com/<username>/rebullos-telegram-bot.git
cd rebullos-telegram-bot
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
export TG_TOKEN="TOKEN_BOT"
export ADMIN_ID="5942781514"
export REINSTALL_PATH="/root/reinstall.sh"
./venv/bin/python bot_rebullos.py
```
