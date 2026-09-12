import os
import discord
from discord.ext import commands

# ==================================================
# إعدادات البوت الأساسية
# ==================================================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# إعدادات yt-dlp المتوافقة لتجاوز حماية يوتيوب
ytdl_format_options = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "ignoreerrors": True,
    "no_warnings": True,
    "extract_flat": False,
    "cookiefile": None,
}

# (يُفترض أن كلاس YTDLSource ومساعدات الـ coordinator معرفة عندك هنا في الملف)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content
    content_lower = content.lower()
    guild_id = message.guild.id if message.guild else None

    # ==================================================
    # تحكم بالصوت (مثلاً v70)
    # ==================================================
    if content_lower.startswith("v"):
        voice = message.guild.voice_client if message.guild else None

        if voice and voice.is_playing():
            try:
                vol_str = content[1:].strip()
                vol = int(vol_str)

                if 0 <= vol <= 200:
                    if hasattr(voice.source, "volume"):
                        voice.source.volume = vol / 100.0

                    await message.channel.send(
                        f"🔊 {vol}%"
                    )
                else:
                    await message.channel.send(
                        "حط رقم بين 0 و 200"
                    )
            except ValueError:
                await message.channel.send(
                    "اكتب كذا: v70"
                )
        else:
            await message.channel.send(
                "مافي أغنية شغالة!"
            )
        return

    # ==================================================
    # 5 - تشغيل أغنية
    # ش اسم الأغنية
    # p اسم الأغنية
    # ==================================================
    if (
        content.startswith("ش ")
        or content_lower.startswith("p ")
    ):
        if (
            message.guild.voice_client
            and not is_my_voice_channel(message)
        ):
            return

        query = content[2:].strip()

        if not query:
            return

        if not message.author.voice:
            await message.channel.send(
                "ادخلي روم صوتي أول!"
            )
            return

        channel = message.author.voice.channel
        voice = message.guild.voice_client

        if not voice:
            claimed = await coordinator.claim_channel(
                message.guild,
                channel,
                bot.user.id
            )

            if not claimed:
                return

            try:
                voice = await channel.connect()
            except Exception as e:
                await coordinator.release_claim(
                    message.guild.id,
                    channel.id,
                    bot.user.id
                )
                await message.channel.send(
                    f"خطأ أثناء الاتصال بالروم: {e}"
                )
                return

        if voice.channel.id != channel.id:
            return

        # حفظ حالة التشغيل (إذا كانت المعرّفات متوفرة)
        # state = guild_playback_state[guild_id]
        # state["current_url"] = query
        # state["current_position"] = 0

        async with message.channel.typing():
            try:
                player = await YTDLSource.from_url(
                    query,
                    loop=bot.loop,
                    stream=True,
                    seek_time=0
                )

                if voice.is_playing():
                    voice.stop()

                voice.play(
                    player,
                    after=lambda e:
                    print(f"Player error: {e}")
                    if e else None
                )

                await message.channel.send(
                    f"🎶 {player.title}"
                )

            except Exception as e:
                await message.channel.send(
                    f"خطأ أثناء التشغيل: {e}"
                )

        return

    await bot.process_commands(message)


# ==================================================
# تشغيل البوت
# ==================================================
bot.run(os.getenv('TOKEN'))