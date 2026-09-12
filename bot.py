import os
import discord
from discord.ext import commands
import yt_dlp
import asyncio
import coordinator

# ==================================================
# توكن البوت
# ==================================================

TOKEN = os.getenv("TOKEN")


# ==================================================
# إعدادات البوت
# ==================================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==================================================
# إعدادات yt_dlp مع الكوكيز لتجاوز حظر يوتيوب
# ==================================================

ytdl_format_options = {
    "format": "ba/best",
    "noplaylist": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "ignoreerrors": True,
    "no_warnings": True,
    "extract_flat": False,
    "cookiefile": "cookies.txt",
}# ملف الكوكيز لتجاوز الحظر
}


def get_ffmpeg_options(seek_seconds=0):

    opts = "-vn"

    if seek_seconds > 0:
        opts += f" -ss {seek_seconds}"

    return {
        "options": opts
    }


ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


# ==================================================
# مشغل الأغاني
# ==================================================

class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(
        self,
        source,
        *,
        data,
        volume=0.5,
        seek_time=0
    ):

        super().__init__(source, volume)

        data = data or {}

        self.data = data
        self.title = data.get("title")
        self.url = data.get("url")
        self.seek_time = seek_time


    @classmethod
    async def from_url(
        cls,
        url,
        *,
        loop=None,
        stream=False,
        seek_time=0
    ):

        loop = loop or asyncio.get_running_loop()

        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(
                url,
                download=not stream
            )
        )

        if "entries" in data:
            data = data["entries"][0]

        filename = (
            data["url"]
            if stream
            else ytdl.prepare_filename(data)
        )

        return cls(
            discord.FFmpegPCMAudio(
                filename,
                **get_ffmpeg_options(seek_time)
            ),
            data=data,
            seek_time=seek_time
        )


# ==================================================
# حالة التشغيل لكل سيرفر
# ==================================================

guild_playback_state = {}


# ==================================================
# التحقق أن البوت يخدم نفس الروم
# ==================================================

def is_my_voice_channel(message):

    voice = message.guild.voice_client

    if not voice:
        return False

    if not voice.channel:
        return False

    if not message.author.voice:
        return False

    return (
        voice.channel.id
        == message.author.voice.channel.id
    )


# ==================================================
# عند تشغيل البوت
# ==================================================

@bot.event
async def on_ready():

    await coordinator.setup()

    if bot.user:

        await coordinator.release_bot(
            bot.user.id
        )

        print(
            f"✅ دخل البوت بنجاح: {bot.user}"
        )


# ==================================================
# إذا البوت طلع من الروم
# ==================================================

@bot.event
async def on_voice_state_update(
    member,
    before,
    after
):

    if (
        bot.user
        and member.id == bot.user.id
        and before.channel
        and after.channel is None
    ):

        guild_id = before.channel.guild.id

        await coordinator.release_claim(
            guild_id,
            before.channel.id,
            bot.user.id
        )

        if guild_id in guild_playback_state:

            guild_playback_state.pop(
                guild_id,
                None
            )


# ==================================================
# استقبال الرسائل
# ==================================================

@bot.event
async def on_message(message):

    # تجاهل البوتات والرسائل خارج السيرفرات
    if message.author.bot:
        return

    if not message.guild:
        return


    guild_id = message.guild.id

    content = message.content.strip()

    content_lower = content.lower()


    # القاعدة الذهبية: إذا البوت داخل روم، لا يقبل الأوامر إلا من الشخص اللي معه بنفس الروم
    voice_client = message.guild.voice_client
    if voice_client and voice_client.channel:
        if not message.author.voice or message.author.voice.channel.id != voice_client.channel.id:
            if content != "بوت" and content_lower != "join" and content != "مسح" and content_lower != "clear":
                return


    # إنشاء حالة السيرفر إذا ما كانت موجودة
    if guild_id not in guild_playback_state:

        guild_playback_state[guild_id] = {
            "current_url": None,
            "current_position": 0
        }


    # ==================================================
    # 1 - دخول الروم
    # ==================================================

    if (
        content == "بوت"
        or content_lower == "join"
    ):

        # لازم الشخص يكون داخل روم صوتي
        if not message.author.voice:

            await message.channel.send(
                "ادخلي روم صوتي أول!"
            )

            return


        channel = message.author.voice.channel

        voice = message.guild.voice_client


        # إذا البوت موجود أصلًا
        if voice:

            # إذا موجود مع الشخص بنفس الروم
            if voice.channel.id == channel.id:

                return

            # إذا البوت موجود بروم ثاني
            return


        # محاولة حجز الروم لهذا البوت
        claimed = await coordinator.claim_channel(
            message.guild,
            channel,
            bot.user.id
        )


        # إذا الروم محجوز لبوت ثاني
        if not claimed:

            return


        try:

            await channel.connect()

        except Exception as e:

            print(
                f"❌ فشل الاتصال بالروم: {e}"
            )

            await coordinator.release_claim(
                message.guild.id,
                channel.id,
                bot.user.id
            )

        return


    # ==================================================
    # 2 - إيقاف أو تخطي الأغنية (سكب) عبر "س" أو "s"
    # ==================================================

    if (
        content == "س"
        or content_lower == "s"
    ):

        if not is_my_voice_channel(message):

            return

        voice = message.guild.voice_client

        if voice and voice.is_playing():

            voice.stop()

            guild_playback_state[guild_id][
                "current_url"
            ] = None

            guild_playback_state[guild_id][
                "current_position"
            ] = 0

            await message.channel.send(
                "⏭️ تم تخطي الأغنية!"
            )

        return


    # ==================================================
    # 3 - تقديم الأغنية عبر "قد"
    # ==================================================

    if content == "قد":

        if not is_my_voice_channel(message):

            return

        voice = message.guild.voice_client

        if voice and voice.is_playing():

            await message.channel.send(
                "⏩ جاري تقديم الأغنية..."
            )

        else:

            await message.channel.send(
                "مافي أغنية شغالة حالياً!"
            )

        return


    # ==================================================
    # 4 - مسح الشات
    # ==================================================

    if (
        content == "مسح"
        or content_lower == "clear"
    ):

        try:

            deleted = await message.channel.purge(
                limit=100
            )

            await message.channel.send(
                f"تم مسح {len(deleted)} رسالة 🧹",
                delete_after=2
            )

        except Exception as e:

            await message.channel.send(
                f"خطأ في الصلاحيات: {e}"
            )

        return


    # ==================================================
    # 5 - التحكم بالصوت
    # مثال: v70
    # ==================================================

    if content_lower.startswith("v"):

        if not is_my_voice_channel(message):

            return

        voice = message.guild.voice_client

        if voice and voice.source:

            try:

                vol = int(
                    content[1:].strip()
                )

                if 0 <= vol <= 200:

                    voice.source.volume = (
                        vol / 100.0
                    )

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
    # 6 - تشغيل أغنية
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

        state = guild_playback_state[guild_id]

        state["current_url"] = query

        state["current_position"] = 0

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
                    print(
                        f"Player error: {e}"
                    )
                    if e else None
                )

                await message.channel.send(
                    f"🎶 **{player.title}**"
                )

            except Exception as e:

                await message.channel.send(
                    f"خطأ أثناء التشغيل: {e}"
                )

        return


    # ==================================================
    # أوامر Discord العادية
    # ==================================================

    await bot.process_commands(message)


# ==================================================
# تشغيل البوت
# ==================================================

bot.run(TOKEN)