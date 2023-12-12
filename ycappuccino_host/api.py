#app="all"
from ycappuccino_core.api import CFQCN




class IClobReplaceService(object):
    """ interface of YCappuccino component """
    name = CFQCN.build("IClobReplaceService")

    def __init__(self):
        """ abstract constructor """
        pass


class IHost(object):
    """ interface of YCappuccino component """
    name = CFQCN.build("IHost")

    def __init__(self):
        """ abstract constructor """
        pass

class IHostFactory(object):
    """ interface of YCappuccino component """
    name = CFQCN.build("IHostFactory")

    def __init__(self):
        """ abstract constructor """
        pass
