import os

from breadcrumb_intellegence.searchengines.google_search import GoogleWebSearch
import breadcrumb.settings as settings

class WebCollector:
    def __init__(self, aliases, sentiment_analyer=None):
        self.aliases = aliases
        self.sentiment_analyser = sentiment_analyer

    def run(self):
        content = []
        for alias in self.aliases:
            google_search = GoogleWebSearch(query=alias, num=50, start=0)
            content += google_search.search(2)


if __name__ == "__main__":
    import sys, os, django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "breadcrumb.settings")
    django.setup()
    print "HELLO"