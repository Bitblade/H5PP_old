##
# self class is used for exporting zips
##
import glob
import json
import os
import zipfile
from pathlib import Path
from typing import Union, Dict


class H5PExport:

    ##
    # Constructor for the H5PExport
    ##
    def __init__(self, framework, core):
        self.h5p_framework = framework
        self.h5p_core = core

    ##
    # Return path to h5p package.
    #
    # Creates package if not already created
    ##
    def create_export_file(self, content: Dict[str, Union[Dict, str]]):

        # Get path to temporary folder, where export will be contained
        tmp_path = self.h5p_core.fs.get_tmp_path()
        os.mkdir(tmp_path)

        try:
            # Create content folder and populate with files
            self.h5p_core.fs.export_content(content["id"], tmp_path / 'content')
        except IOError as e:
            print("Error during the creation of content folder: %s" % e)
            self.h5p_core.delete_file_tree(tmp_path)
            return False

        # Update content.json with content from database
        # TODO Rewrite for pathlib
        with open(str(tmp_path / "content/content.json"), "ab") as f:
            f.write(content["params"].encode("utf-8"))

        # Make embedType into an array
        embed_types = content["embedType"].split(", ")

        # Build h5p.json
        h5p_json = {"title": content["title"], "language": content["language"] if (
                "language" in content and len(content["language"].strip()) != 0) else "und",
            "mainLibrary": content["library"]["name"], "embedTypes": embed_types}

        # Add dependencies to h5p
        for key, dependency in list(content["dependencies"].items()):
            library = dependency["library"]

            try:
                export_folder = None

                # Determine path of export library
                # TODO Remove support for non-functioning devmode
                # if self.h5p_core in locals() and self.h5p_core.h5p_development in locals():
                #     # Tries to find library in development folder
                #     is_dev_library = self.h5p_core.h5p_development.getLibrary(
                #         library["machineName"], library["majorVersion"], library["minorVersion"]
                #     )
                #
                #     if is_dev_library is None:
                #         export_folder = "/" + library["path"]

                # Export required libraries
                self.h5p_core.fs.export_library(library, tmp_path, export_folder)
            except IOError as e:
                print("Error during export the required libraries: %s" % e)
                self.h5p_core.delete_file_tree(tmp_path)
                return False

            # Do not add editor dependencies to h5p json.
            if dependency["type"] == "editor":
                continue

            # Add to h5p.json dependencies
            if dependency["type"] + "Dependencies" not in h5p_json:
                h5p_json[dependency["type"] + "Dependencies"] = list()
            h5p_json[dependency["type"] + "Dependencies"].append(
                {"machineName": library["machine_name"], "majorVersion": library["major_version"],
                    "minorVersion": library["minor_version"]})

        # Save h5p.json
        results = json.dumps(h5p_json)
        # TODO Rewrite for pathlib
        with open(str(tmp_path / "h5p.json"), "w") as f:
            f.write(results)

        # Get a complete file list from our tmp dir
        files = list()
        self.populate_file_list(tmp_path, files)

        # Get path to temporary export target file
        tmp_file = self.h5p_core.fs.get_tmp_path()

        # Create new zip instance
        zipf = zipfile.ZipFile(tmp_file, 'w')

        # Add all the files from the tmp dir.
        for f in files:
            # Please not that the zip format has no concept of folders, we must
            # use forward slashes to separate our directories.
            zipf.write(f['absolutePath'], f['relativePath'])

        # Close zip and remove tmp dir
        zipf.close()
        self.h5p_core.delete_file_tree(tmp_path)

        try:
            # Save export
            self.h5p_core.fs.save_export(tmp_file, content["slug"] + "-" + content["id"] + ".h5p")
        except IOError as e:
            print("Error during export save: %s" % e)
            return False

        os.remove(tmp_file)
        self.h5p_framework.afterExportCreated()

        return True

    ##
    # Recursive function the will add the files of the given directory to the
    # given files list. All files are objects with an absolute path and
    # a relative path. The relative path is forward slashes only ! Great for
    # use in zip files and URLs.
    ##
    # TODO Rewrite function to use pathlib
    def populate_file_list(self, directory: Path, files, relative=""):
        strip = len(str(directory)) + 1
        contents = glob.glob(str(directory) + '/' + '*')
        if contents:
            for f in contents:
                rel = relative + f[strip:strip + len(str(directory))]
                if os.path.isdir(f):
                    self.populate_file_list(f, files, rel + '/')
                else:
                    files.append({'absolutePath': f, 'relativePath': rel})

    ##
    # Delete .h5p file
    ##
    # TODO Something is going very wrong here. The function is being used, but how?!
    @staticmethod
    def delete_export(content):
        ##
        # Add editor libraries to the list of libraries
        #
        # These are not supposed to go into h5p.json, but must be included with the rest
        # of the libraries
        #
        # TODO self is a function that is not currently being used
        ##
        def add_editor_libraries(libraries, editor_libraries):
            for editorLibrary in editor_libraries:
                libraries[editorLibrary["machineName"]] = editorLibrary
            return libraries
