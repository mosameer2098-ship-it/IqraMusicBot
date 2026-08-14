import asyncio
import os
import re
import json
import base64
from typing import Union
from pathlib import Path

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from InflexMusic.utils.database import is_on_off
from InflexMusic.utils.formatters import time_to_seconds


# ============================================================
# YOUTUBE COOKIES
# ============================================================

COOKIE_DIR = Path("cookies")
COOKIE_FILE = COOKIE_DIR / "cookies.txt"


def setup_youtube_cookies():
    encoded = os.getenv("YOUTUBE_COOKIES_B64")

    if not encoded:
        print(
            "WARNING: YOUTUBE_COOKIES_B64 not found. "
            "Using YouTube without cookies."
        )
        return False

    try:
        COOKIE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        encoded = encoded.strip()

        cookie_data = base64.b64decode(
            encoded,
            validate=True,
        )

        with open(
            COOKIE_FILE,
            "wb",
        ) as f:
            f.write(cookie_data)

        if (
            COOKIE_FILE.exists()
            and COOKIE_FILE.stat().st_size > 0
        ):
            print(
                "YouTube cookies loaded successfully: "
                f"{COOKIE_FILE} "
                f"({COOKIE_FILE.stat().st_size} bytes)"
            )
            return True

        print(
            "WARNING: YouTube cookies file is empty."
        )
        return False

    except Exception as e:
        print(
            f"WARNING: Failed to load YouTube cookies: {e}"
        )
        return False


setup_youtube_cookies()


def cookie_txt_file():
    """
    Return cookies file path if available.
    Otherwise return None.
    """

    if (
        COOKIE_FILE.exists()
        and COOKIE_FILE.stat().st_size > 0
    ):
        return str(COOKIE_FILE)

    return None


def youtube_options(extra=None):
    """
    Create yt-dlp options.

    Cookies are optional.
    """

    options = {
        "geo_bypass": True,
        "nocheckcertificate": True,
        "quiet": True,
        "no_warnings": True,
    }

    cookie_file = cookie_txt_file()

    if cookie_file:
        options["cookiefile"] = cookie_file

    if extra:
        options.update(extra)

    return options


def youtube_command_args():
    """
    Return optional yt-dlp cookie arguments.
    """

    cookie_file = cookie_txt_file()

    if cookie_file:
        return [
            "--cookies",
            cookie_file,
        ]

    return []


# ============================================================
# COMMON HELPERS
# ============================================================

async def check_file_size(link):

    async def get_format_info(link):

        command = [
            "yt-dlp",
            *youtube_command_args(),
            "-J",
            link,
        ]

        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:

            print(
                "YouTube format info error:\n"
                + stderr.decode(
                    "utf-8",
                    "replace",
                )
            )

            return None

        try:

            return json.loads(
                stdout.decode(
                    "utf-8",
                    "replace",
                )
            )

        except Exception as e:

            print(
                f"YouTube JSON parse error: {e}"
            )

            return None

    def parse_size(formats):

        total_size = 0

        for fmt in formats:

            filesize = fmt.get(
                "filesize"
            )

            if filesize:
                total_size += filesize

        return total_size

    info = await get_format_info(link)

    if info is None:
        return None

    formats = info.get(
        "formats",
        [],
    )

    if not formats:

        print(
            "YouTube: No formats found."
        )

        return None

    return parse_size(formats)


async def shell_cmd(cmd):

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    out, errorz = await proc.communicate()

    if errorz:

        error_text = errorz.decode(
            "utf-8",
            "replace",
        )

        if (
            "unavailable videos are hidden"
            in error_text.lower()
        ):
            return out.decode(
                "utf-8",
                "replace",
            )

        return error_text

    return out.decode(
        "utf-8",
        "replace",
    )


# ============================================================
# YOUTUBE API
# ============================================================

class YouTubeAPI:

    def __init__(self):

        self.base = (
            "https://www.youtube.com/watch?v="
        )

        self.regex = (
            r"(?:youtube\.com|youtu\.be)"
        )

        self.status = (
            "https://www.youtube.com/oembed?url="
        )

        self.listbase = (
            "https://youtube.com/playlist?list="
        )

        self.reg = re.compile(
            r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
        )

    # ========================================================
    # EXISTS
    # ========================================================

    async def exists(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.base + link

        return bool(
            re.search(
                self.regex,
                link,
            )
        )

    # ========================================================
    # URL
    # ========================================================

    async def url(
        self,
        message_1: Message,
    ) -> Union[str, None]:

        messages = [
            message_1
        ]

        if message_1.reply_to_message:

            messages.append(
                message_1.reply_to_message
            )

        text = ""
        offset = None
        length = None

        for message in messages:

            if offset is not None:
                break

            if message.entities:

                for entity in message.entities:

                    if (
                        entity.type
                        == MessageEntityType.URL
                    ):

                        text = (
                            message.text
                            or message.caption
                            or ""
                        )

                        offset = entity.offset
                        length = entity.length

                        break

            elif message.caption_entities:

                for entity in message.caption_entities:

                    if (
                        entity.type
                        == MessageEntityType.TEXT_LINK
                    ):

                        return entity.url

        if offset is None:
            return None

        return text[
            offset:
            offset + length
        ]

    # ========================================================
    # DETAILS
    # ========================================================

    async def details(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1,
        )

        result_data = await results.next()

        if not result_data.get("result"):
            raise ValueError(
                "No YouTube search result found."
            )

        result = result_data["result"][0]

        title = result["title"]

        duration_min = result.get(
            "duration"
        )

        thumbnail = (
            result["thumbnails"][0]["url"]
            .split("?")[0]
        )

        vidid = result["id"]

        if (
            duration_min is None
            or str(duration_min) == "None"
        ):
            duration_sec = 0

        else:

            duration_sec = int(
                time_to_seconds(
                    duration_min
                )
            )

        return (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid,
        )

    # ========================================================
    # TITLE
    # ========================================================

    async def title(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1,
        )

        result_data = await results.next()

        if not result_data.get("result"):
            raise ValueError(
                "No YouTube result found."
            )

        return result_data["result"][0]["title"]

    # ========================================================
    # DURATION
    # ========================================================

    async def duration(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1,
        )

        result_data = await results.next()

        if not result_data.get("result"):
            raise ValueError(
                "No YouTube result found."
            )

        return result_data["result"][0]["duration"]

    # ========================================================
    # THUMBNAIL
    # ========================================================

    async def thumbnail(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1,
        )

        result_data = await results.next()

        if not result_data.get("result"):
            raise ValueError(
                "No YouTube result found."
            )

        return (
            result_data["result"][0]["thumbnails"][0]["url"]
            .split("?")[0]
        )

    # ========================================================
    # VIDEO DIRECT URL
    # ========================================================

    async def video(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        command = [
            "yt-dlp",
            *youtube_command_args(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
        ]

        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if stdout:

            return (
                1,
                stdout.decode(
                    "utf-8",
                    "replace",
                ).split("\n")[0],
            )

        return (
            0,
            stderr.decode(
                "utf-8",
                "replace",
            ),
        )

    # ========================================================
    # PLAYLIST
    # ========================================================

    async def playlist(
        self,
        link,
        limit,
        user_id,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.listbase + link

        if "&" in link:
            link = link.split("&")[0]

        cookie_args = " ".join(
            f'"{arg}"'
            for arg in youtube_command_args()
        )

        command = (
            "yt-dlp -i "
            "--get-id "
            "--flat-playlist "
            f"{cookie_args} "
            f"--playlist-end {limit} "
            "--skip-download "
            f'"{link}"'
        )

        playlist = await shell_cmd(
            command
        )

        result = []

        for key in playlist.split("\n"):

            key = key.strip()

            if key:
                result.append(key)

        return result

    # ========================================================
    # TRACK
    # ========================================================

    async def track(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1,
        )

        result_data = await results.next()

        if not result_data.get("result"):

            raise ValueError(
                "No YouTube search result found."
            )

        result = result_data["result"][0]

        title = result["title"]

        duration_min = result.get(
            "duration"
        )

        vidid = result["id"]

        yturl = result["link"]

        thumbnail = (
            result["thumbnails"][0]["url"]
            .split("?")[0]
        )

        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }

        return (
            track_details,
            vidid,
        )

    # ========================================================
    # FORMATS
    # ========================================================

    async def formats(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        ytdl_opts = youtube_options()

        try:

            with yt_dlp.YoutubeDL(
                ytdl_opts
            ) as ydl:

                formats_available = []

                r = ydl.extract_info(
                    link,
                    download=False,
                )

                for fmt in r.get(
                    "formats",
                    [],
                ):

                    if (
                        "dash"
                        in str(
                            fmt.get(
                                "format",
                                "",
                            )
                        ).lower()
                    ):
                        continue

                    if not all(
                        key in fmt
                        for key in (
                            "format",
                            "format_id",
                            "ext",
                        )
                    ):
                        continue

                    formats_available.append(
                        {
                            "format": fmt.get(
                                "format"
                            ),
                            "filesize": fmt.get(
                                "filesize"
                            ),
                            "format_id": fmt.get(
                                "format_id"
                            ),
                            "ext": fmt.get(
                                "ext"
                            ),
                            "format_note": fmt.get(
                                "format_note"
                            ),
                            "yturl": link,
                        }
                    )

                return (
                    formats_available,
                    link,
                )

        except Exception as e:

            print(
                f"YouTube formats error: {e}"
            )

            raise

    # ========================================================
    # SLIDER
    # ========================================================

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=10,
        )

        result = (
            await results.next()
        ).get("result")

        if not result:

            raise ValueError(
                "No YouTube results found."
            )

        if query_type >= len(result):

            raise ValueError(
                "YouTube result index out of range."
            )

        item = result[
            query_type
        ]

        title = item["title"]

        duration_min = item.get(
            "duration"
        )

        vidid = item["id"]

        thumbnail = (
            item["thumbnails"][0]["url"]
            .split("?")[0]
        )

        return (
            title,
            duration_min,
            thumbnail,
            vidid,
        )

    # ========================================================
    # DOWNLOAD
    # ========================================================

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:

        if videoid:
            link = self.base + link

        loop = asyncio.get_running_loop()

        # ----------------------------------------------------
        # AUDIO DOWNLOAD
        # ----------------------------------------------------

        def audio_dl():

            ydl_opts = youtube_options(
                {
                    "format": "bestaudio/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                }
            )

            with yt_dlp.YoutubeDL(
                ydl_opts
            ) as ydl:

                info = ydl.extract_info(
                    link,
                    download=False,
                )

                xyz = os.path.join(
                    "downloads",
                    f"{info['id']}.{info['ext']}",
                )

                if os.path.exists(xyz):
                    return xyz

                ydl.download(
                    [link]
                )

                return xyz

        # ----------------------------------------------------
        # VIDEO DOWNLOAD
        # ----------------------------------------------------

        def video_dl():

            ydl_opts = youtube_options(
                {
                    "format": (
                        "(bestvideo[height<=?720]"
                        "[width<=?1280][ext=mp4])"
                        "+(bestaudio[ext=m4a])"
                    ),
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "merge_output_format": "mp4",
                }
            )

            with yt_dlp.YoutubeDL(
                ydl_opts
            ) as ydl:

                info = ydl.extract_info(
                    link,
                    download=False,
                )

                xyz = os.path.join(
                    "downloads",
                    f"{info['id']}.{info['ext']}",
                )

                if os.path.exists(xyz):
                    return xyz

                ydl.download(
                    [link]
                )

                return xyz

        # ----------------------------------------------------
        # SONG VIDEO
        # ----------------------------------------------------

        def song_video_dl():

            formats = (
                f"{format_id}+140"
            )

            fpath = (
                f"downloads/{title}"
            )

            ydl_opts = youtube_options(
                {
                    "format": formats,
                    "outtmpl": fpath,
                    "prefer_ffmpeg": True,
                    "merge_output_format": "mp4",
                }
            )

            with yt_dlp.YoutubeDL(
                ydl_opts
            ) as ydl:

                ydl.download(
                    [link]
                )

        # ----------------------------------------------------
        # SONG AUDIO
        # ----------------------------------------------------

        def song_audio_dl():

            fpath = (
                f"downloads/{title}.%(ext)s"
            )

            ydl_opts = youtube_options(
                {
                    "format": format_id,
                    "outtmpl": fpath,
                    "prefer_ffmpeg": True,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }
            )

            with yt_dlp.YoutubeDL(
                ydl_opts
            ) as ydl:

                ydl.download(
                    [link]
                )

        # ----------------------------------------------------
        # SONG VIDEO
        # ----------------------------------------------------

        if songvideo:

            await loop.run_in_executor(
                None,
                song_video_dl,
            )

            return (
                f"downloads/{title}.mp4"
            )

        # ----------------------------------------------------
        # SONG AUDIO
        # ----------------------------------------------------

        elif songaudio:

            await loop.run_in_executor(
                None,
                song_audio_dl,
            )

            return (
                f"downloads/{title}.mp3"
            )

        # ----------------------------------------------------
        # VIDEO
        # ----------------------------------------------------

        elif video:

            if await is_on_off(1):

                downloaded_file = (
                    await loop.run_in_executor(
                        None,
                        video_dl,
                    )
                )

                return (
                    downloaded_file,
                    True,
                )

            command = [
                "yt-dlp",
                *youtube_command_args(),
                "-g",
                "-f",
                "best[height<=?720]"
                "[width<=?1280]",
                link,
            ]

            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            if stdout:

                downloaded_file = (
                    stdout.decode(
                        "utf-8",
                        "replace",
                    )
                    .split("\n")[0]
                )

                return (
                    downloaded_file,
                    False,
                )

            print(
                "YouTube direct video URL failed:\n"
                + stderr.decode(
                    "utf-8",
                    "replace",
                )
            )

            file_size = await check_file_size(
                link
            )

            if not file_size:

                print(
                    "Unable to determine YouTube file size."
                )

                return None

            total_size_mb = (
                file_size
                / (1024 * 1024)
            )

            if total_size_mb > 350:

                print(
                    f"YouTube file size "
                    f"{total_size_mb:.2f} MB "
                    f"exceeds the limit."
                )

                return None

            downloaded_file = (
                await loop.run_in_executor(
                    None,
                    video_dl,
                )
            )

            return (
                downloaded_file,
                True,
            )

        # ----------------------------------------------------
        # NORMAL AUDIO
        # ----------------------------------------------------

        else:

            downloaded_file = (
                await loop.run_in_executor(
                    None,
                    audio_dl,
                )
            )

            return (
                downloaded_file,
                True,
            )
