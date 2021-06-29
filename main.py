import base64
import sys
import requests
import json
from collections import namedtuple
from json import JSONEncoder
import git
import os
from os import path
from iso639 import languages
import re
import http.client as httplib


# A class that holds all necessary information from user configuration such as the URL to the github repository,
# the mediawiki server URL and the name of the folder that contains the local git repository
class UserInfo:
    repo_folder_name: str
    repo_URL: str
    resource_server: str

    def __init__(self, repo_folder_name, repo_url, resource_server):
        self.repo_folder_name = repo_folder_name
        self.repo_URL = repo_url
        self.resource_server = resource_server


# A class that is responsible for processing the resources from mediawiki server to local git repo and then to the
# github repository. This class contains all necessary methods for this processing.
class Processor:
    languages_with_resources = dict()
    repo = None
    userInfo = None

    def __init__(self, user_info: UserInfo):
        if hasattr(user_info, 'repo_folder_name') \
                & hasattr(user_info, 'repo_URL') \
                & hasattr(user_info, 'resource_server'):
            self.userInfo = user_info
        else:
            raise AttributeError()

    # Method used for adding and committing of new files or changed files to the repository.
    def add_and_commit_to_repo(self, file_name):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        new_name = os.path.join(dir_path, file_name)
        self.repo.index.add(new_name)
        self.repo.index.commit(' content changed')
        self.repo.remotes.origin.push()

    # Method that saves given content to the file with given file name.
    def write_to_file(self, file, what_to_write):
        f = open(file, "w+", encoding="utf-8")
        f.write(what_to_write)
        f.close()

    # Method that connects to the mediawiki server and from the Languages page downloads the list of all available
    # languages on the server. The list is saved into the Languages.json file in the git repository.
    def get_languages(self):
        link = 'http://' + self.userInfo.resource_server + '/mediawiki/api.php?action=parse&page=Languages&format=json'
        result = requests.get(link, verify=False)
        decoded_result = json.loads(result.text)
        if decoded_result['parse']['text']['*']:
            res = decoded_result['parse']['text']['*']
            languages_items = re.findall(r'<li>(.*)<\/li>', res)
            extracted = self.extract_languages(languages_items)
            serialized = json.dumps(extracted)
            file_name = self.userInfo.repo_folder_name + '/Languages.json'
            file_exists = path.exists(file_name)
            self.write_to_file(file_name, serialized)
            if not file_exists:
                self.add_and_commit_to_repo(file_name)
            return extracted
        else:
            return []

    # Method used for extracting the names of languages from a list that contains html item tags '<li>' and '</li>'.
    def extract_languages(self, list_to_change):
        for item in list_to_change:
            item.replace('<li>', '')
            item.replace('</li>', '')
        return list_to_change

    # Method that connects to the mediawiki server and downloads the list of all available resources on the server.
    # The list is stored in the Resources.json file in the git repository.
    def get_resources(self):
        link = 'http://' + self.userInfo.resource_server + '/mediawiki/api.php?action=parse&page=Resources&format=json'
        result = requests.get(link, verify=False)
        decoded_result = json.loads(result.text)
        if decoded_result['parse']['text']['*']:
            res = decoded_result['parse']['text']['*']
            resources_items = re.findall(r'<a(.*)>(.*)<\/a>', res)
            extracted = self.extract_resources(resources_items)
            serialized = json.dumps(extracted)
            file_name = self.userInfo.repo_folder_name + '/Resources.json'
            file_exists = path.exists(file_name)
            self.write_to_file(file_name, serialized)
            if not file_exists:
                self.add_and_commit_to_repo(file_name)
            return extracted
        else:
            return []

    # Method used for extracting the resource names from the 2D array that was a result of extracting the <a href ...>
    # parts from the html result of Resources page.
    def extract_resources(self, list_to_change):
        result = list()
        for item in list_to_change:
            result.append(item[1])
        return result

    # Method that downloads an image from given url and returns its base64 value
    def get_base64_img(self, url):
        return base64.b64encode(requests.get(url).content).decode('utf-8')

    # Method that downloads the html source of a resource in given language and adapts it into a suitable form for the
    # mobile application webview (images -> base64 values). The content of the new html text is stored in the language
    # folder in the HTML subfolder.
    def get_html_text(self, resource, language):
        link = ""
        if language != 'en':
            link = 'http://' + self.userInfo.resource_server + '/mediawiki/api.php?action=parse&page=' + resource + \
                   '/' + language + '&format=json'
        else:
            link = 'http://' + self.userInfo.resource_server + '/mediawiki/api.php?action=parse&page=' + resource \
                   + '&format=json'

        result = requests.get(link, verify=False)
        decoded_result = json.loads(result.text)
        resource_name = self.userInfo.repo_folder_name + "/" + language + "/HTML/" + resource + ".html"

        # append the resource in the list for given language
        if language in self.languages_with_resources:
            if len(self.languages_with_resources[language]) == 0:
                self.languages_with_resources[language][0] = resource
            else:
                self.languages_with_resources[language].append(resource)
        else:
            self.languages_with_resources[language] = [resource]

        file_exists = path.exists(resource_name)
        f = open(resource_name, "w+", encoding="utf-8")

        if not decoded_result['parse']['text']['*']:
            return ""
        res = decoded_result['parse']['text']['*']
        # delete the HTML comments
        res = re.sub("<!--([\s\S]*?)-->", "", res)
        # find images
        img = re.findall(r'src=\"(.*)\" decoding', res)

        # get the correct format verion of base64 value of images and insert them into the HTML text
        for i in img:
            url = 'http://' + self.userInfo.resource_server + i
            base64img = self.get_base64_img(url)
            if '.png' in i:
                res = re.sub(i, "data:image/png;base64, " + base64img, res)
            if '.jpeg' in i:
                res = re.sub(i, "data:image/jpeg;base64, " + base64img, res)

        # save the changes content into the file
        f.write(res)
        f.close()
        if not file_exists:
            return resource_name
        else:
            return ""

    # Method for syncing with the main github repository. If the local version exists only pull is called. Otherwise
    # the repository is cloned in the folder that is specified in the user config file.
    def get_repo(self):
        if not path.exists(self.userInfo.repo_folder_name):
            try:
                repo = git.Repo.clone_from(self.userInfo.repo_URL, self.userInfo.repo_folder_name)
            except:
                raise ConnectionError()
        else:
            repo = git.Repo(self.userInfo.repo_folder_name)
            repo.remotes.origin.pull()
        return repo

    # Create a subfolder for given format in given language folder if it does not exist.
    def create_format_folder(self, language, format):
        if not os.path.exists(os.path.join(language, format)):
            os.makedirs(os.path.join(self.userInfo.repo_folder_name, language, format))

    # Creates the language folder in the git repo with the format subfolders for HTML, PDF and ODT
    def create_language_folders(self, shortcuts):
        for short in shortcuts:
            if not os.path.exists(os.path.join(self.userInfo.repo_folder_name, short)):
                os.makedirs(os.path.join(self.userInfo.repo_folder_name, short))
                self.create_format_folder(short, "HTML")
                self.create_format_folder(short, "PDF")
                self.create_format_folder(short, "ODT")

    # Method for finding changed files for a language. All of the new or changed files are stored in the changed_files
    # list passed as an argument of this function and are filtered based on the desired language. The changes of the
    # language resources are then added in a separate list and returned the a result of the function.
    def get_changes_for_language(self, language, changed_files):
        changes = list()
        for file in changed_files:
            if language in file:
                dir_path = os.path.dirname(os.path.realpath(__file__))
                full_name = os.path.join(dir_path, self.userInfo.repo_folder_name, file)
                self.repo.index.add(full_name)
                if ".html" in file:
                    changes.append(file)
        return changes

    # Method to filter files that did not change for the given language.
    def get_rest_for_language(self, language, files, changes):
        rest = list()
        for file in files:
            if (file not in changes) & (language + '/' in file):
                rest.append(file)
        return rest

    # Load previously stored version information and return it as a list of resources and their version numbers.
    def get_previous_versions(self, file):
        if os.path.exists(file):
            f = open(file, "r", encoding="utf-8")
            previous = json.load(f)
            f.close()
            return previous
        else:
            return []

    # Method for updating the version numbers in case of a change. New file gets the version number 1. When a change
    # is detected the version number is incremented by 1.
    def handle_changes(self, versions, changes):
        for file in changes:
            was_found = False
            if versions != []:
                for item in versions:
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

    # Method for ensuring that all the non-changed files have a version number and are stored in the versions list.
    # In case there was a mistake and for some reason the resource does not have a version number,
    # the number is set to 1.
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

    # Method that updates versions of all files and returns the updated list.
    def get_versions(self, file, changes, rest):
        versions = self.get_previous_versions(file)
        versions = self.handle_changes(versions, changes)
        versions = self.handle_rest(versions, rest)
        return versions

    # Method that detects changes for each language and saves them in the Changes.json file in the language
    # folder in the git repo.
    def detect_changes(self, shortcuts, new_files, language_resources):
        changed_files = [item.a_path for item in self.repo.index.diff(None)]
        changed_files += new_files
        for shortcut in shortcuts:
            changes = self.get_changes_for_language(shortcut, changed_files)
            rest = self.get_rest_for_language(shortcut, language_resources, changes)
            file = os.path.join(self.userInfo.repo_folder_name, shortcut, 'Changes.json')
            changes_and_versions = self.get_versions(file, changes, rest)
            with open(file, 'w') as f:
                json.dump(changes_and_versions, f)
            self.add_and_commit_to_repo(file)
        self.repo.index.commit(' content changed')

    # Method for downloading the actual versions of the HTML pages of resources for each language that is available
    # on the mediawiki server. For each language a list of resources is remembered and all of these lists are saved
    # in the LanguagesWithResources.json file in the git repo.
    def get_actual_html_files(self, resources_list, shortcuts):
        self.create_language_folders(shortcuts)
        new_files = list()
        language_resources = list()
        for shortcut in shortcuts:
            for resource in resources_list:
                full_name = resource
                if shortcut != 'en':
                    full_name = full_name + '/' + shortcut
                file_name = shortcut + '/HTML/' + resource + '.html'
                request = requests.get('http://' + self.userInfo.resource_server + '/mediawiki/index.php/' + full_name)
                if request.status_code == 200:
                    exists = self.get_html_text(resource, shortcut)
                    if exists != "":
                        dir_path = os.path.dirname(os.path.realpath(__file__))
                        new_name = re.sub(self.userInfo.repo_folder_name + '/', '', exists)
                        new_files.append(new_name)
                        self.add_and_commit_to_repo(os.path.join(dir_path, exists))
                    language_resources.append(file_name)
        serialized = json.dumps(self.languages_with_resources)
        self.write_to_file(self.userInfo.repo_folder_name + '/LanguagesWithResources.json', serialized)
        self.add_and_commit_to_repo(self.userInfo.repo_folder_name + '/LanguagesWithResources.json')
        self.detect_changes(shortcuts, new_files, language_resources)
        self.repo.remotes.origin.push()

    # Method for saving file into a specified language and format folder with given file name.
    def save_file(self, content, language, format, name):
        full_name = os.path.join(self.userInfo.repo_folder_name, language, format, name)
        with open(full_name, 'wb') as f:
            f.write(content)
            self.add_and_commit_to_repo(full_name)

    # Method for downloading and saving the PDF and ODT files.
    def get_actual_pdf_or_odt_files(self, url, resources_list, shortcuts, format, format_folder):
        for resource in resources_list:
            for shortcut in shortcuts:
                file_name = resource + "-" + shortcut + format
                full_path = url + file_name
                request = requests.get(full_path)
                if request.status_code == 200:
                    self.save_file(request.content, shortcut, format_folder, file_name)
        changed_files = [item.a_path for item in self.repo.index.diff(None)]
        for f in changed_files:
            full_file_name = os.path.join(self.userInfo.repo_folder_name, f)
            self.add_and_commit_to_repo(full_file_name)

    #Method for getting a list of shortcuts for the list of full language names.
    def get_language_shortcuts(self, language_names):
        shortcuts = list()
        for language in language_names:
            language_info = languages.get(name=language)
            shortcuts.append(language_info.alpha2)
        return shortcuts

    #Method to determine if there is an Internet connection.
    def has_internet(self):
        conn = httplib.HTTPConnection(self.userInfo.resource_server, timeout=5)
        try:
            conn.request("HEAD", "/")
            conn.close()
            return True
        except:
            conn.close()
            return False

    #Method for processing the actual state of resources on the mediawiki server.
    def process_server_resources(self):
        try:
            self.repo = self.get_repo()
        except ConnectionError:
            print("The online repository is currently unavailable.")
            return
        print('successfully got repository')
        if not self.has_internet():
            print("The mediawiki server is currently unavailable.")
            return
        print("Getting available languages ...")
        languages = self.get_languages()
        shorts = self.get_language_shortcuts(languages)
        print("Getting available resources ...")
        resources = self.get_resources()
        print("Starting downloading the files ... ")
        print("This may take a while ... ")
        self.get_actual_html_files(resources, shorts)
        url = "http://" + self.userInfo.resource_server + "/mediawiki/index.php/Special:Filepath/"
        self.get_actual_pdf_or_odt_files(url, resources, shorts, ".pdf", "PDF")
        self.get_actual_pdf_or_odt_files(url, resources, shorts, ".odt", "ODT")
        print(self.languages_with_resources)
        print("Update successful!")


class UserInfoEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


def custom_user_info_decoder(user_info_dict):
    return namedtuple('X', user_info_dict.keys())(*user_info_dict.values())


def read_form_file(file_name):
    f = open(file_name, "r", encoding="utf-8")
    result = f.read()
    result = re.sub('\n', '', result)
    f.close()
    return result


def main(argv):
    if len(argv) == 2:
        file = argv[1]
        if not os.path.exists(file):
            print("Non-existent config file!")
            return
        res = read_form_file(file)
        user_info = ""
        try:
            user_info = json.loads(res, object_hook=custom_user_info_decoder)
        except:
            print("Wrong format of the config file!")
            return
        try:
            processor = Processor(user_info)
            processor.process_server_resources()
        except AttributeError:
            print("Wrong internal structure of the config file!")
        except ConnectionError:
            print("The server is currently unavailable.")

    else:
        print("Wrong amount of args.")


if __name__ == '__main__':
    main(sys.argv)
