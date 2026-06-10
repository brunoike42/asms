from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.library.models import Book, BorrowRecord, BookCategory
from apps.students.models import Student


@login_required
def book_list(request):
    q = request.GET.get("q", "")
    category_id = request.GET.get("category", "")
    books = Book.objects.select_related("category")
    if q:
        books = books.filter(title__icontains=q) | books.filter(author__icontains=q)
    if category_id:
        books = books.filter(category_id=category_id)
    categories = BookCategory.objects.all()
    return render(request, "library/book_list.html", {
        "books": books, "categories": categories, "q": q,
    })


@login_required
def book_create(request):
    if request.method == "POST":
        category_id = request.POST.get("category")
        Book.objects.create(
            tenant=request.tenant,
            isbn=request.POST.get("isbn", ""),
            title=request.POST.get("title"),
            author=request.POST.get("author"),
            publisher=request.POST.get("publisher", ""),
            category=BookCategory.objects.get(pk=category_id) if category_id else None,
            edition=request.POST.get("edition", ""),
            year_published=int(request.POST.get("year_published")) if request.POST.get("year_published") else None,
            total_copies=int(request.POST.get("total_copies", 1)),
            available_copies=int(request.POST.get("total_copies", 1)),
            location=request.POST.get("location", ""),
            description=request.POST.get("description", ""),
        )
        messages.success(request, "Book added to catalogue.")
        return redirect("book_list")
    categories = BookCategory.objects.all()
    return render(request, "library/book_form.html", {"categories": categories})


@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book.objects, pk=pk, tenant=request.tenant)
    borrows = BorrowRecord.objects.filter(book=book).select_related("student")[:10]
    return render(request, "library/book_detail.html", {"book": book, "borrows": borrows})


@login_required
def borrow_book(request):
    if request.method == "POST":
        book = get_object_or_404(Book.objects, pk=request.POST.get("book"), tenant=request.tenant)
        student = get_object_or_404(Student.objects, pk=request.POST.get("student"), tenant=request.tenant)
        if book.available_copies <= 0:
            messages.error(request, "No copies available.")
            return redirect("borrow_list")
        from datetime import timedelta, date
        due = date.today() + timedelta(days=int(request.POST.get("days", 14)))
        BorrowRecord.objects.create(
            tenant=request.tenant, book=book,
            student=student, due_date=due, issued_by=request.user,
        )
        book.available_copies -= 1
        book.save()
        messages.success(request, f'"{book.title}" issued to {student.full_name}. Due: {due}')
        return redirect("borrow_list")
    books = Book.objects.filter(available_copies__gt=0)
    students = Student.objects.filter(status="active")
    return render(request, "library/borrow_form.html", {"books": books, "students": students})


@login_required
def return_book(request, record_id):
    record = get_object_or_404(BorrowRecord.objects, pk=record_id, tenant=request.tenant)
    from datetime import date
    record.return_date = date.today()
    record.save()
    record.book.available_copies += 1
    record.book.save()
    if record.fine_amount > 0:
        messages.warning(request, f"Returned. Fine: UGX {record.fine_amount:,.0f}")
    else:
        messages.success(request, "Book returned. No fines.")
    return redirect("borrow_list")


@login_required
def borrow_list(request):
    records = BorrowRecord.objects.select_related("book", "student").order_by("-borrow_date")
    overdue = BorrowRecord.objects.filter(status="overdue").count()
    return render(request, "library/borrow_list.html", {"records": records, "overdue": overdue})
