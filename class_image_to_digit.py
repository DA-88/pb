import requests
from lxml import html
from PIL import Image
import numpy as np
import sys
from io import BytesIO
from tensorflow import keras
import random
import re
sys.setrecursionlimit(1500)

class image_to_digits():
    img_a = None
    digits = []
    iter = 0
    model = keras.models.load_model('../captcha.h5')
    result = ''
    captchaToken = ''
    token = ''
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
   'Accept-Encoding': 'gzip, deflate, br',
   'Accept-Language': 'ru,ru-RU;q=0.9,en-US;q=0.8,en;q=0.7',
   'Connection': 'keep-alive',
   'Host': 'pb.nalog.ru',
   'Referer': 'https://pb.nalog.ru/',
   'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
   'sec-ch-ua-mobile': '?0',
   'sec-ch-ua-platform': '"Windows"',
   'Sec-Fetch-Dest': 'document',
   'Sec-Fetch-Mode': 'navigate',
   'Sec-Fetch-Site': 'same-origin',
   'Sec-Fetch-User': '?1',
   'Upgrade-Insecure-Requests': '1'
    }
    attempts = 0
    solved = False

    def start(self, attempts):
        self.img_a = None
        self.digits = []
        self.iter = 0
        self.result = ''
        self.captchaToken = ''
        self.token = ''
        self.attempts = attempts
        self.solved = False

        # Переходим на форму запроса капчи
        r = requests.get('https://pb.nalog.ru/captcha-dialog.html?aver=2.8.7&sver=4.39.5&pageStyle=GM2',
                         headers=self.headers)

        # Получаем url картинки
        root = html.fromstring(r.text)
        a = [f"https://pb.nalog.ru{root.xpath('//img//@src')[0]}"]
        self.captchaToken = re.search('a=\S+?&version', a[0])[0][2:][:-8]

        # Переходим на форму запроса капчи
        r = requests.get(a[0].replace('version=2', 'version=3'), headers=self.headers)

        self.img_a = np.array(
            Image.open(
                BytesIO(r.content)
            )
        ).astype('int')

        # Сохраняем изображение тетстовой капчи (для поверки)
        # rr = Image.open(BytesIO(r.content))
        # rr.save('c_test.bmp')

        self.clean_image()
        i = 0
        while i <= 5:
            self.digits.append({"c": None, "x_min": 0, "x_max": 0, "y_min": 0, "y_max": 0, "pixelCount": 0,
                                "x_start": 0, "y_start": 0, "start_point_found": False})
            i += 1

        i = 0
        while i <= 5:
            self.digits[i] = {"c": None, "x_min": 0, "x_max": 0, "y_min": 0, "y_max": 0, "pixelCount": 0,
                              "x_start": 0, "y_start": 0, "start_point_found": False}
            self.iter = i
            self.get_digit()
            if self.digits[i]["start_point_found"]:
                self.digits[i]['x_min'] = self.digits[i]['x_start']
                self.digits[i]['x_max'] = self.digits[i]['x_start']
                self.digits[i]['y_min'] = self.digits[i]['y_start']
                self.digits[i]['y_max'] = self.digits[i]['y_start']

                self.plot_area(self.digits[i]["y_start"], self.digits[i]["x_start"], depth=0)

                # Если случайно захватили 2 цифры - вторую половину красим в черный, пересчитываем pixelCount и сужаем фрейм
                if (self.digits[i]['x_max'] - self.digits[i]['x_min']) > 35:
                    x_limit = self.digits[i]['x_min'] + ((self.digits[i]['x_max'] - self.digits[i]['x_min']) // 2)

                    self.digits[i]['pixelCount'] = 0
                    for iy, y in enumerate(self.img_a):
                        for ix, x in enumerate(y):
                            if ix > x_limit:
                                if self.img_a[iy][ix][0] == 100:
                                    self.img_a[iy][ix][0] = 0
                                    self.img_a[iy][ix][1] = 0
                                    self.img_a[iy][ix][2] = 0
                            else:
                                if self.img_a[iy][ix][0] == 100:
                                    self.digits[i]['pixelCount'] += 1
                    self.digits[i]['x_max'] = x_limit

                if self.digits[i]['pixelCount'] > 250:
                    self.copy_digit()
                else:  # Ложное срабатывание
                    i -= 1
                # Затираем закрашенную область
                self.clean_plotted()
            else:  # Если стартовая точка не найдена - выходим из цикла
                break
            i += 1

        self.get_token()



    def get_token(self):
        # На этом месте должен быть уже готовый результат. Если не получилось дополняем result рандомным чмслом до 6 цифр
        while len(self.result) < 6:
            self.result = f"{self.result}{random.randint(0, 9)}"

        # Получаем токен
        payload = {'captcha': self.result, 'captchaToken': self.captchaToken}
        resp = requests.post(url='https://pb.nalog.ru/captcha-proc.json', data=payload, headers=self.headers)

        # Если не угадали, рекурсивно вызываем старт
        if resp.status_code == 200:
            self.token = resp.text.replace('"', '')
            print(f"Угадали с {5-self.attempts+1} попытки")
            self.solved = True
        else:
            if self.attempts > 0:
                self.start(attempts=self.attempts-1)

    def clean_image(self):
        for iy, y in enumerate(self.img_a):
            for ix, x in enumerate(y):
                pass
                if self.img_a[iy][ix][0] > 100 and self.img_a[iy][ix][1] > 100 and self.img_a[iy][ix][2] > 100:
                    self.img_a[iy][ix][0], self.img_a[iy][ix][1], self.img_a[iy][ix][2] = 255, 255, 255
                # Чистим полосы
                if self.img_a[iy][ix][0] >= 27 and self.img_a[iy][ix][0] <= 97 and \
                        self.img_a[iy][ix][1] >= 52 and self.img_a[iy][ix][1] <= 104 and \
                        self.img_a[iy][ix][2] >= 48 and self.img_a[iy][ix][2] <= 117:
                    self.img_a[iy][ix][0], self.img_a[iy][ix][1], self.img_a[iy][ix][2] = 255, 255, 255
                # Все, что осталось, делаем одного цвета
                if not (self.img_a[iy][ix][0] == 255 and self.img_a[iy][ix][1] == 255 and self.img_a[iy][ix][2] == 255):
                    self.img_a[iy][ix][0], self.img_a[iy][ix][1], self.img_a[iy][ix][2] = 0, 0, 0

    def get_digit(self):
        # Вычисляем точку старта
        a = self.img_a
        for ix, x in enumerate(a[0]):
            if not self.digits[self.iter]["start_point_found"]:
                for iy, y in enumerate(a):
                    if iy <= 94:  # чтобы не уперется в ограничение по высоте
                        # Если 5 пикселей по вертикали черные - старт найден
                        if a[iy][ix][0] == 0 and a[iy + 1][ix][0] == 0 and a[iy + 2][ix][0] == 0 and \
                                a[iy + 3][ix][0] == 0 and a[iy + 4][ix][0] == 0:
                            if not self.digits[self.iter]["start_point_found"]:
                                self.digits[self.iter]["start_point_found"] = True
                                self.digits[self.iter]["x_start"] = ix
                                self.digits[self.iter]["y_start"] = iy + 2
                                break
            else:
                break

    def plot_area(self, y, x, depth):
        if depth > 1000: return 0

        # Если пиксель черный - работаем дальше, иначе ничего не делаем
        if self.img_a[y][x][0] == 0:
            self.img_a[y][x][0] = 100  # Красим пиксель
            self.digits[self.iter]['pixelCount'] += 1  # Считаем количество пикселей
            # Определяем границы области с цифрой
            if x < self.digits[self.iter]['x_min']: self.digits[self.iter]['x_min'] = x
            if x > self.digits[self.iter]['x_max']: self.digits[self.iter]['x_max'] = x
            if y < self.digits[self.iter]['y_min']: self.digits[self.iter]['y_min'] = y
            if y > self.digits[self.iter]['y_max']: self.digits[self.iter]['y_max'] = y

            # Проверяем соседние пиксели по часовой стрелке
            # 1
            if x > 0 and y > 0:
                if self.img_a[y - 1][x - 1][0] != 100: self.plot_area(y - 1, x - 1, depth=depth + 1)
            # 2
            if y > 0:
                if self.img_a[y - 1][x][0] != 100: self.plot_area(y - 1, x, depth=depth + 1)
            # 3
            if x < 199 and y > 0:
                if self.img_a[y - 1][x + 1][0] != 100: self.plot_area(y - 1, x + 1, depth=depth + 1)
            # 4
            if x < 199:
                if self.img_a[y][x + 1][0] != 100: self.plot_area(y, x + 1, depth=depth + 1)
            # 5
            if x < 199 and y < 99:
                if self.img_a[y + 1][x + 1][0] != 100: self.plot_area(y + 1, x + 1, depth=depth + 1)
            # 6
            if y < 99:
                if self.img_a[y + 1][x][0] != 100: self.plot_area(y + 1, x, depth=depth + 1)
            # 7
            if x > 0 and y < 99:
                if self.img_a[y + 1][x - 1][0] != 100: self.plot_area(y + 1, x - 1, depth=depth + 1)
            # 8
            if x > 0:
                if self.img_a[y][x - 1][0] != 100: self.plot_area(y, x - 1, depth=depth + 1)

    def clean_plotted(self):
        for iy, y in enumerate(self.img_a):
            for ix, x in enumerate(y):
                if self.img_a[iy][ix][0] == 100:
                    self.img_a[iy][ix][0] = 255
                    self.img_a[iy][ix][1] = 255
                    self.img_a[iy][ix][2] = 255

    def copy_digit(self):
        area = np.zeros((self.digits[self.iter]['y_max'] - self.digits[self.iter]['y_min'] + 1,
                         self.digits[self.iter]['x_max'] - self.digits[self.iter]['x_min'] + 1))
        y = self.digits[self.iter]['y_min']
        while y <= self.digits[self.iter]['y_max']:
            x = self.digits[self.iter]['x_min']
            while x <= self.digits[self.iter]['x_max']:
                if self.img_a[y][x][0] == 100:
                    area[y - self.digits[self.iter]['y_min']][x - self.digits[self.iter]['x_min']] = 255
                x += 1
            y += 1

        # Трансформируем область с цифрой
        area = np.array(
            Image.fromarray(
                area.astype('byte'), 'L').resize((24, 44))
        ).astype('int')
        # Выполняем предсказание
        self.digits[self.iter]['c'] = np.argmax(
            self.model.predict(
                np.array([area])
            ))
        # Складываем в результат
        self.result = f"{self.result}{self.digits[self.iter]['c']}"

    def get_jsessionid(self, requestcookiejar):
        result = ''
        for i in requestcookiejar:
            if i.name == 'JSESSIONID': result = i.value
        return f"JSESSIONID={result};"