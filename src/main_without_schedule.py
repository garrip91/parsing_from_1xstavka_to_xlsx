import json

import asyncio
import sqlite3
from dataclasses import dataclass
from time import sleep
import io

import aiogram
import aiohttp
from aiogram.bot import Bot
from bs4 import BeautifulSoup
from selenium import webdriver

# import schedule

from aiogram import Bot, Dispatcher, executor, filters, types

import logging

#from pyvirtualdisplay import Display

from config import TOKEN, CHANNEL_ID



#display = Display(visible=0, size=(800, 800))  
#display.start()

# Импортируем функции для обработки текста
# del_space удаляет лишние пробелы и переносы строк и заменяет их на один пробел
# remove_trash убирает данные в ссылке после "?"
from funcs import del_space, remove_trash


# Создаем класс для представления данных из таблицы с названием, описанием, ссылкой
@dataclass()
class Cards:
    title: str  # Название
    desc: str  # Описание
    url: str  # Ссылка
    
# Создаем класс для представления данных из таблицы с названием, описанием, ссылкой
@dataclass
class Galleries:
    url: str
    images: list[str]


# Указываем ID канала и токен бота
CHANNEL_ID = CHANNEL_ID
BOT_TOKEN = TOKEN

# Создаем бота
bot = Bot(token=BOT_TOKEN)



opts = webdriver.ChromeOptions()
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')



# Функция получения HTML-кода страницы
def get_whole_page(page_link: str, filename: str):
    # Открываем chrome
    with webdriver.Chrome(executable_path="./chromedriver", options=opts) as chrome:
        
        # Переходим на страницу канала в Дзене
        chrome.get(page_link)
        
        # Записываем положение вертикальной прокрутки страницы
        offset = chrome.execute_script("return window.pageYOffset;")
        while True:
            # Опускаем ползунок прокрутки до максимально нижнего состояния
            chrome.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            # Ждем подгрузки постов
            sleep(1)
            # Если положение прокрутки изменилось по сравнению с предыдущим - продолжаем прокручивать
            # При прокручивании подгружаются нижние записи, которые сохраняются в коде страницы
            # Когда мы достигнем самого низа страницы - положение прокрутки перестанет меняться и мы остановимся
            if (new_offset := chrome.execute_script("return window.pageYOffset;")) != offset:
                # Записываем новое положение прокрутки, которое мы получили в условии
                offset = new_offset
            else:
                # Прекращаем прокручивать, если достигли самого низа
                break
            
        # Если имя файла не оканчивается на html, делаем так, чтобы оканчивалось
        filename += '.html' if not filename.endswith('.html') else ''
        
        # Открываем файл на запись и сохраняем в него подгруженную страницу
        with open(filename, 'w', encoding='UTF-8') as file:
            file.write(chrome.page_source)
            
        # Закрываем chrome
        chrome.quit()
        



# В этой функции мы проходимся по всем карточкам на странице и возвращаем данные по ним
def get_page_data(filename: str):
    # Если имя g_fileа не оканчивается на html, делаем так, чтобы оканчивалось
    filename += '.html' if not filename.endswith('.html') else ''

    # Открываем g_file с html на чтение и получаем из него данные
    with open(filename, 'r', encoding='UTF-8') as file:
        html_data = file.read()

    # Преобразовываем данные в объект
    soup = BeautifulSoup(html_data, 'lxml')
    
    # Получаем список всех карточек на странице
    cards = soup.find_all('div', attrs={'class': 'card-image-2-view__content'})

    # Проходимся по всем карточкам...
    for card in reversed(cards):
	    # С помощью специального селектора выбираем необходимые нам данные (название и ссылка, верхний блок карточки)
        main_data = card.find('a', attrs={'class': 'card-image-2-view__clickable'})

        try:
            # С помощью специального селектора выбираем необходимые нам данные (название)
            title = main_data.get('aria-label')
            # С помощью специального селектора выбираем необходимые нам данные (ссылка)
            link = remove_trash(main_data.get('href'))
        except AttributeError:
            # Если карточка не содержит нужных нам данных, то это не статья и мы такое пропускаем
            continue

        try:
            # С помощью специального селектора выбираем необходимые нам данные (описание)
            desc = del_space(card.find('div', attrs={'class': 'line-clamp _clamped'}).text)
        except AttributeError:
            # Если данных нет (описание есть не везде), записываем "пустоту"
            desc = None

        # С помощью ключевого слова yield мы возвращаем не сразу весь список, а элементы по очереди (оптимизация)
        # Здесь мы превращаем три наши переменные в объект Cards, описанный выше
        yield Cards(title, desc, link)
        
        
        
# В этой функции мы проходимся по всем карточкам на странице и возвращаем данные по ним
def get_galleries_data(filename: str):
    # Если имя g_fileа не оканчивается на html, делаем так, чтобы оканчивалось
    filename += '.html' if not filename.endswith('.html') else ''

    # Открываем g_file с html на чтение и получаем из него данные
    with open(filename, 'r', encoding='UTF-8') as file:
        html_data = file.read()

    # Преобразовываем данные в объект
    soup = BeautifulSoup(html_data, 'lxml')
    # Получаем список всех карточек на странице
    galleries = soup.find_all('div', attrs={'class': 'card-gallery-base-2 _type_carousel _with-animations'})

    # Проходимся по всем карточкам...
    for gallery in reversed(galleries):
	    # С помощью специального селектора выбираем необходимые нам данные (ссылки на галереи)
        try:
            # С помощью специального селектора выбираем необходимые нам данные (ссылку)
            url = remove_trash(gallery.find('a', attrs={'class': 'card-carousel-view-2__clickable'}).get('href'))
            img = gallery.find_all('div', attrs={'class': 'zen-ui-carousel-canvas__item-position'})
            images = []
            for i in img:
                i = i.find('img').get('src')
                images.append(i)
        except AttributeError:
            # Если карточка не содержит нужных нам данных, то это не статья и мы такое пропускаем
            continue
        # С помощью ключевого слова yield мы возвращаем не сразу весь список, а элементы по очереди (оптимизация)
        # Здесь мы превращаем три наши переменные в объект Card, описанный выше
        yield Galleries(url, images)



################################################################################################################################
#                                             Отправка фотографий одним сообщением                                             #
#                                                  с описаниями в виде ссылок                                                  #
################################################################################################################################

logging.basicConfig(format=u'%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s', level=20)

# асинхронное получение данных из интернета (то же самое что requests.get, только асинхронно)
async def get_data(link: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(link) as response:
            return await response.content.read()
            
# Возвращает объект изображения по ссылке
async def get_image(link: str):
    # Получениен данных из интерета (байты)
    image_bytes = await get_data(link)
    # Преобразование байтов в поток
    image_stream = io.BytesIO(image_bytes)
    # Преобразование потока в изображение для телеграма
    return aiogram.types.InputFile(image_stream)
    
# Возвращает медиагруппу по группе ссылок
async def create_media_group(links: list[str], caption = None):
    # Создаем медиагруппу
    group = aiogram.types.MediaGroup()
    # Добавляем туда каждое изображение по ссылке, получая в i номер картинки
    for i, link in enumerate(links):
        # Если есть описание и картинка первая, то добавляем описание ей
        if caption and i == 0:
            group.attach_photo(await get_image(link), caption)
        # Иначе добавляем просто картинку
        else:
            group.attach_photo(await get_image(link))
    # Возвращаем группу
    return group
    
    
    
################################################################################################################################
################################################################################################################################
################################################################################################################################
################################################################################################################################




# Настраиваем подключение к базе данных
conn = sqlite3.connect('DATA.db')
# Настраиваем "курсор" с помощью которого будем обращаться к БД
cursor = conn.cursor()

# Получаем цикл событий asyncio (это понимать не надо, я сам до конца не понимаю)
loop = asyncio.get_event_loop()

# Указываем ссылку на канал
input_link = 'https://zen.yandex.ru/id/601d76de40f32972e4d8ce59?clid=101&country_code=ru'
# Запрашиваем идентификатор канала по которому будем записывать статьи
input_filename = 'DATA'

# Создаем таблицу по идентификатору, если ее не существует
cursor.execute(
    f"CREATE TABLE IF NOT EXISTS 'Cards' ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT DEFAULT 1,"
    "title TEXT NOT NULL,"
    "desc TEXT,"
    "url TEXT NOT NULL)"
)
cursor.execute(
    f"CREATE TABLE IF NOT EXISTS 'Galleries' ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT DEFAULT 1,"
    "url TEXT NOT NULL,"
    "images TEXT NOT NULL)"
)
        
# Записываем изменения таблицы в g_file
conn.commit()

# Получаем html с помощью функции описанной выше
get_whole_page(input_link, input_filename)
    
    

# СТАТЬИ: Проходимся по обработанным объектам, содержащим в себе название, описание и ссылку
for card_data in get_page_data(input_filename):
    # Проверяем есть ли ссылка в БД
    if cursor.execute(f"SELECT * FROM 'Cards' WHERE url=?", [card_data.url]).fetchone():
        # Если ссылка есть, то ничего не делаем
        pass
    else:
        # Если запись новая, то отправляем в канал сообщение со статьей
        loop.run_until_complete(bot.send_message(CHANNEL_ID, f'<a href="{card_data.url}">Ссылка</a>', parse_mode='HTML'))
        # Ждём 3 секунды, чтобы телегграм не забанил бота за чрезмерную активность
        sleep(3)

        # Пишем в консоль, что отправили сообщение
        print(f"Отправлено сообщение с постом {card_data.url}")

        # Добавляем статью, которой в БД не было в базу, чтобы в следующий раз ее не обрабатывать
        cursor.execute(f"INSERT INTO 'Cards' (title, desc, url) VALUES (?, ?, ?)", [card_data.title, card_data.desc, card_data.url])
        # Сохраняем изменения в базе данных
        conn.commit()

# ГАЛЕРЕИ: Проходимся по обработанным объектам, содержащим в себе название, описание и ссылку
for gallery_data in get_galleries_data(input_filename):
    # Проверяем есть ли ссылка в БД
    if cursor.execute(f"SELECT * FROM 'Galleries' WHERE url=?", [gallery_data.url]).fetchone():
        # Если ссылка есть, то ничего не делаем
        pass
    else:
        # Если запись новая, то отправляем в канал сообщение со статьей
        dp = aiogram.dispatcher.Dispatcher(bot=bot)
        media = loop.run_until_complete(create_media_group(gallery_data.images[:-1], caption=F'{gallery_data.url}'))
        loop.run_until_complete(bot.send_media_group(CHANNEL_ID, media))
        # Ждём 3 секунды, чтобы телегграм не забанил бота за чрезмерную активность
        sleep(9)

        # Пишем в консоль, что отправили сообщение
        print(f"Отправлено сообщение с медиагруппой {gallery_data.url}")

        # Добавляем галерею, которой в БД не было в базу, чтобы в следующий раз ее не обрабатывать
        cursor.execute(f"INSERT INTO 'Galleries' (url, images) VALUES (?, ?)", [gallery_data.url, json.dumps(gallery_data.images)])
        # Сохраняем изменения в базе данных
        conn.commit()
            
            
#if __name__ == '__main__':            
#    schedule.every(5).minutes.do(task_function)
#    #schedule.every().day.at("03:00").do(task_function)

#    while True:
#        schedule.run_pending()
#        sleep(1)