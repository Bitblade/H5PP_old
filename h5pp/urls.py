from django.conf.urls import url
from django.urls import path, include
from django.views.generic import TemplateView

from .views import (librariesView, CreateContentView, ContentDetailView, contentsView,
                    createView, editorAjax, listView, ajax, scoreView, embedView)

app_name = 'h5pp'
urlpatterns = [  # Base
    url(r'^home/$', TemplateView.as_view(template_name="h5p/home.html"), name="h5phome"),

    # Contents and Libraries
    url(r'^libraries/$', librariesView, name="h5plibraries"),
    url(r'^listContents/$', listView, name="h5plistContents"),
    url(r'^content/$', contentsView, name='h5pcontent'),
    # url(r'^content/(?P<content_id>\d+)/$', login_required(ContentDetailView.as_view()), name="h5pcontent"),
    url(r'^content/(?P<content_id>\d+)/$', ContentDetailView.as_view(), name="h5pcontent"),

    # Contents creation / upload
    # url(r'^create/$', login_required(CreateContentView.as_view()), name="h5pcreate"),
    url(r'^create/$', CreateContentView.as_view(), name="h5pcreate"),
    # url(r'^update/(?P<content_id>\d+)/$', login_required(UpdateContentView.as_view()), name="h5pedit"),
    url(r'^create/(?P<content_id>\d+)/$', createView, name='h5pedit'),

    # Users score
    url(r'^score/(?P<content_id>\d+)/$', scoreView, name='h5pscore'),  # Embed page
    url(r'^embed/$', embedView, name='h5pembed'),

    # Ajax
    url(r'^ajax/$', ajax, name="h5pajax"), url(r'^editorajax/(?P<content_id>\d+)/$', editorAjax, name="h5peditorAjax"),

    path('accounts/', include('django.contrib.auth.urls'))]
