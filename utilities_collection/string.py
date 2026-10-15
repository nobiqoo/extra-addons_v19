from datetime import datetime
import unicodedata
import base64


def remove_accents(message):
    """
    Quita los acentos de un string
    @params:
        message: str
    @return:
        bytes
    """
    return message.encode('ascii', 'replace').replace(b'?', b' ')

def unicode_remove_accents(message):
    """
    Quita los acentos de un string usando unicodedata
    @params:
        message: str
    @return:
        str
    """
    message = message.upper()
    message_normalize = unicodedata.normalize('NFD', message)
    message_without_acents = ''.join(
        c for c in message_normalize if unicodedata.category(c) != 'Mn' or c == 'Ñ'
    )
    return unicodedata.normalize('NFC', message_without_acents)

def bytes2base64(message):
    """
    Conveirte bytes ascci a bytes base64
    @params:
        message: bytes
    @return:
        bytes
    """
    return base64.b64encode(message)


def prep_field(s, align='left', size=0, fill=' ', date=False):
    """
    Transforma un str con alineacion y relleno 
    @params:
        s: str
        align: str -> left, right
        size: int
        fill: str
        date: bool
    @return:
        str 
    """
    if s in [False, None]:
        s = ''
    if date:
        s = datetime.strftime(s, "%Y-%m-%d")
    if align == 'right':
        s = str(s)[0:size].rjust(size, str(fill))
    elif align == 'left':
        s = str(s)[0:size].ljust(size, str(fill))
    return s
