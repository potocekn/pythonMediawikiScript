# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import base64
import requests
import json
import git
import os
from os import path
import re


# pip install requests
# needed to use requests and not piwikibot because of self signed certificate (authentication failed)
# Press the green button in the gutter to run the script.

class Processor:
    languages_with_resources = dict()
    repo = None
    repo_folder_name = None
    repo_URL = None
    resource_server = None

    def __init__(self, repo_folder_name, repo_url, resource_server):
        self.repo_folder_name = repo_folder_name
        self.repo_URL = repo_url
        self.resource_server = resource_server

    def add_and_commit_to_repo(self, file_name):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        # print(dir_path)
        new_name = os.path.join(dir_path, file_name)
        self.repo.index.add(new_name)
        self.repo.index.commit(' content changed')
        self.repo.remotes.origin.push()

    def write_to_file(self, file, what_to_write):
        f = open(file, "w+", encoding="utf-8")
        f.write(what_to_write)
        f.close()

    def get_languages(self):
        link = 'http://' + self.resource_server + '/mediawiki/api.php?action=parse&page=Languages&format=json'
        result = requests.get(link, verify=False)
        decoded_result = json.loads(result.text)
        res = decoded_result['parse']['text']['*']
        languages_items = re.findall(r'<li>(.*)<\/li>', res)
        extracted = self.extract_languages(languages_items)
        serialized = json.dumps(extracted)
        file_name = self.repo_folder_name + '/Languages.json'
        file_exists = path.exists(file_name)
        self.write_to_file(file_name, serialized)
        if not file_exists:
            self.add_and_commit_to_repo(file_name)
        return extracted

    def extract_languages(self, list_to_change):
        for item in list_to_change:
            item.replace('<li>', '')
            item.replace('</li>', '')
        return list_to_change

    def get_resources(self):
        link = 'http://' + self.resource_server + '/mediawiki/api.php?action=parse&page=Resources&format=json'
        result = requests.get(link, verify=False)
        decoded_result = json.loads(result.text)
        res = decoded_result['parse']['text']['*']
        resources_items = re.findall(r'<a(.*)>(.*)<\/a>', res)
        extracted = self.extract_resources(resources_items)
        serialized = json.dumps(extracted)
        file_name = self.repo_folder_name + '/Resources.json'
        file_exists = path.exists(file_name)
        self.write_to_file(file_name, serialized)
        if not file_exists:
            self.add_and_commit_to_repo(file_name)
        return extracted

    def extract_resources(self, list_to_change):
        result = list()
        for item in list_to_change:
            result.append(item[1])
        return result

    def get_base64_img(self, url):
        return base64.b64encode(requests.get(url).content).decode('utf-8')

    def get_html_text(self, resource, language):
        link = ""
        if language != 'en':
            link = 'http://' + self.resource_server + '/mediawiki/api.php?action=parse&page=' + resource + '/' \
                   + language + '&format=json'
        else:
            link = 'http://' + self.resource_server + '/mediawiki/api.php?action=parse&page=' + resource \
                   + '&format=json'
        # 'http://localhost/mediawiki/api.php?action=parse&page=Languages&format=json'
        # 'http://4training.net/mediawiki/api.php?action=parse&page=Prayer&format=json'
        result = requests.get(link, verify=False)
        decoded_result = json.loads(result.text)
        resource_name = self.repo_folder_name + "/" + language + "/" + resource + ".html"
        if language in self.languages_with_resources:
            if len(self.languages_with_resources[language]) == 0:
                self.languages_with_resources[language][0] = resource
            else:
                self.languages_with_resources[language].append(resource)
        else:
            self.languages_with_resources[language] = [resource]
        file_exists = path.exists(resource_name)
        f = open(resource_name, "w+", encoding="utf-8")
        res = decoded_result['parse']['text']['*']
        res = re.sub("<!--([\s\S]*?)-->", "", res)
        img = re.findall(r'src=\"(.*)\" decoding', res)
        # print('img:')
        # print(img)
        for i in img:
            url = 'http://' + self.resource_server + i
            base64img = self.get_base64_img(url)
            if '.png' in i:
                # print(resource_name)
                # print(type(base64img))
                res = re.sub(i, "data:image/png;base64, " + base64img, res)
            if '.jpeg' in i:
                res = re.sub(i, "data:image/jpeg;base64, " + base64img, res)
        # print(res)
        f.write(res)
        f.close()
        if not file_exists:
            return resource_name
        else:
            return ""

    def get_repo(self):
        if not path.exists(self.repo_folder_name):
            repo = git.Repo.clone_from(self.repo_URL, self.repo_folder_name)
            # print('first time')
        else:
            repo = git.Repo(self.repo_folder_name)
            repo.remotes.origin.pull()
            # print('second time')
        return repo

    def create_language_folders(self, shortcuts):
        for short in shortcuts:
            if not os.path.exists(os.path.join(short)):
                os.makedirs(os.path.join(short))

    def save_changes(self, file, changes):
        f = open(file, "w+", encoding="utf-8")
        f.write(json.dumps(changes))
        f.close()

    def get_changes_for_language(self, language, changed_files):
        changes = list()
        for file in changed_files:
            if language in file:
                dir_path = os.path.dirname(os.path.realpath(__file__))
                full_name = os.path.join(dir_path, self.repo_folder_name, file)
                self.repo.index.add(full_name)
                changes.append(file)
        print(language + 'changes:')
        print(changes)
        return changes

    def get_rest_for_language(self, language, files, changes):
        rest = list()
        # print('changes from method')
        # print(changes)
        print('lwr from method')
        print(files)
        for file in files:
            if (file not in changes) & (language + '/' in file):
                rest.append(file)
        # print('rest from method')
        # print(rest)
        return rest

    def get_previous_versions(self, file):
        if os.path.exists(file):
            f = open(file, "r", encoding="utf-8")
            previous = json.load(f)
            f.close()
            return previous
        else:
            return []

    def handle_changes(self, versions, changes):
        for file in changes:
            print(file)
            was_found = False
            if versions != []:
                for item in versions:
                    # print('item: ')
                    # print(item)
                    if item != []:
                        if file in item[0]:
                            item[1] = item[1] + 1
                            was_found = True
                            break
                if not was_found:
                    versions.append((file, 1))
            else:
                versions.append((file, 1))
        return versions

    def handle_rest(self, versions, rest):
        for file in rest:
            was_found = False
            for item in versions:
                if item != []:
                    if file in item[0]:
                        was_found = True
                        break
            if not was_found:
                versions.append((file, 1))
        return versions

    def get_versions(self, file, changes, rest):
        versions = self.get_previous_versions(file)
        print('versions previous')
        print(versions)
        versions = self.handle_changes(versions, changes)
        print('versions changes')
        print(versions)
        versions = self.handle_rest(versions, rest)
        print('versions rest')
        print(versions)
        return versions

    def detect_changes(self, shortcuts, new_files, language_resources):
        changed_files = [item.a_path for item in self.repo.index.diff(None)]
        changed_files += new_files
        # rest = [item for item in language_resources if item not in changed_files]
        print('Changed files')
        print(changed_files)
        for shortcut in shortcuts:
            changes = self.get_changes_for_language(shortcut, changed_files)
            # print('changes:')
            # print(changes)
            rest = self.get_rest_for_language(shortcut, language_resources, changes)
            # print('rest')
            # print(rest)
            # changes = changes + rest
            file = os.path.join(self.repo_folder_name, shortcut, 'Changes.json')
            # print('Changes file: ' + file)
            changes_and_versions = self.get_versions(file, changes, rest)
            # print(shortcut)
            # print(changes_and_versions)
            with open(file, 'w') as f:
                json.dump(changes_and_versions, f)
            self.add_and_commit_to_repo(file)
        self.repo.index.commit(' content changed')

    def work_with_repo(self, resources_list, shortcuts):
        self.create_language_folders(shortcuts)
        new_files = list()
        language_resources = list()
        for shortcut in shortcuts:
            # new_files = list()
            for resource in resources_list:
                full_name = resource
                if shortcut != 'en':
                    full_name = full_name + '/' + shortcut
                file_name = shortcut + '/' + resource + '.html'
                # print(full_name)
                request = requests.get('http://' + self.resource_server + '/mediawiki/index.php/' + full_name)
                if request.status_code == 200:
                    # print('exists' + full_name)
                    exists = self.get_html_text(resource, shortcut)
                    if exists != "":
                        dir_path = os.path.dirname(os.path.realpath(__file__))
                        # print(dir_path)
                        new_name = re.sub(self.repo_folder_name + '/', '', exists)
                        new_files.append(new_name)
                        self.add_and_commit_to_repo(os.path.join(dir_path, exists))
                        # print('new name: ' + shortcut + '/' + resource + '.html')
                    language_resources.append(file_name)
        serialized = json.dumps(self.languages_with_resources)
        self.write_to_file(self.repo_folder_name + '/LanguagesWithResources.json', serialized)
        self.add_and_commit_to_repo(self.repo_folder_name + '/LanguagesWithResources.json')
        # print('lwr')
        # print(language_resources)
        self.detect_changes(shortcuts, new_files, language_resources)
        self.repo.remotes.origin.push()

    def process_server_resources(self):
        self.repo = self.get_repo()
        print('got repo')
        languages = self.get_languages()
        print(languages)
        shorts = ['en', 'cs', 'de']
        resources = self.get_resources()
        print(resources)
        self.work_with_repo(resources, shorts)
        print(self.languages_with_resources)


if __name__ == '__main__':
    processor = Processor('ResourcesTest-https', 'https://github.com/potocekn/ResourcesTest.git', 'localhost')
    processor.process_server_resources()
    # repo url 'https://github.com/potocekn/ResourcesTest.git'
