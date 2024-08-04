from typing import *

import imaplib
import email
import os
import time
import socket

from email.policy import default
from email.utils import parsedate_to_datetime


class Message:
	def __init__(self, raw_email: bytes, mailbox: str = None):
		self.msg = email.message_from_bytes(raw_email, policy=default)

		self.id = self.msg['Message-ID']
		self.From = self.msg['From']
		self.To = self.msg['To']
		self.subject = self.msg['Subject']
		self.date_sent = parsedate_to_datetime(self.msg['Date'])
		self.date_received = parsedate_to_datetime(self.msg['Received'].split('; ')[-1].split(';')[-1])
		self.body = self._get_body(self.msg)
		self.attachments = self._get_attachments(self.msg)

		self.mailbox_name = str(mailbox) if mailbox else None

		self.keys = ['id', 'From', 'To', 'subject', 'date_sent', 'date_received', 'attachments', 'body']

	@property
	def mailbox(self) -> 'MailBox':
		return self.get_mailbox()
	def get_mailbox(self) -> 'MailBox':
		return self.mailer[self.mailbox_name]

	def format_long(self) -> Optional[str]:
		res = f'''-----
MAILBOX: {self.mailbox_name};
=====
FROM: {self.From}; TO: {self.To}
========
Subject: {self.subject}
'''

		if self.body:
			res += f'========\n{self.body}\n'

		return res + '-----'

	def format_short(self) -> Optional[str]:
		res = f'''-----
MAILBOX: {self.mailbox_name};
=====
FROM: {self.From}; TO: {self.To}
========
Subject: {self.subject}
'''

		if self.body:
			res += f'========\nBody: text {len(self.body)} symbols at {self.__class__.__name__}.body\n'

		return res + '-----\n'

	def format(type: str = 'long') -> Optional[str]:
		if type == 'short':
			return self.format_short()
		elif type == 'long':
			return self.format_long()

	def _get_body(self, msg: str) -> Optional[str]:
		if msg.is_multipart():
			for part in msg.iter_parts():
				if part.get_content_type() == "text/plain":
					return part.get_payload(decode=True).decode('utf-8')
		else:
			return msg.get_payload(decode=True).decode('utf-8')

	def _get_attachments(self, msg: 'email.message.Message') -> List[str]:
		attachments = []

		if msg.is_multipart():
			for part in msg.iter_parts():
				filename = part.get_filename()
				if filename:
					attachments.append([ filename, part.get_payload(decode=True) ])

		return attachments

	def save_attachments(self, directory: str, name_format: str = '{short_id}_{name}', format_kwargs: dict = {}) -> List[str]:
		saved_files = []

		for filename, file_data in self.attachments:
			new_file_name = name_format.format(short_id=self.id.split("@")[0][1:], name=filename, **format_kwargs)
			file_path = os.path.join(directory, new_file_name)
			open(file_path, 'wb').write(file_data)
			saved_files.append(new_file_name)

		return saved_files

	def serialize(self) -> List[dict]:
		return { key:str(self[key]) for key in self.keys }
	def json(self, indent: int = None) -> str:
		return json.dumps(self.serialize()) if not indent else json.dumps(self.serialize(), indent=indent)


	def __getitem__(self, i: str) -> str:
		if i in self.keys:
			return getattr(self, i)
		else:
			raise KeyError(f'{self.__class__.__name__} has only {len(self.keys)} allowed keys: {self.keys}')
	def __str__(self):
		return self.format_short()
	def __repr__(self):
		return f'{self.__class__.__name__}({self.mailbox_name}, {self.From} -> {self.To}, "{self.subject}", body {len(self.body)} symbols, {len(self.attachments)} attachments)'

class MailBox:
	def __init__(self, mailer: 'Mailer', name: str):
		self.name = str(name)
		self.mailer = mailer

	def __getitem__(self, msg_id: int):
		if isinstance(msg_id, int):
			return self.mailer.get_message(msg_id, self.name)
		elif isinstance(msg_id, slice):
			return self.mailer.slice_messages(msg_id.start, msg_id.stop, self.name, step=msg_id.step if msg_id.step != None else 1)

	@property
	def messages(self) -> List['Message']:
		return self.get_messages()
	def get_messages(self) -> List['Message']:
		return self.mailer.get_messages(self.name)

	def serialize(self) -> List[dict]:
		return [ msg.serialize() for msg in self.messages ]
	def json(self, indent: int = None) -> str:
		return json.dumps(self.serialize()) if not indent else json.dumps(self.serialize(), indent=indent)

	def __list__(self):
		return self.messages
	def __len__(self):
		return len(self.messages)
	def __str__(self):
		return f'{self.__class__.__name__}_{self.name}({len(self.messages)} messages)'
	def __repr__(self):
		return f'{self.__class__.__name__}({self.mailer}, "{self.name}")'


class Mailer(imaplib.IMAP4_SSL):
	def __init__(self, username: str, password: str, host: str, port: int = 993, default_box: str = 'INBOX'):
		try:
			super().__init__(host, port)
		except socket.gaierror:
			raise ValueError(f'Can not connect to host with port: {host}:{port}')

		self.username = str(username)
		self.password = str(password)
		self.default_box = str(default_box)
		self.host = str(host)
		self.port = int(port)

		self.login(self.username, self.password)

		if self.default_box in self.mailboxes:
			self.select(self.default_box)
		else:
			raise ValueError(f'Typed invalid mailbox name as default_box kwarg: {default_box}')

	@property
	def mailboxes(self) -> List[str]:
		return self.get_mailboxes()
	def get_mailboxes(self) -> List[str]:
		try:
			rv, mailboxes = self.list()
			if rv == 'OK':
				return [mailbox.decode().replace('"', '').split(' | ')[-1].split(' / ')[-1] for mailbox in mailboxes]
			else:
				return []
		except imaplib.IMAP4.abort:
			return self.copy().get_mailboxes()

	@property
	def messages(self) -> Union[List[int], str]:
		try:
			rv, data = self.search(None, 'ALL')
			if rv == 'OK':
				return [int(msg_id) for msg_id in data[0].split()]
			return rv
		except imaplib.IMAP4.abort:
			return self.copy().get_messages(mailbox_name)

	def get_messages(self, mailbox_name: str) -> List[int]:
		try:
			if mailbox_name in self.mailboxes:
				self.select(mailbox_name)
				msgs = self.messages
				self.select(self.default_box)
				return msgs
			else:
				raise ValueError(
f'{self.__class__.__name__}.messages method takes a string mailbox name, that exists in list from {self.__class__.__name__}.get_mailboxes() method'
				)
		except imaplib.IMAP4.abort:
			return self.copy().get_messages(mailbox_name)

	def get_message(self, msg_id: int, mailbox_name: str) -> Union['Message', str]:
		try:
			if mailbox_name in self.mailboxes:
				self.select(mailbox_name)

				if msg_id <= 0:
					msg_id += len(self.messages)

				rv, data = self.fetch(str(msg_id), '(RFC822)')
				if rv == 'OK':
					return Message(data[0][1], mailbox=mailbox_name)

				self.select(self.default_box)
				return rv

			else:
				raise ValueError(
	f'{method_name} requires a string mailbox name as a key or an integer message index in {self.default_box}, that exists in list from {self.__class__.__name__}.get_mailboxes() method'
				)

		except imaplib.IMAP4.abort:
			return self.copy().get_message(msg_id, mailbox_name)

	def slice_messages(self, start: int, end: int, mailbox_name: str, step: int = 1) -> Union[List['Message'], str]:
		try:
			if mailbox_name in self.mailboxes:
				self.select(mailbox_name)

				if start <= 0:
					start += len(self.messages)
				if end <= 0:
					end += len(self.messages)

				start = max(1, start)
				end = min(len(self.messages), end)

				rv, list_data = self.fetch(f'{start}:{end}', '(RFC822)')
				if rv == 'OK':
					return [
						Message(data[1], mailbox=mailbox_name) for i, data in enumerate(list_data) if isinstance(data, tuple) and isinstance(data[1], bytes) and i % step == 0
					]

				self.select(self.default_box)
				return rv

			else:
				raise ValueError(
	f'{method_name} requires a string mailbox name as a key or an integer message index in {self.default_box}, that exists in list from {self.__class__.__name__}.get_mailboxes() method'
				)

		except imaplib.IMAP4.abort:
			return self.copy().slice_messages(start, end, mailbox_name, step=step)

	def __getitem__(self, mailbox: Union[str, int]) -> Union['MailBox', 'Message']:
		err_text = '{}.__geitem__ requires a string mailbox name as a key or an integer message index in {}, that exists in list from {}.get_mailboxes() method'.format(
			self.__class__.__name__, self.default_box, self.__class__.__name__
		)

		if isinstance(mailbox, str):
			if mailbox.lower() == 'inbox':
				mailbox = 'INBOX'

			if mailbox in self.mailboxes:
				return MailBox(self, mailbox)
			else:
				raise KeyError(err_text)

		elif isinstance(mailbox, slice):
			return self.slice_messages(mailbox.start, mailbox.stop, self.default_box, step=mailbox.step if mailbox.step != None else 1)

		elif isinstance(mailbox, int):
			return MailBox(self, self.default_box)[mailbox]

		else:
			raise ValueError(err_text)

	def serialize(self) -> List[dict]:
		return [ msg.serialize() for msg in self.messages ]
	def json(self, indent: int = None) -> str:
		return json.dumps(self.serialize()) if not indent else json.dumps(self.serialize(), indent=indent)

	def copy(self) -> 'MailBox':
		return self.__class__(self.username, self.password, self.host, port=self.port, default_box=self.default_box)

	def __str__(self):
		return f'{self.__class__.__name__}(client "{self.username}", {self.host}:{self.port})'