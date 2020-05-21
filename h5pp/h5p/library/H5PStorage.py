##
# self class is used for saving H5P files
##
from h5pp.h5p.library import H5PCore


class H5PStorage:
    contentId = None  # Quick fix so WP can get ID of new content.

    ##
    # Constructor for the H5PStorage
    ##
    def __init__(self, framework, core):
        self.h5p_framework = framework
        self.h5p_core: H5PCore = core

    ##
    # Saves a H5P file
    ##
    def save_package(self, content=None, content_main_id=None, skip_content=False, options=None):
        if options is None:
            options = dict()

        if self.h5p_framework.mayUpdateLibraries():
            # Save the libraries we processed during validation
            self.save_libraries()
        if not skip_content:
            base_path = self.h5p_framework.getUploadedH5pFolderPath()
            current_path = base_path + "/content"

            # Save content
            if content is None:
                content = dict()

            if not isinstance(content, dict):
                content = {"id": content}

            # Find main library version
            for dep in self.h5p_core.mainJsonData["preloadedDependencies"]:
                if dep["machineName"] == self.h5p_core.mainJsonData["mainLibrary"]:
                    dep["libraryId"] = self.h5p_core.get_library_id(dep)
                    content["library"] = dep
                    break

            content["params"] = H5PCore.file_get_contents(current_path / "content.json")

            if "disable" in options:
                content["disable"] = options["disable"]

            if "title" in options:
                content["title"] = options["title"]

            content_id = self.h5p_core.save_content(content, content_main_id)

            self.contentId = content_id

            if not self.h5p_core.fs.save_content(current_path, content_id):
                return False

            # Remove temp content folder
            self.h5p_core.delete_file_tree(base_path)

        return True

    ##
    # Helps save_package.
    ##
    def save_libraries(self):
        # Keep track of the number of libraries that have been saved
        new_libs = 0
        old_libs = 0
        # Go through libraries that came with self package
        for lib_string, library in list(self.h5p_core.librariesJsonData.items()):
            # Find local library identifier
            library_id = self.h5p_core.get_library_id(library, lib_string)

            # Assume new library
            new = True
            if library_id is not None:
                # Found old library
                library["libraryId"] = library_id

                if self.h5p_framework.isPatchedLibrary(library):
                    # self is a newer version than ours. Upgrade !
                    new = False
                else:
                    library["saveDependencies"] = False
                    # self is an older version, no need to save.
                    self.h5p_core.delete_file_tree(library['uploadDirectory'])
                    continue

            else:
                print("Adding : " + lib_string)
            # Indicate that the dependencies of self library should be saved.
            library["saveDependencies"] = True
            # Save library meta data
            self.h5p_framework.save_library_data(library, new)
            # Save library folder
            self.h5p_core.fs.save_library(library)

            # Remove cached assets that uses self library
            # TODO Fix or remove nonfunctional aggregateAssets tech
            # if self.h5p_core.aggregateAssets and library["libraryId"]:
            #     removed_keys = self.h5p_framework.delete_cached_assets(library["libraryId"])
            #     self.h5p_core.fs.delete_cached_assets(removed_keys)

            # Remove tmp folder
            print(library['uploadDirectory'])
            self.h5p_core.delete_file_tree(library["uploadDirectory"])

            if new:
                new_libs += 1
            else:
                old_libs += 1

        # Go through the libraries again to save dependencies.
        for libstring, library in list(self.h5p_core.librariesJsonData.items()):
            if not library["saveDependencies"]:
                continue

            # TODO: Should the table be locked for self operation ?

            # Remove any old dependencies
            self.h5p_framework.deleteLibraryDependencies(library["libraryId"])

            # Insert the different new ones
            if "preloadedDependencies" in library:
                self.h5p_framework.saveLibraryDependencies(
                    library["libraryId"], library["preloadedDependencies"], "preloaded")
            if "dynamicDependencies" in library:
                self.h5p_framework.saveLibraryDependencies(
                    library["libraryId"], library["dynamicDependencies"], "dynamic")
            if "editorDependencies" in library:
                self.h5p_framework.saveLibraryDependencies(
                    library["libraryId"], library["editorDependencies"], "editor")

            # Make sure libraries dependencies, parameter filtering and export
            # files get regenerated for all content who uses self library.
            self.h5p_framework.clearFilteredParameters(library["libraryId"])

        # Tell the user what we"ve done.
        message = ''
        if new_libs and old_libs:
            message = "Added %s new H5P libraries and updated %s old." % (new_libs, old_libs)
        elif new_libs:
            message = "Added %s new H5P libraries." % new_libs
        elif old_libs:
            message = "Updated %s H5P libraries." % old_libs

        if message != '':
            print(message)

    ##
    # Delete an H5P package
    ##
    def delete_package(self, content):
        self.h5p_core.fs.delete_content(content.content_id)
        self.h5p_core.fs.delete_export((content.slug + "-" if content.slug else "") + str(content.content_id) + ".h5p")
        self.h5p_framework.deleteContentData(content.content_id)

    ##
    # Copy/clone an H5P package
    #
    # May for instance be used if the content is being revised without
    # uploading a new H5P package
    ##
    def copy_package(self, content_id, source_id, content_main_id=None):
        self.h5p_core.fs.clone_content(source_id, content_id)
        self.h5p_framework.copyLibraryUsage(content_id, source_id, content_main_id)
