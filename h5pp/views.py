from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.base import ContentFile
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (FormView, CreateView, TemplateView)

from .forms import LibrariesForm, CreateForm
from .models import h5p_libraries, h5p_contents, h5p_content_user_data, h5p_points
from h5pp.h5p.h5pmodule import (include_h5p, h5p_set_started, h5p_set_finished, h5p_get_content_id,
                                h5p_get_list_content, h5p_load, h5p_delete, h5p_embed, get_user_score,
                                uninstall, export_score)
from h5pp.h5p.h5pclasses import H5PDjango
from h5pp.h5p.editor.h5peditormodule import (h5peditorContent, handleContentUserData)
from h5pp.h5p.editor.library.h5peditorfile import H5PEditorFile


def librariesView(request):
    if request.user.is_authenticated and request.user.is_superuser:
        libraries = h5p_libraries.objects.all()
        if request.method == 'POST':
            form = LibrariesForm(request.user, request.POST, request.FILES)
            if form.is_valid():
                if 'h5p' in request.FILES and request.FILES['h5p'] is not None:
                    return render(request, 'h5p/libraries.html',
                                  {'form': form, 'libraries': libraries, 'status': 'Upload complete'})
                elif 'download' in request.POST:
                    return render(request, 'h5p/libraries.html',
                                  {'form': form, 'libraries': libraries, 'status': 'Update complete'})
                else:
                    status = uninstall()
                    return render(request, 'h5p/libraries.html',
                                  {'form': form, 'libraries': libraries, 'status': status})
            return render(request, 'h5p/libraries.html', {'form': form, 'libraries': libraries})

        form = LibrariesForm(request.user)
        return render(request, 'h5p/libraries.html', {'form': form, 'libraries': libraries})

    return HttpResponseRedirect('/h5p/login/?next=/h5p/libraries/')


class CreateContentView(CreateView):
    template_name = "h5p/create.html"
    success_url = "h5pcontent"
    form_class = CreateForm

    def get_form_kwargs(self):
        kwargs = {'request': self.request, }
        return kwargs

    def get_success_url(self, pk):
        return reverse("h5pp:h5pcontent", args=[pk])

    def get_context_data(self, **kwargs):
        """
        Get the editor for the template

        """
        ctx = super(CreateContentView, self).get_context_data(**kwargs)
        ctx["data"] = h5peditorContent(self.request.user,
                                       self.request.GET.get('content_id', None),
                                       self.request.GET.get('title', None),
                                       self.request.GET.get('json_content', None),
                                       self.request.GET.get('language', None),
                                       self.request.GET.get('main_library', None),
                                       self.request.GET.get('filtered', None),
                                       self.request.GET.get('slug', None),
                                       )

        return ctx

    def post(self, request, *args, **kwargs):
        form = CreateForm(self.request, self.request.POST, self.request.FILES)
        if form.is_valid():
            return self.form_valid(form)
        else:
            # TODO Somewhere around here sanitation is neglected or performed badly. On the editor page, I was able
            # to upload a simple DOC file and have h5pp try to interpret it as a .h5p file
            return self.form_invalid(form)

    def form_valid(self, form):
        # this is hacky and needs to be corrected in the form.
        new_id = h5p_contents.objects.all().order_by('-content_id')[0]

        return HttpResponseRedirect(self.get_success_url(str(new_id.content_id)))

# TODO Remove unused class after verification
# class UpdateContentView(FormView):
#     template_name = "h5p/create.html"
#     success_url = "h5pcontent"
#     form_class = CreateForm
#
#     def get_form_kwargs(self):
#         framework = H5PDjango(self.request.user)
#         edit = framework.loadContent(self.kwargs.get("content_id"))
#         self.request.GET = self.request.GET.copy()
#         self.request.GET['contentId'] = self.kwargs.get("content_id")
#         self.request.GET["title"] = edit["title"]
#         self.request.GET["language"] = "en"
#         self.request.GET["filtered"] = edit['filtered']
#         self.request.GET['json_content'] = edit['params']
#         self.request.GET['h5p_slug'] = edit['slug']
#         self.request.GET['h5p_library'] = edit['library_name'] + ' ' + str(edit['library_major_version']) + '.' + str(
#             edit['library_minor_version'])
#         # self.request.GET['main_library'] = self.request.GET["h5p_library"]
#
#         kwargs = {'request': self.request, }
#         return kwargs
#
#     def get_success_url(self, pk):
#         return reverse("h5pcontent", args=[pk])
#
#     def get_context_data(self, **kwargs):
#         """
#         Get the editor for the template
#
#         """
#         ctx = super(UpdateContentView, self).get_context_data(**kwargs)
#         ctx["data"] = h5peditorContent(self.request)
#
#         return ctx
#
#     def post(self, request, *args, **kwargs):
#         form = CreateForm(self.request, self.request.POST, self.request.FILES)
#         if form.is_valid():
#             return self.form_valid(form)
#         else:
#             return self.form_invalid(form)
#
#     def form_valid(self, form):
#         return HttpResponseRedirect(self.get_success_url(self.pk_url_kwarg))


def createView(request, content_id=None):
    if request.user.is_authenticated:
        editor = h5peditorContent(request.user, content_id, request.GET.get('title', None))

        if request.method == 'POST':
            if content_id is not None:
                request.POST = request.POST.copy()
                request.POST['contentId'] = content_id
            form = CreateForm(request, request.POST, request.FILES)
            if form.is_valid():
                if content_id is not None:
                    return HttpResponseRedirect(reverse("h5pp:h5pcontent", args=[content_id]))
                else:
                    new_id = h5p_contents.objects.all().order_by('-content_id')[0]
                    return HttpResponseRedirect(reverse("h5pp:h5pcontent", args=[new_id.content_id]))
            return render(request, 'h5p/create.html', {'form': form, 'data': editor})

        else:
            framework = H5PDjango(request.user)
            edit = framework.loadContent(content_id)
            request.GET = request.GET.copy()
            request.GET['contentId'] = content_id
            request.GET['json_content'] = edit['params']
            request.GET['h5p_library'] = edit['library_name'] + ' ' + str(edit['library_major_version']) + '.' + str(
                edit['library_minor_version'])

        form = CreateForm(request)

        return render(request, 'h5p/create.html', {'form': form, 'data': editor})

    return HttpResponseRedirect('/h5p/login/?next=/h5p/create/')


class ContentDetailView(TemplateView):
    template_name = "h5p/content.html"

    def get_context_data(self, **kwargs):
        ctx = super(ContentDetailView, self).get_context_data(**kwargs)

        self.request.GET = self.request.GET.copy()
        self.request.GET["contentId"] = self.kwargs.get("content_id")
        h5p_load(self.request)
        content = include_h5p(self.request)
        h5p_set_started(self.request.user, self.kwargs.get("content_id"))
        score = get_user_score(self.kwargs.get("content_id"), self.request.user)

        if "html" not in content:
            ctx["html"] = "<div>Sorry, preview of H5P content is not yet available.</div>"
        else:
            ctx["html"] = content["html"]

        ctx["html"] = content["html"]
        ctx["data"] = content["data"]
        ctx["score"] = score[0] if score is not None else None
        ctx["content_id"] = self.kwargs.get("content_id")

        return ctx


def contentsView(request):
    if 'contentId' in request.GET:
        try:
            owner = h5p_contents.objects.get(content_id=h5p_get_content_id(request))
        except:
            raise Http404
        h5p_load(request)
        content = include_h5p(request)

        if "html" not in content:
            html = '<div>Sorry, preview of H5P content is not yet available.</div>'
            return render(request, 'h5p/content.html', {'html': html})
        else:
            if request.user.is_authenticated():
                h5p_set_started(request.user, h5p_get_content_id(request))
                score = get_user_score(h5p_get_content_id(request), request.user)

                return render(request, 'h5p/content.html',
                              {'html': content['html'], 'data': content['data'], 'owner': owner.author,
                               'score': score[0]})
            return render(request, 'h5p/content.html',
                          {'html': content['html'], 'data': content['data'], 'owner': owner.author})

    return HttpResponseRedirect('/h5p/listContents')


def listView(request):
    if request.method == 'POST':
        if request.user.is_superuser and 'contentId' in request.POST:
            h5p_delete(request)
            return HttpResponseRedirect('/h5p/listContents')
        return render(request, 'h5p/listContents.html',
                      {'status': 'You do not have the necessary rights to delete a video.'})

    list_content = h5p_get_list_content(request)
    if list_content and len(list_content) > 0:
        return render(request, 'h5p/listContents.html', {'listContent': list_content})

    return render(request, 'h5p/listContents.html', {'status': 'No contents installed.'})


def scoreView(request, content_id):
    try:
        content = h5p_contents.objects.get(content_id=content_id)
    except:
        raise Http404
    if request.user.is_authenticated:
        if request.method == 'POST' and (request.user.username == content.author or request.user.is_superuser):
            user_data = h5p_content_user_data.objects.filter(content_main_id=content.content_id)
            if user_data:
                user_data.delete()
            user_points = h5p_points.objects.filter(content_id=content.content_id)
            if user_points:
                user_points.delete()

            return HttpResponseRedirect('/h5p/score/%s' % content.content_id, {'status': "Scores has been reset !"})

        if 'user' in request.GET and (request.user.username == content.author or request.user.is_superuser):
            user = User.objects.get(username=request.GET['user'])
            user_data = h5p_content_user_data.objects.filter(user_id=user.id, content_main_id=content.content_id)
            if user_data:
                user_data.delete()
            user_points = h5p_points.objects.filter(uid=user.id, content_id=content.content_id)
            if user_points:
                user_points.delete()

            return HttpResponseRedirect('/h5p/score/%s' % content.content_id,
                                        {'status': "%s's score has been reset !" % user.username})

        if 'download' in request.GET and request.user.is_superuser:
            if request.GET['download'] == 'all':
                scores = export_score()
                scores = ContentFile(scores)
                response = HttpResponse(scores, 'text/plain')
                response['Content-Length'] = scores.size
                response['Content-Disposition'] = 'attachment; filename="h5pp_users_score.txt"'
            else:
                scores = export_score(request.GET['download'])
                scores = ContentFile(scores)
                response = HttpResponse(scores, 'text/plain')
                response['Content-Length'] = scores.size
                response['Content-Disposition'] = 'attachment; filename="content_%s_users_score.txt"' % request.GET[
                    'download']

            return response

        list_score = dict()
        if request.user.username == content.author or request.user.is_superuser:
            list_score['owner'] = True

        list_score['data'] = get_user_score(content.content_id)
        if list_score['data'] and list_score['data'].count() > 0:
            return render(request, 'h5p/score.html', {'listScore': list_score, 'content': content})

        return render(request, 'h5p/score.html', {'status': 'No score available yet.', 'content': content})

    return HttpResponseRedirect('/h5p/login/?next=/h5p/score/' + content_id + '/')


def embedView(request):
    if 'contentId' in request.GET:
        h5p_load(request)
        embed = h5p_embed(request)
        score = None
        if request.user.is_authenticated:
            h5p_set_started(request.user, h5p_get_content_id(request))
            score = get_user_score(request.GET['contentId'], request.user)[0]
        return render(request, 'h5p/embed.html', {'embed': embed, 'score': score})

    return HttpResponseForbidden()


@csrf_exempt
def editorAjax(request, content_id):
    data = None
    if request.method == 'POST':
        if 'libraries' in request.GET:
            framework = H5PDjango(request.user)
            editor = framework.getEditor()
            data = editor.getLibraries(request)
            return HttpResponse(data, content_type='application/json')
        elif 'file' in request.FILES:
            framework = H5PDjango(request.user)
            f = H5PEditorFile(request, request.FILES, framework)
            if not f.isLoaded():
                return HttpResponse('File Not Found', content_type='application/json')

            if f.validate():
                core = framework.getCore()
                core.fs.save_file(f, request.POST['contentId'])

            data = f.printResult()
            return HttpResponse(data, content_type='application/json')
        return HttpResponseRedirect('h5p/')
    if 'libraries' in request.GET:
        name = request.GET['machineName'] if 'machineName' in request.GET else ''
        major = request.GET['majorVersion'] if 'majorVersion' in request.GET else 0
        minor = request.GET['minorVersion'] if 'minorVersion' in request.GET else 0

        framework = H5PDjango(request.user)
        editor = framework.getEditor()
        if name != '':
            data = editor.getLibraryData(name, major, minor, settings.H5P_LANGUAGE)
            return HttpResponse(data, content_type='application/json')
        else:
            data = editor.getLibraries(request)
            return HttpResponse(data, content_type='application/json')

    return HttpResponse(data, content_type='application/json')


@csrf_exempt
def ajax(request):
    if request.method == 'POST':
        if 'content-user-data' in request.GET:
            data = handleContentUserData(request)
            return HttpResponse(data, content_type='application/json')

        elif 'setFinished' in request.GET:
            data = h5p_set_finished(request)
            return HttpResponse(data, content_type='application/json')

    if 'content-user-data' in request.GET:
        data = handleContentUserData(request)
        return HttpResponse(data, content_type='application/json')

    elif 'user-scores' in request.GET:
        score = get_user_score(request.GET['user-scores'], None, True)
        return HttpResponse(score, content_type='application/json')
    return HttpResponseRedirect('/h5p/create')
