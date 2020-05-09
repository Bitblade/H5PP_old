# Django module h5p editor

import time
import json
import os
import re
import urllib.parse
from pathlib import PurePath

from django.conf import settings

from h5pp.models import h5p_content_user_data, h5p_libraries
from h5pp.h5p.h5pmodule import h5p_add_core_assets, h5p_add_files_and_settings
from h5pp.h5p.h5pclasses import H5PDjango

STYLES = ["libs/darkroom.css", "styles/css/application.css"]

OVERRIDE_STYLES = urllib.parse.urljoin(settings.STATIC_URL, 'h5p/styles/h5pp.css')

SCRIPTS = [
    "scripts/h5peditor.js", "scripts/h5peditor-semantic-structure.js", "scripts/h5peditor-editor.js",
    "scripts/h5peditor-library-selector.js", "scripts/h5peditor-form.js", "scripts/h5peditor-text.js",
    "scripts/h5peditor-html.js", "scripts/h5peditor-number.js", "scripts/h5peditor-textarea.js",
    "scripts/h5peditor-file-uploader.js", "scripts/h5peditor-file.js", "scripts/h5peditor-image.js",
    "scripts/h5peditor-image-popup.js", "scripts/h5peditor-av.js", "scripts/h5peditor-group.js",
    "scripts/h5peditor-boolean.js", "scripts/h5peditor-list.js", "scripts/h5peditor-list-editor.js",
    "scripts/h5peditor-library.js", "scripts/h5peditor-library-list-cache.js", "scripts/h5peditor-select.js",
    "scripts/h5peditor-dimensions.js", "scripts/h5peditor-coordinates.js", "scripts/h5peditor-none.js",
    "ckeditor/ckeditor.js"
]


def h5peditorContent(request):
    assets = h5p_add_core_assets()
    core_assets = h5p_add_core_assets()
    editor = h5p_add_files_and_settings(request, True)
    framework = H5PDjango(request.user)
    add = list()

    for style in STYLES:
        css = settings.STATIC_URL + 'h5p/h5peditor/' + style
        assets['css'].append(css)

    # Override Css
    assets['css'].append(OVERRIDE_STYLES)

    for script in SCRIPTS:
        if script != 'scripts/h5peditor-editor.js':
            js = settings.STATIC_URL + 'h5p/h5peditor/' + script
            assets['js'].append(js)

    add.append(settings.STATIC_URL + 'h5p/h5peditor/scripts/h5peditor-editor.js')
    add.append(settings.STATIC_URL + 'h5p/h5peditor/application.js')

    language_file = settings.STATIC_URL + 'h5p/h5peditor/language/' + settings.H5P_LANGUAGE + '.js'
    if not os.path.exists(settings.BASE_DIR + language_file):
        language_file = settings.STATIC_URL + 'h5p/h5peditor/language/en.js'

    add.append(language_file)

    content_validator = framework.getContentValidator()
    editor['editor'] = {
        'filesPath': str(PurePath(settings.H5P_STORAGE_ROOT / 'editor')),
        'fileIcon': {
            'path': "{}h5p/h5peditor/images/binary-file.png".format(settings.STATIC_URL),
            'width': 50,
            'height': 50
        },
        'ajaxPath': "{}editorajax/{}/".format(
            settings.H5P_URL,
            (request['contentId'] if 'contentId' in request else '0')
        ),
        'libraryPath': "{}h5p/h5peditor/".format(settings.STATIC_URL),
        'copyrightSemantics': content_validator.getCopyrightSemantics(),
        'assets': assets,
        'contentRelUrl': '../media/h5pp/content/'}

    return {'editor': json.dumps(editor), 'coreAssets': core_assets, 'assets': assets, 'add': add}


##
# Retrieves ajax parameters for content and update or delete
##


def handleContentUserData(request):
    # framework = H5PDjango(request.user)
    content_id = request.GET['contentId']
    sub_content_id = request.GET['subContentId']
    data_id = request.GET['dataType']

    if content_id is None or data_id is None or sub_content_id is None:
        return ajaxError('Missing parameters')

    if 'data' in request.POST and 'preload' in request.POST and 'invalidate' in request.POST:
        data = request.POST['data']
        preload = request.POST['preload']
        invalidate = request.POST['invalidate']

        # Saving data
        if data is not None and preload is not None and invalidate is not None:
            if data == '0':
                # Delete user data
                deleteUserData(content_id, sub_content_id, data_id, request.user.id)
            else:
                # Save user data
                saveUserData(content_id, sub_content_id, data_id, preload, invalidate, data, request.user.id)

            return ajaxSuccess()
    else:
        # Fetch user data
        user_data = getUserData(content_id, sub_content_id, data_id, request.user.id)
        if not user_data:
            # Did not find data, return nothing
            return ajaxSuccess()
        else:
            # Found data, return encoded data
            return ajaxSuccess(user_data.data)

    return


##
# Get user data for content
##


def getUserData(contentId, subContentId, dataId, userId):
    try:
        result = h5p_content_user_data.objects.get(
            user_id=userId, content_main_id=contentId, sub_content_id=subContentId, data_id=dataId
        )
    except:
        result = False

    return result


##
# Save user data for specific content in database
##


def saveUserData(contentId, subContentId, dataId, preload, invalidate, data, userId):
    update = getUserData(contentId, subContentId, dataId, userId)

    preload = 0 if preload == '0' else 1
    invalidate = 0 if invalidate == '0' else 1

    if not update:
        h5p_content_user_data.objects.create(
            user_id=userId, content_main_id=contentId, sub_content_id=subContentId,
            data_id=dataId, timestamp=time.time(), data=data, preloaded=preload, delete_on_content_change=invalidate
        )
    else:
        update.user_id = userId
        update.content_main_id = contentId
        update.sub_content_id = subContentId
        update.data_id = dataId
        update.data = data
        update.preloaded = preload
        update.delete_on_content_change = invalidate
        update.save()


##
# Delete user data with specific content from database
##


def deleteUserData(contentId, subContentId, dataId, userId):
    h5p_content_user_data.objects.get(
        user_id=userId, content_main_id=contentId, sub_content_id=subContentId, data_id=dataId
    ).delete()


##
# Create or update H5P content
##


def createContent(request, content, params):
    framework = H5PDjango(request.user)
    editor = framework.getEditor()
    content_id = content['id']

    if not editor.createDirectories(content_id):
        print(('Unable to create content directory.', 'error'))
        return False

    editor.processParameters(content_id, content['library'], params)

    return True


def getLibraryProperty(library, prop='all'):
    matches = re.search(r'(.+)\s(\d+)\.(\d+)$', library)
    if matches:
        library_data = {
            'machineName': matches.group(1),
            'majorVersion': matches.group(2),
            'minorVersion': matches.group(3)
        }
        if prop == 'all':
            return library_data
        elif prop == 'libraryId':
            temp = h5p_libraries.objects.filter(
                machine_name=library_data['machineName'], major_version=library_data['majorVersion'],
                minor_version=library_data['minorVersion']
            ).values('library_id')
            return temp
        else:
            return library_data[prop]
    else:
        return False


def ajaxSuccess(data=None):
    response = {'success': True}
    if data is not None:
        response['data'] = data

    return json.dumps(response)


def ajaxError(message=None):
    response = {'success': False}
    if message is not None:
        response['message'] = message

    return json.dumps(response)
