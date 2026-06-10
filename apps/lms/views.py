from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.lms.models import LessonPlan, LMSResource, Quiz, QuizQuestion, QuizOption
from apps.academics.models import ClassSubject


@login_required
def lms_dashboard(request):
    class_subjects = ClassSubject.objects.select_related("classroom", "subject", "teacher").all()
    return render(request, "lms/dashboard.html", {"class_subjects": class_subjects})


@login_required
def resource_list(request, class_subject_id=None):
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    resources = LMSResource.objects.select_related("class_subject").all()
    selected_cs = None
    if class_subject_id:
        selected_cs = get_object_or_404(ClassSubject.objects, pk=class_subject_id, tenant=request.tenant)
        resources = resources.filter(class_subject=selected_cs)
    return render(request, "lms/resource_list.html", {
        "resources": resources, "class_subjects": class_subjects, "selected_cs": selected_cs,
    })


@login_required
def resource_create(request):
    if request.method == "POST":
        cs = ClassSubject.objects.get(pk=request.POST.get("class_subject"))
        LMSResource.objects.create(
            tenant=request.tenant,
            class_subject=cs,
            title=request.POST.get("title"),
            description=request.POST.get("description", ""),
            resource_type=request.POST.get("resource_type", "document"),
            external_url=request.POST.get("external_url", ""),
            week_number=int(request.POST.get("week_number")) if request.POST.get("week_number") else None,
            uploaded_by=request.user,
            file=request.FILES.get("file"),
        )
        messages.success(request, "Resource uploaded.")
        return redirect("resource_list")
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "lms/resource_form.html", {
        "class_subjects": class_subjects, "resource_types": LMSResource.RESOURCE_TYPES,
    })


@login_required
def lesson_plan_list(request):
    plans = LessonPlan.objects.select_related(
        "class_subject__classroom", "class_subject__subject"
    ).all()
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "lms/lesson_plan_list.html", {
        "plans": plans, "class_subjects": class_subjects,
    })


@login_required
def lesson_plan_create(request):
    if request.method == "POST":
        cs = ClassSubject.objects.get(pk=request.POST.get("class_subject"))
        LessonPlan.objects.create(
            tenant=request.tenant,
            class_subject=cs,
            title=request.POST.get("title"),
            week_number=int(request.POST.get("week_number", 1)),
            lesson_number=int(request.POST.get("lesson_number", 1)),
            objectives=request.POST.get("objectives", ""),
            content=request.POST.get("content", ""),
            activities=request.POST.get("activities", ""),
            resources_needed=request.POST.get("resources_needed", ""),
        )
        messages.success(request, "Lesson plan created.")
        return redirect("lesson_plan_list")
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "lms/lesson_plan_form.html", {"class_subjects": class_subjects})


@login_required
def quiz_list(request):
    quizzes = Quiz.objects.select_related(
        "class_subject__classroom", "class_subject__subject"
    ).all()
    return render(request, "lms/quiz_list.html", {"quizzes": quizzes})


@login_required
def quiz_create(request):
    if request.method == "POST":
        cs = ClassSubject.objects.get(pk=request.POST.get("class_subject"))
        quiz = Quiz.objects.create(
            tenant=request.tenant,
            class_subject=cs,
            title=request.POST.get("title"),
            description=request.POST.get("description", ""),
            duration_minutes=int(request.POST.get("duration_minutes", 30)),
            max_attempts=int(request.POST.get("max_attempts", 1)),
            shuffle_questions=bool(request.POST.get("shuffle_questions")),
            created_by=request.user,
        )
        messages.success(request, f'Quiz "{quiz.title}" created.')
        return redirect("quiz_add_questions", quiz_id=quiz.pk)
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "lms/quiz_form.html", {"class_subjects": class_subjects})


@login_required
def quiz_add_questions(request, quiz_id):
    quiz = get_object_or_404(Quiz.objects, pk=quiz_id, tenant=request.tenant)
    if request.method == "POST":
        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text=request.POST.get("question_text"),
            question_type=request.POST.get("question_type", "mcq"),
            marks=float(request.POST.get("marks", 1)),
            order=quiz.questions.count() + 1,
        )
        q_type = request.POST.get("question_type", "mcq")
        if q_type == "mcq":
            for i in range(1, 5):
                opt = request.POST.get(f"option_{i}", "").strip()
                if opt:
                    QuizOption.objects.create(
                        question=question,
                        option_text=opt,
                        is_correct=(request.POST.get("correct_option") == str(i)),
                    )
        elif q_type == "true_false":
            correct = request.POST.get("tf_answer", "True")
            QuizOption.objects.create(question=question, option_text="True", is_correct=(correct == "True"))
            QuizOption.objects.create(question=question, option_text="False", is_correct=(correct == "False"))
        messages.success(request, "Question added.")
        return redirect("quiz_add_questions", quiz_id=quiz_id)
    questions = quiz.questions.prefetch_related("options").all()
    return render(request, "lms/quiz_questions.html", {"quiz": quiz, "questions": questions})


@login_required
def quiz_publish(request, quiz_id):
    quiz = get_object_or_404(Quiz.objects, pk=quiz_id, tenant=request.tenant)
    quiz.is_published = True
    quiz.save()
    messages.success(request, f'Quiz "{quiz.title}" is now live.')
    return redirect("quiz_list")
