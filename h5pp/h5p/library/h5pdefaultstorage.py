import os
import zipfile
import re
import json
import pprint
import glob
import hashlib
import cgi
import uuid
import shutil
from django.conf import settings
from pathlib import Path

is_array = lambda var: isinstance(var, (list, tuple))


def empty(variable):
    if not variable:
        return True
    return False


def isset(variable):
    return variable in locals() or variable in globals()


def substr_replace(subject, replace, start, length):
    if length is None:
        return subject[:start] + replace
    elif length < 0:
        return subject[:start] + replace + subject[length:]
    else:
        return subject[:start] + replace + subject[start + length:]


def mb_substr(s, start, length=None, encoding="UTF-8"):
    u_s = s.decode(encoding)
    return (u_s[start:(start + length)] if length else u_s[start:]).encode(encoding)


##
# The default file storage class for H5P.
##


class H5PDefaultStorage:

    ##
    # Constructor for H5PDefaultStorage
    ##
    def __init__(self, path):
        self.path = path

    ##
    # Store the library folder.
    ##
    def saveLibrary(self, library):
        dest = self.path / 'libraries' / self.libraryToString(library, True)

        # Make sure destination dir doesn't exist
        self.deleteFileTree(dest)

        # Move library folder
        self.copyFileTree(library['uploadDirectory'], dest)

    ##
    # Store the content folder.
    ##
    def saveContent(self, source, pid):
        dest = self.path / 'content' / str(pid)
        # Remove any old content
        self.deleteFileTree(dest)

        self.copyFileTree(source, dest)

        return True

    ##
    # Remove content folder.
    ##
    def deleteContent(self, pid):
        self.deleteFileTree(self.path / 'content' / str(pid))

    ##
    # Creates a stored copy of the content folder.
    ##
    def cloneContent(self, pid, newId):
        path = self.path / 'content'
        self.copyFileTree(path / pid, path / newId)

    ##
    # Get path to a new unique tmp folder.
    ##
    def getTmpPath(self):
        temp = self.path / 'tmp'
        self.dirReady(temp)
        return temp / str(uuid.uuid1())

    ##
    # Fetch content folder and save in target directory.
    ##
    def exportContent(self, pid, target):
        self.copyFileTree(self.path / 'content' / pid, target)

    ##
    # Fetch library folder and save in target directory.
    ##
    def exportLibrary(self, library, target, developmentPath=None):
        folder = self.libraryToString(library, True)
        srcPath = Path('libraries') / folder if developmentPath == None else developmentPath
        self.copyFileTree(self.path / srcPath, Path(target) / folder)

    ##
    # Save export in file system
    ##
    def saveExport(self, source, filename):
        self.deleteExport(filename)

        if not self.dirReady(self.path / 'exports'):
            raise Exception('Unable to create directory for H5P export file.')

        try:
            shutil.copy(source, self.path / 'exports' / filename)
        except IOError as e:
            print(('Unable to copy %s' % e))

        return True

    ##
    # Remove given export file.
    ##
    def deleteExport(self, filename):
        target = self.path / 'exports' / filename
        if os.path.exists(target):
            os.remove(target)

    ##
    # Check if the given export file exists.
    ##
    def hasExport(self, filename):
        target = self.path / 'exports' / filename
        return os.path.exists(target)

    ##
    # Will concatenate all JavaScripts and Stylesheets into two files in order
    # to improve page performance.
    ##
    def cacheAssets(self, files, key):

        for dtype, assets in files.items():
            if empty(assets):
                continue  # Skip no assets

            content = ''
            for asset in assets:
                # Get content form asset file
                assetContent = open(self.path + asset['path']).read()
                cssRelPath = re.sub('/[^\/]+$/', '', asset['path'])

                # Get file content and concatenate
                if dtype == 'scripts':
                    content = content + assetContent + ';\n'
                else:
                    # Rewrite relative URLs used inside Stylesheets
                    content = content + re.sub('/url\([\'"]?([^"\')]+)[\'"]?\)/i',
                                               lambda matches: matches[0] if re.search('/^(data:|([a-z0-9]+:)?\/)/i',
                                                                                       matches[
                                                                                           1] == 1) else 'url("../' + cssRelPath +
                                                                                                         matches[
                                                                                                             1] + '")',
                                               assetContent) + '\n'

            self.dirReady(self.path / 'cachedassets')
            ext = 'js' if dtype == 'scripts' else 'css'
            outputfile = '/cachedassets/' + key + '.' + ext

            with open(self.path + outputfile, 'w') as f:
                f.write(content)
            files[dtype] = [{'path': outputfile, 'version': ''}]

    ##
    # Will check if there are cache assets available for content.
    ##
    def getCachedAssets(self, key):
        files = {'scripts': [], 'styles': []}
        js = '/cachedassets/' + key + '.js'
        if os.path.exists(self.path + js):
            files['scripts'].append({'path': js, 'version': ''})

        css = '/cachedassets/' + key + '.css'
        if os.path.exists(self.path + css):
            files['styles'].append({'path': css, 'version': ''})

        return None if empty(files) else files

    ##
    # Remove the aggregated cache files.
    ##
    def deleteCachedAssets(self, keys):
        for hhash in keys:
            for ext in ['js', 'css']:
                path = self.path / 'cachedassets' / hhash / ext
                if os.path.exists(path):
                    os.remove(path)

    ##
    # Recursive function for copying directories.
    ##
    def copyFileTree(self, source, destination):
        #TODO Function can be much improved by using Python3 techniques
        if not self.dirReady(destination):
            raise Exception('Unable to copy')

        for f in os.listdir(source):
            if (f != '.') and (f != '..') and f != '.git' and f != '.gitignore':
                if os.path.isdir(Path(source) / f):
                    self.copyFileTree(Path(source) / f, Path(destination) / f)
                else:
                    shutil.copy(Path(source) / f, Path(destination) / f)

    ##
    # Recursive function that makes sure the specified directory exists and
    # is writable.
    ##
    def dirReady(self, path):
        if not os.path.exists(path):
            parent = Path(path).parent
            if not self.dirReady(parent):
                return False

            os.mkdir(path, 0o777)

        if not os.path.isdir(path):
            raise Exception('Path is not a directory')
            return False

        if not os.access(path, os.W_OK):
            raise Exception('Unable to write to %s - check directory permissions -' % path)
            return False

        return True

    ##
    # Writes library data as string on the form {machineName} {majorVersion}.{minorVersion}
    ##
    def libraryToString(self, library, folderName=False):
        if 'machine_name' in library:
            return library['machine_name'] + ('-' if folderName else ' ') + str(library['major_version']) + '.' + str(
                library['minor_version'])
        else:
            return library['machineName'] + ('-' if folderName else ' ') + str(library['majorVersion']) + '.' + str(
                library['minorVersion'])

    ##
    # Recursive function for removing directories.
    ##
    def deleteFileTree(self, pdir):
        #TODO Function can and must be improved considerably using Python3 techniques
        if not os.path.isdir(pdir):
            return False

        files = list(set(os.listdir(pdir)).difference(['.', '..']))

        for f in files:
            self.deleteFileTree(Path(pdir / f)) if os.path.isdir(Path(pdir / f)) else os.remove(Path(pdir / f))

        return os.rmdir(pdir)

    ##
    # Save files uploaded through the editor.
    ##
    def saveFile(self, files, contentid, pid=None):
        filedata = files.getData()
        base_path = settings.H5P_STORAGE_ROOT
        if filedata != None and contentid == '0':
            path = base_path / 'editor' / files.getType() + 's'
            if not os.path.exists(path):
                os.makedirs(path)
            with open(path / files.getName(), 'wb+') as f:
                f.write(filedata)
        elif filedata != None and contentid != '0':
            path = base_path / 'content' / str(contentid) / files.getType() + 's'
            if not os.path.exists(path):
                os.makedirs(path)
            with open(path / files.getName(), 'wb+') as f:
                f.write(filedata)
        elif contentid == '0':
            path = base_path / 'editor' / files.getType() + 's'
            content = files.getFile()
            if not os.path.exists(path):
                os.makedirs(path)
            with open(path / files.getName(), 'wb+') as f:
                for chunk in content.chunks():
                    f.write(chunk)
        else:
            path = base_path / 'content' / str(contentid) / files.getType() + 's'
            content = files.getFile()
            if not os.path.exists(path):
                os.makedirs(path)
            with open(path / files.getName(), 'wb+') as f:
                for chunk in content.chunks():
                    f.write(chunk)

    ##
    # Recursive function for removing directories.
    ##
    def deleteFileTree(self, pdir):
        if not os.path.isdir(pdir):
            return False

        files = list(set(os.listdir(pdir)).difference([".", ".."]))

        for f in files:
            filepath = Path(pdir) / f
            self.deleteFileTree(filepath) if os.path.isdir(filepath) else os.remove(filepath)

        return os.rmdir(pdir)

    ##
    # Read file content of given file and then return it
    ##
    def getContent(self, path):
        content = open(Path(self.path) / Path(path), 'rb')
        result = content.read().decode('utf8', 'ignore')
        return result
