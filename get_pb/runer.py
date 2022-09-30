from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings

from get_pb import settings
from spiders.pb import PbSpider

if __name__ == '__main__':

    crawler_settings = Settings()
    crawler_settings.setmodule(settings)

    process = CrawlerProcess(settings=crawler_settings)
    process.crawl(PbSpider)

    process.start()