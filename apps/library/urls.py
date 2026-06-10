from django.urls import path
from . import views

urlpatterns = [
    path('',                       views.book_list,   name='book_list'),
    path('add/',                   views.book_create, name='book_create'),
    path('<int:pk>/',              views.book_detail, name='book_detail'),
    path('borrow/',                views.borrow_book, name='borrow_book'),
    path('return/<int:record_id>/',views.return_book, name='return_book'),
    path('loans/',                 views.borrow_list, name='borrow_list'),
]
