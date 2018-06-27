#!/usr/bin/env python3

import json
import requests
import time
import urllib
from github import Github

import sqlalchemy

import db
from db import Task
import datetime
from contracts import contract

# take out the token to other file
FILENAME = "TOKEN.txt"

# user name and password
USERLOGIN = "user.txt"


@contract
def read_file_token(FILENAME):
    """ Function description.
        :type FILENAME: string
    """
    print("Loading Token")
    inFile = open(FILENAME, 'r')
    TOKEN = inFile.readline().rstrip()
    return TOKEN


@contract
def read_user_login(USERLOGIN):
    """ Function description.
        :type USERLOGIN: string
    """
    print("Loading User")
    inFile = open(USERLOGIN, 'r')
    user_name = inFile.readline().rstrip()
    user_password = inFile.readline().rstrip()

    return user_name, user_password


TOKEN = read_file_token(FILENAME)
user_name, user_password = read_user_login(USERLOGIN)

user_login = Github(user_name, user_password)
repository = user_login.get_repo("TecProg-20181/T--sexta_feira_br")

# after take out the token to other file
URL = "https://api.telegram.org/bot{}/".format(TOKEN)

HELP = """
 /new NOME
 /todo ID...
 /doing ID...
 /done ID...
 /delete ID
 /list
 /rename ID NOME
 /dependson ID ID...
 /duplicate ID
 /priority ID PRIORITY{low, medium, high}
 /help
 /date ID DAY/MONTH/YEAR
"""

# put into a classe api


class API(object):
    @contract
    def get_url(self, url):
        """ Function description.
            :type url: string
        """

        response = requests.get(url)
        content = response.content.decode("utf8")
        return content

    @contract
    def get_json_from_url(self, url):
        """ Function description.
            :type url: string
        """
        content = self.get_url(url)
        js = json.loads(content)
        return js


    def get_updates(self, offset=None):

        url = URL + "getUpdates?timeout=100"
        if offset:
            url += "&offset={}".format(offset)
        js = self.get_json_from_url(url)
        return js

    @contract
    def send_message(self, text, chat_id, reply_markup=None):
        """ Function description.
            :type text: string
            :type chat_id: int
        """
        text = urllib.parse.quote_plus(text)
        url = URL + \
            "sendMessage?text={}&chat_id={}&parse_mode=Markdown".format(
                text, chat_id)
        if reply_markup:
            url += "&reply_markup={}".format(reply_markup)
        self.get_url(url)

    @contract
    def get_last_update_id(self, updates):
        """ Function description.
            :type updates: dict
        """
        update_ids = []
        for update in updates["result"]:
            update_ids.append(int(update["update_id"]))

        return max(update_ids)


@contract
def deps_text(task, chat, preceed=''):
    """ Function description.
        :type chat: int
    """
    text = ''

    for i in range(len(task.dependencies.split(',')[:-1])):
        line = preceed
        query = db.session.query(Task).filter_by(
            id=int(task.dependencies.split(',')[:-1][i]), chat=chat)
        dep = query.one()

        icon = '\U0001F195'
        if dep.status == 'DOING':
            icon = '\U000023FA'
        elif dep.status == 'DONE':
            icon = '\U00002611'

        if i + 1 == len(task.dependencies.split(',')[:-1]):
            line += '└── [[{}]] {} {} [[{}]]\n'.format(
                dep.id, icon, dep.name, task.priority)
            line += deps_text(dep, chat, preceed + '    ')
        else:
            line += '├── [[{}]] {} {} [[{}]]\n'.format(
                dep.id, icon, dep.name, task.priority)
            line += deps_text(dep, chat, preceed + '│   ')

        text += line

    return text


class Tags(object):
    apiBot = API()

    @contract
    def new(self, message, chat, apiBot):
        """ Function description.
            :type message: string
            :type chat: int
        """
        task = Task(chat=chat, name=message, status='TODO',
                    dependencies='', parents='', priority='low', duedate=datetime.date(2100, 12, 12))
        issue = repository.create_issue(message)
        task.issue_number = issue.number
        db.session.add(task)
        db.session.commit()
        apiBot.send_message(
            "New task *TODO* [[{}]] {}".format(task.id, task.name), chat)

    @contract
    def find_task(self, task_id, chat):
        """ Function description.
            :type chat: int
        """
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        task = query.one()

        return task

    @contract
    def id_error_message(self, message, chat, apiBot):
        """ Function description.
            :type message: string
            :type chat: int
        """
        if message.isdigit():
            apiBot.send_message("Task {} not found".format(message), chat)
        else:
            apiBot.send_message("You must inform the task id", chat)

    @contract
    def separate_message(self, message):
        """ Function description.
            :type message: string
        """
        terms_list = ''

        if len(message.split(' ', 1)) > 1:
            terms_list = message.split(' ', 1)[1]
        priority_id = message.split(' ', 1)[0]

        return priority_id, terms_list

    @contract
    def rename(self, message, chat, apiBot):
        """ Function description.
            :type message: string
            :type chat: int
        """
        new_name = ''
        message_is_not_blank = message != ''
        if message_is_not_blank:
            priority_id, new_name = self.separate_message(message)

        if priority_id.isdigit():
            task_id = int(priority_id)
            try:
                task = self.find_task(task_id, chat)
            except sqlalchemy.orm.exc.NoResultFound:
                self.id_error_message(priority_id, chat, apiBot)
                return

            new_name_is_blank = new_name == ''
            if new_name_is_blank:
                apiBot.send_message(
                    "You want to modify task {}, but you didn't provide any new name".format(task_id), chat)
                return

            old_name = task.name
            task.name = new_name
            issue = repository.get_issue(task.issue_number)
            issue.edit(title=new_name)
            db.session.commit()
            apiBot.send_message("Task {} redefined from {} to {}".format(
                task_id, old_name, new_name), chat)
        else:
            self.id_error_message(priority_id, chat, apiBot)

    @contract
    def duplicate(self, message, chat, apiBot):
        """ Function description.
            :type message: string
            :type chat: int
        """
        if message.isdigit():
            task_id = int(message)
            try:
                task = self.find_task(task_id, chat)
            except sqlalchemy.orm.exc.NoResultFound:
                self.id_error_message(message, chat, apiBot)
                return

            duplicated_task = Task(chat=task.chat,
                                   name=task.name,
                                   status=task.status,
                                   dependencies=task.dependencies,
                                   parents=task.parents,
                                   priority=task.priority,
                                   duedate=task.duedate)
            db.session.add(duplicated_task)

            for dependent_task_id in task.dependencies.split(',')[:-1]:
                dependent_task = self.find_task(dependent_task_id, chat)
                dependent_task.parents += '{},'.format(duplicated_task.id)

            issue = repository.create_issue(duplicated_task.name)
            duplicated_task.issue_number = issue.number
            db.session.commit()
            apiBot.send_message(
                "New task *TODO* [[{}]] {}".format(duplicated_task.id,
                                                   duplicated_task.name),
                chat)
        else:
            self.id_error_message(message, chat, apiBot)

    @contract
    def delete(self, message, chat, apiBot):
        """ Function description.
            :type message: string
            :type chat: int
        """
        if message.isdigit():
            task_id = int(message)
            try:
                task = self.find_task(task_id, chat)
            except sqlalchemy.orm.exc.NoResultFound:
                self.id_error_message(message, chat, apiBot)
                return
            for dependent_task_id in task.dependencies.split(',')[:-1]:
                dependent_task = self.find_task(dependent_task_id, chat)
                dependent_task.parents = dependent_task.parents.replace(
                    '{},'.format(task.id), '')
            issue = repository.get_issue(task.issue_number)
            issue.edit(state='closed')
            db.session.delete(task)
            db.session.commit()
            apiBot.send_message("Task [[{}]] deleted".format(task_id), chat)
        else:
            self.id_error_message(message, chat, apiBot)

    @contract
    def change_status(self, message, chat, apiBot, command):
        """ Function description.
            :type message: string
            :type chat: int
            :type command: string
        """
        for task_id in message.split(' '):
            if task_id.isdigit():
                task_id = int(task_id)
                try:
                    task = self.find_task(task_id, chat)
                except sqlalchemy.orm.exc.NoResultFound:
                    self.id_error_message(message, chat, apiBot)
                    return
                if command == '/todo':
                    task.status = 'TODO'
                    apiBot.send_message(
                        "*TODO* task [[{}]] {}".format(task.id, task.name), chat)
                    issue = repository.get_issue(task.issue_number)
                    issue.edit(state='open')
                elif command == '/doing':
                    task.status = 'DOING'
                    apiBot.send_message(
                        "*DOING* task [[{}]] {}".format(task.id, task.name), chat)
                else:
                    task.status = 'DONE'
                    apiBot.send_message(
                        "*DONE* task [[{}]] {}".format(task.id, task.name), chat)
                    issue = repository.get_issue(task.issue_number)
                    issue.edit(state='closed')
                db.session.commit()
            else:
                self.id_error_message(message, chat, apiBot)

    @contract
    def list_tasks(self, chat, apiBot):
        """ Function description.
            :type chat: int
        """
        task_list = ''
        task_list += '\U0001F4CB Task List\n'
        query = db.session.query(Task).filter_by(
            parents='', chat=chat).order_by(Task.id)
        for task in query.all():
            icon = '\U0001F195'
            if task.status == 'DOING':
                icon = '\U000023FA'
            elif task.status == 'DONE':
                icon = '\U00002611'

            task_list += '[[{}]] {} {} [[{}]]-----{}\n'.format(
                task.id, icon, task.name, task.priority, task.duedate.strftime("%d/%m/%Y"))
            task_list += deps_text(task, chat)

        apiBot.send_message(task_list, chat)
        task_list = ''

        task_list += '\U0001F4DD _Status_\n'
        query = db.session.query(Task).filter_by(
            status='TODO', chat=chat).order_by(Task.id)

        task_list += '\n\U0001F195 *TODO*\n'
        for task in query.all():
            task_list += '[[{}]] {}\n'.format(task.id, task.name)
        query = db.session.query(Task).filter_by(
            status='DOING', chat=chat).order_by(Task.id)

        task_list += '\n\U000023FA *DOING*\n'
        for task in query.all():
            task_list += '[[{}]] {}\n'.format(task.id, task.name)
        query = db.session.query(Task).filter_by(
            status='DONE', chat=chat).order_by(Task.id)

        task_list += '\n\U00002611 *DONE*\n'
        for task in query.all():
            task_list += '[[{}]] {}\n'.format(task.id, task.name)

        apiBot.send_message(task_list, chat)

    @contract
    def check_dependency(self, task_id, string_id, chat, apiBot):
        """ Function description.
            :type task_id: int
            :type string_id: string
            :type chat: int
        """
        dependency_is_possible = True
        task_father = self.find_task(task_id, chat)
        if task_father.parents != '':
            print(task_father.parents)
            for task_id in task_father.parents.split(','):
                if task_id != '':
                    grandfather_id = int(task_id)
                    dependency_is_possible = self.check_dependency(grandfather_id,
                                                                   string_id,
                                                                   chat,
                                                                   apiBot)
                    if task_id == string_id:
                        dependency_is_possible = False
                        apiBot.send_message(
                            "This dependency is not possible", chat)
                        break
        return dependency_is_possible

    @contract
    def dependson(self, message, chat, apiBot):
        """ Function description.
            :type message: string
            :type chat: int
        """

        son_id = ''
        message_is_not_blank = message != ''
        if message_is_not_blank:
            father_id, son_id = self.separate_message(message)

        else:
            apiBot.send_message("Please, write something", chat)
            return

        if father_id.isdigit():
            task_father_id = int(father_id)
            try:
                task_father = self.find_task(task_father_id, chat)
            except sqlalchemy.orm.exc.NoResultFound:
                self.id_error_message(father_id, chat, apiBot)
                return

            son_id_is_blank = son_id == ''
            if son_id_is_blank:
                for task_son in task_father.dependencies.split(',')[:-1]:
                    task_son = int(task_son)
                    task_son = self.find_task(task_son, chat)
                    task_son.parents = task_son.parents.replace(
                        '{},'.format(task_father.id), '')

                task_father.dependencies = ''
                apiBot.send_message(
                    "Dependencies removed from task {}".format(task_father_id), chat)
            else:
                for task_id in son_id.split(' '):
                    if not task_id.isdigit():
                        apiBot.send_message(
                            "All dependencies ids must be numeric, and not {}".format(task_id), chat)
                    else:
                        string_id = task_id
                        task_id = int(task_id)
                        try:
                            dependency_is_possible = self.check_dependency(task_father_id,
                                                                           string_id,
                                                                           chat,
                                                                           apiBot)
                            if dependency_is_possible == False:
                                continue
                            task = self.find_task(task_id, chat)
                            task.parents += str(task_father.id) + ','
                        except sqlalchemy.orm.exc.NoResultFound:
                            self.id_error_message(string_id, chat, apiBot)
                            continue

                        dependent_list = task_father.dependencies.split(',')
                        if str(task_id) not in dependent_list:
                            task_father.dependencies += str(task_id) + ','
            db.session.commit()
            apiBot.send_message(
                "Task {} dependencies up to date".format(task_father_id), chat)
        else:
            self.id_error_message(father_id, chat, apiBot)

    @contract
    def priority(self, message, chat, apiBot):
        """ Function description.
            :type message: string
            :type chat: int
        """
        text = ''
        if message != '':
            task_id, priority = self.separate_message(message)

        if task_id.isdigit():
            task_id = int(task_id)
            query = db.session.query(Task).filter_by(id=task_id, chat=chat)
            try:
                task = query.one()
            except sqlalchemy.orm.exc.NoResultFound:
                apiBot.send_message(
                    "_404_ Task {} not found x.x".format(task_id), chat)
                return

            if priority == '':
                task.priority = ''
                apiBot.send_message(
                    "_Cleared_ all priorities from task {}".format(task_id), chat)
            else:
                if priority.lower() not in ['high', 'medium', 'low']:
                    apiBot.send_message(
                        "The priority *must be* one of the following: high, medium, low", chat)
                else:
                    task.priority = priority.lower()
                    apiBot.send_message(
                        "*Task {}* priority has priority *{}*".format(task_id, priority.lower()), chat)
            db.session.commit()

        else:
            apiBot.send_message("You must inform the task id", chat)

    @contract
    def set_date(self, message, chat, apiBot):
        """ Function description.
            :type message: string
            :type chat: int
        """
        day = 0
        month = 0
        year = 0

        if message != '':
            message, duedate = self.separate_message(message)
            if len(duedate.split('/', 2)) > 1:
                month = int(duedate.split('/', 2)[1])
                year = int(duedate.split('/', 2)[2])

            day = int(duedate.split('/', 2)[0])

        if day > 31:
            apiBot.send_message("Sorry,this day doesn't exist,please", chat)
        elif month > 12:
            apiBot.send_message("Sorry,this month doesn't exist", chat)
        elif message.isdigit():
            task_id = int(message)
            query = db.session.query(Task).filter_by(id=task_id, chat=chat)
            try:
                task = query.one()
            except sqlalchemy.orm.exc.NoResultFound:
                apiBot.send_message(
                    "_404_ Task {} not found x.x".format(task_id), chat)
                return

            task.duedate = datetime.date(year, month, day)

            db.session.commit()
            apiBot.send_message(
                "Your date is this {}".format(task.duedate.strftime("%d/%m/%Y")), chat)
        else:
            apiBot.send_message("You must inform the task id", chat)


@contract
def handle_updates(updates):
    """ Function description.
        :type updates: dict
    """

    tags = Tags()
    apiBot = API()
    for update in updates["result"]:
        if 'message' in update:
            message = update['message']
        elif 'edited_message' in update:
            message = update['edited_message']
        else:
            print('Can\'t process! {}'.format(update))
            return

        command = message["text"].split(" ", 1)[0]
        msg = ''
        if len(message["text"].split(" ", 1)) > 1:
            msg = message["text"].split(" ", 1)[1].strip()

        chat = message["chat"]["id"]

        print(command, msg, chat)

        if command == '/new':
            tags.new(msg, chat, apiBot)
        elif command == '/rename':
            tags.rename(msg, chat, apiBot)
        elif command == '/duplicate':
            tags.duplicate(msg, chat, apiBot)
        elif command == '/delete':
            tags.delete(msg, chat, apiBot)
        elif command == '/todo':
            tags.change_status(msg, chat, apiBot, command)
        elif command == '/doing':
            tags.change_status(msg, chat, apiBot, command)
        elif command == '/done':
            tags.change_status(msg, chat, apiBot, command)
        elif command == '/list':
            tags.list_tasks(chat, apiBot)
        elif command == '/dependson':
            tags.dependson(msg, chat, apiBot)
        elif command == '/priority':
            tags.priority(msg, chat, apiBot)
        elif command == '/start':
            apiBot.send_message(
                "Welcome! Here is a list of things you can do.", chat)
            apiBot.send_message(HELP, chat)
        elif command == '/help':
            apiBot.send_message("Here is a list of things you can do.", chat)
            apiBot.send_message(HELP, chat)
        elif command == '/date':
            tags.set_date(msg, chat, apiBot)
        else:
            apiBot.send_message(
                "I'm sorry dave. I'm afraid I can't do that.", chat)


def main():
    last_update_id = None
    apiBot = API()
    while True:
        print("Updates")
        updates = apiBot.get_updates(last_update_id)

        if len(updates["result"]) > 0:
            last_update_id = apiBot.get_last_update_id(updates) + 1
            handle_updates(updates)

        time.sleep(0.5)


if __name__ == '__main__':
    main()
