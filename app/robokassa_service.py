from robokassa import Robokassa, HashAlgorithm
from config import ROBOKASSA_LOGIN, ROBOKASSA_PASS_1, ROBOKASSA_PASS_2

robokassa = Robokassa(
    merchant_login=ROBOKASSA_LOGIN,
    password1=ROBOKASSA_PASS_1,
    password2=ROBOKASSA_PASS_2,
    is_test=False,
    algorithm=HashAlgorithm.md5,
)
