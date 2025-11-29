# Mr. Tutor Discord Bot

A Socratic teaching assistant Discord bot powered by AI. Mr. Tutor helps learners develop problem-solving skills by guiding them through questions rather than giving direct answers.

## Features

- **Socratic Teaching Method** - Guides learners with questions instead of direct answers
- **Multi-Model Support** - Choose between GPT-5-mini and Gemini-2.5-Flash models
- **Conversation Memory** - Maintains context within user sessions
- **File Attachments** - Supports images and text file uploads for context
- **Per-User History** - Each user has their own conversation history

## Commands

| Command | Description |
|---------|-------------|
| `$tut <message>` | Ask Mr. Tutor using GPT-5-mini |
| `$tutor <message>` | Same as $tut |
| `$tutplus <message>` | Ask using Gemini-2.5-Flash (web search enabled) |
| `$tutorplus <message>` | Same as $tutplus |
| `$clear` | Clear your conversation history |
| `$help` | Display help message |

## Teaching Philosophy

Mr. Tutor follows these core principles:

1. **Never give final answers** - Break problems into smaller steps
2. **Encourage participation** - Ask learners what they think
3. **Use Socratic method** - Lead with thought-provoking questions
4. **Provide structure** - Outline steps without completing them
5. **Adapt to level** - Adjust complexity based on the learner
6. **Promote confidence** - Highlight correct reasoning

## Setup

### Prerequisites

- Python 3.8+
- Discord Bot Token
- Poe API Key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/owenawsong-max/mr-tutor-discord-bot.git
cd mr-tutor-discord-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables:
```bash
export DISCORD_BOT_TOKEN="your_discord_token"
export POE_API_KEY="your_poe_api_key"
```

4. Run the bot:
```bash
python main.py
```

### Deployment

This bot is designed for deployment on Railway:

1. Fork this repository
2. Create a new Railway project
3. Connect your GitHub repository
4. Add environment variables in Railway dashboard
5. Deploy!

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token |
| `POE_API_KEY` | Your Poe API key for model access |

## Tech Stack

- **discord.py** - Discord API wrapper
- **openai** - API client for Poe
- **aiohttp** - Async HTTP for file downloads

## Usage Examples

**Asking for help with math:**
```
User: $tut How do I solve 2x + 5 = 15?
Mr. Tutor: Great question! Let's think about this step by step. 
          What operation do you think we should do first to isolate x?
```

**Using the advanced model:**
```
User: $tutplus What are the latest developments in quantum computing?
Mr. Tutor: That's a fascinating topic! Before we dive in, what do you 
          already know about quantum computing basics?
```

## License

MIT License

## Author

Created by Owen Song

---

*"The goal is not to give answers, but to teach how to find them."*
