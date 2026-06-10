from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.staff_hr.models import StaffProfile, LeaveRequest, LeaveType, CPDRecord
from apps.academics.models import Department

User = get_user_model()


@login_required
def staff_list(request):
    staff = StaffProfile.objects.select_related("user", "department").filter(is_active=True)
    return render(request, "staff_hr/staff_list.html", {"staff": staff})


@login_required
def staff_detail(request, pk):
    staff = get_object_or_404(StaffProfile.objects, pk=pk, tenant=request.tenant)
    leaves = staff.leave_requests.all()[:10]
    cpd = staff.cpd_records.all()[:10]
    return render(request, "staff_hr/staff_detail.html", {
        "staff": staff, "leaves": leaves, "cpd": cpd,
    })


@login_required
def staff_create(request):
    if request.method == "POST":
        try:
            user = User.objects.create_user(
                username=request.POST.get("username"),
                password=request.POST.get("password", "Staff@2025"),
                first_name=request.POST.get("first_name"),
                last_name=request.POST.get("last_name"),
                email=request.POST.get("email", ""),
                role=request.POST.get("role", "teacher"),
                tenant=request.tenant,
            )
            dept_id = request.POST.get("department")
            StaffProfile.objects.create(
                tenant=request.tenant,
                user=user,
                staff_no=request.POST.get("staff_no", ""),
                department=Department.objects.get(pk=dept_id) if dept_id else None,
                designation=request.POST.get("designation", ""),
                employment_type=request.POST.get("employment_type", "permanent"),
                date_joined=request.POST.get("date_joined") or None,
            )
            messages.success(request, f"Staff member {user.get_full_name()} added.")
            return redirect("staff_list")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    departments = Department.objects.all()
    role_choices = [
        ("principal", "Principal"), ("teacher", "Teacher"),
        ("accountant", "Accountant"), ("counsellor", "Counsellor"),
        ("librarian", "Librarian"), ("receptionist", "Receptionist"),
        ("nurse", "Nurse"),
    ]
    return render(request, "staff_hr/staff_form.html", {
        "departments": departments, "roles": role_choices,
    })


@login_required
def leave_list(request):
    leaves = LeaveRequest.objects.select_related(
        "staff__user", "leave_type"
    ).order_by("-applied_at")
    leave_types = LeaveType.objects.all()
    return render(request, "staff_hr/leave_list.html", {
        "leaves": leaves, "leave_types": leave_types,
    })


@login_required
def leave_apply(request):
    if request.method == "POST":
        try:
            staff = StaffProfile.objects.get(user=request.user, tenant=request.tenant)
        except StaffProfile.DoesNotExist:
            messages.error(request, "Your staff profile was not found.")
            return redirect("leave_list")
        leave_type = LeaveType.objects.get(pk=request.POST.get("leave_type"))
        LeaveRequest.objects.create(
            tenant=request.tenant,
            staff=staff,
            leave_type=leave_type,
            start_date=request.POST.get("start_date"),
            end_date=request.POST.get("end_date"),
            reason=request.POST.get("reason"),
        )
        messages.success(request, "Leave application submitted.")
        return redirect("leave_list")
    leave_types = LeaveType.objects.all()
    return render(request, "staff_hr/leave_form.html", {"leave_types": leave_types})


@login_required
def leave_action(request, pk, action):
    leave = get_object_or_404(LeaveRequest.objects, pk=pk, tenant=request.tenant)
    if action == "approve":
        leave.status = "approved"
        leave.approved_by = request.user
        leave.approved_at = timezone.now()
        leave.save()
        messages.success(request, f"Leave approved for {leave.staff.user.get_full_name()}.")
    elif action == "reject":
        leave.status = "rejected"
        leave.rejection_reason = request.POST.get("reason", "")
        leave.save()
        messages.warning(request, "Leave rejected.")
    return redirect("leave_list")


@login_required
def cpd_list(request):
    records = CPDRecord.objects.select_related("staff__user").order_by("-start_date")
    return render(request, "staff_hr/cpd_list.html", {"records": records})


@login_required
def cpd_create(request):
    if request.method == "POST":
        try:
            staff = StaffProfile.objects.get(pk=request.POST.get("staff"))
        except StaffProfile.DoesNotExist:
            messages.error(request, "Staff not found.")
            return redirect("cpd_list")
        CPDRecord.objects.create(
            tenant=request.tenant,
            staff=staff,
            title=request.POST.get("title"),
            institution=request.POST.get("institution", ""),
            cpd_type=request.POST.get("cpd_type", "workshop"),
            start_date=request.POST.get("start_date"),
            end_date=request.POST.get("end_date") or None,
            hours=float(request.POST.get("hours", 0)),
            notes=request.POST.get("notes", ""),
        )
        messages.success(request, "CPD record added.")
        return redirect("cpd_list")
    all_staff = StaffProfile.objects.select_related("user").filter(is_active=True)
    return render(request, "staff_hr/cpd_form.html", {
        "all_staff": all_staff,
        "cpd_types": CPDRecord._meta.get_field("cpd_type").choices,
    })
