from .mailer import *

'''
Яндекс требует создать ключ приложения на https://id.yandex.ru/security/app-passwords и использовать как пароль
Mail.ru требует создать ключ приложения на https://account.mail.ru/user/2-step-auth/passwords/ и использовать как пароль
'''

imap_hosts = {
	'yandex': 'imap.yandex.com',
	'gmail': 'imap.gmail.com',
	'mail': 'imap.mail.ru',
}

def yandexMailer(username: str, password: str, default_box: str = 'inbox'):
	return Mailer(username, password, 'imap.yandex.com', 993, default_box=default_box)

def mailruMailer(username: str, password: str, default_box: str = 'inbox'):
	return Mailer(username, password, 'imap.mail.ru', 993, default_box=default_box)

def gmailMailer(username: str, password: str, default_box: str = 'inbox'):
	return Mailer(username, password, 'imap.gmail.com', 993, default_box=default_box)