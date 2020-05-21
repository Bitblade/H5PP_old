# Implementation of H5PFrameworkInterface

import collections
import json
import time
from pathlib import Path

import requests
import django

from django.contrib import messages
from django.db import connection
from django.utils.text import slugify

from h5pp.h5p.library import H5PCore, H5PContentValidator, H5PExport, H5PStorage, H5PValidator
from h5p_django import settings

from h5pp.models import h5p_libraries, h5p_libraries_libraries, h5p_libraries_languages, h5p_contents, \
    h5p_contents_libraries, h5p_content_user_data, h5p_counters
from h5pp.h5p.h5pevent import H5PEvent
from h5pp.h5p.editor.h5peditorclasses import H5PDjangoEditor
from h5pp.h5p.editor.library.h5peditorstorage import H5PEditorStorage


# noinspection PyMethodMayBeStatic
class H5PDjango:
    # noinspection SpellCheckingInspection
    global path, dirpath, h5pWhitelist, h5pWhitelistExtras
    path = None
    dirpath = None
    h5pWhitelist = \
        'json png jpg jpeg gif bmp tif tiff svg eot ttf woff woff2 otf webm mp4 ogg mp3 txt pdf rtf doc ' \
        'docx xls xlsx ppt pptx odt ods odp xml csv diff patch swf md textile'
    h5pWhitelistExtras = ' js css'
    interface: 'H5PDjango' = None
    core: H5PCore = None

    def __init__(self, user):
        self.user = user

    def init(self, h5p_dir: Path, h5p):
        if not self.interface:
            self.interface = H5PDjango(self.user)

        if h5p_dir is not None and h5p is not None:
            self.interface.getUploadedH5pFolderPath(h5p_dir)
            self.interface.getUploadedH5pPath(h5p)

        if not self.core:
            self.core = H5PCore(self.interface, settings.H5P_STORAGE_ROOT, settings.BASE_DIR, 'en',
                                True if getattr(settings, 'H5P_EXPORT') else False, False)

    def getValidatorInstance(self, h5p_dir: Path = None, h5p=None) -> H5PValidator:
        self.init(h5p_dir, h5p)
        return H5PValidator(self.interface, self.core)

    def getStorageInstance(self, h5p_dir: Path = None, h5p=None) -> H5PStorage:
        self.init(h5p_dir, h5p)
        return H5PStorage(self.interface, self.core)

    def getContentValidator(self, h5p_dir: Path = None, h5p=None) -> H5PContentValidator:
        self.init(h5p_dir, h5p)
        return H5PContentValidator(self.interface, self.core)

    def getExporter(self, h5p_dir: Path = None, h5p=None) -> H5PExport:
        self.init(h5p_dir, h5p)
        return H5PExport(self.interface, self.core)

    def getInterface(self, h5p_dir: Path = None, h5p=None) -> 'H5PDjango':
        self.init(h5p_dir, h5p)
        return self.interface

    def getCore(self, h5p_dir: Path = None, h5p=None) -> H5PCore:
        self.init(h5p_dir, h5p)
        return self.core

    def getEditor(self, h5p_dir: Path = None, h5p=None) -> H5PDjangoEditor:
        self.init(h5p_dir, h5p)
        storage = H5PEditorStorage()
        return H5PDjangoEditor(self.core, storage, settings.BASE_DIR, settings.H5P_STORAGE_ROOT)

    ##
    # Get an instance of one of the h5p library classes
    ##
    @DeprecationWarning
    def h5pGetInstance(self, instance_type: str, h5pdir=None, h5p=None):

        if instance_type == 'validator':
            return self.getValidatorInstance(h5pdir, h5p)
        elif instance_type == 'storage':
            return self.getStorageInstance(h5pdir, h5p)
        elif instance_type == 'contentvalidator':
            return self.getContentValidator(h5pdir, h5p)
        elif instance_type == 'export':
            return self.getExporter(h5pdir, h5p)
        elif instance_type == 'interface':
            return self.getInterface(h5pdir, h5p)
        elif instance_type == 'core':
            return self.getCore(h5pdir, h5p)
        elif instance_type == 'editor':
            return self.getEditor(h5pdir, h5p)

    ##
    # Returns info for the current platform
    ##
    def getPlatformInfo(self):
        # h5pInfo = settings.H5P_VERSION

        return {'name': 'django', 'version': django.get_version(), 'h5pVersion': '7.x'}

    ##
    # Fetches a file from a remote server using HTTP GET
    ##

    def fetchExternalData(self, url, data=None):
        if data is not None:
            response = requests.post(url, data)
        else:
            response = requests.get(url)

        return response.content if response.status_code == 200 else response.raise_for_status()

    ##
    # Set the tutorial URL for a library. All versions of the library is set
    ##
    def setLibraryTutorialUrl(self, machine_name, tutorial_url):
        tutorial = h5p_libraries.objects.get(machine_name=machine_name)
        tutorial.tutorial_url = tutorial_url
        tutorial.save()

    ##
    # Show the user an error message
    ##
    def setErrorMessage(self, request, message):
        messages.error(request, message)

    ##
    # Show the user an information message
    def setInfoMessage(self, request, message):
        messages.info(request, message)

    ##
    # Get the path to the last uploaded h5p dir
    ##
    def getUploadedH5pFolderPath(self, folder=None):
        global dirpath
        if folder is not None:
            dirpath = folder
        return dirpath

    ##
    # Get the path to the last uploaded h5p file
    ##
    def getUploadedH5pPath(self, files=None):
        global path
        if files is not None:
            path = files
        return path

    ##
    # Get a list of the current installed libraries
    ##
    def loadLibraries(self):
        result = h5p_libraries.objects.extra(
            select={'id': 'library_id', 'name': 'machine_name'})\
            .values('id', 'machine_name', 'title', 'major_version', 'minor_version', 'patch_version',
                    'runnable', 'restricted')\
            .order_by('title', 'major_version', 'minor_version')
        if result.exists():
            libraries = dict()
            for library in result:
                libraries[library['machine_name']] = library
            return libraries
        else:
            return ''

    ##
    # Returns the URL to the library admin page
    ##
    def getAdminUrl(self):
        # TODO
        return ''

    ##
    # Get id to an existing library
    # If version number is not specified, the newest version will be returned
    ##
    def getLibraryId(self, machine_name, major_version=None, minor_version=None):
        if major_version is None or minor_version is None:
            library_id = h5p_libraries.objects.filter(machine_name=machine_name).values('library_id')
        else:
            library_id = h5p_libraries.objects.filter(
                machine_name=machine_name, major_version=major_version, minor_version=minor_version
            ).values('library_id')

        return library_id[0]['library_id'] if len(library_id) > 0 and 'library_id' in library_id[0] else None

    ##
    # Is the library a patched version of an existing library ?
    ##
    def isPatchedLibrary(self, library):
        if self.isInDevMode():
            result = h5p_libraries.objects.filter(machine_name=library['machineName'],
                                                  major_version=library['majorVersion'],
                                                  minor_version=library['minorVersion'],
                                                  patch_version__lte=library['patchVersion'])
        else:
            result = h5p_libraries.objects.filter(machine_name=library['machineName'],
                                                  major_version=library['majorVersion'],
                                                  minor_version=library['minorVersion'],
                                                  patch_version__lt=library['patchVersion'])

        return result.exists()

    ##
    # Is H5P in development mode ?
    ##
    def isInDevMode(self):
        return bool(settings.H5P_DEV_MODE)

    ##
    # Is the current user allowed to update libraries ?
    ##
    def mayUpdateLibraries(self):
        # TODO
        return True

    ##
    # Get number of content using a library, and the number of
    # dependencies to other libraries
    ##
    def getLibraryUsage(self, library_id):
        usage = dict()
        cursor = connection.cursor()
        cursor.execute(f"""
            SELECT COUNT(distinct n.content_id)
            FROM h5p_libraries l
            JOIN h5p_contents_libraries cl ON l.library_id = cl.library_id
            JOIN h5p_contents n ON cl.content_id = n.content_id
            WHERE l.library_id = {library_id}
        """)
        usage['content'] = cursor.fetchall()
        usage['libraries'] = h5p_libraries_libraries.objects.filter(required_library_id=library_id).count()

        return usage

    ##
    # Get a key value list of library version and count of content created
    # using that library
    ##
    def getLibraryContentCount(self):
        cursor = connection.cursor()
        cursor.execute("""
            SELECT machine_name, major_version, minor_version, count(*) AS count
            FROM h5p_contents, h5p_libraries
            WHERE main_library_id = library_id
            GROUP BY machine_name, major_version, minor_version
        """)
        result = self.dictfetchall(cursor)

        # Extract results
        content_count = dict()
        for lib in result:
            identifier = lib['machine_name'] + ' ' + str(lib['major_version']) + '.' + str(lib['minor_version'])
            content_count[identifier] = lib['count']

        return content_count

    ##
    # Generates statistics from the event log per library
    ##
    @staticmethod
    def get_library_stats(typ):
        results = h5p_counters.objects.filter(type=typ).extra(
            select={'name': 'library_name', 'version': 'library_version'}).values('name', 'version')

        if results.exists():
            count = []  # MLD: Added to make method function
            for library in results:
                count[library.name + ' ' + library.version] = library.num
            return count

        return ''

    ##
    # Aggregate the current number of H5P authors
    ##
    # TODO Unimplemented
    @staticmethod
    def get_num_authors():
        return ''

    ##
    # Store data about a library
    # Also fills in the libraryId in the libraryData object if the object is new
    ##
    def save_library_data(self, library_data, new=True):
        preloaded_js = self.pathsToCsv(library_data, 'preloadedJs')
        preloaded_css = self.pathsToCsv(library_data, 'preloadedCss')
        drop_library_css = ''

        if 'dropLibraryCss' in library_data:
            libs = []  # MLD: Added to make method functional TODO Figure out what libs is meant to be
            for lib in library_data['dropLibraryCss']:
                libs.append(lib['machineName'])
            drop_library_css = libs.split(', ')

        embed_types = ''
        if 'embedTypes' in library_data:
            embed_types = library_data['embedTypes']
        if 'semantics' not in library_data:
            library_data['semantics'] = ''
        if 'fullscreen' not in library_data:
            library_data['fullscreen'] = 0
        if new:
            library_id = h5p_libraries.objects.create(
                machine_name=library_data['machineName'],
                title=library_data['title'], major_version=library_data['majorVersion'],
                minor_version=library_data['minorVersion'], patch_version=library_data['patchVersion'],
                runnable=library_data['runnable'], fullscreen=library_data['fullscreen'], embed_types=embed_types,
                preloaded_js=preloaded_js, preloaded_css=preloaded_css, drop_library_css=drop_library_css,
                semantics=library_data['semantics']
            )

            library_data['libraryId'] = library_id.library_id
        else:
            library = h5p_libraries.objects.get(library_id=library_data['libraryId'])
            library.title = library_data['title']
            library.patch_version = library_data['patchVersion']
            library.runnable = library_data['runnable']
            library.fullscreen = library_data['fullscreen']
            library.embed_types = embed_types
            library.preloaded_js = preloaded_js
            library.preloaded_css = preloaded_css
            library.drop_library_css = drop_library_css
            library.semantics = library_data['semantics']
            library.save()

            self.deleteLibraryDependencies(library_data['libraryId'])

        # Log library, installed or updated
        H5PEvent(self.user, 'library', ('create' if new else 'update'), None, None, library_data['machineName'],
                 str(library_data['majorVersion']) + '.' + str(library_data['minorVersion']))

        h5p_libraries_languages.objects.filter(library_id=library_data['libraryId']).delete()
        if 'language' in library_data:
            for languageCode, languageJson in list(library_data['language'].items()):
                h5p_libraries_languages.objects.create(library_id=library_data['libraryId'],
                                                       language_code=languageCode, language_json=languageJson)

    ##
    # Convert list of file paths to csv
    ##
    def pathsToCsv(self, library_data, key):
        if key in library_data:
            paths = list()
            for f in library_data[key]:
                paths.append(f['path'])
            return paths
        return ''

    ##
    # Delete all dependencies belonging to given library
    ##
    def deleteLibraryDependencies(self, library_id):
        if h5p_libraries_libraries.objects.filter(library_id=library_id).count() > 0:
            h5p_libraries_libraries.objects.get(library_id=library_id).delete()

    ##
    # Delete a library from database and file system
    ##
    def delete_library(self, library_id):
        library = h5p_libraries.objects.get(library_id=library_id)
        library_dir = library.machine_name + '-' + library.major_version + '.' + library.minor_version

        # Delete files
        self.core.delete_file_tree(settings.H5P_STORAGE_ROOT / 'libraries' / library_dir)

        # Delete data in database (won't delete content)
        h5p_libraries_libraries.objects.get(library_id=library_id).delete()
        h5p_libraries_languages.objects.get(library_id=library_id).delete()
        h5p_libraries.objects.get(library_id=library_id).delete()

    ##
    # Save what libraries a library is depending on
    ##
    def saveLibraryDependencies(self, library_id, dependencies, dependency_type):
        for dependency in dependencies:
            pid = h5p_libraries.objects.filter(machine_name=dependency['machineName'],
                                               major_version=dependency['majorVersion'],
                                               minor_version=dependency['minorVersion']).values('library_id')[0]
            h5p_libraries_libraries.objects.create(library_id=library_id, required_library_id=pid['library_id'],
                                                   dependency_type="'" + dependency_type + "'")

    ##
    # Update old content
    ##
    def updateContent(self, content):
        result = h5p_contents.objects.filter(content_id=content['id'])
        if not result.exists():
            self.insertContent(content)
            return
        content_id = result.first().content_id

        # Update content
        update = h5p_contents.objects.get(content_id=content_id)
        update.title = content['title']
        update.author = content['author']
        update.json_contents = content['params']
        update.embed_type = 'div'
        update.main_library_id = content['library']['libraryId']
        update.filtered = ''
        update.disable = content['disable']
        update.slug = slugify(content['title'])
        update.save()

        # Derive library data from string
        if 'h5p_library' in content:
            library_data = content['h5p_library'].split(' ')
            content['library']['machineName'] = library_data[0]
            content['machineName'] = library_data[0]
            library_versions = library_data[1].split('.')
            content['library']['majorVersion'] = library_versions[0]
            content['library']['minorVersion'] = library_versions[1]

        # Log update event
        H5PEvent('content', 'update', content['id'], content['title'], content['library']['machineName'],
                 str(content['library']['majorVersion']) + '.' + str(content['library']['minorVersion']))

    ##
    # Insert new content
    ##
    def insertContent(self, content):
        # Insert
        result = h5p_contents.objects.create(
            title=content['title'], json_contents=content['params'], embed_type='div',
            content_type=content['library']['machineName'], main_library_id=content['library']['libraryId'],
            author=content.get('author', ''), disable=content['disable'], filtered='', slug=slugify(content['title'])
        )

        H5PEvent('content', 'create', result.content_id, content['title'] if 'title' in content else '',
                 content['library']['machineName'],
                 str(content['library']['majorVersion']) + '.' + str(content['library']['minorVersion']))

        return result.content_id

    ##
    # Resets marked user data for the given content
    ##
    def resetContentUserData(self, content_id):
        if h5p_content_user_data.objects.filter(content_main_id=content_id, delete_on_content_change=1).count() > 0:
            # Reset user datas for this content
            user_data = h5p_content_user_data.objects.filter(content_main_id=content_id, delete_on_content_change=1)
            for user in user_data:
                user.timestamp = int(time.time())
                user.data = 'RESET'
                user.save()

    ##
    # Get file extension whitelist
    # The default extension list is part of h5p, but admins should be allowed to modify it
    ##

    def getWhitelist(self, is_library):
        global h5pWhitelist, h5pWhitelistExtras
        whitelist = h5pWhitelist
        if is_library:
            whitelist = whitelist + h5pWhitelistExtras
        return whitelist

    ##
    # Give an H5P the same library dependencies as a given H5P
    ##
    def copyLibraryUsage(self, content_id, copy_from_id):
        copy = h5p_contents_libraries.objects.get(content_id=copy_from_id)
        h5p_contents_libraries.objects.filter(content_id=copy_from_id)\
            .create(
            content_id=content_id, library_id=copy.library_id, dependency_type=copy.dependency_type,
            drop_css=copy.drop_css, weight=copy.weight
        )

    ##
    # Deletes content data
    ##
    def deleteContentData(self, content_id):
        h5p_contents.objects.get(content_id=content_id).delete()
        self.deleteLibraryUsage(content_id)

    ##
    # Delete what libraries a content item is using
    ##
    def deleteLibraryUsage(self, content_id):
        h5p_contents_libraries.objects.filter(content_id=content_id).delete()

    ##
    # Saves what libraries the content uses
    ##
    def saveLibraryUsage(self, content_id, libraries_in_use):
        drop_library_css_list = dict()
        for key, dependency in list(libraries_in_use.items()):
            if 'dropLibraryCss' in dependency['library']:
                drop_library_css_list = drop_library_css_list + dependency['library']['drop_library_css'].split(', ')

        for key, dependency in list(libraries_in_use.items()):
            drop_css = 1 if dependency['library']['machine_name'] in drop_library_css_list else 0
            h5p_contents_libraries.objects.create(
                content_id=content_id, library_id=dependency['library']['library_id'],
                dependency_type=dependency['type'].replace("'", ""), drop_css=drop_css, weight=dependency['weight']
            )

    ##
    # Load a library
    ##
    def loadLibrary(self, machine_name, major_version, minor_version):
        library = h5p_libraries.objects.filter(
            machine_name=machine_name, major_version=major_version, minor_version=minor_version
        ).defer('restricted').values()

        if not library.exists():
            return False

        library = library[0]

        cursor = connection.cursor()
        cursor.execute(f"""
            SELECT hl.machine_name AS name,
                    hl.major_version AS major,
                    hl.minor_version AS minor,
                    hll.dependency_type AS type
            FROM h5p_libraries_libraries hll
            JOIN h5p_libraries hl ON hll.required_library_id = hl.library_id
            WHERE hll.library_id = {library['library_id']}
        """)
        result = self.dictfetchall(cursor)

        for dependency in result:
            typ = dependency['type'].replace("'", "") + 'Dependencies'
            if typ not in library:
                library[typ] = list()
            library[typ].append({
                'machineName': dependency['name'], 'majorVersion': dependency['major'],
                'minorVersion': dependency['minor']
            })
        if self.isInDevMode():
            # TODO Test / remove: Since devmode is documented to be unusable, remove this
            assert False
            # semantics = self.getSemanticsFromFile(library['machine_name'], library['major_version'],
            #                                       library['minor_version'])
            # if semantics:
            #     library['semantics'] = semantics

        return library

    # TODO Test assumption and if correct, remove method
    # Given that settings.H5P_PATH isn't configured and even if it were, 'libraries' isn't used anywhere H5P_PATH
    # could conceivably point to, this method is assumed to be unused and as such, commented out. Also commented
    # out the two sections of other methods that use it, which are only executed conditionally based on 'isInDevMode',
    # which is documented to be unusable in its current state.
    # def getSemanticsFromFile(self, machineName, majorVersion, minorVersion):
    #     semanticsPath = os.path.join(settings.H5P_PATH, 'libraries',
    #                                machineName + '-' + str(majorVersion) + '.' + str(minorVersion), 'semantics.json')
    #     if os.path.exists(semanticsPath):
    #         semantics = semanticsPath.read()
    #         if not json.loads(semantics):
    #             print(('Invalid json in semantics for %s' % library['machineName']))
    #         return semantics
    #     return False

    ##
    # Loads library semantics
    ##
    def loadLibrarySemantics(self, machine_name, major_version, minor_version):
        if False or self.isInDevMode():  # TODO test / remove: Disabled devmode
            semantics = ''
            # semantics = self.getSemanticsFromFile(machineName, majorVersion, minorVersion)
        else:
            semantics = h5p_libraries.objects.filter(
                machine_name=machine_name, major_version=major_version, minor_version=minor_version
            ).values('semantics')

        return None if len(semantics) == 0 else semantics[0]

    # ##
    # # Make it possible to alter the semantics, adding custom fields, etc.
    # ##
    # def alterLibrarySemantics(self, semantics, name, major_version, minor_version):
    #     # TODO
    #     return ''

    ##
    # Load content
    ##
    def loadContent(self, pid):
        cursor = connection.cursor()
        cursor.execute(f"""
            SELECT hn.content_id AS id,
                    hn.title,
                    hn.json_contents AS params,
                    hn.embed_type,
                    hn.content_type,
                    hn.author,
                    hl.library_id,
                    hl.machine_name AS library_name,
                    hl.major_version AS library_major_version,
                    hl.minor_version AS library_minor_version,
                    hl.embed_types AS library_embed_types,
                    hl.fullscreen AS library_fullscreen,
                    hn.filtered,
                    hn.disable,
                    hn.slug
            FROM h5p_contents hn
            JOIN h5p_libraries hl ON hl.library_id = hn.main_library_id
            WHERE content_id = {pid}
        """)
        content = self.dictfetchall(cursor)
        return None if len(content) == 0 else content[0]

    ##
    # Load all contents available
    ##
    def loadAllContents(self):
        result = h5p_contents.objects.values('content_id', 'title')
        return result if len(result) > 0 else None

    ##
    # Load dependencies for the given content of the given type
    ##
    def loadContentDependencies(self, pid, typ=None):
        cursor = connection.cursor()
        if typ is not None:
            cursor.execute(f"""
                SELECT hl.library_id,
                        hl.machine_name,
                        hl.major_version,
                        hl.minor_version,
                        hl.patch_version,
                        hl.preloaded_css,
                        hl.preloaded_js,
                        hnl.drop_css,
                        hnl.dependency_type
                FROM h5p_contents_libraries hnl
                JOIN h5p_libraries hl ON hnl.library_id = hl.library_id
                WHERE hnl.content_id = {pid} AND hnl.dependency_type = {"'" + typ + "'"}
                ORDER BY hnl.weight
            """)
        else:
            cursor.execute("""
                SELECT hl.library_id,
                        hl.machine_name,
                        hl.major_version,
                        hl.minor_version,
                        hl.patch_version,
                        hl.preloaded_css,
                        hl.preloaded_js,
                        hnl.drop_css,
                        hnl.dependency_type
                FROM h5p_contents_libraries hnl
                JOIN h5p_libraries hl ON hnl.library_id = hl.library_id
                WHERE hnl.content_id = %s
                ORDER BY hnl.weight
            """ % pid)

        result = self.dictfetchall(cursor)
        dependencies = collections.OrderedDict()
        for dependency in result:
            dependencies[dependency['library_id']] = dependency

        return dependencies

    def updateTutorial(self):
        response = json.loads(self.fetchExternalData('https://h5p.org/libraries-metadata.json'))
        libraries = list(h5p_libraries.objects.values())
        for name, url in list(response['libraries'].items()):
            for library in libraries:
                if library['machine_name'] == name:
                    self.setLibraryTutorialUrl(library['machine_name'], url['tutorialUrl'])

        return 0

    ##
    # Get stored setting
    ##
    def getOption(self, name, default=None):
        return getattr(settings, name, default)

    ##
    # Stores the given setting
    ##
    def setOption(self, name, value):
        setattr(settings, name, value)

    # TODO Remove seemingly unused and faulty method
    # ##
    # # Convert variables to fit our DB
    # ##
    # def camelToString(self, inputValue):
    #     matches = re.search('[a-z0-9]([A-Z])[a-z0-9]', inputValue)
    #     if matches:
    #         matches = re.sub('[a-z0-9]([A-Z])[a-z0-9]', matches.group(1), inputValue)
    #         return result.lower()
    #     else:
    #         return inputValue

    ##
    # This will update selected fields on the given content
    ##
    def updateContentFields(self, pid, fields):
        # cursor = connection.cursor()
        for name, value in list(fields.items()):
            query = {'{0}'.format(name): value}
            h5p_contents.objects.filter(content_id=pid).update(**query)

    ##
    # Not implemented yet
    ##
    def afterExportCreated(self):
        return 0

    ##
    # Will clear filtered params for all the content that uses the specified
    # library. This means that the content dependencies will have to be rebuilt,
    # and the parameters refiltered
    ##
    # noinspection PyUnusedLocal
    def clearFilteredParameters(self, library_id):
        # TODO
        return ''

    ##
    # Get number of contents that has to get their content dependencies rebuilt
    ##
    # TODO Remove unused method
    # def getNumNotFiltered(self):
    #     return int(
    #       h5p_contents.objects.filter(filtered='', main_library_id__level__gt=0).values('content_id').count()
    #     )

    # ##
    # # Get number of contents using library as main library
    # ##
    # # TODO Remove unused method
    # def getNumContent(self, libraryId):
    #     return int(h5p_contents.objects.filter(main_library_id=libraryId).values('content_id').count())

    ##
    # Get number of contents
    ##
    def getNumContentPlus(self):
        return int(h5p_contents.objects.values('content_id').count())

    ##
    # Determines if content slug is used
    ##
    def isContentSlugAvailable(self, slug):
        result = h5p_contents.objects.filter(slug=slug).values('slug')
        return False if len(result) > 0 else True

    ##
    # Returns all rows from a cursor as a dict
    ##
    def dictfetchall(self, cursor):
        desc = cursor.description
        return [dict(list(zip([col[0] for col in desc], row))) for row in cursor.fetchall()]
