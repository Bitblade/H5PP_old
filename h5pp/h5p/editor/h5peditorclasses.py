# Handles all communication with the database

import collections
import shutil
import json
import re
import os
import urllib.parse
from pathlib import Path

from django.conf import settings


class H5PDjangoEditor:
    global buildBase
    buildBase = None

    ##
    # Constructor for the core editor library
    ##
    def __init__(self, h5p, storage, base_path, files_dir, editor_files_dir=None):
        self.h5p = h5p
        self.storage = storage
        self.basePath = base_path
        self.contentFilesDir = Path(files_dir) / 'content'
        if editor_files_dir is None:
            self.editorFilesDir = Path(files_dir) / 'editor'
        else:
            self.editorFilesDir = Path(editor_files_dir) / 'editor'

    ##
    # This does a lot of the same as getLibraries in library/H5PClasses.py. Use that instead ?
    ##
    def getLibraries(self, request):
        libraries = None
        if 'libraries[]' in request.POST:
            lib = dict(request.POST.lists())
            lib_list = list()
            for name in lib['libraries[]']:
                lib_list.append(name)
            libraries = list()
            for libraryName in lib_list:
                matches = re.search(r'(.+)\s(\d+)\.(\d+)$', libraryName)
                if matches:
                    libraries.append(
                        {'uberName': libraryName, 'name': matches.group(1), 'majorVersion': matches.group(2),
                         'minorVersion': matches.group(3)})

        libraries = self.storage.getLibraries(libraries)

        return json.dumps(libraries)

    ##
    # Get all scripts, css and semantics data for a library
    ##
    def getLibraryData(self, machine_name, major_version, minor_version, language_code, prefix=''):
        libraries = self.findEditorLibraries(machine_name, major_version, minor_version)
        library_data = dict()
        library_data['semantics'] = self.h5p.load_library_semantics(machine_name, major_version, minor_version)
        library_data['language'] = self.getLibraryLanguage(machine_name, major_version, minor_version, language_code)

        # TODO Fix or remove nonfunctional aggregateAssets tech
        # aggregateAssets = self.h5p.aggregateAssets
        # self.h5p.aggregateAssets = False

        files = self.h5p.get_dependencies_files(libraries)

        # TODO Fix or remove nonfunctional aggregateAssets tech
        # self.h5p.aggregateAssets = aggregateAssets

        # Create base URL
        url = urllib.parse.urljoin(settings.MEDIA_URL, 'h5pp/')
        url = urllib.parse.urljoin(url, prefix)
        # url = settings.MEDIA_URL + '/h5pp' + prefix

        # JavaScripts
        if 'scripts' in files:
            for script in files['scripts']:
                if re.search(r'/://', script['path']):
                    # External file
                    if 'javascript' not in library_data:
                        library_data['javascript'] = collections.OrderedDict()
                    library_data['javascript'][script['path'] + script['version']] = '\n' + script['path'].read()
                else:
                    # Local file
                    if 'javascript' not in library_data:
                        library_data['javascript'] = collections.OrderedDict()

                    library_data['javascript'][url + script['path'] + script['version']] = \
                        '\n' + self.h5p.fs.get_content(Path(script['path']))

        # Stylesheets
        if 'styles' in files:
            for css in files['styles']:
                if re.search(r'/:///', css['path']):
                    # External file
                    if 'css' not in library_data:
                        library_data['css'] = dict()
                    library_data['css'][css['path'] + css['version']] = css['path'].read()
                else:
                    # Local file
                    if 'css' not in library_data:
                        library_data['css'] = dict()
                    self.buildCssPath(None, url + os.path.dirname(css['path']) + '/')
                    library_data['css'][url + css['path'] + css['version']] = re.sub(
                        r'(?i)url\([\']?(?![a-z]+:|/+)([^\')]+)[\']?\)', self.buildCssPath,
                        self.h5p.fs.get_content(Path(css['path'])))

        # Add translations for libraries
        for key, library in list(libraries.items()):
            language = self.getLibraryLanguage(library['machine_name'], library['major_version'],
                                               library['minor_version'], language_code)
            if language is not None:
                lang = '; H5PEditor.language["' + library['machine_name'] + '"] = ' + language + ';'
                library_data['javascript'][lang] = lang

        return json.dumps(library_data)

    ##
    # Return all libraries used by the given editor library
    ##
    def findEditorLibraries(self, machineName, majorVersion, minorVersion):
        library = self.h5p.load_library(machineName, majorVersion, minorVersion)
        dependencies = dict()
        self.h5p.find_library_dependencies(dependencies, library)

        # Order dependencies by weight
        ordered_dependencies = collections.OrderedDict()
        for i in range(1, len(dependencies) + 1):
            for key, dependency in list(dependencies.items()):
                if dependency['weight'] == i and dependency['type'] == 'editor':
                    # Only load editor libraries
                    dependency['library']['id'] = dependency['library']['library_id']
                    ordered_dependencies[dependency['library']['library_id']] = dependency['library']
                    break

        return ordered_dependencies

    def getLibraryLanguage(self, machineName, majorVersion, minorVersion, langageCode):
        language = self.storage.getLanguage(machineName, majorVersion, minorVersion, langageCode)
        return None if not language else language

    ##
    # Create directories for uploaded content
    ##
    def createDirectories(self, contentId):
        self.contentDirectory = self.contentFilesDir / str(contentId)
        if not os.path.isdir(self.contentFilesDir):
            os.mkdir(self.basePath / self.contentFilesDir)

        sub_directories = ['', 'files', 'images', 'videos', 'audios']
        for sub_directory in sub_directories:
            sub_directory = self.contentDirectory / sub_directory
            if not os.path.isdir(sub_directory):
                os.mkdir(sub_directory)

        return True

    ##
    # Move uploaded files, remove old files and update library usage
    ##
    def processParameters(self, content_Id, new_library, new_parameters, old_library=None, old_parameters=None):
        new_files = list()
        old_files = list()
        field = {'type': 'library'}
        library_params = {'library': self.h5p.library_to_string(new_library), 'params': new_parameters}
        self.processField(field, library_params, new_files)
        if old_library is not None:
            old_semantics = self.h5p.load_library_semantics(
                old_library['name'], old_library['majorVersion'],
                old_library['minorVersion'], old_parameters
            )

            # TODO Parameter params unfilled...
            self.processSemantics(old_files, old_semantics, [])

            for i in range(0, len(old_files)):
                if not old_files[i] in new_files and not re.search(r'(?i)^(\w+://|\.\./)', old_files[i]):
                    remove_file = self.contentDirectory + old_files[i]
                    self.storage.removeFile(remove_file)

    ##
    # Recursive function that moves the new files in to the h5p content folder and generates a list over the old files
    # Also locates all the libraries
    ##
    def processSemantics(self, files, semantics, params):
        for i in range(0, len(semantics)):
            field = semantics[i]
            if not field['name'] in params:
                continue
            self.processField(field, params[field['name']], files)

    ##
    # Process a single field
    ##
    def processField(self, field, params, files):
        if field['type'] == 'image' or field['type'] == 'file':
            if 'path' in params:
                self.processFile(params, files)
                if 'originalImage' in params and 'path' in params['originalImage']:
                    self.processFile(params['originalImage'], files)
            return
        elif field['type'] == 'audio' or field['type'] == 'video':
            if isinstance(params, list):
                for i in range(0, len(params)):
                    self.processFile(params[i], files)
            return
        elif field['type'] == 'library':
            if 'library' in params and 'params' in params:
                library = self.libraryFromString(params['library'])
                semantics = self.h5p.load_library_semantics(library['machineName'], library['majorVersion'],
                                                            library['minorVersion'])
                self.processSemantics(files, semantics, params['params'])
            return
        elif field['type'] == 'group':
            if params:
                if len(field['fields']) == 1:
                    params = {field['fields'][0]['name']: params}
                self.processSemantics(files, field['fields'], params)
            return
        elif field['type'] == 'list':
            if isinstance(params, list):
                for j in range(0, len(params)):
                    self.processField(field['field'], params[j], files)
            return
        return

    def processFile(self, params, files):
        editor_path = self.editorFilesDir

        matches = re.search(self.h5p.relativePathRegExp, params['path'])
        if matches:
            source = self.contentDirectory / matches.group(1) / matches.group(4) / matches.group(5)
            dest = self.contentDirectory / matches.group(5)
            if os.path.exists(source) and not os.path.exists(dest):
                shutil.copy(source, dest)

            params['path'] = matches.group(5)
        else:
            old_path = self.basePath / editor_path / Path(params['path'])
            new_path = self.basePath / self.contentDirectory / params['path']
            if not os.path.exists(new_path) and os.path.exists(old_path):
                shutil.copy(old_path, new_path)

        files.append(params['path'])

    ##
    # This function will prefix all paths within a css file.
    ##
    def buildCssPath(self, matches, base=None):
        global buildBase
        if base is not None:
            buildBase = base

        if matches is None:
            return

        dirr = re.sub(r'(css/|styles/|Styles/|Css/)', 'fonts/', buildBase)
        path = dirr + matches.group(1)

        return 'url(' + path + ')'

    ##
    # Parses library data from a string on the form {machineName} {majorVersion}.{minorVersion}
    ##
    def libraryFromString(self, libraryString):
        pre = r'^([\w0-9\-\.]{1,255})[\-\ ]([0-9]{1,5})\.([0-9]{1,5})$'
        res = re.search(pre, libraryString)
        if res:
            return {'machineName': res.group(1), 'majorVersion': res.group(2), 'minorVersion': res.group(3)}
        return False
