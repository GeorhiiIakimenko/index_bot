import logging
import aiohttp
from aiogram import Bot, types
from aiogram.dispatcher.router import Router
from aiogram.dispatcher.dispatcher import Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
import asyncio
import pandas as pd
import os
import aiofiles
import time
import requests

API_TOKEN = '7010458179:AAG5iRfYAPph_d-fSq8phkoUhP1iYBRt7v0'

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN, session=AiohttpSession())
router = Router()
router_check_index = Router()
router_start_index = Router()


@router.message(Command('start'))
async def send_welcome(message: types.Message):
    await message.answer("Send me a URL to either check its indexing status or request indexing. Use commands /check_index or /start_index followed by the URL.")

# Function to send files via HTTP directly using requests
async def send_file_via_http(chat_id, file_path, token):
    url = f'https://api.telegram.org/bot{token}/sendDocument'
    with open(file_path, 'rb') as f:
        files = {'document': f}
        data = {'chat_id': chat_id}
        response = requests.post(url, files=files, data=data)
    return response.json()


# Handler for checking index status of URLs from a text file
@router_check_index.message(Command('check_index'))
async def handle_check_index_document(message: types.Message):
    document = message.document
    if document.mime_type == 'text/plain' and document.file_name.endswith('.txt'):
        await message.answer("File received, processing...")
        file_info = await bot.get_file(document.file_id)
        file_path = os.path.join('downloaded_files', document.file_name)
        if not os.path.exists('downloaded_files'):
            os.makedirs('downloaded_files')
        await bot.download_file(file_info.file_path, destination=file_path)
        result_path = await check_indexing(file_path)
        await message.answer("Check completed, sending results.")

        if os.path.exists(result_path):
            token = bot.token  # Ensure you have access to the bot's token
            response = await send_file_via_http(message.chat.id, result_path, token)
            if response['ok']:
                await message.answer("Document sent successfully!")
            else:
                await message.answer("Failed to send document.")
        else:
            await message.answer("Error: Result file does not exist.")
    else:
        await message.answer("Please send a text file with the .txt extension.")

# Handler for simulating Googlebot visits from a text file
@router_start_index.message(Command('start_index'))
async def handle_start_index_document(message: types.Message):
    document = message.document
    if document.mime_type == 'text/plain' and document.file_name.endswith('.txt'):
        await message.answer("File received, processing...")
        file_info = await bot.get_file(document.file_id)
        file_path = os.path.join('downloaded_files', document.file_name)
        if not os.path.exists('downloaded_files'):
            os.makedirs('downloaded_files')
        await bot.download_file(file_info.file_path, destination=file_path)
        result_path = await handle_googlebot_visits(file_path)
        await message.answer("Googlebot visits completed, sending results.")

        if os.path.exists(result_path):
            token = bot.token  # Ensure you have access to the bot's token
            response = await send_file_via_http(message.chat.id, result_path, token)
            if response['ok']:
                await message.answer("Document sent successfully!")
            else:
                await message.answer("Failed to send document.")
        else:
            await message.answer("Error: Result file does not exist.")
    else:
        await message.answer("Please send a text file with the .txt extension.")


# Function to check the indexation status of URLs in a given file
async def check_indexing(filename):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36"
    }
    data = {'URL': [], 'Status': []}

    async with aiohttp.ClientSession() as session, aiofiles.open(filename, mode='r', encoding='utf-8') as f:
        urls = await f.readlines()

        for url in urls:
            url = url.strip()
            if not url:
                continue

            indexed = True  # Assume the URL is indexed initially
            if not await check_indexation(session, f'site:{url}', headers):
                indexed = False
            elif not await check_indexation(session, f'inurl:{url}', headers):
                indexed = False
            elif not await check_indexation(session, url, headers):
                indexed = False
            elif not await check_indexation(session, f'"{url}"', headers):
                indexed = False

            status = "Indexed" if indexed else "Not indexed"
            data['URL'].append(url)
            data['Status'].append(status)
            time.sleep(8)  # Delay to prevent rate limiting

    df = pd.DataFrame(data)
    df.to_excel('_results.xlsx', index=False)
    return '_results.xlsx'


# Function to simulate a Googlebot visit to a URL
async def check_indexation(session, query, headers):
    url = f'https://www.google.com/search?q={query}'
    async with session.get(url, headers=headers) as response:
        text = await response.text()
        return "No documents found" not in text


# Function to handle Googlebot visits for URLs listed in a text file
async def visit_as_googlebot(session, url):
    headers_googlebot = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36"
    }
    async with session.get(url, headers=headers_googlebot) as response:
        if response.status == 200:
            return "Visited"
        else:
            return f"Access error: HTTP {response.status}"


async def handle_googlebot_visits(file_path):
    data = {'URL': [], 'Status': []}
    async with aiohttp.ClientSession() as session, aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        urls = await f.readlines()
        for url in urls:
            url = url.strip()
            if url:
                visit_status = await visit_as_googlebot(session, url)
                data['URL'].append(url)
                data['Status'].append(visit_status)
                await asyncio.sleep(5)  # Delay to avoid rate limits

    df = pd.DataFrame(data)
    result_path = 'googlebot_visits.xlsx'
    df.to_excel(result_path, index=False)
    return result_path


async def main():
    dp = Dispatcher()
    dp.include_router(router)
    dp.include_router(router_check_index)
    dp.include_router(router_start_index)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
