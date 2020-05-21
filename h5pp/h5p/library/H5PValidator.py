

##
# self class is used for validating H5P files
##
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any

from h5pp.h5p.library.H5PContentValidator import H5PContentValidator
from h5pp.h5p.library import H5PCore


class H5PValidator:
    h5pRequired = {
        "title": r"^.{1,255}$",
        "language": r"^[a-z]{1,5}$",
        "preloadedDependencies": {
            "machineName": r"^[\w0-9\-\.]{1,255}$",
            "majorVersion": r"^[0-9]{1,5}$",
            "minorVersion": r"^[0-9]{1,5}$"
        },
        "mainLibrary": r"(?i)^[$a-z_][0-9a-z_\.$]{1,254}$",
        "embedTypes": {"iframe", "div"}}

    h5pOptional = {
        "contentType": r"^.{1,255}$",
        "author": r"^.{1,255}$",
        "license": r"^(cc-by|cc-by-sa|cc-by-nd|cc-by-nc|cc-by-nc-sa|cc-by-nc-nd|pd|cr|MIT|GPL1|GPL2|GPL3|MPL|MPL2)$",
        "dynamicDependencies": {
            "machineName": r"^[\w0-9\-\.]{1,255}$",
            "majorVersion": r"^[0-9]{1,5}$",
            "minorVersion": r"^[0-9]{1,5}$"
        },
        "w": r"^[0-9]{1,4}$",
        "n": r"^[0-9]{1,4}$",
        "metaKeywords": r"^.{1,}$",
        "metaDescription": r"^.{1,}$"
    }

    libraryRequired = {
        "title": r"^.{1,255}$",
        "majorVersion": r"^[0-9]{1,5}$",
        "minorVersion": r"^[0-9]{1,5}$",
        "patchVersion": r"^[0-9]{1,5}$",
        "machineName": r"^[\w0-9\-\.]{1,255}$",
        "runnable": r"^(0|1)$"
    }

    libraryOptional = {
        "author": r"^.{1,255}$",
        "license": r"^(cc-by|cc-by-sa|cc-by-nd|cc-by-nc|cc-by-nc-sa|cc-by-nc-nd|pd|cr|MIT|GPL1|GPL2|GPL3|MPL|MPL2)$",
        "description": r"^.{1,}$",
        "dynamicDependencies":
            {"machineName": r"^[\w0-9\-\.]{1,255}$", "majorVersion": r"^[0-9]{1,5}$", "minorVersion": r"^[0-9]{1,5}$"},
        "preloadedDependencies":
            {"machineName": r"^[\w0-9\-\.]{1,255}$", "majorVersion": r"^[0-9]{1,5}$", "minorVersion": r"^[0-9]{1,5}$"},
        "editorDependencies":
            {"machineName": r"^[\w0-9\-\.]{1,255}$", "majorVersion": r"^[0-9]{1,5}$", "minorVersion": r"^[0-9]{1,5}$"},
        "preloadedJs": {"path": r"(?i)^((\/)?[a-z_\-\s0-9\.]+)+\.js$"},
        "preloadedCss": {"path": r"(?i)^((\/)?[a-z_\-\s0-9\.]+)+\.css$"},
        "dropLibraryCss": {"machineName": r"^[\w0-9\-\.]{1,255}$"},
        "w": r"^[0-9]{1,4}$", "h": r"^[0-9]{1,4}$",
        "embedTypes": {"iframe", "div"}, "fullscreen": r"^(0|1)$",
        "coreApi": {"majorVersion": r"^[0-9]{1,5}$", "minorVersion": r"^[0-9]{1,5}$"}
    }

    ##
    # Constructor for the H5PValidator
    ##
    def __init__(self, framework, core):
        self.h5p_framework = framework
        self.h5p_core: H5PCore = core
        self.h5p_content_validator = H5PContentValidator(self.h5p_framework, self.h5p_core)

    def unpack_h5p(self, source, destination):

        # Only allow files with the .h5p extension.
        if source.suffix.lower() != ".h5p":
            print("The file you uploaded is not a valid HTML5 Package (It does not have the .h5p file extension)")
            self.h5p_core.delete_file_tree(destination)
            return False

        zipf = zipfile.ZipFile(source, "r")
        if zipf:
            zipf.extractall(destination)
            zipf.close()
        else:
            print("The file you uploaded is not a valid HTML5 Package (We are unable to unzip it)")
            self.h5p_core.delete_file_tree(destination)
            return False

        os.remove(source)
        return True

    def process_h5p_content(self, tmp_dir, skip_content, upgrade_only):
        # Process content and libraries
        valid = True
        libraries = dict()
        files = os.listdir(tmp_dir)
        main_h5p_data = None
        content_json_data = None
        main_h5p_exists = content_exists = False
        for f in files:
            if f[0:1] in [".", "_"]:
                continue

            file_path = tmp_dir / f
            # Check for h5p.json file.
            if f.lower() == "h5p.json":
                if skip_content: continue

                result = self.validate_main_h5p(file_path, f)
                if not result:
                    valid = False
                    continue
                else:
                    main_h5p_data = result
                    main_h5p_exists = True

            # Check for h5p.jpg ?
            elif f.lower() == "h5p.jpg":
                pass

            # Content directory holds content.
            elif f == "content":
                # We do a separate skip_content check to avoid having the
                # content folder being treated as a library.
                if skip_content: continue
                result = self.validate_content_directory(file_path)
                if not result:
                    valid = False
                    continue
                content_exists = True
                content_json_data = result

            # The rest should be library folders.
            elif self.h5p_framework.mayUpdateLibraries():
                if not os.path.isdir(file_path):
                    # Ignore self. Probably a file that shouldn"t have been
                    # included.
                    continue

                result = self.validate_library(f, file_path, tmp_dir)
                if not result:
                    valid = False
                    continue

                libraries[self.h5p_core.library_to_string(result)] = result

        if not skip_content:
            if not content_exists:
                print("A valid content folder is missing")
                valid = False
            if not main_h5p_exists:
                print("A valid main h5p.json file is missing")
                valid = False

        if valid:
            if upgrade_only:
                # When upgrading, we only add the already installed libraries, and
                # the new dependent libraries
                upgrades = {}
                for libString, library in libraries:
                    # Is self library already installed ?
                    if self.h5p_framework.get_library_id(library["machineName"]):
                        upgrades[libString] = library

                missing_libraries = self.get_missing_libraries(upgrades)
                while missing_libraries:
                    for libString, missing in missing_libraries:
                        library = libraries[libString]
                        if library:
                            upgrades[libString] = library

                libraries = upgrades

            self.h5p_core.librariesJsonData = dict(libraries)

            if not skip_content:
                self.h5p_core.mainJsonData = main_h5p_data
                self.h5p_core.contentJsonData = content_json_data
                # Check for the dependencies in h5p.json as well as in the
                # libraries
                libraries["main_h5p_data"] = main_h5p_data

            missing_libraries = self.get_missing_libraries(libraries)

            for libString, missing in list(missing_libraries[0].items()):
                if self.h5p_core.get_library_id(missing, libString):
                    del missing_libraries[libString]

            if not H5PCore.empty(missing_libraries[0]):
                for libString, library in list(missing_libraries[0].items()):
                    print("Missing required library %s" % libString)
                if not self.h5p_framework.mayUpdateLibraries():
                    print("Note that the libraries may exist in the file you uploaded, "
                          "but you\"re not allowed to upload new libraries. "
                          "Contact the site administrator about self.")

            valid = H5PCore.empty(missing_libraries[0]) and valid

        if not valid:
            self.h5p_core.delete_file_tree(tmp_dir)
        return valid

    def validate_main_h5p(self, file_path, file):
        main_h5p_data = self.get_json_data(file_path)
        if not main_h5p_data:
            print("Could not parse the main h5p.json file")
            return False
        else:
            valid_h5p = self.is_valid_h5p_data(main_h5p_data, file, self.h5pRequired, self.h5pOptional)
            if not valid_h5p:
                print("The main h5p.json file is not valid")
                return False

        return main_h5p_data

    def validate_content_directory(self, file_path):
        if not os.path.isdir(file_path):
            print("Invalid content folder")
            return False

        content_json_data = self.get_json_data(file_path / "content.json")

        if not content_json_data:
            print("Could not find or parse the content.json file")
            return False

        if not self.h5p_content_validator.validateContentFiles(file_path):
            # validateContentFiles adds potential errors to the queue
            return False

        return content_json_data

    def validate_library(self, f, file_path, tmp_dir):
        library_h5_p_data = self.get_library_data(f, file_path, tmp_dir)

        if not library_h5_p_data:
            return False

        # Library"s directory name must be:
        # - <machineName>
        #      - or -
        # - <machineName>-<majorVersion>.<minorVersion>
        # where machineName, majorVersion and minorVersion is read
        # from library.json
        short_name = library_h5_p_data["machineName"]
        long_name = self.h5p_core.library_to_string(library_h5_p_data, True)
        if short_name != f and long_name != f:
            print("Library directory name must match machineName or machineName-majorVersion.minorVersion"
                  " (from library.json). (Directory: %s %s %s %s)" %
                  (f, library_h5_p_data["machineName"], library_h5_p_data["majorVersion"],
                   library_h5_p_data["minorVersion"])
                  )
            return False

        library_h5_p_data["uploadDirectory"] = file_path
        return library_h5_p_data

    ##
    # Validates a .h5p file
    ##
    def is_valid_package(self, skip_content=False, upgrade_only=False):
        # Create a temporary dir to extract package in.
        tmp_dir = self.h5p_framework.getUploadedH5pFolderPath()
        if not self.unpack_h5p(self.h5p_framework.getUploadedH5pPath(), tmp_dir): return False

        return self.process_h5p_content(tmp_dir, skip_content, upgrade_only)

    ##
    # Validates a H5P library
    ##
    def get_library_data(self, f, file_path: Path, tmp_dir: Path) -> Any:
        if not re.search(r"^[\w0-9\-.]{1,255}$", f):
            print("Invalid library name: %s" % f)
            return False

        h5p_data = self.get_json_data(file_path / 'library.json')

        if not h5p_data:
            print("Could not find library.json file with valid json format for library %s" % f)
            return False

        # validate json if a semantics file is provided
        semantics_path = file_path / 'semantics.json'

        if semantics_path.exists():
            semantics = self.get_json_data(semantics_path, True)
            if not semantics:
                print("Invalid semantics.json file has been included in the library %s" % f)
                return False
            else:
                h5p_data["semantics"] = semantics

        # validate language folder if it exists
        language_path = file_path / "language"

        if language_path.is_dir():
            for language_file in language_path.iterdir():
                if str(language_file.name) in [".", ".."]:
                    continue
                if not re.search(r"^(?:-?[a-z]+){1,7}\.json$", str(language_file.name)):
                    print("Invalid language file %s in library %s" % (language_file, f))
                    return False

                language_json = self.get_json_data(language_file, True)

                if not language_json:
                    print("Invalid language file %s has been included in the library %s" % (language_file.name, f))
                    return False

                # parts[0] is the language code
                lang = {language_file.stem: language_json}
                if "language" not in h5p_data:
                    h5p_data["language"] = lang
                else:
                    h5p_data["language"][language_file.stem] = language_json

        valid_library = self.is_valid_h5p_data(h5p_data, f, self.libraryRequired, self.libraryOptional)

        valid_library = self.h5p_content_validator.validateContentFiles(file_path, True) and valid_library

        if "preloadedJs" in h5p_data:
            valid_library = self.is_existing_files(h5p_data["preloadedJs"], tmp_dir, f) and valid_library
        if "preloadedCss" in h5p_data:
            valid_library = self.is_existing_files(h5p_data["preloadedCss"], tmp_dir, f) and valid_library

        if valid_library:
            return h5p_data

        return False

    ##
    # Use the dependency declarations to find any missing libraries
    ##
    def get_missing_libraries(self, libraries):
        missing = []
        for library, content in list(libraries.items()):
            if "preloadedDependencies" in content:
                missing.append(self.get_missing_dependencies(content["preloadedDependencies"], libraries))
            if "dynamicDependencies" in content:
                missing.append(self.get_missing_dependencies(content["dynamicDependencies"], libraries))
            if "editorDependencies" in content:
                missing.append(self.get_missing_dependencies(content["editorDependencies"], libraries))
        return missing

    ##
    # Helper function for get_missing_libraries for dependency required libraries in
    # the provided list of libraries
    ##
    def get_missing_dependencies(self, dependencies, libraries):
        missing = dict()
        for dependency in dependencies:
            lib_string = self.h5p_core.library_to_string(dependency)
            if lib_string not in libraries:
                missing[lib_string] = dependency
        return missing

    ##
    # Figure out if the provided file paths exists
    #
    # Triggers error messages if files doesn't exist
    ##
    @staticmethod
    def is_existing_files(files, tmp_dir: Path, library):
        for f in files:
            path = f["path"].replace("\\", "/")
            if not os.path.exists(tmp_dir / library / path):
                print(("The file %s is missing from library: %s" % (path, library)))
                return False
        return True

    ##
    # Validates h5p.json and library.json h5p data
    #
    # Error message are triggered if the data isn't valid
    ##
    def is_valid_h5p_data(self, h5p_data, library_name, required, optional):
        valid = self.is_valid_required_h5p_data(h5p_data, required, library_name)
        valid = self.is_valid_optional_h5p_data(h5p_data, optional, library_name) and valid

        # Check the library"s required API version of Core.
        # If no requirement is set self implicitly means 1.0.
        if "coreApi" in h5p_data and not H5PCore.empty(h5p_data["coreApi"]):
            if (h5p_data["coreApi"]["majorVersion"] > self.h5p_core.coreApi["majorVersion"] or (
                    h5p_data["coreApi"]["majorVersion"] == self.h5p_core.coreApi["majorVersion"] and
                    h5p_data["coreApi"]["minorVersion"] > self.h5p_core.coreApi["minorVersion"])):
                print("The system was unable to install the %s component from the package,"
                      " it requires a newer version of the H5P plugin. "
                      "self site is currently running version %s, whereas the required version is %s or higher. "
                      "You should consider upgrading and then try again." % (
                          h5p_data["title"] if h5p_data["title"] else library_name,
                          str(self.h5p_core.coreApi["majorVersion"]) + "." + str(self.h5p_core.coreApi["minorVersion"]),
                          str(h5p_data["coreApi"]["majorVersion"]) + "." + str(h5p_data["coreApi"]["minorVersion"])))

                valid = False

        return valid

    ##
    # Helper function for is_valid_h5p_data
    #
    # Validates the optional part of the h5pData
    #
    # Triggers error messages
    ##
    def is_valid_optional_h5p_data(self, h5p_data, requirements, library_name):
        valid = True

        for key, value in list(h5p_data.items()):
            if key in requirements:
                valid = self.is_valid_requirement(value, requirements[key], library_name, key) and valid
        return valid

    ##
    # Validate a requirement given as regexp or an array of requirements
    ##
    def is_valid_requirement(self, h5p_data, requirement, library_name, property_name):
        valid = True

        if isinstance(requirement, str):
            if requirement == "boolean":
                if not isinstance(h5p_data, bool):
                    print("Invalid data provided for %s in %s. Boolean expected." % (property_name, library_name))
                    valid = False
            else:
                # The requirement is a regexp, match it against the data
                if isinstance(h5p_data, str) or isinstance(h5p_data, int):
                    if not re.search(requirement, str(h5p_data)):
                        print("Invalid data provided for %s in %s. No Matches between %s and %s" %
                              (property_name, library_name, requirement, h5p_data))
                        valid = False
                else:
                    print("Invalid data provided for %s in %s. String or Integer expected." %
                          (property_name, library_name))
                    valid = False
        elif isinstance(requirement, dict) or isinstance(requirement, set):
            # we have sub requirements
            if isinstance(h5p_data, list):
                if isinstance(h5p_data[0], dict):
                    for sub_h5pData in h5p_data:
                        valid = self.is_valid_required_h5p_data(sub_h5pData, requirement, library_name) and valid
                else:
                    valid = self.is_valid_required_h5p_data(h5p_data[0], requirement, library_name) and valid

            elif isinstance(h5p_data, dict):
                valid = self.is_valid_required_h5p_data(h5p_data, requirement, library_name) and valid

            else:
                print("Invalid data provided for %s in %s." % (property_name, library_name))
                valid = False

        else:
            print("Can\"t read the property %s in %s." % (property_name, library_name))
            valid = False

        return valid

    ##
    # Validates the required h5p data in library.json and h5p.json
    ##
    def is_valid_required_h5p_data(self, h5p_data, requirements, library_name):
        valid = True
        if isinstance(requirements, dict):
            for required, requirement in list(requirements.items()):
                if isinstance(required, int):
                    # We have an array of allowed options
                    return self.is_valid_h5p_data_options(h5p_data, requirements, library_name)
                if required in h5p_data:
                    valid = self.is_valid_requirement(h5p_data[required], requirement, library_name, required) and valid
                else:
                    print("The required property %s is missing from %s" % (required, library_name))
                    valid = False
        return valid

    ##
    # Validates h5p data against a set of allowed values(options)
    ##
    @staticmethod
    def is_valid_h5p_data_options(selected, allowed, library_name):
        valid = True
        for value in selected:
            if value not in allowed:
                print("Illegal option %s in %s." % (value, library_name))
                valid = False
        return valid

    ##
    # Fetch json data from file
    ##
    @staticmethod
    def get_json_data(file_path: Path, return_as_string=False) -> Any:
        json_file = H5PCore.file_get_contents(file_path)
        if json_file is False:
            return False  # Cannot read from file.

        json_data = json.loads(json_file)
        if json_data is None:
            return False

        if return_as_string:
            return json_file
        else:
            return json_data
