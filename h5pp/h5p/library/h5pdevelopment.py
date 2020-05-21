# -*-coding:Latin-1 -*

import os
import json
from pathlib import Path


def empty(variable):
    if not variable:
        return True
    return False


def is_set(variable):
    return variable in locals() or variable in globals()

# TODO Remove seemingly unused method
# def substr_replace(subject, replace, start, length):
#     if length is None:
#         return subject[:start] + replace
#     elif length < 0:
#         return subject[:start] + replace + subject[length:]
#     else:
#         return subject[:start] + replace + subject[start + length:]


# TODO Remove seemingly unused method
# def mb_substr(s, start, length=None, encoding="UTF-8"):
#     u_s = s.decode(encoding)
#     return (u_s[start:(start + length)] if length else u_s[start:]).encode(encoding)


##
# This is a data which uses the file system so it isn't specific to any framework.
##


class H5PDevelopment:
    MODE_NONE = 0
    MODE_CONTENT = 1
    MODE_LIBRARY = 2

    ##
    # Constructor of H5PDevelopment
    ##
    def __init__(self, framework, files_path: Path, language, libraries=None):
        self.h5p_framework = framework
        self.language = language
        self.filesPath = files_path
        if libraries is not None:
            self.libraries = libraries
        else:
            self.find_libraries(files_path / 'development')

    ##
    # Get contents of file.
    ##
    @staticmethod
    def get_file_contents(path: Path):
        if not path.exists():
            return None

        contents = path.open().read(1000)
        if not contents:
            return None

        return contents

    ##
    # Scans development directory and fin all libraries.
    ##
    def find_libraries(self, path):
        self.libraries = []

        if not os.path.isdir(path):
            return

        contents = os.listdir(path)

        for i in contents:
            if i[0] == '.':
                continue  # Skip hidden stuff.

            library_path = path / i / 'library.json'
            library_json = self.get_file_contents(library_path)
            if library_json is None:
                continue  # No JSON file, skip.

            library = json.loads(library_json)
            if library is None:
                continue  # Invalid JSON.

            # Save/update library.
            library['libraryId'] = self.h5p_framework.getLibraryId(library['machineName'], library['majorVersion'],
                                                                   library['minorVersion'])
            self.h5p_framework.save_library_data(library, (not library['libraryId']))

            library['path'] = Path('development') / i
            self.libraries[H5PDevelopment.library_to_string(library['machineName'], library['majorVersion'],
                                                            library['minorVersion'])] = library

            # Go trough libraries and insert dependencies. Missing deps. Will
            # just be ignored and not available.
            self.h5p_framework.lockDependencyStorage()
            for library in self.libraries:
                self.h5p_framework.deleteLibraryDependencies(library['libraryId'])
                # This isn't optimal, but without it we would get duplicate
                # warnings.
                types = ['preloaded', 'dynamic', 'editor']
                for dtype in types:
                    if is_set(library[dtype + 'Dependencies']):
                        self.h5p_framework.saveLibraryDependencies(
                            library['libraryId'], library[dtype + 'Dependencies'], dtype
                        )

            self.h5p_framework.unlockDependencyStorage()

        # TODO Remove seemingly unused method
        # def get_libraries():
            # return self.libraries

        ##
        # Get library
        ##
        # TODO Remove seemingly unused method
        # def get_library(name, major_version, minor_version):
        #     lib = H5PDevelopment.library_to_string(name, major_version, minor_version)
        #     return self.libraries[lib] if is_set(self.libraries[lib]) else None

        ##
        # Get semantics for the given library.
        ##
        # TODO Remove seemingly unused method
        # def get_semantics(name, major_version, minor_version):
        #     lib = H5PDevelopment.library_to_string(name, major_version, minor_version)
        #     if not is_set(self.libraries[lib]):
        #         return None
        #
        #     return self.get_file_contents(self.filesPath + self.libraries[lib]['path'] + '/semantics.json')

        # ##
        # # Get translations for the given library
        # TODO Remove seemingly unused method
        # def get_language(name, major_version, minor_version, language):
        #     lib = H5PDevelopment.library_to_string(name, major_version, minor_version)
        #     if not is_set(self.libraries[lib]):
        #         return None
        #
        #     return self.get_file_contents(
        #         self.filesPath + self.libraries[lib]['path'] + '/language/' + language + '.json')

    ##
    # Writes library as string on the form 'name majorVersion.minorVersion'
    ##
    @staticmethod
    def library_to_string(name, major_version, minor_version):
        return name + ' ' + major_version + '.' + minor_version
