from django.contrib import admin
from .models import MenuItem, WeeklyMenu, MealAccount, MealTransaction
@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name',)
@admin.register(WeeklyMenu)
class WeeklyMenuAdmin(admin.ModelAdmin):
    list_display = ('week_start_date', 'day', 'published')
    list_filter = ('published',)
    filter_horizontal = ('items',)
@admin.register(MealAccount)
class MealAccountAdmin(admin.ModelAdmin):
    list_display = ('student', 'balance', 'is_active', 'allow_overdraft')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    readonly_fields = ('balance',)
@admin.register(MealTransaction)
class MealTransactionAdmin(admin.ModelAdmin):
    list_display = ('meal_account', 'transaction_type', 'amount', 'method', 'created_at')
    list_filter = ('transaction_type', 'method')
    readonly_fields = ('balance_after', 'created_at')
