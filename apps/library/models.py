from django.db import models
from apps.core.models import Tenant, TenantManager
from apps.students.models import Student
from django.conf import settings

class BookCategory(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'book_categories'

    def __str__(self):
        return self.name

class Book(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    isbn = models.CharField(max_length=20, blank=True)
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=200)
    publisher = models.CharField(max_length=200, blank=True)
    category = models.ForeignKey(BookCategory, on_delete=models.SET_NULL, null=True, blank=True)
    edition = models.CharField(max_length=50, blank=True)
    year_published = models.IntegerField(null=True, blank=True)
    total_copies = models.IntegerField(default=1)
    available_copies = models.IntegerField(default=1)
    location = models.CharField(max_length=100, blank=True, help_text='Shelf/rack location')
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'books'
        ordering = ['title']

    def __str__(self):
        return f"{self.title} by {self.author}"

class BorrowRecord(models.Model):
    STATUS_CHOICES = [
        ('borrowed', 'Borrowed'), ('returned', 'Returned'), ('overdue', 'Overdue'), ('lost', 'Lost'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='borrow_records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='borrow_records')
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='issued_books')
    borrow_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='borrowed')
    fine_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    fine_paid = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'borrow_records'
        ordering = ['-borrow_date']

    def __str__(self):
        return f"{self.student} — {self.book.title} ({self.status})"

    def save(self, *args, **kwargs):
        if self.return_date and self.due_date and self.return_date > self.due_date:
            days_late = (self.return_date - self.due_date).days
            self.fine_amount = days_late * 500  # 500 UGX per day
            self.status = 'returned'
        elif not self.return_date:
            from django.utils import timezone
            if timezone.now().date() > self.due_date:
                self.status = 'overdue'
                days_late = (timezone.now().date() - self.due_date).days
                self.fine_amount = days_late * 500
        super().save(*args, **kwargs)

class BookReservation(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reservations')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reservations')
    reserved_at = models.DateTimeField(auto_now_add=True)
    is_fulfilled = models.BooleanField(default=False)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'book_reservations'

    def __str__(self):
        return f"{self.student} reserved {self.book.title}"
