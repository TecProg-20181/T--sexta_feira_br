import taskbot
from taskbot import Tags
import db
from db import Task
import unittest

class TestTaskbot(unittest.TestCase):

    def test_read_file_token(self):
        file_token = "tokentest.txt"
        token = taskbot.read_file_token(file_token)
        result = "gfggfghhgfhfhf"
        self.assertEqual(result, token)

    def test_read_user_login(self):
        file_user_login = "usertest.txt"
        user_name, password = taskbot.read_user_login(file_user_login)
        user_name_test = "Elvis"
        password_test = "gfgg123"
        self.assertEqual(user_name, user_name_test)
        self.assertEqual(password, password_test)

    def test_find_task(self):
        task_id = 1
        chat = 432672201
        task = Tags.find_task(Tags, task_id, chat)
        result = db.session.query(Task).filter_by(id=task_id, chat=chat).one()
        self.assertEqual(result, task)

if __name__ == '__main__':
    unittest.main()
