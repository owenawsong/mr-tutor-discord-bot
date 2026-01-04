# Oracle Cloud Free Tier Deployment Guide

## Mr. Tutor Discord Bot - 100% Free Forever Hosting

This guide will walk you through deploying your Discord bot on Oracle Cloud's Always Free Tier for permanent, cost-free hosting.

## Prerequisites

1. Oracle Cloud Account (free tier)
2. SSH client (Windows: PuTTY or Windows PowerShell, Mac/Linux: Terminal)
3. Your Discord Bot Token
4. Your POE API Key
5. GitHub repo cloned locally or accessible

## Step 1: Complete Oracle Cloud Account Creation

1. Go to https://www.oracle.com/cloud/free/
2. Click "Start for free"
3. Fill in your details (Owen Song, Owen.aw.song@gmail.com, United States)
4. Complete the hCaptcha verification
5. Click "Verify my email"
6. Check your email for verification link and click it
7. Set up your account password and tenancy
8. Once logged in, keep the dashboard open for next steps

## Step 2: Create an Ubuntu VM Instance

### Via Oracle Cloud Console:

1. Log into Oracle Cloud Console (cloud.oracle.com)
2. Click the hamburger menu (three lines, top left)
3. Go to **Compute > Instances**
4. Click "Create Instance"
5. Configure as follows:
   - **Name**: mr-tutor-bot
   - **Compartment**: root (or your compartment)
   - **Image**: Ubuntu 22.04 (LTS)
   - **Shape**: VM.Standard.A1.Flex (ARM - included in Always Free)
   - **OCPU**: 4 (max free tier)
   - **Memory**: 24 GB (max free tier)
   - **Networking**: Create new VCN or use default
   - **SSH Key**: Download and save the private key (IMPORTANT!)
   - **Public IP**: Enabled
6. Click "Create"
7. Wait 2-5 minutes for instance to launch
8. Note down the Public IP address displayed

## Step 3: Configure Firewall Rules

1. In Oracle Cloud Console, go to **Networking > Virtual Cloud Networks**
2. Click on your VCN
3. Click on **Security Lists**
4. Click on **Default Security List**
5. Click "Add Ingress Rule"
6. Add this rule:
   - **Stateless**: No
   - **Source Type**: CIDR
   - **Source CIDR**: 0.0.0.0/0
   - **IP Protocol**: TCP
   - **Source Port Range**: All
   - **Destination Port Range**: All
   - Click "Add Ingress Rule"
7. This allows SSH access

## Step 4: SSH into Your Instance

### On Windows (PowerShell):
```powershell
# Change permissions on private key
icacls "C:\path\to\private_key.key" /inheritance:r /grant:r "%USERNAME%:F"

# SSH into instance
ssh -i "C:\path\to\private_key.key" ubuntu@YOUR_PUBLIC_IP
```

### On Mac/Linux:
```bash
# Make private key readable only by you
chmod 600 ~/private_key.key

# SSH into instance
ssh -i ~/private_key.key ubuntu@YOUR_PUBLIC_IP
```

Replace `YOUR_PUBLIC_IP` with the IP from your Oracle Cloud instance

## Step 5: Update System and Install Dependencies

Once SSH'd in, run these commands:

```bash
# Update system packages
sudo apt update
sudo apt upgrade -y

# Install Python 3.10+
sudo apt install -y python3 python3-pip python3-venv git curl wget

# Verify Python installation
python3 --version
```

## Step 6: Clone Your Bot Repository

```bash
# Create directory for bot
mkdir -p ~/discord-bot
cd ~/discord-bot

# Clone repository
git clone https://github.com/owenawsong/mr-tutor-discord-bot.git .

# List files to confirm
ls -la
```

## Step 7: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install bot dependencies
pip install -r requirements.txt
```

## Step 8: Set Up Environment Variables

```bash
# Create .env file
cat > .env << 'EOF'
DISCORD_BOT_TOKEN=your_discord_token_here
POE_API_KEY=your_poe_api_key_here
ADMIN_IDS=your_admin_id
ADMIN_ROLE_NAME=Admin
EOF

# Verify .env file created
cat .env
```

## Step 9: Test the Bot Locally

```bash
# Make sure venv is activated
source venv/bin/activate

# Run the bot
python3 main.py

# Look for output like:
# ✅ Logged in as mr-tutor#1234
# ✅ Bot is ready!

# If working, stop with Ctrl+C
```

## Step 10: Create Systemd Service (Auto-Start on Reboot)

```bash
# Create systemd service file
sudo tee /etc/systemd/system/mr-tutor-bot.service > /dev/null << 'EOF'
[Unit]
Description=Mr. Tutor Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/discord-bot
Environment="PATH=/home/ubuntu/discord-bot/venv/bin"
ExecStart=/home/ubuntu/discord-bot/venv/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable the service (auto-start on reboot)
sudo systemctl enable mr-tutor-bot

# Start the service
sudo systemctl start mr-tutor-bot

# Check status
sudo systemctl status mr-tutor-bot
```

## Step 11: Monitor the Bot

```bash
# View real-time logs
sudo journalctl -u mr-tutor-bot -f

# View last 50 lines
sudo journalctl -u mr-tutor-bot -n 50

# Check service status
sudo systemctl status mr-tutor-bot
```

## Step 12: Verify Bot is Running

1. Go to your Discord server
2. Test bot commands:
   - `$help` - should show help menu
   - `$tut hello` - should respond with tutor prompt
   - `/tutor hello` - slash commands should work
3. If bot responds, it's working!
4. Leave instance SSH session open or reconnect anytime with: `ssh -i private_key.key ubuntu@PUBLIC_IP`

## Important Commands for Future Use

```bash
# Restart the bot
sudo systemctl restart mr-tutor-bot

# Stop the bot
sudo systemctl stop mr-tutor-bot

# View logs
sudo journalctl -u mr-tutor-bot -f

# Update bot code from GitHub
cd ~/discord-bot
git pull origin main

# Restart after code update
sudo systemctl restart mr-tutor-bot
```

## Troubleshooting

### Bot Not Starting
```bash
# Check logs
sudo journalctl -u mr-tutor-bot -n 100

# Check if process is running
ps aux | grep python3
```

### SSH Connection Issues
- Verify public IP is correct: `curl https://ifconfig.me` from instance
- Check firewall rules allow SSH (port 22)
- Ensure private key has correct permissions (600)

### Bot Token Issues
```bash
# Edit .env file
nano .env

# Update your token, save (Ctrl+X, Y, Enter)
# Restart bot
sudo systemctl restart mr-tutor-bot
```

### Memory/CPU Issues
```bash
# Check resource usage
free -h  # Memory
df -h    # Disk space
top      # CPU usage
```

## Cost Summary

- **VM.Standard.A1.Flex**: FREE (4 OCPU, 24GB RAM, Always Free)
- **Outbound data transfer**: 10 TB/month FREE
- **Total cost**: $0 FOREVER

Oracle Cloud won't charge as long as you stay within Always Free limits.

## Next Steps

1. Complete Oracle Cloud account creation
2. Create Ubuntu VM instance
3. Follow SSH and deployment steps above
4. Test bot in Discord
5. Configure auto-restart service
6. Monitor with `systemctl` commands

Your bot is now deployed for 100% free, forever!
