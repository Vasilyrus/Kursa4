""" Модуль определяет порядок авторизации и дальнейшей работы с сервисом vk.com"""
import json
import os
import time
from datetime import datetime

import requests
from tqdm import tqdm

users_list = []

now = int(time.mktime(datetime.now().timetuple()))


class VKAPIAuth:
    """ Класс предназначен для авторизации на сервисе vk.com"""
    ACCESS_TOKEN = ""

    def __init__(self, login=None, password=None):
        self.AUTHORIZE_URL = 'https://oauth.vk.com/authorize'
        self.oath_params = {
            'client_id': 3116505,
            'scope': "users,friends,photos",
            'display': 'page',
            'response_type': 'token',
            'v': '5.120',
        }

        self.login = login
        self.password = password
        with open("access_token.json") as file:
            access_key_dic = json.load(file)
        if access_key_dic["expires_in"] > now:
            self.ACCESS_TOKEN = access_key_dic["access_token"]
            self.expires_in = access_key_dic["expires_in"]
            print(f"\nТокен пользователя действителен в течение {int((self.expires_in - now) / 3600)} ч.\n")
        else:
            self.get_token = self.authorize()
            if "access_token" in self.get_token:
                self.ACCESS_TOKEN = self.get_token.split("access_token=")[1].split("&")[0]
                self.expires_in = int(int(self.get_token.split("expires_in=")[1].split("&")[0]) / 3600)
                access_key_dic["access_token"] = self.ACCESS_TOKEN
                access_key_dic["granted"] = now
                access_key_dic["expires_in"] = now + self.expires_in * 3600
                with open("access_token.json", "w", encoding="utf-8") as file:
                    json.dump(access_key_dic, file)
                print(f"\nТокен пользователя выдан со сроком действия {self.expires_in} ч.\n")
            else:
                print("\nЧто-то пошло не так.")
                print(self.get_token)




class User:
    """Класс определяет методы работы с сервисами vk.com"""

    def __init__(self, _id: int):
        self.id = _id
        self.URL = 'https://vk.com/id'
        self.API_URL = 'https://api.vk.com/method/'
        self.params = {
            'access_token': VKAPIAuth.ACCESS_TOKEN,
            'v': '5.120'
        }
        self.methods = {
            'users': {'get': 'users.get?'},
            'friends': {'get': 'friends.get?',
                        'areFriends': 'friends.areFriends?',
                        'getMutual': 'friends.getMutual?',
                        },
            'photos': {'get': 'photos.get?',
                       'get_albums': 'photos.getAlbums?'},
        }
        user_params = {"user_ids": self.id}
        user_params.update(self.params)
        # print(requests.get(self.API_URL + self.methods['users']['get'],
        #              params=user_params).json())
        resp = requests.get(self.API_URL + self.methods['users']['get'],
                            params=user_params).json()['response'][0]
        self.name = resp['first_name'] + ' ' + resp['last_name']
        if not users_list:
            users_list.append(self)
        else:
            id_list = {_user.id for _user in users_list}
            if self.id not in id_list:
                users_list.append(self)

    # noinspection Pylint
    def __repr__(self):
        return str(self.id)

    # noinspection Pylint
    def __str__(self):
        return self.URL + str(self.id)

    # noinspection Pylint
    def __and__(self, other):
        return self.mutual_friends(other.id)


    def get_photos(self):
        """Метод получает ссылки на 5 последних по дате загрузки фотографий из различных альбомов пользователя"""

        def get_albums():
            param = {"owner_id": self.id}
            param.update(self.params)
            response = requests.get(self.API_URL + self.methods['photos']['get_albums'],
                                    params=param).json()['response']['items']
            albums = {num: {album["title"]: album["id"]} for num, album in enumerate(response, start=1)}
            try:
                last_key = max(albums.keys()) + 1
                albums[last_key] = {"Фото профиля": "profile"}
                return albums
            except ValueError:
                albums[0] = {"Фото профиля": "profile"}
                return albums

        albums = get_albums()

        print("Фото из какого альбома Вы хотите загрузить?")
        for keys, values in albums.items():
            for key in values.keys():
                print(f'{keys}: "{key}"')
        album_number = albums[int(input("Введите номер альбома: "))]
        album_id = (album_number[key] for key in album_number.keys())

        param = {"album_id": album_id, "photo_sizes": "1", 'extended': 1, "owner_id": self.id}
        param.update(self.params)
        photos_list = requests.get(self.API_URL + self.methods['photos']['get'],
                                   params=param).json()['response']['items'][-5:]

        photos_info = []
        for photo in photos_list:
            info = {
                "file_name": str(photo['likes']['count']) + "_" + str(
                    datetime.fromtimestamp(photo['date']).date()) + ".jpg",
                "size": photo['sizes'][-1]['type']
            }
            photos_info.append(info)
        with open("downloaded_vk_photos.json", "w") as file:
            json.dump(photos_info, file)

        url_list = [(photo['sizes'][-1]['url'], photo['likes']['count'], photo['date']) for photo in photos_list]
        return url_list, self.name

    @staticmethod
    def download(urls_list):
        """Метод скачивает на жесткий диск фотографии пользователя"""
        tuples, name = urls_list
        target_folder = os.path.join('downloads', name)
        os.makedirs(target_folder, exist_ok=True)
        target_folder = os.path.abspath(target_folder)
        for url, likes, date in tqdm(tuples):
            file_to_download = requests.get(url)
            with open(os.path.join(target_folder, str(likes) + "_" + str(datetime.fromtimestamp(date).date()) + ".jpg"),
                      'wb') as file:
                file.write(file_to_download.content)
        return target_folder.split(os.path.sep)[-1]


def track_upload_progress(pbar):
    """Прогресс-бар для загрузки одиночных файлов на Яндекс.Диск"""
    prev_value = 0

    def callback(monitor):
        nonlocal prev_value
        diff = monitor.bytes_read - prev_value
        prev_value = monitor.bytes_read
        pbar.update(diff)

    return callback


class YaDisk:
    """Класс определяет атрибуты Яндекс.Диска (файлы и папки) и методы работы с ними"""

    def __init__(self, token):
        self.name = None
        self.all_files = []
        self.all_folders = []
        self.token = token
        self.URL = "https://cloud-api.yandex.net/v1/disk/resources"
        self.params = {"path": '/'}
        self.headers = {"port": "443", "Authorization": f"OAuth {self.token}"}
        print("Загрузка содержимого Я.Диска:")
        self._parse_catalogues()

    # noinspection Pylint
    def __repr__(self):
        return self.name

    def _parse_catalogues(self, path="/"):
        """Метод получает информацию обо всех файлах и папках на Яндекс.Диске"""
        self._point()
        yadisk_size = 0
        param = {"path": path}
        response = requests.get(self.URL, params=param, headers=self.headers)
        # try:
        for item in response.json()['_embedded']['items']:
            if item['type'] == "dir":
                folder_size = self._parse_catalogues(item["path"])
                yadisk_size += folder_size
                fsize = {"size": folder_size}
                item.update(fsize)
                self.all_folders.append(YaFolder(item))
            else:
                yadisk_size += item["size"]
                self.all_files.append(YaFile(item))
        return yadisk_size

    @staticmethod
    def _point():
        """Метод симулирует работу прогресс-бара: выводит одну точку на каждой итерации"""
        sys.stdout.write('.')
        sys.stdout.flush()

    @staticmethod
    def _size(item):
        size = int(round(item.size / 1024, 0))
        if size > 100000:
            size = str(round(size / 1024 ** 2, 2)) + " GB"
        elif 100000 > size > 1000:
            size = str(round(size / 1024, 2)) + " MB"
        else:
            size = str(size) + " KB"
        return size

    def create_folder(self, folder_name, path=None):
        """метод создает папку на яндекс.диске с заданным именем"""

        def _create(_param):
            put = requests.put(self.URL, headers=self.headers, params=_param)
            try:
                return put.status_code, put.json()["href"]
            except KeyError:
                return put.status_code, put.json()["message"]

        if path is None:
            print("Текущий список папок:")
            for num, dir in enumerate(self.all_folders):
                print("dir <index>" + str(num) + ".", dir)
            print("\nЕсли вы хотите создать папку в корне диска - нажмите Enter.\n"
                  "Если вы хотите создать папку внутри другой папки - введите индекс соответствующей папки.\n")
            tree = input('Введите ответ?')
            if not tree:
                param = {"path": folder_name}
            else:
                param = {"path": self.all_folders[int(tree)].path + "/" + folder_name}
        else:
            param = {"path": path}
        test = requests.get(self.URL, headers=self.headers, params=param)
        if test.status_code == 404:
            creator = _create(param)
            if creator[0] == 201:
                print(f'Папка "{folder_name}" успешно создана на Яндекс.Диске')
                print()
            else:
                print(creator)
                print()
        elif test.status_code == 200:
            print(f'Папка "{folder_name}" уже существует на Яндекс.Диске')
            print()
        else:
            print(test)

        self.reload()
        print("Текущий список папок:")
        self.print_all('folder')

    







