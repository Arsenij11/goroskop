import asyncio
import datetime
import re
import time
from datetime import timedelta
import requests
from aiogram.enums import ParseMode
from aiogram.filters.command import Command
import aiogram
from aiogram.types import ReplyKeyboardRemove, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram import F
from TOKEN import TOKEN
import sqlite3
import logging
import zodiacs

# получение пользовательского логгера и установка уровня логирования
py_logger = logging.getLogger(__name__)
py_logger.setLevel(logging.ERROR)

# настройка обработчика и форматировщика в соответствии с нашими нуждами
py_handler = logging.FileHandler("app.txt", mode='a')
py_formatter = logging.Formatter("%(name)s %(asctime)s %(levelname)s %(message)s")

# добавление форматировщика к обработчику
py_handler.setFormatter(py_formatter)
# добавление обработчика к логгеру
py_logger.addHandler(py_handler)

# Начало логирования
py_logger.info('Start_logging: app.py')



user_status = {}
user_data = {}

WAITING_NAME = 'waiting_name'
WAITING_FOR_START = 'waiting_for_start'
WAITING_ZODIAC = 'waiting_zodiac'
WAITING_NEW_ZODIAC = 'waiting_new_zodiac'
JUST_WAIT_PLEASE = 'just wait please'

class NotEmptyData(Exception):
    pass


try:
    with sqlite3.connect('goroskop.SQLite') as f:
        cur = f.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        zodiac VARCHAR(100) NOT NULL,
        tg_id VARCHAR(50) NOT NULL UNIQUE,
        notification BOOLEAN NOT NULL DEFAULT(false)
        );
        CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id VARCHAR(50),
        message_id VARCHAR(50),
        is_last_zodiac BOOLEAN NOT NULL DEFAULT(false)
        );
        """)
except sqlite3.Error as error:
    print(f"Ошибка при создании таблиц: {error}")
    py_logger.error(f"Ошибка при создании таблиц: {error}")
else:
    print("Таблицы были успешно созданы!")


def check_data_of_users(chat_id):
    try:
        with sqlite3.connect('goroskop.SQLite') as f:
            cur = f.cursor()
            sql = cur.execute("""
            SELECT *
            FROM users
            WHERE tg_id = ? 
            """, (str(chat_id),))

            result = sql.fetchone()
    except sqlite3.Error as error:
        py_logger.error(f'Ошибка {chat_id} {error}')
    else:
        return result



# Объект бота
bot = aiogram.Bot(token=TOKEN)
# Диспетчер
dp = aiogram.Dispatcher()

async def insert_history_to_db(mes, message, is_last_zodiac=False):
    if mes is None:
        history = [(message.chat.id, message.message_id,is_last_zodiac,)]
    elif message is None:
        history = [(mes.chat.id, mes.message_id, is_last_zodiac,)]
    else:
        history = [(message.chat.id, mes.message_id , is_last_zodiac,), (message.chat.id, message.message_id,is_last_zodiac,)]
    with sqlite3.connect('goroskop.SQLite') as f:
        cur = f.cursor()
        cur.executemany("""
            INSERT INTO history(tg_id, message_id, is_last_zodiac)
            VALUES (?,?,?)
            """, history)
async def notification(message):
    time_of_notification = timedelta(hours=10 - datetime.datetime.now().hour,
                                     minutes=0 - datetime.datetime.now().minute,
                                     seconds=0 - datetime.datetime.now().second).seconds
    await asyncio.sleep(time_of_notification)
    try:
        with sqlite3.connect('goroskop.SQLite') as f:
            cur = f.cursor()
            req = cur.execute(
                """
                SELECT *
                FROM users
                WHERE tg_id = ? AND notification = true
                """, (message.chat.id,))
            resp = req.fetchone()
    except sqlite3.Error as error:
        py_logger.error(f'Ошибка {error} при рассылке ежедневного гороскопа\nПользователь chat_id - {message.chat.id}')
        mes = await message.answer('Ошибка! Не удалось прислать ежедневный гороскоп!\nВы можете сообщить '
                             'о проблеме в техподдержку <b>support@example.ru</b>', parse_mode=ParseMode.HTML)
        await insert_history_to_db(mes, message)
        await notification(message)
    else:
        if resp is not None:

            try:
                with sqlite3.connect('goroskop.SQLite') as f:
                    cur = f.cursor()
                    res = cur.execute("""
                    SELECT u.zodiac
                    FROM users AS u
                    WHERE u.tg_id = ? 
                    """, (message.chat.id,))

                    res = res.fetchone()
            except sqlite3.Error as error:
                py_logger.error(f'Ошибка {error} при рассылке ежедневного гороскопа\nПользователь chat_id - {message.chat.id}')
                mes = await message.answer('Ошибка! Не удалось прислать ежедневный гороскоп!\nВы можете сообщить '
                                     'о проблеме в техподдержку <b>support@example.ru</b>', parse_mode=ParseMode.HTML)
                await insert_history_to_db(mes, message=None)
                await notification(message)

            else:

                image = FSInputFile(f"знаки_зодиака/изображения/{res[0].lower()}.gif")
                r = requests.get(f'https://horoscopes.rambler.ru/{zodiacs.zodiac_signs_lat.get(res[0]).lower()}')
                resp = r.content.decode('utf-8')
                result = re.findall(r'<p\s+class="_5yHoW AjIPq">.*</p>', resp)[0]
                result = re.findall(r'[^<p\s+class="_5yHoW AjIPq">].*[^</p>]', result)[0]

                keyboard = InlineKeyboardBuilder()
                keyboard.add(InlineKeyboardButton(
                    text="Обновить",
                    callback_data="refresh")
                )
                only_date = re.findall(r'\d{4}-0*\d{1,2}-0*\d{1,2}', str(datetime.datetime.now()))[0]
                mes = await message.answer_photo(
                    image,
                    caption=f'Гороскоп на <b>{only_date}</b>' + '\n' + result,
                    reply_markup=keyboard.as_markup(),
                    parse_mode=ParseMode.HTML
                )
                await insert_history_to_db(mes, message=None)
                await notification(message)






@dp.message(lambda message: user_status.get(message.chat.id) is None or user_status.get(message.chat.id) ==
                            WAITING_FOR_START, Command('start'))
async def start(message):
    mes = await message.answer(f'Добро пожаловать, <b>{message.chat.username}</b>\nДанный бот отправляет информацию о гороскопе\n'
                         f'Для получения дополнительной информации введите команду /info', parse_mode=ParseMode.HTML)

    await insert_history_to_db(mes,message)



@dp.message(lambda message: user_status.get(message.chat.id) is None or user_status.get(message.chat.id) ==
                            WAITING_FOR_START, Command('info'))
async def info(message):
    mes = await message.answer('Данный бот отправляет информацию о гороскопе.\n'
                               'Чтобы зарегистрироваться, введите команду /registration\n'
                               'Чтобы подписаться на ежедневную рассылку, введите /subscribe\n'
                               'Чтобы отписаться от ежедневной рассылки, введите /unsubscribe\n'
                               'Чтобы обновить информацию о знаке зодиака, введите /update\n'
                               'Чтобы сменить знак зодиака, введите /change_zodiac\n'
                               'Чтобы очистить историю сообщений, введите /clear_history')

    await insert_history_to_db(mes,message)


@dp.message(lambda message: user_status.get(message.chat.id) is None or user_status.get(message.chat.id) ==
                            WAITING_FOR_START, Command('registration'))
async def registration(message):
    try:
        checking = check_data_of_users(message.chat.id)
        if checking is not None:
            raise NotEmptyData
    except NotEmptyData as error:
        mes = await message.answer('Вы уже зарегистрированы!')
        await insert_history_to_db(mes,message)
    else:
        user_status[message.chat.id] = WAITING_NAME
        mes = await message.answer('Введите своё имя!\nОно должно состоять не более, чем из 100 символов')
        await insert_history_to_db(mes, message)



@dp.message(lambda message: user_status.get(message.chat.id) == WAITING_NAME)
async def get_name(message):
    if len(message.text) > 100:
        mes = await message.reply('Ошибка! Имя должно состоять не более, чем из 100 символов')
        await insert_history_to_db(mes, message)
    else:

        user_data[message.chat.id] = {'Имя' : message.text}
        kbrd = ReplyKeyboardBuilder()
        for e, z in zodiacs.zodiac_signs.items():
            kbrd.add(aiogram.types.KeyboardButton(text=f'{e} - {z}'))
        kbrd.adjust(3)
        user_status[message.chat.id] = WAITING_ZODIAC
        mes = await message.answer('Введите Ваш знак зодиака!\nВведите значение с <b>клавиатуры</b>! Другое '
                             'значение <b><i>не будет засчитано</i></b>!!!',
                             reply_markup = kbrd.as_markup(resize_keyboard=True), parse_mode=ParseMode.HTML)
        await insert_history_to_db(mes, message)



@dp.message(lambda message: user_status.get(message.chat.id) == WAITING_ZODIAC)
async def get_zodiac(message):

    get_emoji = False
    for emoji,zodiac in zodiacs.zodiac_signs.items():
        if message.text == f'{emoji} - {zodiac}':
            user_data[message.chat.id].update({'знак зодиака' : zodiac})
            get_emoji = True
            break

    if not get_emoji:
        mes = await message.reply('Ошибка! Введите значение с <b>клавиатуры</b>!',
                            parse_mode=ParseMode.HTML)
        await insert_history_to_db(mes, message)
    else:
        try:
            with sqlite3.connect('goroskop.SQLite') as f:
                cur = f.cursor()
                cur.execute("""
                INSERT INTO users (name, zodiac, tg_id)
                VALUES (?,?,?)
                """, (user_data[message.chat.id]['Имя'], user_data[message.chat.id]['знак зодиака'], message.chat.id))
        except sqlite3.Error as error:
            print(f'Ошибка при внесении данных в БД {error}\n'
                  f'Пользователь {message.chat.id}')
            py_logger.error(f'Ошибка при внесении данных в БД {error}\n'
                            f'Пользователь {message.chat.id}')
            mes = await message.answer('Произошла ошибка при регистрации!\nПопробуйте зарегистрироваться ещё раз /registration\n'
                                 'Если ошибка не пропадёт, напишите нам на почту support@example.com',
                                  reply_markup=ReplyKeyboardRemove())
            await insert_history_to_db(mes, message)
            user_data[message.chat.id] = None
            user_status[message.chat.id] = WAITING_FOR_START
        else:
            user_status[message.chat.id] = JUST_WAIT_PLEASE

            mes = await message.answer('Поздравляем! Вы успешно зарегистрировались!', reply_markup=ReplyKeyboardRemove())
            await insert_history_to_db(mes, message)

            image = FSInputFile(f"знаки_зодиака/изображения/{user_data[message.chat.id]['знак зодиака'].lower()}.gif")
            with open(f'знаки_зодиака/описание/{user_data[message.chat.id]["знак зодиака"].lower()}.txt', mode='rt', encoding='utf-8') as f:
                caption = f.read()

            mes = await message.answer_photo(image,caption=re.findall(r'.*',caption)[0])
            await insert_history_to_db(mes, message=None, is_last_zodiac=True)

            result = None
            for ru, lat in zodiacs.zodiac_signs_lat.items():
                if ru == user_data[message.chat.id]['знак зодиака']:
                    r = requests.get(f'https://horoscopes.rambler.ru/{lat.lower()}/')
                    resp = r.content.decode('utf-8')
                    result = re.findall(r'<p\s+class="_5yHoW AjIPq">.*</p>', resp)[0]
                    break



            result = re.findall(r'[^<p\s+class="_5yHoW AjIPq">].*[^</p>]',result)[0]


            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(
                text="Обновить",
                callback_data="refresh")
            )

            only_date = re.findall(r'\d{4}-0*\d{1,2}-0*\d{1,2}', str(datetime.datetime.now()))[0]
            mes = await message.answer_photo(
                image,
                caption= f'Гороскоп на <b>{only_date}</b>' + '\n' + result + '\nЧтобы подписаться на ежедневную рассылку '
                                                                            'с информацией о гороскопе, введите /subscribe',
                reply_markup=keyboard.as_markup(),
                parse_mode=ParseMode.HTML
            )
            await insert_history_to_db(mes, message=None)

            user_status[message.chat.id] = WAITING_FOR_START

@dp.callback_query(F.data == 'refresh')
async def refresh(callback):
    try:
        with sqlite3.connect('goroskop.SQLite') as f:
            cur = f.cursor()
            res = cur.execute("""
            SELECT u.zodiac
            FROM users AS u
            WHERE u.tg_id = ? 
            """, (callback.from_user.id,))

            res = res.fetchone()
    except sqlite3.Error as error:
        py_logger.error(f'Ошибка {error} при обновлении гороскопа\nchat_id - {callback.from_user.id}')
        await callback.answer('Ошибка! не удалось обновить гороскоп!')
        mes = await callback.message.answer('Произошла ошибка при обновлении гороскопа!')
        await insert_history_to_db(mes, message=None)
    else:
        if res is None:
            await callback.answer('Ошибка! Ваш аккаунт был удалён!')
        else:
            image = FSInputFile(f"знаки_зодиака/изображения/{res[0].lower()}.gif")
            r = requests.get(f'https://horoscopes.rambler.ru/{zodiacs.zodiac_signs_lat.get(res[0]).lower()}')
            resp = r.content.decode('utf-8')
            result = re.findall(r'<p\s+class="_5yHoW AjIPq">.*</p>', resp)[0]
            result = re.findall(r'[^<p\s+class="_5yHoW AjIPq">].*[^</p>]', result)[0]

            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(
                text="Обновить",
                callback_data="refresh")
            )
            await callback.answer('Гороскоп обновлён')
            only_date = re.findall(r'\d{4}-0*\d{1,2}-0*\d{1,2}', str(datetime.datetime.now()))[0]
            mes = await callback.message.answer_photo(
                image,
                caption=f'Гороскоп на <b>{only_date}</b>' + '\n' + result + '\nЧтобы подписаться на ежедневную рассылку '
                                                                            'с информацией о гороскопе, введите /subscribe',
                reply_markup=keyboard.as_markup(),
                parse_mode=ParseMode.HTML
            )
            await insert_history_to_db(mes, message=None)

@dp.message(lambda message: user_status.get(message.chat.id) is None or user_status.get(message.chat.id) ==
                            WAITING_FOR_START, Command('update'))
async def update(message):
    try:
        with sqlite3.connect('goroskop.SQLite') as f:
            cur = f.cursor()
            res = cur.execute("""
               SELECT u.zodiac
               FROM users AS u
               WHERE u.tg_id = ? 
               """, (message.chat.id,))

            res = res.fetchone()
    except sqlite3.Error as error:
        py_logger.error(f'Ошибка {error} при обновлении гороскопа\nchat_id - {message.chat.id}')
        mes = await message.answer('Произошла ошибка при обновлении гороскопа!')
        await insert_history_to_db(mes, message)
    else:
        if res is None:
            mes = await message.answer('Ошибка! Ваш аккаунт был удалён или его ещё не существует!\n'
                                       'Чтобы зарегистрироваться, введите команду /registration')
            await insert_history_to_db(mes, message)
        else:
            user_status[message.chat.id] = JUST_WAIT_PLEASE

            image = FSInputFile(f"знаки_зодиака/изображения/{res[0].lower()}.gif")
            r = requests.get(f'https://horoscopes.rambler.ru/{zodiacs.zodiac_signs_lat.get(res[0]).lower()}')
            resp = r.content.decode('utf-8')
            result = re.findall(r'<p\s+class="_5yHoW AjIPq">.*</p>', resp)[0]
            result = re.findall(r'[^<p\s+class="_5yHoW AjIPq">].*[^</p>]', result)[0]

            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(
                text="Обновить",
                callback_data="refresh")
            )
            only_date = re.findall(r'\d{4}-0*\d{1,2}-0*\d{1,2}', str(datetime.datetime.now()))[0]
            mes = await message.answer_photo(
                image,
                caption=f'Гороскоп на <b>{only_date}</b>' + '\n' + result + '\nЧтобы подписаться на ежедневную рассылку '
                                                                            'с информацией о гороскопе, введите /subscribe',
                reply_markup=keyboard.as_markup(),
                parse_mode=ParseMode.HTML
            )
            await insert_history_to_db(mes, message)

            user_status[message.chat.id] = WAITING_FOR_START


@dp.message(lambda message: user_status.get(message.chat.id) is None or user_status.get(message.chat.id) ==
                            WAITING_FOR_START, Command('change_zodiac'))
async def change_zodiac(message):
    try:
        with sqlite3.connect('goroskop.SQLite') as f:
            cur = f.cursor()
            res = cur.execute("""
               SELECT zodiac
               FROM users 
               WHERE tg_id = ? 
               """, (message.chat.id,))

            res = res.fetchone()
    except sqlite3.Error as error:
        py_logger.error(f'Ошибка {error} при обновлении знака зодиака\nchat_id - {message.chat.id}')
        mes = await message.answer('Произошла ошибка при обновлении знака зодиака!\n'
                             'Попробуйте ещё раз ввести команду /change_zodiac')
        await insert_history_to_db(mes, message)
    else:
        if res is None:
            await message.answer('Ошибка! Вы ещё не регистрировались!\n'
                                 'Чтобы зарегистрироваться, введите команду /registration')
        else:
            kbrd = ReplyKeyboardBuilder()
            for e, z in zodiacs.zodiac_signs.items():
                kbrd.add(aiogram.types.KeyboardButton(text=f'{e} - {z}'))
            kbrd.adjust(3)
            user_status[message.chat.id] = WAITING_NEW_ZODIAC
            mes = await message.answer('Введите Ваш знак зодиака!\nВведите значение с <b>клавиатуры</b>! Другое '
                                 'значение <b><i>не будет засчитано</i></b>!!!',
                                 reply_markup=kbrd.as_markup(resize_keyboard=True), parse_mode=ParseMode.HTML)
            await insert_history_to_db(mes, message)


@dp.message(lambda message: user_status.get(message.chat.id) == WAITING_NEW_ZODIAC)
async def waiting_new_zodiac (message):
        get_emoji = False
        for emoji, zodiac in zodiacs.zodiac_signs.items():
            if message.text == f'{emoji} - {zodiac}':
                new_zodiac = zodiac
                get_emoji = True
                break

        if not get_emoji:
            mes = await message.reply('Ошибка! Введите значение с <b>клавиатуры</b>!',
                                parse_mode=ParseMode.HTML)
            await insert_history_to_db(mes, message)
        else:
            try:
                with sqlite3.connect('goroskop.SQLite') as f:
                    cur = f.cursor()
                    res = cur.execute("""
                       UPDATE users
                       SET zodiac = ?
                       WHERE tg_id = ? 
                       """, (new_zodiac, message.chat.id,))

            except sqlite3.Error as error:
                py_logger.error(f'Ошибка {error} при обновлении знака зодиака\nchat_id - {message.chat.id}')
                user_status[message.chat.id] = WAITING_FOR_START
                mes = await message.answer('Произошла ошибка при обновлении знака зодиака!\n'
                                     'Попробуйте ещё раз ввести команду /change_zodiac\n'
                                     'Если ошибка повториться, напишите в техподдержку support@example.ru')
                await insert_history_to_db(mes, message)
            else:
                user_status[message.chat.id] = JUST_WAIT_PLEASE

                mes = await message.answer('Знак зодиака был успешно сменён!', reply_markup=ReplyKeyboardRemove())
                await insert_history_to_db(mes, message)

                image = FSInputFile(
                    f"знаки_зодиака/изображения/{new_zodiac.lower()}.gif")
                with open(f'знаки_зодиака/описание/{new_zodiac.lower()}.txt', mode='rt',
                          encoding='utf-8') as f:
                    caption = f.read()

                mes = await message.answer_photo(image, caption=re.findall(r'.*', caption)[0])
                await insert_history_to_db(mes, message=None, is_last_zodiac=True)

                result = None
                for ru, lat in zodiacs.zodiac_signs_lat.items():
                    if ru == new_zodiac:
                        r = requests.get(f'https://horoscopes.rambler.ru/{lat.lower()}/')
                        resp = r.content.decode('utf-8')
                        result = re.findall(r'<p\s+class="_5yHoW AjIPq">.*</p>', resp)[0]
                        break

                result = re.findall(r'[^<p\s+class="_5yHoW AjIPq">].*[^</p>]', result)[0]

                keyboard = InlineKeyboardBuilder()
                keyboard.add(InlineKeyboardButton(
                    text="Обновить",
                    callback_data="refresh")
                )

                only_date = re.findall(r'\d{4}-0*\d{1,2}-0*\d{1,2}', str(datetime.datetime.now()))[0]

                mes = await message.answer_photo(
                    image,
                    caption=f'Гороскоп на <b>{only_date}</b>' + '\n' + result,
                    reply_markup=keyboard.as_markup(),
                    parse_mode=ParseMode.HTML
                )
                await insert_history_to_db(mes, message=None)

                user_status[message.chat.id] = WAITING_FOR_START


@dp.message(lambda message: user_status.get(message.chat.id) is None or user_status.get(message.chat.id) ==
                            WAITING_FOR_START, Command('subscribe'))
async def subscribe(message):
    try:
        with sqlite3.connect('goroskop.SQLite') as f:
            cur = f.cursor()
            req = cur.execute(
                """
                SELECT *
                FROM users
                WHERE tg_id = ? AND notification = false
                """, (message.chat.id,))
            resp = req.fetchone()
    except sqlite3.Error as error:
        py_logger.error(f'Произошла ошибка подписки пользователя {message.chat.id} на рассылку {error}')
        mes = await message.answer('Произошла ошибка! Попробуйте ввести команду /subscribe снова\n'
                             'Если проблема не исчезнет, то напишите в техподдержку support@example.ru')
        await insert_history_to_db(mes, message)
    else:
        if resp is None:
            mes = await message.answer('Ошибка! Вы не зарегистрированы или уже подписались на рассылку\n'
                                 'Чтобы отписаться от рассылки, введите команду /unsubscribe')
            await insert_history_to_db(mes, message)
        else:

            try:
                with sqlite3.connect('goroskop.SQLite') as f:
                    cur = f.cursor()
                    cur.execute(
                        """
                        UPDATE users
                        SET notification = true
                        WHERE tg_id = ?
                        """, (message.chat.id,))
            except sqlite3.Error as error:
                py_logger.error(f'Произошла ошибка при изменении данных в БД (notification = false -> true)\n'
                                f'у пользователя {message.chat.id} - {error}')
                mes = await message.answer('Произошла ошибка! Попробуйте снова ввести команду /subscribe снова\n'
                               'Если проблема не исчезнет, то напишите в техподдержку support@example.ru')
                await insert_history_to_db(mes, message)
            else:
                mes = await message.answer('Вы успешно подписались на рассылку')
                await insert_history_to_db(mes, message)
                await notification(message)

@dp.message(lambda message: user_status.get(message.chat.id) is None or user_status.get(message.chat.id) ==
                            WAITING_FOR_START, Command('unsubscribe'))
async def unsubscribe(message):
    try:
        with sqlite3.connect('goroskop.SQLite') as f:
            cur = f.cursor()
            req = cur.execute(
                """
                SELECT *
                FROM users
                WHERE tg_id = ? AND notification = true
                """, (message.chat.id,))
            resp = req.fetchone()
    except sqlite3.Error as error:
        py_logger.error(f'Произошла ошибка отписки пользователя {message.chat.id} от рассылки {error}')
        mes = await message.answer('Произошла ошибка! Попробуйте снова ввести команду /unsubscribe снова\n'
                             'Если проблема не исчезнет, то напишите в техподдержку support@example.ru')
        await insert_history_to_db(mes, message)
    else:
        if resp is None:
            mes = await message.answer('Ошибка! Вы не зарегистрированы или уже отписались от рассылки\n'
                                 'Чтобы подписаться снова на рассылку, введите команду /subscribe')
            await insert_history_to_db(mes, message)
        else:
            try:
                with sqlite3.connect('goroskop.SQLite') as f:
                    cur = f.cursor()
                    cur.execute(
                        """
                        UPDATE users
                        SET notification = false
                        WHERE tg_id = ?
                        """, (message.chat.id,))
            except sqlite3.Error as error:
                py_logger.error(f'Произошла ошибка при изменении данных в БД (notification = true -> false)\n'
                                f'у пользователя {message.chat.id} - {error}')
                mes = await message.answer('Произошла ошибка! Попробуйте снова ввести команду /unsubscribe снова\n'
                                'Если проблема не исчезнет, то напишите в техподдержку support@example.ru')
                await insert_history_to_db(mes, message)
            else:
                mes = await message.answer('Вы успешно отписались от рассылки')
                await insert_history_to_db(mes, message)



@dp.message(lambda message: user_status.get(message.chat.id) is None or user_status.get(message.chat.id) ==
                            WAITING_FOR_START, Command('clear_history'))
async def clear_history(message):
    try:
        await insert_history_to_db(mes=None, message=message)
        with sqlite3.connect('goroskop.SQLite') as f:
            cur = f.cursor()
            req = cur.execute("""
            SELECT DISTINCT tg_id, message_id, is_last_zodiac
            FROM history 
            WHERE tg_id = ?
            ORDER BY message_id ASC
            """, (message.chat.id,))
            resp = req.fetchall()
    except sqlite3.Error as error:
        py_logger.error(f"Ошибка {error} во время очистки данных у пользователя {message.chat.id}")
        mes = await message.answer("Произошла ошибка при очистке диалога\n"
                                   "Попробуйте ввести команду /clear_history\n"
                                   "Если проблема останется, то напишите в техподдержку support@example.ru")
        await insert_history_to_db(mes, message)
    else:
        user_status[message.chat.id] = JUST_WAIT_PLEASE
        last_zodiac = None
        for r in resp:
            try:
                if r[2]:
                    if last_zodiac is None:
                        last_zodiac = r
                    else:
                        print(last_zodiac, r, sep=" - ")
                        await bot.delete_message(last_zodiac[0], last_zodiac[1])
                        last_zodiac = r
                else:
                    await bot.delete_message(r[0], r[1])
            except Exception as error:
                print(error, r, sep=" ")
                continue
        with sqlite3.connect('goroskop.SQLite') as f:
            cur = f.cursor()
            cur.execute(
                """
                DELETE
                FROM history
                WHERE tg_id = ? AND message_id != ?
                """, (message.chat.id, last_zodiac[1],))
        user_status[message.chat.id] = WAITING_FOR_START


@dp.message(lambda message: user_status.get(message.chat.id) is None or user_status.get(message.chat.id) ==
                            WAITING_FOR_START, F.content_type.in_({'text', 'sticker', 'photo', 'video'}))
async def other_text(message):
    mes = await message.reply('Извините, я не понял.')
    await insert_history_to_db(mes, message)


@dp.message(lambda message: user_status.get(message.chat.id) == JUST_WAIT_PLEASE)
async def just_wait(message):
    pass

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Работа бота окончена')

