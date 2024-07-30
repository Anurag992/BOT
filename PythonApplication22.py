import discord
from discord.ext import commands
from discord import app_commands
import random
import string
import secrets
import pymongo
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone
import urllib.parse
import re
import psutil
import platform
import time
import psutil
import socket
import cpuinfo
import os
import GPUtil
from discord import Embed

# MongoDB setup
username = urllib.parse.quote_plus('Anoop')
password = urllib.parse.quote_plus('AnoopDFIRHQ2024')
mongo_client = MongoClient(
    f'mongodb+srv://{username}:{password}@cluster0.dlzzzdo.mongodb.net/?retryWrites=true&w=majority&ssl=true'
)
db = mongo_client['discord_bot']
licenses_col = db['licenses']
detections_col = db['detections']
keys_col = db['keys']  
enterprise_col = db['enterprise_licenses']  

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)
MY_DISCORD_ID = 702050985660514364

def generate_random_key():
    characters = string.ascii_letters + string.digits + string.punctuation
    key_length = random.randint(20, 30)
    return ''.join(secrets.choice(characters) for _ in range(key_length))

async def check_license(user_id):
    license = licenses_col.find_one({"user_id": user_id})
    enterprise_license = enterprise_col.find_one({"members": user_id})
    now = datetime.now(timezone.utc)
    
    # Check for personal license
    if license:
        expiry_date = license.get('expiry_date')
        if isinstance(expiry_date, datetime) and expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        if expiry_date > now:
            print(f"Personal license found for user {user_id}, expires on {expiry_date}")
            return True
    
    # Check for enterprise license
    if enterprise_license:
        expiry_date = enterprise_license.get('expiry_date')
        if isinstance(expiry_date, datetime) and expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        if expiry_date > now:
            print(f"Enterprise license found for user {user_id}, expires on {expiry_date}")
            return True
    
    print(f"No valid license found for user {user_id}")
    return False

async def add_key(user_id, key):
    expiry_time = datetime.now(timezone.utc) + timedelta(minutes=2)
    keys_col.insert_one({
        "user_id": user_id,
        "key": key,
        "expiry_time": expiry_time,
        "used": False
    })

async def validate_key(user_id, key):
    record = keys_col.find_one({"user_id": user_id, "key": key})
    if record:
        if datetime.now(timezone.utc) <= record['expiry_time'] and not record['used']:
            keys_col.update_one({"user_id": user_id, "key": key}, {"$set": {"used": True}})
            return True
        else:
            keys_col.delete_one({"user_id": user_id, "key": key})
    return False

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@bot.command(name='key')
async def generate_key(ctx):
    if not await check_license(ctx.author.id):
        return await ctx.send("You are not authorized to use this command.")
    
    key = generate_random_key()
    await add_key(ctx.author.id, key)

    embed = discord.Embed(title="Key Request", color=discord.Color.blue())
    embed.add_field(name="Requestor", value=f"<@{ctx.author.id}>", inline=False)
    embed.add_field(name="On", value=f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", inline=False)
    embed.add_field(name="Key", value=f"```{key}```", inline=False)
    
    await ctx.send(embed=embed)


@bot.command(name='usekey')
async def use_key(ctx, key: str):
    if await validate_key(ctx.author.id, key):
        await ctx.send("Key used successfully.")
    else:
        await ctx.send("Invalid or expired key.")
import re
from datetime import datetime, timedelta, timezone

@bot.command(name='license')
async def manage_license(ctx, action: str, *args):
    if ctx.author.id != MY_DISCORD_ID:
        return await ctx.send("You are not authorized to use this command.")
    
    if action == 'add':
        if len(args) < 3:
            return await ctx.send("You need to provide a license type, a user ID, and a time period.")
        
        license_type = args[0].lower()
        user = args[1]
        time_period = ' '.join(args[2:])

        if license_type not in ['personal', 'enterprise']:
            return await ctx.send("Invalid license type. Use 'personal' or 'enterprise'.")
        
        try:
            user_id = int(user.strip('<@!>'))
        except ValueError:
            return await ctx.send("Invalid user ID format. Please provide a valid user ID.")
        
        
        days_match = re.match(r'(\d+)\s*days?', time_period, re.IGNORECASE)
        months_match = re.match(r'(\d+)\s*months?', time_period, re.IGNORECASE)

        if days_match:
            days = int(days_match.group(1))
            expiry_date = datetime.now(timezone.utc) + timedelta(days=days)
            formatted_time_period = f"```{days} days```"
        elif months_match:
            months = int(months_match.group(1))
            expiry_date = datetime.now(timezone.utc) + timedelta(days=months * 30)
            formatted_time_period = f"```{months} months```"
        else:
            return await ctx.send("Invalid time period. Use 'days' or 'months'.")

        if license_type == 'personal':
            licenses_col.update_one(
                {"user_id": user_id},
                {"$set": {"expiry_date": expiry_date, "license_type": "personal"}},
                upsert=True
            )
        elif license_type == 'enterprise':
            enterprise_col.update_one(
                {"owner_id": user_id},
                {"$set": {"expiry_date": expiry_date, "members": [user_id]}},
                upsert=True
            )
        
        embed = discord.Embed(title="License Addition", color=discord.Color.green())
        embed.add_field(name="User", value=f"<@{user_id}>", inline=False)
        embed.add_field(name="Executor", value=f"<@{ctx.author.id}>", inline=False)
        embed.add_field(name="License Type", value=f"```{license_type.capitalize()}```", inline=False)
        embed.add_field(name="Time Period", value=formatted_time_period, inline=False)
        embed.set_footer(text=f"Added on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

        await ctx.send(embed=embed)
    
    elif action == 'remove':
        if len(args) < 1:
            return await ctx.send("You need to provide a user ID to remove the license.")
        
        user = args[0]
        reason = ' '.join(args[1:]) if len(args) > 1 else "No reason provided"
        
        try:
            user_id = int(user.strip('<@!>'))
        except ValueError:
            return await ctx.send("Invalid user ID format. Please provide a valid user ID.")
        
        if licenses_col.find_one({"user_id": user_id}):
            licenses_col.delete_one({"user_id": user_id})
            embed = discord.Embed(title="License Removal", color=discord.Color.red())
            embed.add_field(name="License Owner", value=f"<@{user_id}>", inline=False)
            embed.add_field(name="Executor", value=f"<@{ctx.author.id}>", inline=False)
            embed.add_field(name="License Type", value="```Personal```", inline=False)
            embed.add_field(name="Reason", value=f"```{reason}```", inline=False)
            embed.set_footer(text=f"Removed on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            await ctx.send(embed=embed)
        elif enterprise_col.find_one({"owner_id": user_id}):
            enterprise_col.delete_one({"owner_id": user_id})
            embed = discord.Embed(title="License Removal", color=discord.Color.red())
            embed.add_field(name="License Owner", value=f"<@{user_id}>", inline=False)
            embed.add_field(name="Executor", value=f"<@{ctx.author.id}>", inline=False)
            embed.add_field(name="License Type", value="```Enterprise```", inline=False)
            embed.add_field(name="Reason", value=f"```{reason}```", inline=False)
            embed.set_footer(text=f"Removed on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            await ctx.send(embed=embed)
        else:
            await ctx.send("License not found.")
    else:
        await ctx.send("Invalid action. Use 'add' or 'remove'.")



@bot.command(name='addmember')
async def add_member(ctx, user: str):
    # Find the enterprise license for the current user
    enterprise_license = enterprise_col.find_one({"owner_id": ctx.author.id})
    
    if not enterprise_license:
        return await ctx.send("You do not have an enterprise license.")
    
    # Check if the command user is the license owner
    if ctx.author.id != enterprise_license['owner_id']:
        return await ctx.send("You are not authorized to use this command.")
    
    if user.isdigit():
        user_id = int(user)
    else:
        user_id = int(user.strip('<@!>'))
    
    members = enterprise_license.get('members', [])
    
    if len(members) >= 3:
        return await ctx.send("You can only add up to 3 members to your enterprise license.")
    
    if user_id in members:
        return await ctx.send("This user is already a member.")
    
    # Add the new member
    enterprise_col.update_one(
        {"owner_id": ctx.author.id},
        {"$addToSet": {"members": user_id}}
    )
    await ctx.send(f'Member <@{user_id}> added to your enterprise license.')


@bot.command(name='removemember')
async def remove_member(ctx, user: str):
    # Find the enterprise license for the current user
    enterprise_license = enterprise_col.find_one({"owner_id": ctx.author.id})
    
    if not enterprise_license:
        return await ctx.send("You do not have an enterprise license.")
    
    # Check if the command user is the license owner
    if ctx.author.id != enterprise_license['owner_id']:
        return await ctx.send("You are not authorized to use this command.")
    
    if user.isdigit():
        user_id = int(user)
    else:
        user_id = int(user.strip('<@!>'))
    
    members = enterprise_license.get('members', [])
    
    if user_id not in members:
        return await ctx.send("This user is not a member of your enterprise license.")
    
    # Remove the member
    enterprise_col.update_one(
        {"owner_id": ctx.author.id},
        {"$pull": {"members": user_id}}
    )
    await ctx.send(f'Member <@{user_id}> removed from your enterprise license.')

@bot.command(name='licenseinfo')
async def license_info(ctx: commands.Context) -> None:
    user_id = ctx.author.id
    personal_license = licenses_col.find_one({"user_id": user_id})
    enterprise_license = enterprise_col.find_one({"members": user_id})

    embed = discord.Embed(title="License Information", color=discord.Color.blue())

    if enterprise_license:
        license_type = "Enterprise"
        expiry_date = enterprise_license['expiry_date']
        if isinstance(expiry_date, datetime) and expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        time_remaining = expiry_date - datetime.now(timezone.utc)
        members = enterprise_license.get('members', [])
        owner_id = enterprise_license['owner_id']

        # Prepare member list excluding owner and command invoker
        other_members = [f"<@{member}>" for member in members if member != owner_id and member != user_id]

        if user_id == owner_id:
            # For the owner, do not include "Member Of" field
            embed.add_field(name="License Owner", value=f"<@{owner_id}>", inline=False)
            embed.add_field(name="License Type", value=f"```{license_type}```", inline=False)
            embed.add_field(name="License Status", value="✅", inline=False)
            embed.add_field(name="Time Remaining", value=f"```{str(time_remaining)}```", inline=False)
            embed.add_field(name="License Expires on", value=f"```{expiry_date.strftime('%Y-%m-%d %H:%M:%S %Z')}```", inline=False)
            embed.add_field(name="Members", value=f"{', '.join(other_members) if other_members else 'None'}", inline=False)
        else:
            # For members, include "Member" field with user tag and exclude owner and self from members list
            embed.add_field(name="Member", value=f"<@{user_id}>", inline=False)
            embed.add_field(name="License Owner", value=f"<@{owner_id}>", inline=False)
            embed.add_field(name="License Type", value=f"```{license_type}```", inline=False)
            embed.add_field(name="License Status", value="✅", inline=False)
            embed.add_field(name="Time Remaining", value=f"```{str(time_remaining)}```", inline=False)
            embed.add_field(name="License Expires on", value=f"```{expiry_date.strftime('%Y-%m-%d %H:%M:%S %Z')}```", inline=False)
            embed.add_field(name="Other Members", value=f"{', '.join(other_members) if other_members else 'None'}", inline=False)

    elif personal_license:
        license_type = "Personal"
        expiry_date = personal_license['expiry_date']
        if isinstance(expiry_date, datetime) and expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        time_remaining = expiry_date - datetime.now(timezone.utc)
        status = "✅"
        embed.add_field(name="License Owner", value=f"<@{user_id}>", inline=False)
        embed.add_field(name="License Type", value=f"```{license_type}```", inline=False)
        embed.add_field(name="License Status", value=f"{status}", inline=False)
        embed.add_field(name="Time Remaining", value=f"```{str(time_remaining)}```", inline=False)
        embed.add_field(name="License Expires on", value=f"```{expiry_date.strftime('%Y-%m-%d %H:%M:%S %Z')}```", inline=False)

    else:
        embed.add_field(name="License Status", value="`No valid license found.`", inline=False)

    embed.set_footer(text=f"Checked on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    await ctx.send(embed=embed)





@bot.tree.command(name='adddetection')
@app_commands.describe(cheat_name='Name of the cheat', hash_type='Type of hash (MD5, SHA-1, SHA-256)', hash_value='Hash value')
async def add_detection(interaction: discord.Interaction, cheat_name: str, hash_type: str, hash_value: str):
    cheat_name = cheat_name.strip()
    hash_type = hash_type.strip().upper()
    hash_value = hash_value.strip()

    valid_hash_types = ['MD5', 'SHA-1', 'SHA-256']
    if hash_type not in valid_hash_types:
        return await interaction.response.send_message(f"Invalid hash type. Valid types are: {', '.join(valid_hash_types)}", ephemeral=True)

    detections_col.update_one(
        {"cheat_name": cheat_name, "hash_type": hash_type, "hash_value": hash_value},
        {"$set": {"cheat_name": cheat_name, "hash_type": hash_type, "hash_value": hash_value}},
        upsert=True
    )

    await interaction.response.send_message(f"Detection added: {cheat_name} - {hash_type} - {hash_value}", ephemeral=True)
@bot.command(name='ping')
async def ping(ctx):
    embed = discord.Embed(
        title="Ping",
        description=f"🏓 Pong! {round(bot.latency * 1000)}ms",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Checked on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    await ctx.send(embed=embed)
    
@bot.command(name='botinfo')
async def bot_info(ctx):
    if ctx.author.id != MY_DISCORD_ID:
        return await ctx.send("You are not authorized to use this command.")

    # System and architecture information
    uname = platform.uname()
    arch = platform.architecture()[0]
    python_version = platform.python_version()
    cpu_name = platform.processor() or "Unknown CPU"
    system_name = uname.system
    node_name = uname.node
    machine = uname.machine
    release = uname.release
    version = uname.version
    platform_info = platform.platform()
    os_name = os.name

    # CPU information
    cpu_info = f"Name: {cpu_name}\nCores: {psutil.cpu_count(logical=True)}\nPhysical Cores: {psutil.cpu_count(logical=False)}"
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    cpu_stats = psutil.cpu_stats()
    cpu_cores = psutil.cpu_count(logical=False)
    cpu_info_detailed = cpuinfo.get_cpu_info()
    vendor_id = cpu_info_detailed.get('vendor_id', 'Unknown')
    brand_raw = cpu_info_detailed.get('brand_raw', 'Unknown')

    # Memory information
    svmem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Disk information
    partitions = psutil.disk_partitions()
    disk_usage = psutil.disk_usage('/')
    disk_info = '\n'.join([f"{p.device} ({p.fstype}): Total: {psutil.disk_usage(p.mountpoint).total / (1024 ** 3):.2f} GB, Free: {psutil.disk_usage(p.mountpoint).free / (1024 ** 3):.2f} GB, Used: {psutil.disk_usage(p.mountpoint).used / (1024 ** 3):.2f} GB, Usage: {psutil.disk_usage(p.mountpoint).percent}%" for p in partitions])

    # Network information
    net_io = psutil.net_io_counters()
    net_if_addrs = psutil.net_if_addrs()
    network_info = '\n'.join([f"{iface}: {', '.join([f'{addr.address} ({addr.family})' for addr in net_if_addrs[iface]])}" for iface in net_if_addrs])
    net_if_stats = psutil.net_if_stats()
    network_stats = '\n'.join([f"{iface}: {'Up' if stats.isup else 'Down'}, Speed: {stats.speed} Mbps, Duplex: {stats.duplex}, MTU: {stats.mtu}" for iface, stats in net_if_stats.items()])

    # System uptime
    uptime = time.time() - psutil.boot_time()
    days = int(uptime // (24 * 3600))
    hours = int((uptime % (24 * 3600)) // 3600)
    minutes = int((uptime % 3600) // 60)
    seconds = int(uptime % 60)

    # Load averages
    load_avg = psutil.getloadavg()  # (1, 5, 15 minutes average load)

    # Temperatures (if available)
    try:
        sensors = psutil.sensors_temperatures()
        temperature_info = '\n'.join([f"{name}: {temp.current}°C" for name, temps in sensors.items() for temp in temps])
    except AttributeError:
        temperature_info = "Temperature information not available."

    # Battery information
    try:
        battery = psutil.sensors_battery()
        battery_info = f"Percent: {battery.percent}%\nPlugged In: {'Yes' if battery.power_plugged else 'No'}\nSeconds Left: {battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else 'Unlimited'}"
    except AttributeError:
        battery_info = "Battery information not available."

    # System environment variables
    env_vars = '\n'.join([f"{key}={value}" for key, value in os.environ.items() if key.startswith('PATH') or key.startswith('HOME') or key.startswith('USER')])

    # System Boot Information
    boot_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    system_arch = platform.architecture()[0]
    machine_type = platform.machine()

    # Disk I/O statistics
    disk_io = psutil.disk_io_counters()
    
    # Python and Discord library versions
    discord_version = discord.__version__

    # GPU information
    try:
        gpus = GPUtil.getGPUs()
        gpu_info = '\n'.join([f"GPU {i}: {gpu.name}, Memory Free: {gpu.memoryFree} MB, Memory Used: {gpu.memoryUsed} MB, GPU Load: {gpu.load * 100:.2f}%, Temperature: {gpu.temperature}°C" for i, gpu in enumerate(gpus)])
    except ImportError:
        gpu_info = "No GPU information available. Install GPUtil for GPU details."

    # Detailed Process information
    processes = [f"{p.pid} - {p.name()}" for p in psutil.process_iter(['pid', 'name'])]

    # Formatting the message into chunks
    def split_message(message, max_length=4000):
        return [message[i:i+max_length] for i in range(0, len(message), max_length)]


    def split_message(message, max_length=2000):
        """Split a message into chunks of up to `max_length` characters."""
        return [message[i:i+max_length] for i in range(0, len(message), max_length)]
    
    # Create sections with titles
    sections = {
        "Bot Information": (
            f"**Bot Name:** {bot.user.name}\n"
            f"**System Name:** {system_name}\n"
            f"**Node Name:** {node_name}\n"
            f"**Machine:** {machine}\n"
            f"**Release:** {release}\n"
            f"**Version:** {version}\n"
            f"**Platform:** {platform_info}\n"
            f"**OS Name:** {os_name}\n"
            f"**Architecture:** {arch}\n"
            f"**Python Version:** {python_version}\n"
        ),
        "CPU Info": (
            f"**CPU Info:**\n"
            f"{cpu_info}\n"
            f"**CPU Detailed Info:**\n"
            f"Vendor ID: {vendor_id}\n"
            f"Model: {brand_raw}\n"
            f"Arch: {arch}\n"
            f"**CPU Frequency:** Current: {cpu_freq.current} MHz, Min: {cpu_freq.min} MHz, Max: {cpu_freq.max} MHz\n"
            f"**CPU Stats:**\n"
            f"Context Switches: {cpu_stats.ctx_switches}\n"
            f"Interrupts: {cpu_stats.interrupts}\n"
            f"Soft Interrupts: {cpu_stats.soft_interrupts}\n"
            f"System Calls: {cpu_stats.syscalls}\n"
            f"**CPU Usage:** {cpu_percent}%\n"
        ),
        "RAM": (
            f"**RAM**\n"
            f"Total: {svmem.total / (1024 ** 3):.2f} GB\n"
            f"Available: {svmem.available / (1024 ** 3):.2f} GB\n"
            f"Used: {svmem.used / (1024 ** 3):.2f} GB\n"
            f"Usage: {svmem.percent}%\n"
        ),
        "Swap": (
            f"**Swap**\n"
            f"Total: {swap.total / (1024 ** 3):.2f} GB\n"
            f"Free: {swap.free / (1024 ** 3):.2f} GB\n"
            f"Used: {swap.used / (1024 ** 3):.2f} GB\n"
            f"Usage: {swap.percent}%\n"
        ),
        "Disk Usage": (
            f"**Disk Usage**\n"
            f"Root: Total: {disk_usage.total / (1024 ** 3):.2f} GB\n"
            f"Free: {disk_usage.free / (1024 ** 3):.2f} GB\n"
            f"Used: {disk_usage.used / (1024 ** 3):.2f} GB\n"
            f"Usage: {disk_usage.percent}%\n"
        ),
        "Disk Partitions": disk_info,
        "Network": (
            f"**Network**\n"
            f"Bytes Sent: {net_io.bytes_sent / (1024 ** 2):.2f} MB\n"
            f"Bytes Received: {net_io.bytes_recv / (1024 ** 2):.2f} MB\n"
            f"Interfaces:\n{network_info}\n"
            f"Statistics:\n{network_stats}\n"
        ),
        "Uptime": (
            f"**Uptime**\n"
            f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds\n"
        ),
        "Load Averages": (
            f"**Load Averages**\n"
            f"1 min: {load_avg[0]}, 5 min: {load_avg[1]}, 15 min: {load_avg[2]}\n"
        ),
        "Temperatures": temperature_info,
        "Battery": battery_info,
        "Environment Variables": env_vars,
        "Boot Time": boot_time,
        "Current Time": current_time,
        "System Architecture": system_arch,
        "Machine Type": machine_type,
        "Disk I/O Stats": (
            f"**Disk I/O Stats:**\n"
            f"Read Count: {disk_io.read_count}\n"
            f"Write Count: {disk_io.write_count}\n"
            f"Read Bytes: {disk_io.read_bytes / (1024 ** 2):.2f} MB\n"
            f"Write Bytes: {disk_io.write_bytes / (1024 ** 2):.2f} MB\n"
        ),
        "Python Version": python_version,
        "Discord.py Version": discord_version,
        "Processes": '\n'.join(processes),
        "GPU Information": gpu_info
    }

    for title, content in sections.items():
        embed = Embed(title=title, description=content, color=0x00ff00)
        await ctx.send(embed=embed)

    
bot.run('MTI2NjI0NTA5MTk1ODMyOTM3Ng.G6nxq-.J6uec2qplRVmhodGIc-GV44EAfeT7q6nqkHkms')
