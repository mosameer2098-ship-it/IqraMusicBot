import asyncio
import os
import shutil
import socket
from datetime import datetime

import urllib3
from pyrogram import filters

import config
from config import OWNER_ID
from InflexMusic import app
from InflexMusic.misc import HAPP, SUDOERS, XCB
from InflexMusic.utils.database import (
    get_active_chats,
    remove_active_chat,
    remove_active_video_chat,
)
from InflexMusic.utils.decorators.language import language
from InflexMusic.utils.pastebin import InflexBin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


async def is_heroku():
    return "heroku" in socket.getfqdn()


@app.on_message(filters.command(["getlog", "logs", "getlogs"]) & filters.user(OWNER_ID))
@language
async def log_(client, message, _):
    try:
        await message.reply_document(document="log.txt")
    except:
        await message.reply_text(_["server_1"])


