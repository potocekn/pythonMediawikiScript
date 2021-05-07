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

languages_with_resources = dict()


def add_and_commit_to_repo(repo, file_name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    # print(dir_path)
    new_name = os.path.join(dir_path, file_name)
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


def get_base64_img(url):
    return base64.b64encode(requests.get(url).content).decode('utf-8')


def get_html_text(resource, language):
    link = ""
    if language != 'en':
        link = 'http://localhost/mediawiki/api.php?action=parse&page=' + resource + '/' + language + '&format=json'
    else:
        link = 'http://localhost/mediawiki/api.php?action=parse&page=' + resource + '&format=json'
    # 'http://localhost/mediawiki/api.php?action=parse&page=Languages&format=json'
    # 'http://4training.net/mediawiki/api.php?action=parse&page=Prayer&format=json'
    result = requests.get(link, verify=False)
    decoded_result = json.loads(result.text)
    resource_name = "ResourcesTest-https/" + language + "/" + resource + ".html"
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
    res = re.sub("<!--([\s\S]*?)-->", "", res)
    img = re.findall(r'src=\"(.*)\" decoding', res)
    # print('img:')
    # print(img)
    for i in img:
        if '.png' in i:
            url = " http://localhost" + i
            base64img = get_base64_img(url)
            # print(resource_name)
            # print(type(base64img))
            res = re.sub(i, "data:image/png;base64, " + base64img, res)
    # print(res)
    f.write(res)
    f.close()
    if not file_exists:
        return resource_name
    else:
        return ""


def get_repo():
    if not path.exists('ResourcesTest-https'):
        repo = git.Repo.clone_from('https://github.com/potocekn/ResourcesTest.git', 'ResourcesTest-https')
        # print('first time')
    else:
        repo = git.Repo('ResourcesTest-https')
        repo.remotes.origin.pull()
        # print('second time')
    return repo


def create_language_folders(repo, shortcuts):
    for short in shortcuts:
        if not os.path.exists(os.path.join(repo, short)):
            os.makedirs(os.path.join(repo, short))


def save_changes(file, changes):
    f = open(file, "w+", encoding="utf-8")
    f.write(json.dumps(changes))
    f.close()


def get_changes_for_language(repo, language, changed_files):
    changes = list()
    for file in changed_files:
        if language in file:
            repo.index.add(file)
            changes.append(file)
    return changes


def get_rest_for_language(language, files, changes):
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


def get_previous_versions(file):
    if os.path.exists(file):
        f = open(file, "r", encoding="utf-8")
        previous = json.load(f)
        f.close()
        return previous
    else:
        return []


def get_versions(file, changes, rest):
    versions = get_previous_versions(file)
    # print('versions')
    # print(type(versions))
    # print(versions)
    for file in changes:
        was_found = False
        if versions != [()]:
            for item in versions:
                # print('item: ')
                # print(item)
                if item != []:
                    if file in item[0]:
                        item[1] = item[1] + 1
                        was_found = True
                        break
        else:
            versions.append((file, 1))
        if not was_found:
            versions.append((file, 1))
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


def detect_changes(repo_name, repo, shortcuts, new_files, language_resources):
    changed_files = [item.a_path for item in repo.index.diff(None)]
    changed_files += new_files
    # rest = [item for item in language_resources if item not in changed_files]
    # print('Changed files')
    # print(changed_files)
    for shortcut in shortcuts:
        changes = get_changes_for_language(repo, shortcut, changed_files)
        # print('changes:')
        # print(changes)
        rest = get_rest_for_language(shortcut, language_resources, changes)
        # print('rest')
        # print(rest)
        # changes = changes + rest
        file = os.path.join(repo_name, shortcut, 'Changes.json')
        # print('Changes file: ' + file)
        changes_and_versions = get_versions(file, changes, rest)
        # print(shortcut)
        # print(changes_and_versions)
        with open(file, 'w') as f:
            json.dump(changes_and_versions, f)
        add_and_commit_to_repo(repo, file)
    repo.index.commit(' content changed')


def work_with_repo(repo, resources_list, shortcuts):
    create_language_folders('ResourcesTest-https', shortcuts)
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
            request = requests.get('http://localhost/mediawiki/index.php/' + full_name)
            if request.status_code == 200:
                # print('exists' + full_name)
                exists = get_html_text(resource, shortcut)
                if exists != "":
                    dir_path = os.path.dirname(os.path.realpath(__file__))
                    # print(dir_path)
                    new_name = os.path.join(dir_path, exists)
                    new_files.append(new_name)
                    print('new name: ' + new_name)
                language_resources.append(file_name)
    serialized = json.dumps(languages_with_resources)
    write_to_file('ResourcesTest-https/LanguagesWithResources.json', serialized)
    add_and_commit_to_repo(repo, 'ResourcesTest-https/LanguagesWithResources.json')
    # print('lwr')
    # print(language_resources)
    detect_changes('ResourcesTest-https', repo, shortcuts,new_files, language_resources)
    repo.remotes.origin.push()


if __name__ == '__main__':
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
