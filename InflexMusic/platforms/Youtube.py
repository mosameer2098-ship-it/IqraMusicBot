import asyncio
import base64
import glob
import json
import os
import re
from pathlib import Path
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from InflexMusic.utils.database import is_on_off
from InflexMusic.utils.formatters import time_to_seconds


# ============================================================
# YOUTUBE COOKIES
# ============================================================

def setup_youtube_cookies():
    encoded = os.getenv("YOUTUBE_COOKIES_B64", "").strip()

    if not encoded:
        print("YOUTUBE_COOKIES_B64 is not set.")
        return

    try:
        os.makedirs("cookies", exist_ok=True)

        cookie_data = base64.b64decode(encoded)

        cookie_path = "cookies/cookies.txt"

        with open(cookie_path, "wb") as f:
            f.write(cookie_data)

        print("YouTube cookies loaded successfully.")

    except Exception as e:
        print(f"Failed to load YouTube cookies: {e}")


setup_youtube_cookies()


# ============================================================
# COOKIE FILE
# ============================================================

def cookie_txt_file():
    folder_path = os.path.join(
        os.getcwd(),
        "cookies",
    )

    txt_files = glob.glob(
        os.path.join(folder_path, "*.txt")
    )

    if not txt_files:
        raise FileNotFoundError(
            "No YouTube cookies.txt file found."
        )

    return txt_files[0]


# ============================================================
# COMMON YT-DLP OPTIONS
# ============================================================

def youtube_options():
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
    }

    cookie_file = cookie_txt_file()

    if cookie_file:
        options["cookiefile"] = cookie_file

    return options


# ============================================================
# FILE SIZE
# ============================================================

async def check_file_size(link):

    async def get_format_info(link):

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",
            cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            print(
                "yt-dlp file size error:\n"
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
        except Exception:
            return None

    def parse_size(formats):

        total_size = 0

        for fmt in formats:

            filesize = (
                fmt.get("filesize")
                or fmt.get("filesize_approx")
                or 0
            )

            try:
                total_size += int(filesize)
            except Exception:
                pass

        return total_size

    info = await get_format_info(link)

    if not info:
        return None

    formats = info.get(
        "formats",
        [],
    )

    if not formats:
        return None

    return parse_size(formats)


# ============================================================
# SHELL
# ============================================================

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
    # URL CHECK
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
    # GET URL FROM MESSAGE
    # ========================================================

    async def url(
        self,
        message_1: Message,
    ) -> Union[str, None]:

        messages = [message_1]

        if message_1.reply_to_message:
            messages.append(
                message_1.reply_to_message
            )

        text = ""
        offset = None
        length = None

        for message in messages:

            if offset:
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
            offset : offset + length
        ]

    # ========================================================
    # SEARCH
    # ========================================================

    async def search(
        self,
        query: str,
        limit: int = 1,
    ):

        loop = asyncio.get_running_loop()

        def search_sync():

            options = youtube_options()

            options.update(
                {
                    "extract_flat": True,
                    "playlistend": limit,
                }
            )

            search_url = (
                "ytsearch"
                + str(limit)
                + ":"
                + query
            )

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    search_url,
                    download=False,
                )

                return info.get(
                    "entries",
                    [],
                )

        return await loop.run_in_executor(
            None,
            search_sync,
        )

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

        if (
            not link.startswith(
                (
                    "http://",
                    "https://",
                )
            )
        ):

            results = await self.search(
                link,
                1,
            )

            if not results:
                raise ValueError(
                    "No YouTube result found."
                )

            link = (
                results[0].get("url")
                or results[0].get("webpage_url")
            )

        loop = asyncio.get_running_loop()

        def extract():

            options = youtube_options()

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                return ydl.extract_info(
                    link,
                    download=False,
                )

        info = await loop.run_in_executor(
            None,
            extract,
        )

        title = info.get(
            "title",
            "Unknown",
        )

        duration_sec = (
            info.get("duration")
            or 0
        )

        duration_sec = int(
            duration_sec
        )

        duration_min = (
            f"{duration_sec // 60}:"
            f"{duration_sec % 60:02d}"
        )

        thumbnail = (
            info.get("thumbnail")
            or ""
        )

        vidid = (
            info.get("id")
            or ""
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

        details = await self.details(
            link,
            videoid,
        )

        return details[0]

    # ========================================================
    # DURATION
    # ========================================================

    async def duration(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        details = await self.details(
            link,
            videoid,
        )

        return details[1]

    # ========================================================
    # THUMBNAIL
    # ========================================================

    async def thumbnail(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        details = await self.details(
            link,
            videoid,
        )

        return details[3]

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

        details = await self.details(
            link,
            False,
        )

        title = details[0]
        duration_min = details[1]
        thumbnail = details[3]
        vidid = details[4]

        yturl = (
            self.base + vidid
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

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",
            cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=720][width<=1280]",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = (
            await proc.communicate()
        )

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

        command = (
            "yt-dlp -i "
            "--get-id "
            "--flat-playlist "
            "--cookies "
            f'"{cookie_txt_file()}" '
            "--playlist-end "
            f"{limit} "
            "--skip-download "
            f'"{link}"'
        )

        playlist = await shell_cmd(
            command
        )

        result = [
            item.strip()
            for item in playlist.split(
                "\n"
            )
            if item.strip()
        ]

        return result

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

        loop = asyncio.get_running_loop()

        def extract():

            options = youtube_options()

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                return ydl.extract_info(
                    link,
                    download=False,
                )

        info = await loop.run_in_executor(
            None,
            extract,
        )

        formats_available = []

        for fmt in info.get(
            "formats",
            [],
        ):

            format_id = fmt.get(
                "format_id"
            )

            ext = fmt.get(
                "ext"
            )

            format_note = fmt.get(
                "format_note"
            )

            filesize = (
                fmt.get("filesize")
                or fmt.get(
                    "filesize_approx"
                )
                or 0
            )

            if not format_id or not ext:
                continue

            formats_available.append(
                {
                    "format": fmt.get(
                        "format",
                        "",
                    ),
                    "filesize": filesize,
                    "format_id": format_id,
                    "ext": ext,
                    "format_note": format_note,
                    "yturl": link,
                }
            )

        return (
            formats_available,
            link,
        )

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

        results = await self.search(
            link,
            10,
        )

        if not results:
            raise ValueError(
                "No YouTube results found."
            )

        result = results[
            query_type
        ]

        title = result.get(
            "title",
            "Unknown",
        )

        duration = result.get(
            "duration",
            "0:00",
        )

        thumbnail = result.get(
            "thumbnail"
            or "thumbnails",
            "",
        )

        if isinstance(
            thumbnail,
            list,
        ):

            thumbnail = (
                thumbnail[0]
                if thumbnail
                else ""
            )

        vidid = result.get(
            "id",
            "",
        )

        return (
            title,
            duration,
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
    ):

        if videoid:
            link = self.base + link

        os.makedirs(
            "downloads",
            exist_ok=True,
        )

        loop = asyncio.get_running_loop()

        def audio_dl():

            options = youtube_options()

            options.update(
                {
                    "format": "bestaudio/best",
                    "outtmpl": (
                        "downloads/"
                        "%(id)s.%(ext)s"
                    ),
                }
            )

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    link,
                    download=True,
                )

                video_id = info[
                    "id"
                ]

                for ext in (
                    "m4a",
                    "webm",
                    "mp3",
                    "opus",
                ):

                    path = os.path.join(
                        "downloads",
                        f"{video_id}.{ext}",
                    )

                    if os.path.exists(path):
                        return path

                return None

        def video_dl():

            options = youtube_options()

            options.update(
                {
                    "format": (
                        "bestvideo"
                        "[height<=720]"
                        "[width<=1280]"
                        "+bestaudio/"
                        "best"
                    ),
                    "outtmpl": (
                        "downloads/"
                        "%(id)s.%(ext)s"
                    ),
                    "merge_output_format": "mp4",
                }
            )

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    link,
                    download=True,
                )

                video_id = info[
                    "id"
                ]

                path = os.path.join(
                    "downloads",
                    f"{video_id}.mp4",
                )

                if os.path.exists(path):
                    return path

                return None

        def song_video_dl():

            fpath = (
                f"downloads/"
                f"{title}.%(ext)s"
            )

            options = youtube_options()

            options.update(
                {
                    "format": (
                        f"{format_id}+140"
                    ),
                    "outtmpl": fpath,
                    "prefer_ffmpeg": True,
                    "merge_output_format": "mp4",
                }
            )

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                ydl.download(
                    [link]
                )

        def song_audio_dl():

            fpath = (
                f"downloads/"
                f"{title}.%(ext)s"
            )

            options = youtube_options()

            options.update(
                {
                    "format": format_id,
                    "outtmpl": fpath,
                    "prefer_ffmpeg": True,
                    "postprocessors": [
                        {
                            "key": (
                                "FFmpegExtractAudio"
                            ),
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }
            )

            with yt_dlp.YoutubeDL(
                options
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

            fpath = (
                f"downloads/{title}.mp4"
            )

            return (
                fpath,
                True,
            )

        # ----------------------------------------------------
        # SONG AUDIO
        # ----------------------------------------------------

        if songaudio:

            await loop.run_in_executor(
                None,
                song_audio_dl,
            )

            fpath = (
                f"downloads/{title}.mp3"
            )

            return (
                fpath,
                True,
            )

        # ----------------------------------------------------
        # VIDEO
        # ----------------------------------------------------

        if video:

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

            proc = (
                await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies",
                    cookie_txt_file(),
                    "-g",
                    "-f",
                    "best[height<=720]"
                    "[width<=1280]",
                    link,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            )

            stdout, stderr = (
                await proc.communicate()
            )

            if stdout:

                return (
                    stdout.decode(
                        "utf-8",
                        "replace",
                    ).split("\n")[0],
                    False,
                )

            file_size = (
                await check_file_size(
                    link
                )
            )

            if not file_size:
                print(
                    "Unable to determine file size."
                )
                return None

            total_size_mb = (
                file_size
                / (1024 * 1024)
            )

            if total_size_mb > 350:

                print(
                    "File size "
                    f"{total_size_mb:.2f} MB "
                    "exceeds the limit."
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
        # AUDIO
        # ----------------------------------------------------

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
