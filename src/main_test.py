import asyncio
import sqlite3
from dataclasses import dataclass
from time import sleep

from aiogram.bot import Bot
from bs4 import BeautifulSoup
from selenium import webdriver

import schedule

#from pyvirtualdisplay import Display

from config import garrip91_TOKEN, CHANNEL_ID



#display = Display(visible=0, size=(800, 800))  
#display.start()

# Импортируем функции для обработки текста
# del_space удаляет лишние пробелы и переносы строк и заменяет их на один пробел
# remove_trash убирает данные в ссылке после "?"
from funcs import del_space, remove_trash


# Создаем класс для представления данных из таблицы с названием, описанием, ссылкой
@dataclass()
class Card:
    title: str  # Название
    desc: str  # Описание
    url: str  # Ссылка


# Указываем ID канала и токен бота
CHANNEL_ID = CHANNEL_ID
BOT_TOKEN = garrip91_TOKEN



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
    # Если имя файла не оканчивается на html, делаем так, чтобы оканчивалось
    filename += '.html' if not filename.endswith('.html') else ''

    # Открываем файл с html на чтение и получаем из него данные
    with open(filename, 'r', encoding='UTF-8') as file:
        html_data = file.read()

    # Преобразовываем данные в объект
    soup = BeautifulSoup(html_data, 'lxml')
    # Получаем список всех карточек на странице
    cards = soup.find_all('div', class_='card-wrapper')

    # Проходимся по всем карточкам...
    for card in reversed(cards):
	    # С помощью специального селектора выбираем необходимые нам данные (название и ссылка, верхний блок карточки)
        main_data = card.find('a', class_='card-image-view-by-metrics__clickable') or card.find('a', class_='card-text-view__clickable')

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
            desc = del_space(card.find('span', class_='_is-ellipsis-needed').text)
        except AttributeError:
            # Если данных нет (описание есть не везде), записываем "пустоту"
            desc = None

        # С помощью ключевого слова yield мы возвращаем не сразу весь список, а элементы по очереди (оптимизация)
        # Здесь мы превращаем три наши переменные в объект Card, описанный выше
        yield Card(title, desc, link)


#def task_function(__name__='__main__'):
#    if __name__ == '__main__':

# Настраиваем подключение к базе данных
conn = sqlite3.connect('cards.db')
# Настраиваем "курсор" с помощью которого будем обращаться к БД
cursor = conn.cursor()

# Получаем цикл событий asyncio (это понимать не надо, я сам до конца не понимаю)
loop = asyncio.get_event_loop()

# Создаем бота
bot = Bot(token=BOT_TOKEN)

# Указываем ссылку на канал
input_link = 'https://zen.yandex.ru/id/601d76de40f32972e4d8ce59?clid=101&country_code=ru'
# Запрашиваем идентификатор канала по которому будем записывать статьи
input_filename = 'DATA'

# Создаем таблицу по идентификатору, если ее не существует
cursor.execute(
    f"CREATE TABLE IF NOT EXISTS {input_filename} ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT DEFAULT 1,"
    "title TEXT NOT NULL,"
    "desc TEXT,"
    "url TEXT NOT NULL)"
)
# Записываем изменения таблицы в файл
conn.commit()

# Получаем html с помощью функции описанной выше
get_whole_page(input_link, input_filename)

# Проходимся по обработанным объектам, содержащим в себе название, описание и ссылку
for card_data in get_page_data(input_filename):
    # Проверяем есть ли ссылка в БД
    if cursor.execute(f"SELECT * FROM {input_filename} WHERE url=?", [card_data.url]).fetchone():
        # Если ссылка есть, то ничего не делаем
        pass
    else:
        # Если запись новая, то отправляем в канал сообщение со статьей
        #loop.run_until_complete(bot.send_message(CHANNEL_ID, f'<b>{card_data.title}</b>\n\n{card_data.desc or ""}\n<a href="{card_data.url}">Ссылка</a>', parse_mode='HTML'))
        loop.run_until_complete(bot.send_message(CHANNEL_ID, f'<a href="{card_data.url}">Ссылка</a>', parse_mode='HTML'))
        # Ждём 3 секунды, чтобы телегграм не забанил бота за чрезмерную активность
        sleep(3)

        # Пишем в консоль, что отправили сообщение
        print(f"Отправлено сообщение с постом {card_data.url}")

        # Добавляем статью, которой в БД не было в базу, чтобы в следующий раз ее не обрабатывать
        cursor.execute(f"INSERT INTO {input_filename} (title, desc, url) VALUES (?, ?, ?)", [card_data.title, card_data.desc, card_data.url])
        # Сохраняем изменения в базе данных
        conn.commit()