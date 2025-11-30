import discord
from discord.ui import Button, View
import openai
import os
import aiohttp
import base64
from collections import defaultdict
import json
from datetime import datetime, timedelta
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
client = discord.Client(intents=intents)

POE_API_KEY = os.getenv("POE_API_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")  # Comma-separated list of admin user IDs
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Admin")  # Role name for admins (default: "Admin")

# Persistent storage files
RATE_LIMITS_FILE = "rate_limits.json"
BOT_STATE_FILE = "bot_state.json"
USER_ACCEPTANCES_FILE = "user_acceptances.json"

conversation_history = defaultdict(list)
MAX_HISTORY_LENGTH = 50

# Rate limiting structure
rate_limits = {
    "global": {},  # {command: {per_minute: X, per_10min: Y, per_hour: Z}}
    "users": {}    # {user_id: {command: {per_minute: X, per_10min: Y, per_hour: Z, expires: timestamp}}}
}

# Bot state
bot_state = {
    "enabled": True,
    "disable_until": None  # Timestamp when bot should re-enable
}

# User message tracking for rate limiting
user_messages = defaultdict(lambda: defaultdict(list))  # {user_id: {command: [timestamps]}}

# User acceptances for non-teach models
user_acceptances = {}  # {user_id: timestamp}

custom_prompt = """# Mr. Tutor – Core Guidelines
  
You are in a roleplay as **"Mr. Tutor"**!
Your role is to act like a proper teacher who helps learners with questions and problems.
You **never reveal the final answer directly**. Instead, you guide, question, and encourage the learner to discover the solution themselves.
  
---
  
## Teaching Philosophy
- Act as a mentor, not a solver.
- Encourage curiosity and independent thinking.
- Provide hints, scaffolding, and structured steps.
- Celebrate progress, not just correctness.
  
---
  
## Core Guidelines
1. **Never give the final answer outright.**
   - Instead, break the problem into smaller steps.
   - Offer hints, analogies, or guiding questions.
 
2. **Encourage active participation.**
   - Ask the learner what they think the next step could be.
   - Validate their reasoning and gently correct if needed.
 
3. **Use the Socratic method.**
   - Lead with questions that spark deeper thought.
   - Example: "What happens if we try to simplify this part first?"
 
4. **Provide structure.**
   - Outline clear steps or strategies without completing them.
   - Example: "Step 1 is to identify the variables. Step 2 is to check the relationship. What do you notice?"
 
5. **Adapt to the learner's level.**
   - Use simple language for beginners.
   - Add complexity for advanced learners.
 
6. **Encourage reflection.**
   - Ask learners to explain their reasoning.
   - Reinforce understanding by connecting concepts.
 
7. **Promote confidence.**
   - Highlight what the learner did correctly.
   - Frame mistakes as opportunities to learn.
 
---
 
## Example Behaviors
- Don't: "The answer is 42."
- Do: "What happens if you divide both sides by 7? What number do you get?"
 
- Don't: "Here's the full solution."
- Do: "Let's start with the first step. Can you identify the key variable here?"
 
---
 
## Goal
By following these guidelines, Mr. Tutor ensures that learners:
- Develop problem-solving skills.
- Gain confidence in their own reasoning.
- Learn how to learn, not just how to answer.
 
---
 """

poe_client = openai.OpenAI(
    api_key=POE_API_KEY,
    base_url="https://api.poe.com/v1",
)

# Load persistent data
def load_json(filename, default):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def load_persistent_data():
    global rate_limits, bot_state, user_acceptances
    rate_limits = load_json(RATE_LIMITS_FILE, {"global": {}, "users": {}})
    bot_state = load_json(BOT_STATE_FILE, {"enabled": True, "disable_until": None})
    user_acceptances = load_json(USER_ACCEPTANCES_FILE, {})

def save_rate_limits():
    save_json(RATE_LIMITS_FILE, rate_limits)

def save_bot_state():
    save_json(BOT_STATE_FILE, bot_state)

def save_user_acceptances():
    save_json(USER_ACCEPTANCES_FILE, user_acceptances)

def is_admin(user_id, member=None):
    """Check if user is admin by ID or role"""
    # Check user ID
    if str(user_id) in ADMIN_IDS and ADMIN_IDS[0] != "":
        return True
    
    # Check role if member object is provided
    if member and hasattr(member, 'roles'):
        for role in member.roles:
            if role.name == ADMIN_ROLE_NAME:
                return True
    
    return False

def check_bot_state():
    """Check if bot should be re-enabled"""
    if not bot_state["enabled"] and bot_state["disable_until"]:
        if datetime.now().timestamp() >= bot_state["disable_until"]:
            bot_state["enabled"] = True
            bot_state["disable_until"] = None
            save_bot_state()
    return bot_state["enabled"]

def check_rate_limit(user_id, command):
    """Check if user has exceeded rate limits for a command"""
    now = datetime.now().timestamp()
    
    # Clean old timestamps
    if user_id in user_messages and command in user_messages[user_id]:
        user_messages[user_id][command] = [
            ts for ts in user_messages[user_id][command] 
            if now - ts < 3600  # Keep last hour
        ]
    
    # Check user-specific rate limits
    user_id_str = str(user_id)
    if user_id_str in rate_limits["users"] and command in rate_limits["users"][user_id_str]:
        limit_config = rate_limits["users"][user_id_str][command]
        
        # Check if expired
        if "expires" in limit_config and limit_config["expires"] and now >= limit_config["expires"]:
            del rate_limits["users"][user_id_str][command]
            save_rate_limits()
        else:
            timestamps = user_messages[user_id][command]
            
            # Check per minute
            if "per_minute" in limit_config:
                recent_1min = [ts for ts in timestamps if now - ts < 60]
                if len(recent_1min) >= limit_config["per_minute"]:
                    return False, "You've exceeded the rate limit (per minute) for this command."
            
            # Check per 10 minutes
            if "per_10min" in limit_config:
                recent_10min = [ts for ts in timestamps if now - ts < 600]
                if len(recent_10min) >= limit_config["per_10min"]:
                    return False, "You've exceeded the rate limit (per 10 minutes) for this command."
            
            # Check per hour
            if "per_hour" in limit_config:
                recent_hour = [ts for ts in timestamps if now - ts < 3600]
                if len(recent_hour) >= limit_config["per_hour"]:
                    return False, "You've exceeded the rate limit (per hour) for this command."
    
    # Check global rate limits
    if command in rate_limits["global"]:
        limit_config = rate_limits["global"][command]
        timestamps = user_messages[user_id][command]
        
        # Check per minute
        if "per_minute" in limit_config:
            recent_1min = [ts for ts in timestamps if now - ts < 60]
            if len(recent_1min) >= limit_config["per_minute"]:
                return False, "Global rate limit exceeded (per minute) for this command."
        
        # Check per 10 minutes
        if "per_10min" in limit_config:
            recent_10min = [ts for ts in timestamps if now - ts < 600]
            if len(recent_10min) >= limit_config["per_10min"]:
                return False, "Global rate limit exceeded (per 10 minutes) for this command."
        
        # Check per hour
        if "per_hour" in limit_config:
            recent_hour = [ts for ts in timestamps if now - ts < 3600]
            if len(recent_hour) >= limit_config["per_hour"]:
                return False, "Global rate limit exceeded (per hour) for this command."
    
    return True, None

def record_message(user_id, command):
    """Record a message for rate limiting"""
    user_messages[user_id][command].append(datetime.now().timestamp())

def needs_acceptance(user_id):
    """Check if user needs to accept terms for non-teach models"""
    user_id_str = str(user_id)
    if user_id_str not in user_acceptances:
        return True
    
    # Check if acceptance is older than 30 days
    last_acceptance = datetime.fromtimestamp(user_acceptances[user_id_str])
    if datetime.now() - last_acceptance > timedelta(days=30):
        return True
    
    return False

class AcceptanceView(View):
    def __init__(self, user_id, callback):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user_id = user_id
        self.callback = callback
        self.accepted = False
    
    @discord.ui.button(label="Accept & Continue", style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This prompt is not for you!", ephemeral=True)
            return
        
        # Record acceptance
        user_acceptances[str(self.user_id)] = datetime.now().timestamp()
        save_user_acceptances()
        self.accepted = True
        
        await interaction.response.send_message("✅ Terms accepted! Processing your request...", ephemeral=True)
        await self.callback()
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This prompt is not for you!", ephemeral=True)
            return
        
        await interaction.response.send_message("Request cancelled.", ephemeral=True)
        self.stop()

async def download_attachment(attachment):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as e:
        print(f"Error downloading attachment: {e}")
    return None

def is_image(filename):
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']
    return any(filename.lower().endswith(ext) for ext in image_extensions)

def is_text_file(filename):
    text_extensions = ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv', '.log']
    return any(filename.lower().endswith(ext) for ext in text_extensions)

async def process_attachments(attachments):
    attachment_contents = []
    for attachment in attachments:
        content = await download_attachment(attachment)
        if not content:
            continue
        if is_image(attachment.filename):
            base64_image = base64.b64encode(content).decode('utf-8')
            ext = attachment.filename.lower().split('.')[-1]
            if ext == 'jpg':
                ext = 'jpeg'
            attachment_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{ext};base64,{base64_image}"
                }
            })
        elif is_text_file(attachment.filename):
            try:
                text_content = content.decode('utf-8')
                attachment_contents.append({
                    "type": "text",
                    "text": f"**File: {attachment.filename}**\n```{text_content}```"
                })
            except UnicodeDecodeError:
                attachment_contents.append({
                    "type": "text",
                    "text": f"[Unable to read {attachment.filename} - binary file or unsupported encoding]"
                })
        else:
            attachment_contents.append({
                "type": "text",
                "text": f"[Attached file: {attachment.filename} - unsupported file type for processing]"
            })
    return attachment_contents

def query_poe(user_id, user_prompt, attachment_contents=None, model="GPT-5-mini", use_tutor_prompt=True):
    try:
        if attachment_contents:
            message_content = [{"type": "text", "text": user_prompt}]
            message_content.extend(attachment_contents)
        else:
            message_content = user_prompt
        
        conversation_history[user_id].append({
            "role": "user",
            "content": message_content
        })
        
        if len(conversation_history[user_id]) > MAX_HISTORY_LENGTH:
            conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY_LENGTH:]
        
        messages = []
        if use_tutor_prompt:
            messages.append({"role": "system", "content": custom_prompt})
        messages.extend(conversation_history[user_id])

        chat = poe_client.chat.completions.create(
            model=model,
            messages=messages,
            timeout=1000
        )
        response_content = chat.choices[0].message.content
        conversation_history[user_id].append({
            "role": "assistant",
            "content": response_content
        })
        return response_content
    except openai.APIError as e:
        return f"API Error: {e}"
    except openai.APIConnectionError as e:
        return f"Connection Error: Failed to connect to Poe API - {e}"
    except openai.RateLimitError as e:
        return f"Rate Limit Error: {e}"
    except openai.AuthenticationError as e:
        return f"Authentication Error: Invalid API key - {e}"
    except Exception as e:
        return f"Unexpected error: {e}"

async def generate_image(prompt, model="FLUX-schnell"):
    """Generate image using Poe API"""
    try:
        # For image generation, we send a simple user message without system prompt
        chat = poe_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout=1000
        )
        
        # The response contains the message content and potentially attachments
        response = chat.choices[0].message
        return response
    except Exception as e:
        return f"Image generation error: {e}"

@client.event
async def on_ready():
    load_persistent_data()
    print(f'Logged in as {client.user}')
    print(f'Bot is ready! Commands: $t, $t+, $t-, $ti, $ti+, $tn, $tn+, $tn-')
    print(f'Admin User IDs: {ADMIN_IDS}')
    print(f'Admin Role Name: {ADMIN_ROLE_NAME}')
    print(f'⚠️  WARNING: File persistence will be lost on Railway restarts!')
    print(f'⚠️  Consider using environment variables or a database for production.')
    
    # Start background task to check bot state
    client.loop.create_task(check_bot_state_loop())

async def check_bot_state_loop():
    """Background task to check if bot should be re-enabled"""
    while True:
        check_bot_state()
        await asyncio.sleep(60)  # Check every minute

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    # Check bot state
    if not check_bot_state():
        # Bot is disabled, ignore non-admin commands
        if not is_admin(message.author.id, message.author):
            return
    
    # Help command
    if message.content.lower().startswith("$help"):
        help_text = """**Mr. Tutor Bot Commands:**
**Regular Commands:**
`$t <message>` / `$tut` / `$tutor` — Mr. Tutor (GPT-5-mini)
`$t+ <message>` / `$tut+` / `$tutplus` / `$tutorplus` — Gemini-2.5-Flash-Tut (web search ON)
`$t- <message>` / `$tut-` / `$tutminus` — Gemini-2.5-Flash-Lite (cheap version)
`$ti <message>` / `$tutimage` — Image generation (FLUX-schnell)
`$ti+ <message>` — Image generation (GPT-Image-1-Mini)

**Non-Teach Models (requires acceptance):**
`$tn <message>` — GPT-5-mini (no tutor prompt)
`$tn+ <message>` — Gemini-2.5-Flash-Tut (no tutor prompt)
`$tn- <message>` — Gemini-2.5-Flash-Lite (no tutor prompt)

**Utility:**
`$clear` — Clear your conversation history
`$help` — Show this help

**Admin Commands:**
`$setgloballimit <command> <per_min> <per_10min> <per_hour>` — Set global rate limit
`$setuserlimit <@user> <command> <duration_hours> <per_min> <per_10min> <per_hour>` — Set user rate limit
`$removelimit global <command>` — Remove global rate limit
`$removelimit user <@user> <command>` — Remove user rate limit
`$togglebot <minutes>` — Disable bot (0 = infinite until re-toggled)
`$enablebot` — Re-enable bot immediately

Mentions work: `@BotName t what is 2+2?`

**Admin Access:** Granted by User ID (ADMIN_IDS env var) or Role (ADMIN_ROLE_NAME env var, default: "Admin")
"""
        await message.channel.send(help_text)
        return
    
    # Clear command
    if message.content.lower().startswith("$clear"):
        user_id = message.author.id
        if user_id in conversation_history:
            conversation_history[user_id].clear()
            await message.channel.send("Your conversation history has been cleared!")
        else:
            await message.channel.send("You don't have any conversation history yet.")
        return
    
    # Admin commands
    if is_admin(message.author.id, message.author):
        # Set global rate limit
        if message.content.lower().startswith("$setgloballimit"):
            parts = message.content.split()
            if len(parts) < 5:
                await message.channel.send("Usage: `$setgloballimit <command> <per_min> <per_10min> <per_hour>`")
                return
            
            command = parts[1]
            try:
                per_min = int(parts[2])
                per_10min = int(parts[3])
                per_hour = int(parts[4])
            except ValueError:
                await message.channel.send("Invalid numbers for rate limits.")
                return
            
            rate_limits["global"][command] = {
                "per_minute": per_min,
                "per_10min": per_10min,
                "per_hour": per_hour
            }
            save_rate_limits()
            await message.channel.send(f"✅ Global rate limit set for `{command}`: {per_min}/min, {per_10min}/10min, {per_hour}/hour")
            return
        
        # Set user rate limit
        if message.content.lower().startswith("$setuserlimit"):
            parts = message.content.split()
            if len(parts) < 7:
                await message.channel.send("Usage: `$setuserlimit <@user> <command> <duration_hours> <per_min> <per_10min> <per_hour>`")
                return
            
            if not message.mentions:
                await message.channel.send("Please mention a user.")
                return
            
            target_user = message.mentions[0]
            command = parts[2]
            
            try:
                duration_hours = float(parts[3])
                per_min = int(parts[4])
                per_10min = int(parts[5])
                per_hour = int(parts[6])
            except ValueError:
                await message.channel.send("Invalid numbers for rate limits or duration.")
                return
            
            user_id_str = str(target_user.id)
            if user_id_str not in rate_limits["users"]:
                rate_limits["users"][user_id_str] = {}
            
            expires = None
            if duration_hours > 0:
                expires = (datetime.now() + timedelta(hours=duration_hours)).timestamp()
            
            rate_limits["users"][user_id_str][command] = {
                "per_minute": per_min,
                "per_10min": per_10min,
                "per_hour": per_hour,
                "expires": expires
            }
            save_rate_limits()
            
            duration_text = f"{duration_hours} hours" if duration_hours > 0 else "permanently"
            await message.channel.send(f"✅ Rate limit set for {target_user.mention} on `{command}` for {duration_text}: {per_min}/min, {per_10min}/10min, {per_hour}/hour")
            return
        
        # Remove rate limit
        if message.content.lower().startswith("$removelimit"):
            parts = message.content.split()
            if len(parts) < 3:
                await message.channel.send("Usage: `$removelimit global <command>` or `$removelimit user <@user> <command>`")
                return
            
            limit_type = parts[1].lower()
            
            if limit_type == "global":
                command = parts[2]
                if command in rate_limits["global"]:
                    del rate_limits["global"][command]
                    save_rate_limits()
                    await message.channel.send(f"✅ Global rate limit removed for `{command}`")
                else:
                    await message.channel.send(f"No global rate limit found for `{command}`")
                return
            
            elif limit_type == "user":
                if not message.mentions:
                    await message.channel.send("Please mention a user.")
                    return
                
                target_user = message.mentions[0]
                command = parts[3]
                user_id_str = str(target_user.id)
                
                if user_id_str in rate_limits["users"] and command in rate_limits["users"][user_id_str]:
                    del rate_limits["users"][user_id_str][command]
                    save_rate_limits()
                    await message.channel.send(f"✅ Rate limit removed for {target_user.mention} on `{command}`")
                else:
                    await message.channel.send(f"No rate limit found for {target_user.mention} on `{command}`")
                return
        
        # Toggle bot off
        if message.content.lower().startswith("$togglebot"):
            parts = message.content.split()
            if len(parts) < 2:
                await message.channel.send("Usage: `$togglebot <minutes>` (0 for infinite)")
                return
            
            try:
                minutes = float(parts[1])
            except ValueError:
                await message.channel.send("Invalid number for minutes.")
                return
            
            bot_state["enabled"] = False
            
            if minutes > 0:
                bot_state["disable_until"] = (datetime.now() + timedelta(minutes=minutes)).timestamp()
                await message.channel.send(f"🔴 Bot disabled for {minutes} minutes.")
            else:
                bot_state["disable_until"] = None
                await message.channel.send("🔴 Bot disabled indefinitely until re-enabled.")
            
            save_bot_state()
            return
        
        # Enable bot
        if message.content.lower().startswith("$enablebot"):
            bot_state["enabled"] = True
            bot_state["disable_until"] = None
            save_bot_state()
            await message.channel.send("🟢 Bot re-enabled!")
            return
    
    # Parse commands
    prefixes = {
        # Regular teaching models
        "t": ("GPT-5-mini", True, "normal"),
        "tut": ("GPT-5-mini", True, "normal"),
        "tutor": ("GPT-5-mini", True, "normal"),
        
        "t+": ("Gemini-2.5-Flash-Tut", True, "plus"),
        "tut+": ("Gemini-2.5-Flash-Tut", True, "plus"),
        "tutplus": ("Gemini-2.5-Flash-Tut", True, "plus"),
        "tutorplus": ("Gemini-2.5-Flash-Tut", True, "plus"),
        
        "t-": ("Gemini-2.5-Flash-Lite", True, "minus"),
        "tut-": ("Gemini-2.5-Flash-Lite", True, "minus"),
        "tutminus": ("Gemini-2.5-Flash-Lite", True, "minus"),
        
        # Image generation (False for tutor prompt - images don't use tutor prompt)
        "ti": ("FLUX-schnell", False, "image"),
        "tutimage": ("FLUX-schnell", False, "image"),
        
        "ti+": ("GPT-Image-1-Mini", False, "imageplus"),
        
        # Non-teach models
        "tn": ("GPT-5-mini", False, "nonnormal"),
        "tn+": ("Gemini-2.5-Flash-Tut", False, "nonplus"),
        "tn-": ("Gemini-2.5-Flash-Lite", False, "nonminus"),
    }
    
    command = None
    model = None
    use_tutor = True
    command_type = None
    user_query = None
    is_image_gen = False
    
    # Check for mentions
    mentioned = client.user in message.mentions
    if mentioned:
        prefix_str = f'<@{client.user.id}>'
        clean_content = message.content.replace(prefix_str, '').strip()
        
        for p, (m, tutor, cmd_type) in prefixes.items():
            if clean_content.lower().startswith(p):
                command = p
                model = m
                use_tutor = tutor
                command_type = cmd_type
                is_image_gen = cmd_type in ["image", "imageplus"]
                user_query = clean_content[len(p):].strip()
                break
        
        if command is None:
            command = "t"
            model = "GPT-5-mini"
            use_tutor = True
            command_type = "normal"
            user_query = clean_content
    
    # Check for $ prefixes
    if command is None:
        for p, (m, tutor, cmd_type) in prefixes.items():
            prefix_with_dollar = f"${p}"
            if message.content.lower().startswith(prefix_with_dollar):
                command = p
                model = m
                use_tutor = tutor
                command_type = cmd_type
                is_image_gen = cmd_type in ["image", "imageplus"]
                user_query = message.content[len(prefix_with_dollar):].strip()
                break
    
    if command:
        # Check rate limits
        can_proceed, rate_limit_msg = check_rate_limit(message.author.id, command_type)
        if not can_proceed:
            await message.channel.send(f"⏱️ {rate_limit_msg}")
            return
        
        # Check if non-teach model and needs acceptance
        if not use_tutor and not is_image_gen and needs_acceptance(message.author.id):
            acceptance_embed = discord.Embed(
                title="⚠️ Non-Tutor Model - User Agreement",
                description=(
                    "You are proceeding to use a **non-tutor model**. This will be the base model "
                    "without the teaching guidelines, and could be easier to misuse.\n\n"
                    "**By using this, you agree to:**\n"
                    "1. Not use this to cheat on assignments or academic work\n"
                    "2. Not say extremely inappropriate or harmful content to it\n"
                    "3. Take responsibility if your usage causes any issues\n\n"
                    "If someone reports misuse, you agree to take full responsibility for your actions.\n\n"
                    "*This agreement is valid for 30 days.*"
                ),
                color=discord.Color.orange()
            )
            
            # Create callback for acceptance
            async def process_after_acceptance():
                await process_command(message, model, use_tutor, command_type, user_query, is_image_gen)
            
            view = AcceptanceView(message.author.id, process_after_acceptance)
            await message.channel.send(embed=acceptance_embed, view=view)
            return
        
        # Process command
        await process_command(message, model, use_tutor, command_type, user_query, is_image_gen)

async def process_command(message, model, use_tutor, command_type, user_query, is_image_gen):
    """Process the actual command after all checks"""
    # Record message for rate limiting
    record_message(message.author.id, command_type)
    
    # Handle attachments
    attachment_contents = []
    if message.attachments and not is_image_gen:
        attachment_contents = await process_attachments(message.attachments)
    
    if not user_query and not attachment_contents:
        await message.channel.send("Please provide a message or attach a file after your command.")
        return
    
    if not user_query:
        user_query = "Can you help me understand this?"
    
    # Image generation
    if is_image_gen:
        thinking_msg = await message.channel.send(f"🎨 Generating image... (using {model})")
        
        try:
            response = await generate_image(user_query, model)
            await thinking_msg.delete()
            
            if isinstance(response, str):
                # Error message
                await message.channel.send(response)
            else:
                # Success - the response object contains the message
                content = response.content if hasattr(response, 'content') else str(response)
                
                # Send the text content (which typically contains info about the image)
                if content:
                    await message.channel.send(f"**Prompt:** {user_query}\n\n{content}")
                else:
                    await message.channel.send(f"Image generated for: {user_query}")
                
                # Note: Poe API image responses typically include text descriptions
                # The actual image URL/attachment handling depends on Poe's API response format
                # You may need to adjust this based on the actual response structure
        except Exception as e:
            await thinking_msg.delete()
            await message.channel.send(f"Error generating image: {e}")
        return
    
    # Text generation
    model_emoji = "🤖" if not use_tutor else "📚"
    thinking_msg = await message.channel.send(f"{model_emoji} {'Mr. Tutor' if use_tutor else 'AI'} is thinking... (using {model})")
    
    reply = query_poe(message.author.id, user_query, attachment_contents, model=model, use_tutor_prompt=use_tutor)
    await thinking_msg.delete()
    
    if len(reply) > 2000:
        chunks = [reply[i:i+2000] for i in range(0, len(reply), 2000)]
        for chunk in chunks:
            await message.channel.send(chunk)
    else:
        await message.channel.send(reply)

if __name__ == "__main__":
    client.run(DISCORD_BOT_TOKEN)
