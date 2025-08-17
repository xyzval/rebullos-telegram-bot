#!/usr/bin/env python3
import asyncio
import os
import shlex
import signal
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# === KONFIGURASI ===
TELEGRAM_TOKEN = os.environ.get("TG_TOKEN", "")        # set via env var
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))        # admin Telegram ID
SCRIPT_PATH = Path(os.environ.get("REINSTALL_PATH", "./reinstall.sh")).resolve()
LOG_FILE = Path("/reinstall.log")  # reinstall.sh menulis log ke path ini

SUPPORTED = """
anolis 7|8|23
opencloudos 8|9|23
rocky 8|9|10
oracle 8|9
almalinux 8|9|10
centos 9|10
fedora 41|42
nixos 25.05
debian 9|10|11|12|13
opensuse 15.6|tumbleweed
alpine 3.19|3.20|3.21|3.22
openeuler 20.03|22.03|24.03|25.03
ubuntu 16.04|18.04|20.04|22.04|24.04|25.04 [--minimal]
kali
arch
gentoo
aosc
fnos
redhat --img="http://.../rhel.qcow2"
dd --img="http://.../image.raw[.gz|.xz|.zst]"
windows --image-name="windows 11 pro" --lang=en-us
windows --image-name="windows 11 pro" --iso="http://.../win11.iso"
netboot.xyz
""".strip()

PENDING = {}

def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Akses ditolak.")
        return
    await update.message.reply_text(
        "Halo! Bot Reinstall OS siap.\n"
        "Perintah:\n"
        "/list – daftar OS\n"
        "/reinstall <distro> <versi> [opsi...] – jalankan reinstall\n"
        "/progress – lihat log berjalan\n\n"
        "Contoh:\n"
        "/reinstall ubuntu 24.04 --minimal --password 'P@ssw0rd!'\n"
        "/reinstall debian 12 --ssh-key 'ssh-ed25519 AAAA...'"
    )

async def list_os(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Akses ditolak.")
        return
    await update.message.reply_text(f"*Supported OS:*\n```\n{SUPPORTED}\n```", parse_mode=ParseMode.MARKDOWN_V2)

async def reinstall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Akses ditolak.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Format: /reinstall <distro> <versi|opsi> [opsi...]")
        return

    cmd = ["sudo", str(SCRIPT_PATH)] + args

    txt = (
        "*Konfirmasi reinstall OS*\n"
        f"Perintah:\n```\n{' '.join(shlex.quote(x) for x in cmd)}\n```\n\n"
        "⚠️ Ini akan mengubah OS dan bisa reboot.\n"
        "Lanjut?"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Lanjut", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Batal", callback_data="confirm_no")
    ]])
    m = await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)
    PENDING[update.effective_chat.id] = {"cmd": cmd, "msg_id": m.message_id}

async def on_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.callback_query.answer("Akses ditolak.", show_alert=True)
        return

    q = update.callback_query
    data = q.data
    await q.answer()

    pend = PENDING.get(update.effective_chat.id)
    if not pend:
        await q.edit_message_text("Tidak ada perintah tertunda.")
        return

    if data == "confirm_no":
        PENDING.pop(update.effective_chat.id, None)
        await q.edit_message_text("Dibatalkan.")
        return

    cmd = pend["cmd"]
    await q.edit_message_text("Menjalankan…\n```\n" + " ".join(shlex.quote(x) for x in cmd) + "\n```",
                              parse_mode=ParseMode.MARKDOWN_V2)

    if not SCRIPT_PATH.exists():
        await context.bot.send_message(update.effective_chat.id, f"Script tidak ditemukan: {SCRIPT_PATH}")
        return

    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"Gagal start: {e}")
        return

    lines_sent = 0
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            if lines_sent < 40:
                try:
                    await context.bot.send_message(update.effective_chat.id, line.decode(errors="ignore")[:4000])
                except:
                    pass
                lines_sent += 1
        await proc.wait()
        rc = proc.returncode
        await context.bot.send_message(update.effective_chat.id, f"Proses selesai dengan kode: {rc}. Gunakan /progress untuk melihat log.")
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"Kesalahan saat streaming output: {e}")

async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Akses ditolak.")
        return
    if not LOG_FILE.exists():
        await update.message.reply_text("Belum ada log di /reinstall.log.")
        return

    await update.message.reply_text("Mengirim tail -f /reinstall.log (stop otomatis setelah 10 menit).")
    try:
        proc = await asyncio.create_subprocess_exec(
            "tail", "-F", "-n", "50", str(LOG_FILE),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )

        async def killer():
            await asyncio.sleep(600)
            try:
                proc.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass

        asyncio.create_task(killer())

        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                await update.message.reply_text(line.decode(errors="ignore")[:4000])
            except:
                pass
    except Exception as e:
        await update.message.reply_text(f"Tail gagal: {e}")

def main():
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        raise SystemExit("Set TG_TOKEN dan ADMIN_ID di environment terlebih dahulu.")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_os))
    app.add_handler(CommandHandler("reinstall", reinstall))
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CallbackQueryHandler(on_confirm, pattern="^confirm_"))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
