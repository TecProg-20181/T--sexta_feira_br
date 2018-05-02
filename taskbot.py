#!/usr/bin/env python3

import json
import requests
import time
import urllib

import sqlalchemy

import db
from db import Task

# take out the token to other file
FILENAME = "TOKEN.txt"


def read_file_token(FILENAME):
    print("Loading Token")
    inFile = open(FILENAME, 'r')
    TOKEN = inFile.readline().rstrip()
    return TOKEN


TOKEN = read_file_token(FILENAME)

# after take out the token to other file
URL = "https://api.telegram.org/bot{}/".format(TOKEN)

HELP = """
 /new NOME
 /todo ID
 /doing ID
 /done ID
 /delete ID
 /list
 /rename ID NOME
 /dependson ID ID...
 /duplicate ID
 /priority ID PRIORITY{low, medium, high}
 /help
"""

# put into a classe api


class API(object):
    def get_url(self, url):
        response = requests.get(url)
        content = response.content.decode("utf8")
        return content

    def get_json_from_url(self, url):
        content = self.get_url(url)
        js = json.loads(content)
        return js

    def get_updates(self, offset=None):
        url = URL + "getUpdates?timeout=100"
        if offset:
            url += "&offset={}".format(offset)
        js = self.get_json_from_url(url)
        return js

    def send_message(self, text, chat_id, reply_markup=None):
        text = urllib.parse.quote_plus(text)
        url = URL + \
            "sendMessage?text={}&chat_id={}&parse_mode=Markdown".format(
                text, chat_id)
        if reply_markup:
            url += "&reply_markup={}".format(reply_markup)
        self.get_url(url)

    def get_last_update_id(self, updates):
        update_ids = []
        for update in updates["result"]:
            update_ids.append(int(update["update_id"]))

        return max(update_ids)


def deps_text(task, chat, preceed=''):
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
            line += '└── [[{}]] {} {}\n'.format(dep.id, icon, dep.name)
            line += deps_text(dep, chat, preceed + '    ')
        else:
            line += '├── [[{}]] {} {}\n'.format(dep.id, icon, dep.name)
            line += deps_text(dep, chat, preceed + '│   ')

        text += line

    return text


class Tags(object):
    apiBot = API()

    def new(self, msg, chat, apiBot):
        task = Task(chat=chat, name=msg, status='TODO',
                    dependencies='', parents='', priority='')
        db.session.add(task)
        db.session.commit()
        apiBot.send_message(
            "New task *TODO* [[{}]] {}".format(task.id, task.name), chat)

    def findTask(self, taskId, chat):
        query = db.session.query(Task).filter_by(id=taskId, chat=chat)
        task = query.one()

        return task

    def idErrorMessage(self, message, chat, apiBot):
        if message.isdigit():
            apiBot.send_message("Task {} not found".format(message), chat)
        else:
            apiBot.send_message("You must inform the task id", chat)

    def rename(self, message, chat, apiBot):
        newName = ''
        messageIsNotBlank = message != ''
        if messageIsNotBlank:
            if len(message.split(' ', 1)) > 1:
                newName = message.split(' ', 1)[1]
            message = message.split(' ', 1)[0]

        if message.isdigit():
            taskId = int(message)
            try:
                task = self.findTask(taskId, chat)
            except sqlalchemy.orm.exc.NoResultFound:
                self.idErrorMessage(message, chat,apiBot)
                return

            newNameIsBlank = newName == ''
            if newNameIsBlank:
                apiBot.send_message(
                    "You want to modify task {}, but you didn't provide any new name".format(taskId), chat)
                return

            oldName = task.name
            task.name = newName
            db.session.commit()
            apiBot.send_message("Task {} redefined from {} to {}".format(
                taskId, oldName, newName), chat)
        elif not message.isdigit():
            self.idErrorMessage(message, chat,apiBot)

    def duplicate(self, message, chat, apiBot):
        if message.isdigit():
            taskId = int(message)
            try:
                task = self.findTask(taskId, chat)
            except sqlalchemy.orm.exc.NoResultFound:
                self.idErrorMessage(message, chat,apiBot)
                return

            duplicatedTask = Task(chat=task.chat,
                                  name=task.name,
                                  status=task.status,
                                  dependencies=task.dependencies,
                                  parents=task.parents,
                                  priority=task.priority,
                                  duedate=task.duedate)
            db.session.add(duplicatedTask)

            for dependentTaskId in task.dependencies.split(',')[:-1]:
                dependentTask = self.findTask(dependentTaskId, chat)
                dependentTask.parents += '{},'.format(duplicatedTask.id)

            db.session.commit()
            apiBot.send_message(
                "New task *TODO* [[{}]] {}".format(duplicatedTask.id,
                                                   duplicatedTask.name),
                chat)
        elif not message.isdigit():
            self.idErrorMessage(message, chat,apiBot)

    def delete(self, message, chat, apiBot):
        if message.isdigit():
            taskId = int(message)
            try:
                task = self.findTask(taskId, chat)
            except sqlalchemy.orm.exc.NoResultFound:
                self.idErrorMessage(message, chat,apiBot)
                return
            for dependentTaskId in task.dependencies.split(',')[:-1]:
                dependentTask = self.findTask(dependentTaskId, chat)
                dependentTask.parents = dependentTask.parents.replace(
                    '{},'.format(task.id), '')
            db.session.delete(task)
            db.session.commit()
            apiBot.send_message("Task [[{}]] deleted".format(taskId), chat)
        elif not message.isdigit():
            self.idErrorMessage(message, chat,apiBot)

    def changeStatus(self, message, chat, apiBot, command):
        if message.isdigit():
            taskId = int(message)
            try:
                task = self.findTask(taskId, chat)
            except sqlalchemy.orm.exc.NoResultFound:
                self.idErrorMessage(message, chat,apiBot)
                return
            if command == '/todo':
                task.status = 'TODO'
                apiBot.send_message(
                    "*TODO* task [[{}]] {}".format(task.id, task.name), chat)
            elif command == '/doing':
                task.status = 'DOING'
                apiBot.send_message(
                    "*DOING* task [[{}]] {}".format(task.id, task.name), chat)
            else:
                task.status = 'DONE'
                apiBot.send_message(
                    "*DONE* task [[{}]] {}".format(task.id, task.name), chat)
            db.session.commit()
        elif not message.isdigit():
            self.idErrorMessage(message, chat, apiBot)

    def list_tasks(self, chat, apiBot):
        a = ''
        a += '\U0001F4CB Task List\n'
        query = db.session.query(Task).filter_by(
            parents='', chat=chat).order_by(Task.id)
        for task in query.all():
            icon = '\U0001F195'
            if task.status == 'DOING':
                icon = '\U000023FA'
            elif task.status == 'DONE':
                icon = '\U00002611'

            a += '[[{}]] {} {}\n'.format(task.id, icon, task.name)
            a += deps_text(task, chat)

        apiBot.send_message(a, chat)
        a = ''

        a += '\U0001F4DD _Status_\n'
        query = db.session.query(Task).filter_by(
            status='TODO', chat=chat).order_by(Task.id)

        a += '\n\U0001F195 *TODO*\n'
        for task in query.all():
            a += '[[{}]] {}\n'.format(task.id, task.name)
        query = db.session.query(Task).filter_by(
            status='DOING', chat=chat).order_by(Task.id)

        a += '\n\U000023FA *DOING*\n'
        for task in query.all():
            a += '[[{}]] {}\n'.format(task.id, task.name)
        query = db.session.query(Task).filter_by(
            status='DONE', chat=chat).order_by(Task.id)

        a += '\n\U00002611 *DONE*\n'
        for task in query.all():
            a += '[[{}]] {}\n'.format(task.id, task.name)

        apiBot.send_message(a, chat)

    def dependson(self, msg, chat, apiBot):
        text = ''
        if msg != '':
            if len(msg.split(' ', 1)) > 1:
                text = msg.split(' ', 1)[1]
            msg = msg.split(' ', 1)[0]

        if not msg.isdigit():
            apiBot.send_message("You must inform the task id", chat)
        else:
            task_id = int(msg)
            query = db.session.query(Task).filter_by(id=task_id, chat=chat)
            try:
                task = query.one()
            except sqlalchemy.orm.exc.NoResultFound:
                apiBot.send_message(
                    "_404_ Task {} not found x.x".format(task_id), chat)
                return

            if text == '':
                for i in task.dependencies.split(',')[:-1]:
                    i = int(i)
                    q = db.session.query(Task).filter_by(id=i, chat=chat)
                    t = q.one()
                    t.parents = t.parents.replace(
                        '{},'.format(task.id), '')

                task.dependencies = ''
                apiBot.send_message(
                    "Dependencies removed from task {}".format(task_id), chat)
            else:
                for depid in text.split(' '):
                    if not depid.isdigit():
                        apiBot.send_message(
                            "All dependencies ids must be numeric, and not {}".format(depid), chat)
                    else:
                        depid = int(depid)
                        query = db.session.query(
                            Task).filter_by(id=depid, chat=chat)
                    try:
                        taskdep = query.one()
                        taskdep.parents += str(task.id) + ','
                    except sqlalchemy.orm.exc.NoResultFound:
                        apiBot.send_message(
                            "_404_ Task {} not found x.x".format(depid), chat)
                        continue

                    deplist = task.dependencies.split(',')
                    if str(depid) not in deplist:
                        task.dependencies += str(depid) + ','
            db.session.commit()
            apiBot.send_message(
                "Task {} dependencies up to date".format(task_id), chat)

    def priority(self, msg, chat, apiBot):
        text = ''
        if msg != '':
            if len(msg.split(' ', 1)) > 1:
                text = msg.split(' ', 1)[1]
            msg = msg.split(' ', 1)[0]

        if not msg.isdigit():
            apiBot.send_message("You must inform the task id", chat)
        else:
            task_id = int(msg)
            query = db.session.query(Task).filter_by(id=task_id, chat=chat)
            try:
                task = query.one()
            except sqlalchemy.orm.exc.NoResultFound:
                apiBot.send_message(
                    "_404_ Task {} not found x.x".format(task_id), chat)
                return

            if text == '':
                task.priority = ''
                apiBot.send_message(
                    "_Cleared_ all priorities from task {}".format(task_id), chat)
            else:
                if text.lower() not in ['high', 'medium', 'low']:
                    apiBot.send_message(
                        "The priority *must be* one of the following: high, medium, low", chat)
                else:
                    task.priority = text.lower()
                    apiBot.send_message(
                        "*Task {}* priority has priority *{}*".format(task_id, text.lower()), chat)
            db.session.commit()


def handle_updates(updates):
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
            tags.changeStatus(msg, chat, apiBot, command)
        elif command == '/doing':
            tags.changeStatus(msg, chat, apiBot, command)
        elif command == '/done':
            tags.changeStatus(msg, chat, apiBot, command)
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
