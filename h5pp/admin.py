from django.contrib import admin
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views import View

from h5pp.forms import CreateForm
from h5pp.h5p.editor.h5peditormodule import h5peditorContent
from h5pp.h5p.h5pclasses import H5PDjango
from h5pp.models import *


class LibrariesAdmin(admin.ModelAdmin):
    list_display = ('title', 'library_id')
    ordering = ('title', 'library_id')
    readonly_fields = ('library_id', 'major_version', 'minor_version', 'patch_version')
    exclude = ('restricted', 'runnable')


admin.site.register(h5p_libraries, LibrariesAdmin)


class LibrariesLanguageAdmin(admin.ModelAdmin):
    list_display = ('library_id', 'language_code')
    ordering = ('library_id', 'language_code')
    readonly_fields = ('library_id',)


admin.site.register(h5p_libraries_languages, LibrariesLanguageAdmin)


class ContentsAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'content_type')
    ordering = ('title', 'author')
    readonly_fields = ('content_id', 'main_library_id')
    exclude = ('disable',)
    change_form_template = 'h5p/create_admin.html'

    def add_view(self, request, form_url='', extra_context=None):
        content_id = request.GET.get('contentId', None)

        if request.method == 'POST':
            editor = h5peditorContent(request.user, content_id, request.GET.get('title', None))

            request.POST = request.POST.copy()
            form = CreateForm(request, request.POST, request.FILES)
            if form.is_valid():
                if content_id is not None:
                    return HttpResponseRedirect(reverse("h5pp:h5pcontent", args=[content_id]))
                else:
                    new_id = h5p_contents.objects.all().order_by('-content_id')[0]
                    return HttpResponseRedirect(reverse("h5pp:h5pcontent", args=[new_id.content_id]))

            return render(request, 'h5p/create_admin.html', {'form': form, 'data': editor})

        editor = h5peditorContent(request.user, content_id, None)
        request.GET = request.GET.copy()
        request.GET['contentId'] = content_id
        # request.GET['h5p_library'] = edit['library_name'] + ' ' + str(edit['library_major_version']) + '.' + str(
        #     edit['library_minor_version'])

        form = CreateForm(request)

        # TODO Pass extra_context?
        return super(ContentsAdmin, self).add_view(request, form_url, {'form': form, 'data': editor})


    def change_view(self, request, object_id, form_url='', extra_context=None):
        if request.method == 'POST':
            editor = h5peditorContent(request.user, object_id, request.GET.get('title', None))

            request.POST = request.POST.copy()
            request.POST['contentId'] = object_id
            form = CreateForm(request, request.POST, request.FILES)
            if form.is_valid():
                return HttpResponseRedirect(reverse("h5pp:h5pcontent", args=[object_id]))

            return render(request, 'h5p/create_admin.html', {'form': form, 'data': editor})

        framework = H5PDjango(request.user)
        edit = framework.loadContent(object_id)
        editor = h5peditorContent(request.user, object_id, edit['title'])
        request.GET = request.GET.copy()
        request.GET['title'] = edit['title']
        request.GET['contentId'] = object_id
        request.GET['json_content'] = edit['params']
        request.GET['h5p_library'] = edit['library_name'] + ' ' + str(edit['library_major_version']) + '.' + str(
            edit['library_minor_version'])

        form = CreateForm(request)

        # TODO Pass extra_context?
        return super(ContentsAdmin, self).change_view(request, object_id, form_url, {'form': form, 'data': editor})


admin.site.register(h5p_contents, ContentsAdmin)


class PointsAdmin(admin.ModelAdmin):
    list_display = ('content_id', 'uid', 'points', 'max_points')
    ordering = ('content_id', 'uid')
    readonly_fields = ('content_id', 'uid')
    exclude = ('started', 'finished')


admin.site.register(h5p_points, PointsAdmin)


class EventsAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'type', 'sub_type')
    ordering = ('type', 'sub_type')
    readonly_fields = (
        'user_id', 'created_at', 'type', 'sub_type', 'content_id', 'content_title', 'library_name', 'library_version'
    )


admin.site.register(h5p_events, EventsAdmin)


class ContentUserDataAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'content_main_id', 'data_id', 'data')
    # change_form_template = 'admin/h5p/change_form.html'

    # def change_view(self, request, object_id, form_url='', extra_context=None):
    #     super().change_view(request, object_id, form_url, extra_context)



admin.site.register(h5p_content_user_data, ContentUserDataAdmin)

# from django.conf.urls import url
# from django.contrib import admin
#
#
# class CustomAdminSite(admin.AdminSite):
#
#     def get_urls(self):
#         urls = super(CustomAdminSite, self).get_urls()
#         custom_urls = [
#             url(r'a$', self.admin_view(testView), name="preview"),
#         ]
#         return urls + custom_urls
#
# def testView(request):
#     return HttpResponse('You did something good!')
