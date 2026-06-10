
from django.contrib import admin
from .models import Book, BorrowRecord, BookCategory, BookReservation

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'total_copies', 'available_copies', 'tenant']
    search_fields = ['title', 'author', 'isbn']

@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ['book', 'student', 'borrow_date', 'due_date', 'status', 'fine_amount']
    list_filter = ['status', 'tenant']

admin.site.register(BookCategory)
admin.site.register(BookReservation)
