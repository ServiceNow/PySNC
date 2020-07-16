class TempTestRecord:
    def __init__(self, client, table, default_data=None):
        self.__gr = client.GlideRecord(table)
        self.__data = default_data

    def __enter__(self):
        self.__gr.initialize()
        if self.__data:
            for k in self.__data.keys():
                self.__gr.set_value(k, self.__data[k])
        self.__gr.insert()
        return self.__gr

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__gr.delete()
