##
# Functions and storage shared by the other H5P classes
##
import binascii
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Union, Any, Dict

import urllib3

from h5pp.h5p.library.H5PExport import H5PExport
from h5pp.h5p.library.H5PDefaultStorage import H5PDefaultStorage
from h5pp.h5p.library.h5pdevelopment import H5PDevelopment
from h5p_django import settings
from django.template.defaultfilters import slugify
from h5pp.h5p.library.H5PContentValidator import H5PContentValidator


http = urllib3.PoolManager()


class H5PCore:
    coreApi = {"majorVersion": 1, "minorVersion": 12}

    styles = ["styles/h5p.css", "styles/h5p-confirmation-dialog.css", "styles/h5p-core-button.css"]

    scripts = [
        "js/jquery.js", "js/h5p.js", "js/h5p-event-dispatcher.js", "js/h5p-x-api-event.js",
        "js/h5p-x-api.js", "js/h5p-content-type.js", "js/h5p-confirmation-dialog.js"]

    # noinspection SpellCheckingInspection
    defaultContentWhitelist = "json png jpg jpeg gif bmp tif tiff svg eot ttf woff woff2 otf webm " \
                              "mp4 ogg mp3 txt pdf rtf doc docx xls xlsx ppt pptx odt ods odp xml " \
                              "csv diff patch swf md textile"

    defaultLibraryWhitelistExtras = "js css"

    SECONDS_IN_WEEK = 604800

    # Disable flags
    DISABLE_NONE = 0
    DISABLE_FRAME = 1
    DISABLE_DOWNLOAD = 2
    DISABLE_EMBED = 4
    DISABLE_COPYRIGHT = 8
    DISABLE_ABOUT = 16

    DISPLAY_OPTION_FRAME = 'frame'
    DISPLAY_OPTION_DOWNLOAD = 'export'
    DISPLAY_OPTION_EMBED = 'embed'
    DISPLAY_OPTION_COPYRIGHT = 'copyright'
    DISPLAY_OPTION_ABOUT = 'icon'

    global libraryIdMap
    libraryIdMap = dict()

    ##
    # Constructor for the H5PCore
    ##
    # TODO Remove support for non-functioning dev-mode
    def __init__(self, framework, path: Path, url, _0="en",
                 export=False, _1=H5PDevelopment.MODE_NONE):
        self.h5p_framework = framework

        self.fs = H5PDefaultStorage(path)

        self.url = url
        self.exportEnabled = export
        # TODO Remove support for non-functioning dev-mode
        # self.development_mode = development_mode
        self.disableFileCheck = False

        # TODO Fix or remove nonfunctional aggregateAssets tech
        # self.aggregateAssets = False  # Off by default.. for now

        # TODO Remove support for non-functioning dev-mode
        # if development_mode and H5PDevelopment.MODE_LIBRARY:
        #     self.h5p_development = H5PDevelopment(self.h5p_framework, path, language)

        self.fullPluginPath = re.sub("/[^/]+[/]?$", "", os.path.dirname(__file__))  # Silly way to filter double slashes

        # Standard regex for converting copied files paths
        self.relativePathRegExp = r"^((\.\.\/){1,2})(.*content\/)?(\d+|editor)\/(.+)$"

        self.librariesJsonData = None
        self.contentJsonData = None
        self.mainJsonData = None

    # # Map flags to string
    # disable = {self.DISABLE_FRAME: self.DISPLAY_OPTION_FRAME, self.DISABLE_DOWNLOAD: self.DISPLAY_OPTION_DOWNLOAD,
    #            self.DISABLE_EMBED: self.DISPLAY_OPTION_EMBED, self.DISABLE_COPYRIGHT: self.DISPLAY_OPTION_COPYRIGHT}

    ##
    # Save content and clear cache.
    ##
    def save_content(self, content, content_main_id=None) -> int:
        if "id" in content:
            self.h5p_framework.updateContent(content)
        else:
            content["id"] = self.h5p_framework.insertContent(content)

        # Some user data for content has to be reset when the content changes.
        self.h5p_framework.resetContentUserData(content_main_id if content_main_id else content["id"])

        return content["id"]

    ##
    # Load content.
    ##
    def load_content(self, pid):
        content = self.h5p_framework.loadContent(pid)

        if content:
            content["library"] = {
                "contentId": pid, "id": content["library_id"], "name": content["library_name"],
                "majorVersion": content["library_major_version"], "minorVersion": content["library_minor_version"],
                "embedTypes": content["library_embed_types"], "fullscreen": content["library_fullscreen"]}

            del content["library_id"]
            del content["library_name"]
            del content["library_embed_types"]
            del content["library_fullscreen"]

            # TODO: Move to filter_parameters ?
        return content

    ##
    # Filter content run parameters, rebuild content dependency cache and export file.
    ##
    def filter_parameters(self, content):
        if not self.empty(content["filtered"]):
            if not self.exportEnabled:
                return content["filtered"]
            elif content['slug']:
                # TODO Fix path handling
                if self.fs.has_export(content["slug"] + "-" + content["id"] + ".h5p"):
                    return content["filtered"]

        # Validate and filter against main library semantics.
        validator = H5PContentValidator(self.h5p_framework, self)
        params = {"library": self.library_to_string(content["library"]), "params": json.loads(content["params"])}

        if "params" not in params:
            return None

        validator.validateLibrary(params, {"options": params['library']})

        params = json.dumps(params['params'])

        # Update content dependencies
        content["dependencies"] = validator.getDependencies()

        # Sometimes the parameters are filtered before content has been
        # created
        if content["id"]:
            self.h5p_framework.deleteLibraryUsage(content["id"])
            self.h5p_framework.saveLibraryUsage(content["id"], content["dependencies"])

            if not content["slug"]:
                content["slug"] = self.generate_content_slug(content)

                # Remove old export file
                self.fs.delete_export(str(content["id"]) + ".h5p")

            if self.exportEnabled:
                # Recreate export file
                exporter = H5PExport(self.h5p_framework, self)
                exporter.create_export_file(content)

            # Cache.
            self.h5p_framework.updateContentFields(content["id"], {"filtered": params, "slug": content["slug"]})
        return params

    ##
    # Generate content slug
    ##
    def generate_content_slug(self, content):
        slug = slugify(content["title"])

        available = None
        while not available:
            if not available:
                # If not available, add number suffix.
                # matches = re.search("(.+-)([0-9]+)$", slug) MLD: Capturing groups make no sense..
                matches = re.search(".+-[0-9]+$", slug)
                if matches:
                    slug = matches.group(1) + str(int(matches.group(2)) + 1)
                else:
                    slug += "-2"

            available = self.h5p_framework.isContentSlugAvailable(slug)
        return slug

    ##
    # Find the files required for self content to work.
    ##
    def load_content_dependencies(self, pid, ptype=None):
        dependencies = self.h5p_framework.loadContentDependencies(pid, ptype)
        # TODO Remove support for non-functioning devmode
        # if self.development_mode and H5PDevelopment.MODE_LIBRARY:
        #     development_libraries = self.h5p_development.getLibraries()
        #
        #     for key, dependency in list(dependencies.items()):
        #         libraryString = self.library_to_string(dependency)
        #         if libraryString in development_libraries:
        #             development_libraries[libraryString]["dependencyType"] = dependencies[key]["dependencyType"]
        #             dependencies[key] = development_libraries[libraryString]

        return dependencies

    ##
    # Get all dependency assets of the given type
    ##
    def get_dependency_assets(self, dependency, ptype, assets, prefix=""):
        # Check if dependency has any files of his type
        if self.empty(dependency[ptype]) or dependency[ptype][0] == "":
            return

        # Check if we should skip CSS.
        if ptype == "preloadedCss" and "dropLibraryCss" in dependency and dependency["dropLibraryCss"] == "1":
            return

        for f in dependency[ptype]:
            # TODO Fix path handling
            assets.append(
                {"path": str(prefix + dependency["path"] + "/" + f.strip(' u\' ')), "version": dependency["version"]})

        return assets

    ##
    # Combines path with cache buster / version.
    ##
    @staticmethod
    def get_assets_urls(assets):
        urls = list()
        for asset in assets:
            url = asset['path']

            # Add URL prefix if not external
            if '://' not in asset['path']:
                # TODO Fix URL handling
                url = "{}{}{}".format(settings.MEDIA_URL, 'h5pp/', url)
                urls.append(url)

            # Add version/cache buster if set  # if 'version' in asset:s  #    url = url + asset['version']

            # urls.append(url)

        return urls

    ##
    # Return file paths for all dependencies files.
    ##
    def get_dependencies_files(self, dependencies, prefix=""):
        # Build files list for assets
        files = {"scripts": [], "styles": []}

        # Avoid caching empty files
        if len(dependencies) == 0:
            return files

        # TODO Fix or remove nonfunctional aggregateAssets tech
        # if self.aggregateAssets:
        #     # Get aggregated files for assets
        #     key = self.get_dependencies_hash(dependencies)
        #     cached_assets = self.fs.get_cached_assets(key)
        #     if cached_assets:
        #         return dict(files, **cached_assets)  # Using cached assets

        # Using content dependencies
        for key, dependency in list(dependencies.items()):
            if "path" not in dependency:
                dependency['path'] = 'libraries/' + self.library_to_string(dependency, True)
                dependency['preloadedJs'] = dependency['preloaded_js'].strip('[]').split(',')
                dependency['preloadedCss'] = dependency['preloaded_css'].strip('[]').split(',')

            dependency['version'] = '?ver=' + str(dependency['major_version']) + '.' + str(
                dependency["minor_version"]) + '.' + str(dependency["patch_version"])

            scripts = self.get_dependency_assets(dependency, "preloadedJs", files["scripts"], prefix)

            if scripts:
                files["scripts"] = scripts

            styles = self.get_dependency_assets(dependency, "preloadedCss", files["styles"], prefix)

            if styles:
                files["styles"] = styles

        # TODO Fix or remove nonfunctional aggregateAssets tech
        # if self.aggregateAssets:
        #     # Aggregate and store assets
        #     self.fs.cache_assets(files, key)
        #
        #     # Keep track of which libraries have been cached in case they
        #     # are updated
        #     self.h5p_framework.saveCachedAssets(key, dependencies)

        return files

    @staticmethod
    def get_dependencies_hash(dependencies):
        to_hash = list()
        # Use unique identifier for each library version
        for dep, lib in list(dependencies.items()):
            to_hash.append(
                lib["machineName"] + "-" + str(lib["majorVersion"]) + "." + str(lib["minorVersion"]) + "." + str(
                    lib["patchVersion"]))

        # Sort in case the same dependencies comes in a different order
        to_hash.sort()

        # Calculate hash sum
        h = hashlib.sha1()
        h.update(''.join([str(i) for i in to_hash]))
        return h.hexdigest()

    ##
    # Load library semantics.
    ##
    def load_library_semantics(self, name, major_version, minor_version):
        semantics = None

        # TODO Remove support for non-functioning devmode
        # if self.development_mode and H5PDevelopment.MODE_LIBRARY:
        #     # Try to load from dev lib
        #     semantics = self.h5p_development.getSemantics(name, major_version, minor_version)

        if semantics is None:
            # Try to load from DB.
            semantics = self.h5p_framework.loadLibrarySemantics(name, major_version, minor_version)

        if semantics is not None:
            semantics = json.loads(semantics['semantics'])

        return semantics

    ##
    # Load library
    ##
    def load_library(self, name, major_version, minor_version):
        library = None
        # TODO Remove support for non-functioning devmode
        # if self.development_mode and H5PDevelopment.MODE_LIBRARY:
        #     # Try to load from dev
        #     library = self.h5p_development.getLibrary(name, major_version, minor_version)
        #     if library is not None:
        #         library["semantics"] = self.h5p_development.getSemantics(name, major_version, minor_version)
        if library is None:
            # Try to load from DB
            library = self.h5p_framework.loadLibrary(name, major_version, minor_version)

        return library

    ##
    # Deletes a library
    ##
    def delete_library(self, library_id):
        self.h5p_framework.delete_library(library_id)

    ##
    # Recursive. Goes through the dependency tree for the given library and
    # adds all the dependencies to the given array in a flat format.
    ##
    def find_library_dependencies(self, dependencies, library, next_weight=0, editor=False):
        for ptype in ["dynamic", "preloaded", "editor"]:
            pproperty = ptype + "Dependencies"
            if pproperty not in library:
                continue  # Skip, no such dependencies

            if ptype == "preloaded" and editor:
                # All preloaded dependencies of an editor library is set to
                # editor.
                ptype = "editor"

            for dependency in library[pproperty]:
                dependency_key = ptype + "-" + dependency["machineName"]
                if dependency_key in dependencies:
                    continue  # Skip, already have self

                dependency_library = self.load_library(dependency["machineName"], dependency["majorVersion"],
                                                       dependency["minorVersion"])
                if dependency_library:
                    dependencies[dependency_key] = {"library": dependency_library, "type": ptype}
                    next_weight = self.find_library_dependencies(dependencies, dependency_library, next_weight,
                                                                 ptype == "editor")
                    next_weight += 1
                    dependencies[dependency_key]["weight"] = next_weight
                else:
                    # self site is missing a dependency !
                    print(("Missing dependency %s required by %s" % (
                        self.library_to_string(dependency), self.library_to_string(library))))

        return next_weight

    # ##
    # # Check if a library is of the version we"re looking for
    # #
    # # Same version means that the majorVersion and minorVersion is the same
    # ##
    # TODO remove seemingly unused method
    # def isSameVersion(library, dependency):
    #     if library["machineName"] != dependency["machineName"]:
    #         return False
    #     if library["majorVersion"] != dependency["majorVersion"]:
    #         return False
    #     if library["minorVersion"] != dependency["minorVersion"]:
    #         return False
    #     return True

    ##
    # Recursive function for removing directories.
    ##
    def delete_file_tree(self, pdir):
        if not os.path.isdir(pdir):
            return False

        files = list(set(os.listdir(pdir)).difference([".", ".."]))

        for f in files:
            self.delete_file_tree(pdir / f) if os.path.isdir(pdir / f) else os.remove(pdir / f)

        return os.rmdir(pdir)

    ##
    # Writes library data as string on the form {machineName} {majorVersion}.{minorVersion}
    ##
    @staticmethod
    def library_to_string(library: Dict[str, Any], folder_name=False):
        if 'machineName' in library:
            return library["machineName"] + ("-" if folder_name else " ") + str(library["majorVersion"]) + "." + str(
                library["minorVersion"])
        elif 'machine_name' in library:
            return library["machine_name"] + ("-" if folder_name else " ") + str(library["major_version"]) + "." + str(
                library["minor_version"])
        else:
            return library["name"] + ("-" if folder_name else " ") + str(library["majorVersion"]) + "." + str(
                library["minorVersion"])

    ##
    # Parses library data from a string on the form {machineName} {majorVersion}.{minorVersion}
    ##
    @staticmethod
    def library_from_string(library_string):
        pre = r"^([\w0-9\-\.]{1,255})[\-\ ]([0-9]{1,5})\.([0-9]{1,5})$"
        res = re.search(pre, library_string)
        if res:
            return {"machineName": res.group(1), "majorVersion": res.group(2), "minorVersion": res.group(3)}
        return False

    ##
    # Determine the correct embed type to use.
    ##
    # TODO Remove faulty and seemingly unused method
    # def determine_embed_type(self, contentEmbedType, libraryEmbedTypes):
    #     # Detect content embed type
    #     embedType = "div" if "div" in libraryEmbedTypes.lower() else "iframe"
    #
    #     if libraryEmbedTypes is not None and libraryEmbedTypes != "":
    #         # Check that embed type is available for library
    #         if embedType not in embedTypes:
    #             # Not available, pick default.
    #             embedType = "div" if "div" in embedTypes else "iframe"
    #
    #     return embedType

    ##
    # Get the absolute version for the library as a human readable string.
    ##
    @staticmethod
    def library_version(library):
        return library.major_version + "." + library.minor_version + "." + library.patch_version

    ##
    # Determine which version content with the given library can be upgraded to.
    ##
    # TODO remove: Seemingly nonfunctional and unused method
    # def getUpgrades(self, library, versions):
    #     for upgrade in versions:
    #         if (
    #                 (upgrade.major_version > library.major_version) or
    #                 (
    #                         (upgrade.major_version == library.major_version) and
    #                         (upgrade.minor_version > library.minor_version)
    #                 )
    #         ):
    #             upgrades[upgrade.id] = library_version(upgrade)
    #
    #     return upgrades

    ##
    # Converts all the properties of the given object or array from
    # snake_case to camelCase. Useful after fetching data from the database.
    #
    # Note that some databases does not support camelCase.
    ##
    # TODO Remove faulty and seemingly unused method
    # def snakeToCamel(self, arr, obj=False):
    #     for key, val in arr:
    #         n = -1
    #         while n:
    #             n = key.find("_", n + 1)
    #             key = substr_replace(key, key[n + 1].upper(), n, 2)
    #
    #         newArr[key] = val
    #
    #     return newArr if obj else newArr

    ##
    # Get a list of installed libraries, different minor version will
    # return a separate entries.
    ##
    def get_libraries_installed(self):
        libraries_installed = dict()
        libs = self.h5p_framework.loadLibraries()

        for libName, library in list(libs.items()):
            libraries_installed[libName + " " + str(library['major_version']) + "." + str(library['minor_version'])] = \
                library['patch_version']

        return libraries_installed

    # TODO Remove seemingly unused method
    # ##
    # # Easy way to combine similar data sets.
    # ##
    # def combine_array_values(self, inputs):
    #     results = dict()
    #     for index, values in list(inputs.items()):
    #         for key, value in list(values.items()):
    #             results[key] = {index: value}
    #
    #     return results

    ##
    # Fetch a list of libraries" metadata from h5p.org.
    # save URL tutorial to database. Each platform implementation
    # is responsible for invoking self, eg using cron
    ##
    def fetch_libraries_metadata(self, fetching_disabled=False):
        # Gather data
        framework_uuid = self.h5p_framework.getOption("H5P_UUID", "")
        platform = self.h5p_framework.getPlatformInfo()
        data = {
            "api_version": 2,
            "uuid": framework_uuid,
            "platform_name": platform["name"],
            "platform_version": platform["version"],
            "h5p_version": platform["h5pVersion"],
            "disabled": 1 if fetching_disabled else 0,
            "local_id": binascii.crc32(self.fullPluginPath),
            "type": self.h5p_framework.getOption("H5P_SITETYPE", "local"),
            "num_authors": self.h5p_framework.get_num_authors(),
            "libraries": json.dumps({
                "patch": self.get_libraries_installed(),
                "content": self.h5p_framework.getLibraryContentCount(),
                "loaded": self.h5p_framework.get_library_stats("library"),
                "created": self.h5p_framework.get_library_stats("content create"),
                "createUpload": self.h5p_framework.get_library_stats("content create upload"),
                "deleted": self.h5p_framework.get_library_stats("content delete"),
                "resultViews": self.h5p_framework.get_library_stats("results content"),
                "shortcodeInserts": self.h5p_framework.get_library_stats("content shortcode insert")}
            )}

        # Send request
        result = self.h5p_framework.fetchExternalData("https://h5p.org/libraries-metadata.json", data)
        if self.empty(result):
            return

        # Process results
        json_data = json.loads(result.read())
        if self.empty(json_data):
            return

        # Handle libraries metadata
        if 'libraries' in json_data:
            for machineName, libInfo in list(json_data['libraries'].items()):
                if 'tutorialUrl' in libInfo:
                    self.h5p_framework.setLibraryTutorialUrl(machineName, libInfo['tutorialUrl'])

        # Handle new uuid
        if framework_uuid == "" and json_data['uuid']:
            self.h5p_framework.setOption("H5P_UUID", json_data['uuid'])

        # Handle latest version of H5P
        if not self.empty(json_data['latest']):
            self.h5p_framework.setOption("H5P_UPDATE_AVAILABLE", json_data['latest']['releasedAt'])
            self.h5p_framework.setOption("H5P_UPDATE_AVAILABLE_PATH", json_data['latest']['path'])

    # TODO Remove seemingly unused method
    # def get_global_disable(self):
    #     disable = self.DISABLE_NONE
    #
    #     # Allow global settings to override and disable options
    #     if not self.h5p_framework.getOption("frame", True):
    #         disable = disable | self.DISABLE_FRAME
    #     else:
    #         if not self.h5p_framework.getOption("export", True):
    #             disable = disable | self.DISABLE_DOWNLOAD
    #         if not self.h5p_framework.getOption("embed", True):
    #             disable = disable | self.DISABLE_EMBED
    #         if not self.h5p_framework.getOption("copyright", True):
    #             disable = disable | self.DISABLE_COPYRIGHT
    #         if not self.h5p_framework.getOption("icon", True):
    #             disable = disable | self.DISABLE_ABOUT
    #
    #     return disable

    ##
    # Determine disable state from sources.
    ##
    # TODO Remove seemingly unused method
    # def get_disable(self, sources, current):
    #     for bit, option in H5PCore.disable:
    #         if self.h5p_framework.getOption("export" if (bit & H5PCore.DISABLE_DOWNLOAD) else option, True):
    #             if not sources[option] or not sources[option]:
    #                 current = current | bit  # Disable
    #             else:
    #                 current = current & bit  # Enable
    #
    #     return current

    ##
    # Small helper for getting the library"s ID.
    ##
    def get_library_id(self, library, lib_string=None):
        global libraryIdMap

        if not lib_string:
            lib_string = self.library_to_string(library)

        if lib_string not in libraryIdMap:
            libraryIdMap[lib_string] = self.h5p_framework.getLibraryId(library["machineName"], library["majorVersion"],
                                                                       library["minorVersion"])

        return libraryIdMap[lib_string]

    ##
    # Makes it easier to print response when AJAX request succeeds.
    ##
    # TODO Remove unused method
    # def ajax_success(self, data=None):
    #     response = {"success": True}
    #     if data is not None:
    #         response["data"] = data
    #
    #     return json.dumps(response)

    ##
    # Makes it easier to print response when AJAX request fails.
    # will exit after printing error.
    ##
    # TODO Remove unused method
    # def ajax_error(self, message=None):
    #     response = {"success": False}
    #     if message is not None:
    #         response["message"] = message
    #
    #     return json.dumps(response)

    ##
    # Print JSON headers with UTF-8 charset and json encode response data.
    # Makes it easier to respond using JSON.
    ##
    # TODO Remove unused method
    # def print_json(self, data):
    #     print("Cache-Control: no-cache\n")
    #     print("Content-type: application/json; charset=utf-8\n")
    #     print((json.dumps(data)))

    ##
    # Get a new H5P security token for the given action
    ##
    # TODO Remove unused method
    # def create_token(self, action):
    #     time_factor = self.get_time_factor()
    #     h = hashlib.new('md5')
    #     h.update(action + str(time_factor) + str(uuid.uuid1()))
    #     return h.digest()

    ##
    # Create a time based number which is unique for each 12 hour.
    ##
    # TODO Remove unused method
    # def get_time_factor(self):
    #     return math.ceil(int(time.time()) / (86400 / 2))

    @staticmethod
    def empty(variable):
        if not variable:
            return True
        return False

    @staticmethod
    def file_get_contents(filename: Union[Path, str], offset=-1, max_length=-1):
        if not isinstance(filename, Path) and filename.find("://") > 0:
            ret = http.request('GET', filename).read()
            if offset > 0:
                ret = ret[offset:]
            if max_length > 0:
                ret = ret[:max_length]
            return ret
        else:
            # TODO Replace with Pathlib built-ins
            fp = open(str(filename), "rb")
            try:
                if offset > 0:
                    fp.seek(offset)
                ret = fp.read(max_length).decode('utf8')
                return ret
            finally:
                fp.close()
