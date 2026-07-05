from orbo.data.static_loader import (
    load_static_data
)

from orbo.static.updater import (
    refresh_static_data
)


class StaticDataManager:

    def __init__(self):
        self._data = load_static_data()

    def all(self):
        return self._data

    def refresh(self):

        refresh_static_data()

        self._data = load_static_data()

        return self._data
