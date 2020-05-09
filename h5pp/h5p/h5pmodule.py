# Django module h5p.
import hashlib
import shutil
import uuid
import time
import math
import json
import os
import re

from django.conf import settings
from django.contrib.sites.models import Site

from h5pp.h5p.h5pevent import H5PEvent
from h5pp.models import *
from h5pp.h5p.h5pclasses import H5PDjango

from django.core import serializers

from h5pp.url_builder import join_url

jsonserializer = serializers.get_serializer("json")
json_serializer = jsonserializer()

STYLES = ["styles/h5p.css", "styles/h5p-confirmation-dialog.css", "styles/h5p-core-button.css"]

OVERRIDE_STYLES = join_url([settings.STATIC_URL, 'h5p/styles/h5pp.css'])

SCRIPTS = [
    "js/jquery.js", "js/h5p.js", "js/h5p-event-dispatcher.js", "js/h5p-x-api-event.js", "js/h5p-x-api.js",
    "js/h5p-content-type.js", "js/h5p-confirmation-dialog.js", "js/h5p-action-bar.js"
]


##
# Get path to HML5 Package
##


def h5p_get_export_path(content):
    # TODO Test
    # Converted from: return os.path.join(settings.MEDIA_ROOT, 'h5pp', 'exports',
    # ((content['slug'] + '-') if 'slug' in content else ''), str(content['id']) + '.h5p')

    return settings.H5P_STORAGE_ROOT \
           / 'exports' \
           / ((content['slug'] + '-') if 'slug' in content else '') \
           / (str(content['id']) + '.h5p')


##
# Creates the title for the library details page
##


def h5p_library_details_title(library_id):
    result = h5p_libraries.objects.filter(library_id=library_id).values('title')
    return result[0] if len(result) > 0 else None


##
# Insert a new content
##


def h5p_insert(request, interface=None):
    if 'h5p_upload' in request.POST:
        storage = interface.getStorage()
        storage.save_package(h5p_get_content_id(request), None, False,
                             {'disable': request.POST['disable'], 'title': request.POST['title']})
    else:
        if 'name' not in request.POST['main_library']:
            lib = h5p_libraries.objects.filter(library_id=request.POST['main_library_id']).values(
                'machine_name', 'major_version', 'minor_version')
            lib = {
                'libraryId': request.POST['main_library_id'],
                'machineName': lib.machine_name,
                'majorVersion': lib.major_version,
                'minorVersion': lib.minor_version
            }
        else:
            lib = {
                'libraryId': request.POST['main_library_id'],
                'machineName': request.POST['main_library']['name'] if 'name' in request.POST['main_library'] else '',
                'majorVersion': request.POST['main_library']['majorVersion'] if 'majorVersion' in request.POST[
                    'main_library'] else '',
                'minorVersion': request.POST['main_library']['minorVersion'] if 'minorVersion' in request.POST[
                    'main_library'] else ''
            }
        core = interface.getCore()
        core.save_content(
            {'id': h5p_get_content_id(request), 'title': request.POST['title'], 'params': request.POST['json_content'],
                'embed_type': request.POST['embed_type'], 'disable': request.POST['disable'], 'library': lib,
                'author': request.user.username,
                'h5p_library': request.POST['h5p_library'] if 'h5p_library' in request.POST else None},
            request.POST['nid'])

    return True

# TODO Remove seemingly unused method
# def h5pUpdate(request):
#     if 'h5p_upload' in request:
#         storage = H5PDjango.h5pGetInstance('storage')
#         storage.save_package(
#             {'id': h5p_get_content_id(request), 'title': request.POST['title'], 'disable': request.POST['disable']},
#             request.POST['nid'], False)
#     else:
#         h5p_insert(request)


def h5p_delete(request):
    content = h5p_contents.objects.get(content_id=request.POST['contentId'])
    h5p_delete_h5p_content(request, content)

    if 'main_library' in request.POST:
        # Log content delete
        H5PEvent(
            'content', 'delete', request.POST['nid'], request.POST['title'], request.POST['main_library']['name'],
            request.POST['main_library']['majorVersion'] + '.' + request.POST['main_library']['minorVersion']
        )


##
# Delete all data related to H5P content
##
def h5p_delete_h5p_content(request, content):
    framework = H5PDjango(request.user)
    storage = framework.getStorageInstance()
    storage.delete_package(content)

    # Remove content points
    h5p_points.objects.filter(content_id=content.content_id).delete()

    # Remove content user data
    h5p_content_user_data.objects.filter(content_main_id=content.content_id).delete()


def h5p_load(request):
    interface = H5PDjango(request.user)
    core = interface.getCore()
    content = core.load_content(h5p_get_content_id(request))

    if content is not None:
        request.GET = request.GET.copy()
        request.GET['json_content'] = content['params']
        request.GET['title'] = content['title']
        request.GET['language'] = 'en'
        request.GET['main_library_id'] = content['library']['id']
        request.GET['embed_type'] = content['embed_type']
        request.GET['main_library'] = content['library']
        request.GET['filtered'] = content['filtered']
        request.GET['disable'] = content['disable']
        request.GET['h5p_slug'] = content['slug']


# TODO Remove seemingly unused method
# def h5pView(request):
#     #TODO Something very wrong with this method...
#      h5p_set_started is called with the user parameter missing (contentId is provided instead of user)
#     #TODO Something very wrong with this method... html is not instantiated correctly and not used!
#     if 'in_preview' not in request.GET and 'main_library_id' in request.GET:
#         html = include_h5p(request)
#
#     if not html:
#         html = '<div>' + 'Sorry, preview of H5P content is not yet available.' + '</div>'
#     else:
#         h5p_set_started(h5p_get_content_id(request))
#
#     return request


# TODO Remove seemingly unused method
# def h5pUserDelete(user):
#     h5p_points.objects.get(uid=user.id).delete()
#
#     # Remove content user data
#     h5p_content_user_data.objects.get(user_id=user.id).delete()


##
# Adds H5P embed code and necessary files
##


def include_h5p(request):
    content_id = h5p_get_content_id(request)
    embed = determine_embed_type(request.GET['embed_type'], request.GET['main_library']['embedTypes'])

    data = h5p_add_files_and_settings(request, embed)
    if embed == 'div':
        html = '<div class="h5p-content" data-content-id="' + content_id + '"></div>'
    else:
        html = '<div class="h5p-iframe-wrapper">' \
               '<iframe id="h5p-iframe-' + content_id + '" class="h5p-iframe" data-content-id="' + content_id + \
               '" style="height:1px" src="about:blank" frameBorder="0" scrolling="no"></iframe></div>'

    return {'html': html, 'data': data}


##
# Set that the logged in user has started on an h5p
##


def h5p_set_started(user, content_id):
    if user.id:
        exist = list(h5p_points.objects.filter(content_id=content_id, uid=user.id).values())
        if len(exist) > 0:
            update = h5p_points.objects.get(content_id=content_id, uid=user.id)
            update.content_id = content_id
            update.uid = user.id
            update.started = int(time.time())
            update.save()
        else:
            h5p_points.objects.create(content_id=content_id, uid=user.id, started=int(time.time()))


##
# Handle grades storage for users
##


def h5p_set_finished(request):
    # Content parameters
    content_id = request.POST['contentId']
    score = request.POST['score']
    max_score = request.POST['maxScore']
    response = {'success': False}

    if content_id.isdigit() and score.isdigit() and max_score.isdigit():
        update = h5p_points.objects.get(content_id=content_id, uid=request.user.id)
        update.finished = int(time.time())
        update.points = score
        update.max_points = max_score
        update.save()
        response['success'] = True

    return json.dumps(response)


##
# Adds content independent scripts, styles and settings
##


def h5p_add_core_assets():
    path = join_url([settings.STATIC_URL, 'h5p'])
    assets = {'css': list(), 'js': list()}

    for style in STYLES:
        css = join_url([path, style])
        assets['css'].append(css)

    for script in SCRIPTS:
        js = join_url([path, script])
        assets['js'].append(js)

    return assets


##
# H5PIntegration object
##


def h5p_get_core_settings(user):
    core_settings = {
        'baseUrl': settings.BASE_URL,
        'url': join_url([settings.MEDIA_URL, 'h5pp']),
        'postUserStatistics': user.id > 0 if user.id else False,
        # TODO This seems to produce example.com/h5p/ajax URLs...
        'ajaxPath': join_url([Site.objects.get_current().domain, settings.H5P_URL, 'ajax']),
        'ajax': {
            'setFinished': join_url([settings.H5P_URL, 'ajax/?setFinished']),
            'contentUserData': join_url(
                [settings.H5P_URL,
                 "ajax/?content-user-data&contentId=:contentId&dataType=:dataType&subContentId=:subContentId"]
            ),
        },
        'tokens': {
            'result': create_token('result'),
            'contentUserData': create_token('contentuserdata')
        },
        'saveFreq': settings.H5P_SAVE if settings.H5P_SAVE != 0 else 'false',
        'l10n':
        {
            'H5P':
                {
                    'fullscreen': 'Fullscreen', 'disableFullscreen': 'Disable fullscreen', 'download': 'Download',
                    'copyrights': 'Rights of use', 'embed': 'Embed', 'size': 'Size', 'showAdvanced': 'Show advanced',
                    'hideAdvanced': 'Hide advanced',
                    'advancedHelp': 'Include this script on your website'
                                    ' if you want dynamic sizing of the embedded content:',
                    'copyrightInformation': 'Rights of use', 'close': 'Close', 'title': 'Title', 'author': 'Author',
                    'year': 'Year', 'source': 'Source', 'license': 'License', 'thumbnail': 'Thumbnail',
                    'noCopyrights': 'No copyright information available for this content.',
                    'downloadDescription': 'Download this content as a H5P file.',
                    'copyrightsDescription': 'View copyright information for this content.',
                    'embedDescription': 'View the embed code for this content.',
                    'h5pDescription': 'Visit H5P.org to check out more cool content.',
                    'contentChanged': 'This content has changed since you last used it.',
                    'startingOver': 'You\'ll be starting over', 'by': 'by', 'showMore': 'Show more',
                    'showLess': 'Show less', 'subLevel': 'Sublevel', 'confirmDialogHeader': 'Confirm action',
                    'confirmDialogBody': 'Please confirm that you wish to proceed. This action is not reversible.',
                    'cancelLabel': 'Cancel', 'confirmLabel': 'Confirm'
                 }
        }
    }

    if user.id:
        core_settings['user'] = {'name': user.username, 'mail': user.email}

    return core_settings


##
# Adds h5p files and settings
##
def h5p_add_files_and_settings(request, embed_type):
    interface = H5PDjango(request.user)
    integration = h5p_get_core_settings(request.user)
    assets = h5p_add_core_assets()

    if 'json_content' not in request.GET or 'contentId' not in request.GET:
        return integration

    content = h5p_get_content(request)
    if 'contents' in integration and content['id'] in integration['contents']:
        return integration

    integration['contents'] = dict()
    integration['contents'][str("cid-%s" % content['id'])] = h5p_get_content_settings(request.user, content)

    core = interface.getCore()
    preloaded_dependencies = core.load_content_dependencies(content['id'], 'preloaded')
    files = core.get_dependencies_files(preloaded_dependencies)
    # library_list = h5p_dependencies_to_library_list(preloaded_dependencies)

    files_assets = {'js': list(), 'css': list()}
    if embed_type == 'div':
        for script in files['scripts']:
            url = join_url([settings.MEDIA_URL, 'h5pp/', script['path']])
            files_assets['js'].append(url)
            integration['loadedJs'] = join_url([url, script['version']])
        for style in files['styles']:
            url = join_url([settings.MEDIA_URL, 'h5pp/', style['path']])
            files_assets['css'].append(url)
            integration['loadedCss'] = join_url([url, style['version']])
        # Override CSS
        files_assets['css'].append(OVERRIDE_STYLES)
        integration['loadedCss'] = OVERRIDE_STYLES

    elif embed_type == 'iframe':
        h5p_add_iframe_assets(request, integration, content['id'], files)

    return {
        'integration': json.dumps(integration),
        'assets': assets,
        'filesAssets': files_assets
    }


##
# Get a content by request
##
def h5p_get_content(request):
    # interface = H5PDjango(request.user)
    # core = interface.h5pGetInstance('core')
    return {
        'id': h5p_get_content_id(request), 'title': request.GET['title'], 'params': request.GET['json_content'],
        'language': request.GET['language'], 'library': request.GET['main_library'], 'embedType': 'div',
        'filtered': request.GET['filtered'],
        'url': join_url([settings.MEDIA_URL, 'h5pp/content/', str(h5p_get_content_id(request)) + '/']),
        'displayOptions': '',
        'slug': request.GET['h5p_slug']
    }


def h5p_get_content_settings(user, content):
    interface = H5PDjango(user)
    core = interface.getCore()
    filtered = core.filter_parameters(content)

    # Get preloaded user data
    results = h5p_content_user_data.objects.filter(user_id=user.id, content_main_id=content['id'], preloaded=1).values(
        'sub_content_id', 'data_id', 'data')

    content_user_data = {0: {'state': '{}'}}
    for result in results:
        content_user_data[result['sub_content_id']][result['data_id']] = result['data']

    content_settings = {
        'library': library_to_string(content['library']),
        'jsonContent': filtered,
        'fullScreen': content['library']['fullscreen'],
        # TODO It seems h5p_get_export_path retrieves an absolute file path, not an URL...
        # TODO Security: Filesystem information leak
        'exportUrl': str(h5p_get_export_path(content)),
        'embedCode': str(
            '<iframe src="' + Site.objects.get_current().domain + settings.H5P_URL + 'embed/' + content[
                'id'] + '" width=":w" height=":h" frameborder="0" allowFullscreen="allowfullscreen"></iframe>'),
        'mainId': content['id'],
        'url': str(content['url']),
        'title': str(content['title'].encode('utf-8')),
        'contentUserData': content_user_data,
        'displayOptions': content['displayOptions']}
    return content_settings

# TODO Use resize js and then either use or remove this seemingly unused method
# def h5pGetResizeUrl():
#     return settings.H5P_PATH + '/js/h5p-resizer.js'


def h5p_get_content_id(request):
    if 'contentId' not in request.GET:
        return None

    return request.GET['contentId']


def h5p_get_list_content(request):
    interface = H5PDjango(request.user)
    contents = interface.getNumContentPlus()
    if contents > 0:
        result = list()
        for content in interface.loadAllContents():
            load = interface.loadContent(content['content_id'])
            load['score'] = get_user_score(content['content_id'])
            result.append(load)
        return result
    else:
        return 0


##
# Determine the correct embed type to use.
##
def determine_embed_type(content_embed_type, library_embed_types):
    # Detect content embed type
    embed_type = "div" if ("div" in content_embed_type.lower()) else "iframe"

    if library_embed_types is not None and library_embed_types != "":
        # Check that embed type is available for library
        embed_types = library_embed_types.lower()
        if embed_type not in embed_types:
            # Not available, pick default.
            embed_type = "div" if "div" in embed_types else "iframe"

    return embed_type


##
# Get a list of libraries more suitable for inspection than the dependencies list
##
def h5p_dependencies_to_library_list(dependencies):
    library_list = dict()
    for key, dependency in list(dependencies.items()):
        library_list[dependency['machine_name']] = {
            'majorVersion': dependency['major_version'],
            'minorVersion': dependency['minor_version']
        }
    return library_list


##
# Add the necessary assets for content to run in an iframe
##
def h5p_add_iframe_assets(request, integration, content_id, files):
    framework = H5PDjango(request.user)
    core = framework.getCore()

    assets = h5p_add_core_assets()
    integration['core'] = dict()
    integration['core']['scripts'] = assets['js']
    integration['core']['styles'] = assets['css']

    writable = False  # Temporary, future feature
    if writable:
        pass
        # if not os.path.exists(os.path.join(settings.H5P_PATH, 'files')):
        #     os.mkdir(os.path.join(settings.H5P_PATH, 'files'))
        #
        # styles = list()
        # externalStyles = list()
        # for style in files['styles']:
        #     if h5p_is_external_asset(style['path']):
        #         externalStyles.append(style)
        #     else:
        #         styles.append({'data': style['path'], 'type': 'file'})
        # integration['contents']['cid-' + content_id]['styles'] = core.get_assets_urls(externalStyles)
        # integration['contents']['cid-' + content_id]['styles'].append(styles)
    else:
        integration['contents']['cid-' + content_id]['styles'] = core.get_assets_urls(files['styles'])
        # Override Css
        integration['contents']['cid-' + content_id]['styles'].append(OVERRIDE_STYLES)

    if writable:
        pass
        # if not os.path.exists(os.path.join(settings.H5P_PATH, 'files')):
        #     os.mkdir(os.path.join(settings.H5P_PATH, 'files'))
        #
        # scripts = dict()
        # externalScripts = dict()
        # for script in files['scripts']:
        #     if h5p_is_external_asset(script['path']):
        #         externalScripts.append(script)
        #     else:
        #         scripts[script['path']] = list()
        #         scripts[script['path']].append({'data': script['path'], 'type': 'file', 'preprocess': True})
        # integration['contents']['cid-' + content_id]['scripts'] = core.get_assets_urls(externalScripts)
        # integration['contents']['cid-' + content_id]['scripts'].append(scripts)
    else:
        integration['contents']['cid-' + content_id]['scripts'] = core.get_assets_urls(files['scripts'])


##
# Generate embed page to be included in iframe
##
def h5p_embed(request):
    h5p_path = join_url([settings.STATIC_URL, 'h5p/'])
    # The template adds the static URL
    # h5pPath = 'h5p/'
    # core_settings = h5p_get_core_settings(request.user)
    framework = H5PDjango(request.user)

    scripts = list()
    for script in SCRIPTS:
        url = join_url([h5p_path, script])
        scripts.append(url)
    styles = list()
    for style in STYLES:
        url = join_url([h5p_path, style])
        styles.append(url)

    integration = h5p_get_core_settings(request.user)

    content = h5p_get_content(request)

    integration['contents'] = dict()
    integration['contents']["cid-%s" % content['id']] = h5p_get_content_settings(request.user, content)

    core = framework.getCore()
    preloaded_dependencies = core.load_content_dependencies(content['id'])
    files = core.get_dependencies_files(preloaded_dependencies)
    # library_list = h5p_dependencies_to_library_list(preloaded_dependencies)

    scripts = scripts + core.get_assets_urls(files['scripts'])
    styles = styles + core.get_assets_urls(files['styles'])

    return {'h5p': json.dumps(integration), 'scripts': scripts, 'styles': styles, 'lang': settings.H5P_LANGUAGE}


def get_user_score(content_id, user=None, ajax=False):
    if user is not None:
        scores = h5p_points.objects.filter(content_id=content_id, uid=user.id).values('points', 'max_points')
    else:
        scores = h5p_points.objects.filter(content_id=content_id)
        for score in scores:
            score.uid = User.objects.get(id=score.uid).username
            score.has_finished = score.finished >= score.started
            score.points = '..' if score.points is None else score.points
            score.max_points = '..' if score.max_points is None else score.max_points

    if len(scores) > 0:
        if ajax:
            serializer = serializers.get_serializer("json")
            serializer = serializer()
            return serializer.serialize(scores)
        return scores

    return None


def export_score(content_id=None):
    response = ''
    if content_id:
        scores = h5p_points.objects.filter(content_id=content_id)
        content = h5p_contents.objects.get(content_id=content_id)
        response += '[Content] : %s - [Users] : %s\n' % (content.title, len(scores))
        for score in scores:
            score.uid = User.objects.get(id=score.uid).username
            score.has_finished = 'Completed' if score.finished >= score.started else 'Not completed'
            score.points = '..' if score.points is None else score.points
            score.max_points = '..' if score.max_points is None else score.max_points
            response += '[Username] : %s | [Current] : %s | [Max] : %s | [Progression] : %s\n' % (
                score.uid, score.points, score.max_points, score.has_finished)
        return response

    scores = h5p_points.objects.all()
    response += '[Users] : %s\n' % len(scores)
    current_content = ''
    for score in scores:
        content = h5p_contents.objects.get(content_id=score.content_id)
        if content.content_id != current_content:
            response = response + '--------------------\n[Content] : %s\n--------------------\n' % content.title
        score.uid = User.objects.get(id=score.uid).username
        score.has_finished = 'Completed' if score.finished >= score.started else 'Not completed'
        score.points = '..' if score.points is None else score.points
        score.max_points = '..' if score.max_points is None else score.max_points
        response += '[Username] : %s | [Current] : %s | [Max] : %s | [Progression] : %s\n' % (
            score.uid, score.points, score.max_points, score.has_finished)
        current_content = content.content_id
    return response


##
# Uninstall H5P
##


def uninstall():
    if os.path.exists(settings.H5P_STORAGE_ROOT):
        shutil.rmtree(settings.H5P_STORAGE_ROOT)

    h5p_contents_libraries.objects.all().delete()
    h5p_libraries.objects.all().delete()
    h5p_libraries_libraries.objects.all().delete()
    h5p_libraries_languages.objects.all().delete()
    h5p_contents.objects.all().delete()
    h5p_points.objects.all().delete()
    h5p_content_user_data.objects.all().delete()
    h5p_events.objects.all().delete()
    h5p_counters.objects.all().delete()

    return 'H5PP is now uninstalled. Don\'t forget to clean your settings.py and run "pip uninstall H5PP".'


##
# Get a new H5P security token for the given action
##


def create_token(action):
    time_factor = get_time_factor()
    h = hashlib.new('md5')
    md5_string = "{}{}{}".format(action, str(time_factor), str(uuid.uuid1()))
    h.update(md5_string.encode("UTF-8"))
    return h.hexdigest()


##
# Create a time based number which is unique for each 12 hour.
##


def get_time_factor():
    return math.ceil(int(time.time()) / (86400 / 2))


##
# Checks to see if the path is external
##


def h5p_is_external_asset(path):
    # TODO Use urllib...
    return True if re.search('(?i)^[a-z0-9]+://', path) else False


##
# Writes library data as string on the form {machineName} {majorVersion}.{minorVersion}
##


def library_to_string(library, folder_name=False):
    return str(
        library["machineName"] if 'machineName' in library else library['name'] + ("-" if folder_name else " ") + str(
            library["majorVersion"]) + "." + str(library["minorVersion"]))


##
# Returns all rows from a cursor as a dict
##
# TODO Remove seemingly unused method
# def dictfetchall(self, cursor):
#     desc = cursor.description
#     return [dict(list(zip([col[0] for col in desc], row))) for row in cursor.fetchall()]
