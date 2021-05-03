# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import pywikibot
import requests
import json
import git
import os.path
from os import path
import re

# pip install requests
# needed to use requests and not piwikibot because of self signed certificate (authentication failed)

# Press the green button in the gutter to run the script.

languages_with_resources = dict()


def add_and_commit_to_repo(repo, file_name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    print(dir_path)
    new_name = dir_path + '/' + file_name
    new_name = re.sub('/', '\\\\', new_name)
    repo.index.add(new_name)
    repo.index.commit(' content changed')
    repo.remotes.origin.push()


def write_to_file(file, what_to_write):
    f = open(file, "w+", encoding="utf-8")
    f.write(what_to_write)
    f.close()


def get_languages(repo, git_folder):
    link = 'http://localhost/mediawiki/api.php?action=parse&page=Languages&format=json'
    result = requests.get(link, verify=False)
    decoded_result = json.loads(result.text)
    res = decoded_result['parse']['text']['*']
    languages_items = re.findall(r'<li>(.*)<\/li>', res)
    extracted = extract_languages(languages_items)
    serialized = json.dumps(extracted)
    file_name = git_folder + '/Languages.json'
    file_exists = path.exists(file_name)
    write_to_file(file_name, serialized)
    if not file_exists:
        add_and_commit_to_repo(repo, file_name)
    return extracted


def extract_languages(list_to_change):
    for item in list_to_change:
        item.replace('<li>', '')
        item.replace('</li>', '')
    return list_to_change


def get_resources(repo, git_folder):
    link = 'http://localhost/mediawiki/api.php?action=parse&page=Resources&format=json'
    result = requests.get(link, verify=False)
    decoded_result = json.loads(result.text)
    res = decoded_result['parse']['text']['*']
    resources_items = re.findall(r'<a(.*)>(.*)<\/a>', res)
    extracted = extract_resources(resources_items)
    serialized = json.dumps(extracted)
    file_name = git_folder + '/Resources.json'
    file_exists = path.exists(file_name)
    write_to_file(file_name, serialized)
    if not file_exists:
        add_and_commit_to_repo(repo, file_name)
    return extracted


def extract_resources(list_to_change):
    result = list()
    for item in list_to_change:
        result.append(item[1])
    return result


def get_html_text(resource, language):
    link = ""
    if language != 'en':
        link = 'http://localhost/mediawiki/api.php?action=parse&page='+resource+'/'+language+'&format=json'
    else:
        link = 'http://localhost/mediawiki/api.php?action=parse&page=' + resource + '&format=json'
    # 'http://localhost/mediawiki/api.php?action=parse&page=Languages&format=json'
    # 'http://4training.net/mediawiki/api.php?action=parse&page=Prayer&format=json'
    result = requests.get(link, verify=False)
    decoded_result = json.loads(result.text)
    resource_name = "ResourcesTest-https/"+language+"/" + resource + ".html"
    print(resource_name)
    if language in languages_with_resources:
        if len(languages_with_resources[language]) == 0:
            languages_with_resources[language][0] = resource
        else:
            languages_with_resources[language].append(resource)
    else:
        languages_with_resources[language] = [resource]
    file_exists = path.exists(resource_name)
    f = open(resource_name, "w+", encoding="utf-8")
    res = decoded_result['parse']['text']['*']
    f.write(res)
    f.close()
    if not file_exists:
        return resource_name
    else:
        return ""


def get_repo():
    if not path.exists('ResourcesTest-https'):
        repo = git.Repo.clone_from('https://github.com/potocekn/ResourcesTest.git', 'ResourcesTest-https')
        print('first time')
    else:
        repo = git.Repo('ResourcesTest-https')
        repo.remotes.origin.pull()
        print('second time')
    return repo


def create_language_folders(repo, shortcuts):
    for short in shortcuts:
        if not os.path.exists(repo + '/' + short):
            os.makedirs(repo + '/' + short)


def work_with_repo(repo, resources_list, shortcuts):
    create_language_folders('ResourcesTest-https', shortcuts)
    new_files = list()
    for shortcut in shortcuts:
        for resource in resources_list:
            full_name = resource
            if shortcut != 'en':
                full_name = full_name + '/' + shortcut
            request = requests.get('http://localhost/mediawiki/index.php/' + full_name)
            if request.status_code == 200:
                exists = get_html_text(resource, shortcut)
                if exists != "":
                    dir_path = os.path.dirname(os.path.realpath(__file__))
                    print(dir_path)
                    new_name = dir_path + '/' + exists
                    new_name = re.sub('/', '\\\\', new_name)
                    new_files.append(new_name)

    changed_files = [item.a_path for item in repo.index.diff(None)]
    print('Changed:')
    print(changed_files)
    for file in changed_files:
        repo.index.add(file)
        repo.index.commit(' content changed')
    print(new_files)
    for file in new_files:
        repo.index.add(file)
        repo.index.commit(' content changed')
    serialized = json.dumps(languages_with_resources)
    write_to_file('ResourcesTest-https/LanguagesWithResources.json',serialized)
    add_and_commit_to_repo(repo, 'ResourcesTest-https/LanguagesWithResources.json')
    repo.remotes.origin.push()


if __name__ == '__main__':
    # site = pywikibot.Site()
    # print('after site')
    # page = pywikibot.Page(site,'Languages')
    # print('after page')
    # print(page.text)
    #work_with_repo()
    repository = get_repo()
    print('got repo')
    languages = get_languages(repository, 'ResourcesTest-https')
    print(languages)
    shorts = ['en', 'cs']
    resources = get_resources(repository, 'ResourcesTest-https')
    print(resources)
    work_with_repo(repository, resources, shorts)
    print(languages_with_resources)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
