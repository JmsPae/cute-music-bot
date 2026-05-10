from dotenv import load_dotenv
import os
import discord
import yt_dlp
import asyncio
from collections import deque

load_dotenv()

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

queues = {}

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = deque()
    return queues[guild_id]

async def play_next(voice_client, channel):
    queue = get_queue(voice_client.guild.id)
    if len(queue) == 0:
        await channel.send('Queue is empty, nothing more to play.')
        return

    url, title, user = queue.popleft()
    source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
    voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
        play_next(voice_client, channel), voice_client.loop
    ))
    await channel.send(f'{user} playing: {title}')

class Client(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith('!help'):
            await message.channel.send(f'Here is how you use the bot {message.author.mention}!```!play <URL or file>\n!next / !skip\n!stop / !clear\n!queue / !list\n!leave```')

        if message.content.startswith('!join'):
            if message.author.voice is None:
                await message.channel.send('You need to be in a voice channel first!')
                return
            channel = message.author.voice.channel
            await channel.connect()
            await message.channel.send(f'Joined {channel.name}!')

        if message.content.startswith('!queue') or message.content.startswith('!list'):
            queue = get_queue(message.guild.id)
            if len(queue) == 0:
                await message.channel.send('No more items in the queue!')
                return
            pretty_queue = "```"
            counter = 0
            for items in queue:
                counter += 1
                pretty_queue += f'{counter}: {items[1]} - queued by {items[2]}\n'
            pretty_queue += "```"
            await message.channel.send(pretty_queue)

        if message.content.startswith('!play'):
            parts = message.content.split(' ', 1)
            if len(parts) < 2:
                await message.channel.send('Please provide a URL: !play <url>')
                return
            url = parts[1]

            if message.author.voice is None:
                await message.channel.send('You need to be in a voice channel first!')
                return

            voice_client = message.guild.voice_client
            if voice_client is None:
                channel = message.author.voice.channel
                voice_client = await channel.connect()

            # Fetch stream info
            await message.channel.send('Fetching audio...')
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    stream_url = info['url']
                    title = info['title']
                except:
                    await message.channel.send('URL/File not supported')

            queue = get_queue(message.guild.id)

            if voice_client.is_playing():
                queue.append((stream_url, title, message.author))
                await message.channel.send(f'{message.author.mention} added this to queue: {title}')
            else:
                queue.append((stream_url, title, message.author))
                await play_next(voice_client, message.channel)

        if message.content.startswith('!next') or message.content.startswith('!skip'):
            voice_client = message.guild.voice_client
            if voice_client and voice_client.is_playing():
                voice_client.stop()  # triggers play_next via after callback
                await message.channel.send('Skipping...')
            else:
                await message.channel.send(f'{message.author.mention} are you dumb? Nothing is playing???') #Nothing is playing

        if message.content.startswith('!stop') or message.content.startswith('!clear'):
            voice_client = message.guild.voice_client
            if voice_client and voice_client.is_playing():
                queues[message.guild.id] = deque()  # clear queue
                voice_client.stop()
                await message.channel.send('Stopped and cleared the queue.')
            else:
                await message.channel.send(f'{message.author.mention} are you dumb? Nothing is playing???') #Nothing is playing

        if message.content.startswith('!leave'):
            voice_client = message.guild.voice_client
            if voice_client:
                queues[message.guild.id] = deque()  # clear queue
                await voice_client.disconnect()
                await message.channel.send('gn chat') # Goodbye message
            else:
                await message.channel.send("I'm not in a voice channel.")

intents = discord.Intents.default()
intents.message_content = True

client = Client(intents=intents)
client.run(os.getenv('DISCORD_TOKEN'))
