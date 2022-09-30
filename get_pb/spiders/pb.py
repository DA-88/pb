import scrapy
from scrapy.http import HtmlResponse
from get_pb.items import GetPbItem

import pickle
from pymongo import MongoClient
from class_image_to_digit import image_to_digits
import json

class PbSpider(scrapy.Spider):
    name = 'pb'
    allowed_domains = ['pb.nalog.ru']
    start_urls = ['http://pb.nalog.ru/']

    CONNECTION_STRING = "mongodb://localhost:27017/pb"
    client = MongoClient(CONNECTION_STRING)
    collection = client['pb']['pb_data']
    chunks = client['pb']['chunks_hp']
    brake_captcha = image_to_digits()

    attempts_default = 2

    inns = []


    def start_requests(self):
        # Находим первую незанятую чанку с иннами
        a = list(self.chunks.find({'busy': False}, {'_id': 1}).limit(1))
        if len(a) > 0:
            id = a[0]['_id']
            self.chunks.update_one({'_id': id}, {'$set': {'busy': True}})
            a = list(self.chunks.find({'_id': id}, {'inns': 1}))
            self.inns = a[0]['inns']


        # for inn in self.inns:
        for inn in self.inns:
            if len(list(self.collection.find({'_id': inn}, {'_id': 1}))) == 0: # проверяем, есть ли такой инн в mongo
                result = {'_id': inn}
                payload = {'page': '1', 'pageSize': '10', 'pbCaptchaToken': '', 'token': '', 'mode': 'search-ul', 'queryAll': '',
                           'queryUl': inn, 'okvedUl': '', 'statusUl': '', 'regionUl': '', 'isMspUl': '', 'queryIp': '', 'okvedIp': '', 'statusIp': '',
                           'regionIp': '', 'isMspIp': '', 'mspIp1': '1', 'mspIp2': '2', 'mspIp3': '3', 'queryUpr': '', 'uprType1': '1', 'uprType0': '1',
                           'queryRdl': '', 'dateRdl': '', 'queryAddr': '', 'regionAddr': '', 'queryOgr': '', 'ogrFl': '1', 'ogrUl': '1', 'npTypeDoc': '1',
                           'ogrnUlDoc': '', 'ogrnIpDoc': '', 'nameUlDoc': '', 'nameIpDoc': '', 'formUlDoc': '', 'formIpDoc': '', 'ifnsDoc': '',
                           'dateFromDoc': '', 'dateToDoc': ''}
                yield scrapy.FormRequest(url='https://pb.nalog.ru/search-proc.json', formdata=payload,
                                         callback=self.get_org_token,
                                         meta={'result': result, 'payload': payload, 'attempts': self.attempts_default})

    # На этом этапе задача - получить токен организации
    def get_org_token(self, response: HtmlResponse):
        if response.status == 200:
            a = json.loads(response.text)
            org_token = a['ul']['data'][0]['token']
            payload = {'token': org_token, 'method': 'get-request'}
            # Экспериментально - пробрасываем уже найденный ранее pbCaptchaToken, если он есть
            payload['pbCaptchaToken'] = response.meta['payload']['pbCaptchaToken']
            yield scrapy.FormRequest(url='https://pb.nalog.ru/company-proc.json', formdata=payload,
                                     callback=self.get_second_token_and_id,
                                     meta={'result': response.meta['result'], 'payload': payload, 'attempts': self.attempts_default})
        else:
            self.brake_captcha.start(attempts=5)  # Запускаем класс взлома капчи
            if self.brake_captcha.solved:  # Если нашли решение, второй раз запускаем search-proc, но уже с pbCaptchaToken
                payload = response.meta['payload']
                payload['pbCaptchaToken'] = self.brake_captcha.token
                if response.meta['attempts'] > 0: # Проверяем, есть ли у нас еще попытки, чтобы не впасть в бесконечную рекурсию
                    yield scrapy.FormRequest(url='https://pb.nalog.ru/search-proc.json', formdata=payload, callback=self.get_org_token,
                                         meta={'result': response.meta['result'], 'payload': payload,
                                               'attempts': response.meta['attempts']-1})

    # На этом этапе задача - получить второй токен организации и id
    def get_second_token_and_id(self, response: HtmlResponse):
        if response.status == 200:
            a = json.loads(response.text)
            payload = {'token': a['token'], 'id': a['id'], 'method': 'get-response'} # тут уже капча не нужна
            yield scrapy.FormRequest(url='https://pb.nalog.ru/company-proc.json', formdata=payload,
                                     callback=self.get_result_data,
                                     meta={'result': response.meta['result'], 'payload': payload,
                                           'attempts': self.attempts_default})
        else:
            self.brake_captcha.start(attempts=5)  # Запускаем класс взлома капчи
            if self.brake_captcha.solved:
                payload = response.meta['payload']
                payload['pbCaptchaToken'] = self.brake_captcha.token
                if response.meta['attempts'] > 0:  # Проверяем, есть ли у нас еще попытки, чтобы не впасть в бесконечную рекурсию
                    yield scrapy.FormRequest(url='https://pb.nalog.ru/company-proc.json', formdata=payload,
                                             callback=self.get_second_token_and_id,
                                             meta={'result': response.meta['result'], 'payload': payload,
                                                   'attempts': response.meta['attempts']-1})

    def get_result_data(self, response: HtmlResponse):
        if response.status == 200 and len(response.text) > 10: # Если получили ответ от сервера
            result = response.meta['result']
            result['pb_data'] = json.loads(response.text)
            self.collection.insert_one(result)
            #yield GetPbItem(data=result)
        else:
            if response.meta['attempts'] > 0:  # Проверяем, есть ли у нас еще попытки, чтобы не впасть в бесконечную рекурсию
                yield scrapy.FormRequest(url='https://pb.nalog.ru/company-proc.json', formdata=response.meta['payload'],
                                     callback=self.get_result_data,
                                     meta={'result': response.meta['result'], 'payload': response.meta['payload'],
                                           'attempts': response.meta['attempts']-1})
