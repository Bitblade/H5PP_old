import os
import uuid
import shutil
from django.conf import settings
from pathlib import Path


##
# The default file storage class for H5P.
##
class H5PDefaultStorage:

    def __init__(self, path: Path):
        """
        Constructor for H5PDefaultStorage
        :param path: Path to the h5p storage directory
        """
        self.path = path

    def save_library(self, library):
        """
        Store the library folder found in library['uploadDirectory'] in the storage path
        :param library: Library dict including uploadDirectory value
        """
        destination = self.path/'libraries'/self.library_to_string(library, True)

        # Make sure destination dir doesn't exist
        self.delete_dir_recursive(destination)

        # Move library folder
        self.copy_dir_recursive(library['uploadDirectory'], destination)

    def save_content(self, source: Path, content_id: int):
        """
        Store the content folder.
        :param source: Path referencing the (temporary) directory containing the content
        :param content_id: content_id to store this content under.
        """

        destination = self.path/'content'/str(content_id)

        self.delete_dir_recursive(destination)  # Remove any old content
        self.copy_dir_recursive(source, destination)

    def delete_content(self, content_id: int):
        """Remove content folder."""
        self.delete_dir_recursive(self.path/'content'/str(content_id))

    ##
    # Creates a stored copy of the content folder.
    ##
    def clone_content(self, old_id: int, new_id: int):
        path = self.path/'content'
        self.copy_dir_recursive(path/str(old_id), path/str(new_id))

    ##
    # Get path to a new unique tmp folder.
    ##
    def get_tmp_path(self) -> Path:
        temp = self.path/'tmp'
        self.create_dir_recursive(temp)
        return temp/str(uuid.uuid1())

    ##
    # Fetch content folder and save in target directory.
    ##
    def export_content(self, content_id, target: Path):
        self.copy_dir_recursive(self.path / 'content' / content_id, target)

    ##
    # Fetch library folder and save in target directory.
    ##
    # TODO Remove devmode
    # MLD: Method contains devmode references, but I'm leaving them in as they do no harm and could
    # help in the future
    def export_library(self, library, target: Path, development_path: Path = None):
        folder = self.library_to_string(library, True)

        if development_path is None:
            src_path = Path('libraries') / folder
        else:
            src_path = development_path

        self.copy_dir_recursive(self.path / src_path, target / folder)

    def save_export(self, source: Path, export_name: str):
        """
        Save file(s) from 'source' in subdirectory 'export_name' in the exports directory
        :param source: Path of the file
        :param export_name:
        """
        self.delete_export(export_name)

        if not self.create_dir_recursive(self.path/'exports'):
            raise Exception('Unable to create directory for H5P export file.')
        try:
            shutil.copy(str(source), str(self.path/'exports'/export_name))
        except IOError as e:
            print('Unable to copy: %s' % e)

    def delete_export(self, filename: str):
        """Remove file pointed to by filename in the exports directory"""
        target = self.path/'exports'/filename
        if target.exists():
            target.unlink()

    def has_export(self, filename: str):
        """Check if the given export file exists in the exports directory."""
        target = self.path/'exports'/filename
        return target.exists()

    def copy_dir_recursive(self, source: Path, destination: Path):
        """Recursive function for copying directories."""
        if not self.create_dir_recursive(destination):
            raise Exception('Unable to copy')

        for file in source.iterdir():
            if file.name != '.git' and file.name != '.gitignore':
                if file.is_dir():
                    self.copy_dir_recursive(file, destination / file.name)
                else:
                    shutil.copy(str(file), str(destination/file.name))

    def create_dir_recursive(self, path: Path):
        """
        Recursive function that makes sure the specified directory exists and is writable.
        :param path: The directory path to create
        :return: True if successful, False otherwise
        """
        if not path.exists():
            if not self.create_dir_recursive(path.parent):
                return False
            path.mkdir(mode=0o777)

        if not path.is_dir():
            raise Exception('Path is not a directory')

        if not os.access(str(path), os.W_OK):
            raise Exception('Unable to write to %s - check directory permissions -' % path)

        return True

    ##
    # Writes library data as string in the form {machineName} {majorVersion}.{minorVersion}
    ##
    @staticmethod
    def library_to_string(library, format_as_folder_name=False):
        separator = '-' if format_as_folder_name else ' '

        if 'machine_name' not in library:
            return f'{library["machineName"]}{separator}{str(library["majorVersion"])}.{str(library["minorVersion"])}'

        return f'{library["machine_name"]}{separator}{str(library["major_version"])}.{str(library["minor_version"])}'

    ##
    # Save files uploaded through the editor.
    ##
    # TODO Improve
    @staticmethod
    def save_file(files, contentid, _=None):
        file_data = files.getData()
        base_path = settings.H5P_STORAGE_ROOT
        if file_data is not None and contentid == '0':
            directory = base_path/'editor'/files.getType() + 's'
            file = directory/files.getName()
            directory.mkdir(exist_ok=True)
            file.write_bytes(file_data)

        elif file_data is not None and contentid != '0':
            directory = base_path/'content'/str(contentid)/files.getType() + 's'
            file = directory/files.getName()
            directory.mkdir(exist_ok=True)
            file.write_bytes(file_data)

        elif contentid == '0':
            directory = base_path/'editor'/files.getType() + 's'
            file = directory/files.getName()
            directory.mkdir(exist_ok=True)
            content = files.getFile()
            with file.open(mode='wb+') as pointer:
                for chunk in content.chunks():
                    pointer.write(chunk)

        else:
            directory = base_path/'content'/str(contentid)/files.getType() + 's'
            file = directory/files.getName()
            content = files.getFile()
            directory.mkdir(exist_ok=True)
            with file.open(mode='wb+') as pointer:
                for chunk in content.chunks():
                    pointer.write(chunk)

    # TODO Merge with H5PCore::delete_file_tree?
    def delete_dir_recursive(self, path: Path):
        """
        Recursively removes directories (including content)
        :param path: The directory to remove
        :return: False if path does not point to a directory. True if removal was successful.
        """
        if not path.is_dir():
            return False

        for dir_content_item in path.iterdir():
            filepath = path/dir_content_item
            if filepath.is_dir():
                self.delete_dir_recursive(filepath)
            else:
                filepath.unlink()

        path.rmdir()
        return True

    def get_content(self, path: Path):
        """
        Return the content of the file pointed to by path
        :param path: The absolute or relative (to the storage dir) path to the file to read
        :return: The contents of the file
        """
        if path.is_absolute():
            file_path = path
        else:
            file_path = self.path/path

        with file_path.open(mode='rb') as pointer:
            result = pointer.read().decode('utf8', 'ignore')

        return result

    ##
    # Will concatenate all JavaScripts and Stylesheets into two files in order
    # to improve page performance.
    ##
    # TODO Fix aggregation tech or remove unused method
    # def cache_assets(self, files, key):
    #
    #     for dtype, assets in files.items():
    #         if empty(assets):
    #             continue  # Skip no assets
    #
    #         content = ''
    #         for asset in assets:
    #             # Get content form asset file
    #             asset_content = open(self.path + asset['path']).read()
    #             css_rel_path = re.sub('[^/]+$', '', asset['path'])
    #
    #             # Get file content and concatenate
    #             if dtype == 'scripts':
    #                 content = content + asset_content + ';\n'
    #             else:
    #                 # Rewrite relative URLs used inside Stylesheets
    #                 content = content + re.sub('/url\([\'"]?([^"\')]+)[\'"]?\)/i',
    #                                            lambda matches: matches[0] if re.search('/^(data:|([a-z0-9]+:)?\/)/i',
    #                                                                 matches[
    #                                                                     1] == 1) else 'url("../' + css_rel_path +
    #                                                                                   matches[
    #                                                                                       1] + '")',
    #                                            asset_content) + '\n'
    #
    #         self.create_dir_recursive(self.path / 'cachedassets')
    #         ext = 'js' if dtype == 'scripts' else 'css'
    #         outputfile = '/cachedassets/' + key + '.' + ext
    #
    #         with open(self.path + outputfile, 'w') as f:
    #             f.write(content)
    #         files[dtype] = [{'path': outputfile, 'version': ''}]

    ##
    # Will check if there are cache assets available for content.
    ##
    # TODO Fix or remove nonfunctional aggregateAssets tech
    # def get_cached_assets(self, key):
    #     files = {'scripts': [], 'styles': []}
    #     js = Path('/cachedassets/') / key / '.js'
    #     if (self.path / js).exists():
    #         files['scripts'].append({'path': js, 'version': ''})
    #
    #     css = Path('/cachedassets/') / key / '.css'
    #     if (self.path / css).exists():
    #         files['styles'].append({'path': css, 'version': ''})
    #
    #     return None if empty(files) else files

    ##
    # Remove the aggregated cache files.
    ##
    # TODO Fix or remove nonfunctional aggregateAssets tech
    # def delete_cached_assets(self, keys):
    #     for hhash in keys:
    #         for ext in ['js', 'css']:
    #             path = self.path / 'cachedassets' / hhash / ext
    #             if path.exists():
    #                 os.remove(path)


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

# TODO Remove seemingly unused method
# def empty(variable):
#     if not variable:
#         return True
#     return False

# TODO Remove seemingly unused method
# def isset(variable):
#     return variable in locals() or variable in globals()
