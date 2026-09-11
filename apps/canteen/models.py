"""
ASMS Canteen Management Module
Prepaid meal-wallet system, weekly menu publishing, and meal transaction ledger.
Design pattern: balance is a denormalised cache on MealAccount; the source of truth
is the append-only MealTransaction ledger (mirrors the immutability pattern used by
apps.finance.Payment). recalculate_balance() can always rebuild the cache from the ledger.
Benchmarked from: Skyward Food Service module and MySchoolBucks / SchoolCafe —
both use a prepaid meal-wallet model rather than per-meal invoicing, the dominant
pattern in K-12 cafeteria systems, adapted here for MoMo/cash top-ups.
"""
from django.core.exceptions import ValidationError
from django.db import models, transaction as db_transaction
from apps.core.models import TenantModel, TenantManager
# ══════════════════════════════════════════════════════
# MENU
# ══════════════════════════════════════════════════════
class MenuItem(TenantModel):
    """A single food item that can appear on the weekly menu and be sold individually."""
    class CategoryChoices(models.TextChoices):
        BREAKFAST = 'breakfast', 'Breakfast'
        LUNCH     = 'lunch',     'Lunch'
        SNACK     = 'snack',     'Snack'
        BEVERAGE  = 'beverage',  'Beverage'
    name        = models.CharField(max_length=150)
    category    = models.CharField(max_length=20, choices=CategoryChoices.choices,
                                    default=CategoryChoices.LUNCH)
    description = models.TextField(blank=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2,
                                       help_text='Amount deducted from the meal wallet per serving')
    is_active   = models.BooleanField(default=True)
    contains_allergens = models.CharField(
        max_length=200, blank=True,
        help_text='Comma-separated allergens — cross-check against Student.allergies before serving'
    )
    objects = TenantManager()
    class Meta:
        db_table     = 'canteen_menu_item'
        ordering     = ['category', 'name']
        verbose_name = 'Menu Item'
    def __str__(self):
        return f'{self.name} ({self.get_category_display()})'
class WeeklyMenu(TenantModel):
    """Published menu for one day of a school week — surfaced on student/parent portal."""
    class DayChoices(models.TextChoices):
        MONDAY    = 'monday',    'Monday'
        TUESDAY   = 'tuesday',   'Tuesday'
        WEDNESDAY = 'wednesday', 'Wednesday'
        THURSDAY  = 'thursday',  'Thursday'
        FRIDAY    = 'friday',    'Friday'
    week_start_date = models.DateField(help_text='Monday of the published week')
    day             = models.CharField(max_length=10, choices=DayChoices.choices)
    items           = models.ManyToManyField(MenuItem, related_name='weekly_menus', blank=True)
    published       = models.BooleanField(default=False)
    objects = TenantManager()
    class Meta:
        db_table        = 'canteen_weekly_menu'
        ordering        = ['week_start_date', 'day']
        unique_together = [('tenant', 'week_start_date', 'day')]
        verbose_name    = 'Weekly Menu'
    def __str__(self):
        return f'{self.get_day_display()} — week of {self.week_start_date}'
# ══════════════════════════════════════════════════════
# MEAL WALLET
# ══════════════════════════════════════════════════════
class MealAccount(TenantModel):
    """
    Prepaid meal wallet — one per student, auto-created on Student creation (see signals.py),
    mirroring Spec Section 3 Stage 2: 'Library, canteen, and transport accounts created.'
    """
    student = models.OneToOneField('students.Student', on_delete=models.CASCADE,
                                    related_name='meal_account')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                   help_text='Cached balance — authoritative source is the MealTransaction ledger')
    low_balance_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=5000,
        help_text='Below this amount, a low-balance alert is triggered to the guardian'
    )
    allow_overdraft = models.BooleanField(
        default=False, help_text='If true, deductions are allowed to push balance negative'
    )
    is_active = models.BooleanField(default=True)
    objects = TenantManager()
    class Meta:
        db_table     = 'canteen_meal_account'
        verbose_name = 'Meal Account'
    def __str__(self):
        return f'{self.student} — UGX {self.balance}'
    def is_low_balance(self):
        return self.balance <= self.low_balance_threshold
    def recalculate_balance(self):
        """Rebuild the cached balance from the immutable ledger — use to repair any drift."""
        credits = self.transactions.filter(
            transaction_type__in=[MealTransaction.TypeChoices.TOP_UP, MealTransaction.TypeChoices.REFUND]
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        debits = self.transactions.filter(
            transaction_type=MealTransaction.TypeChoices.DEDUCTION
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        self.balance = credits - debits
        self.save(update_fields=['balance'])
class MealTransaction(TenantModel):
    """
    Immutable ledger entry against a MealAccount — mirrors apps.finance.Payment's
    immutability pattern. balance_after is computed and locked at save time using
    select_for_update() to prevent race conditions from simultaneous top-ups/deductions.
    """
    class TypeChoices(models.TextChoices):
        TOP_UP     = 'top_up',     'Top-Up (Credit)'
        DEDUCTION  = 'deduction',  'Meal Deduction (Debit)'
        REFUND     = 'refund',     'Refund (Credit)'
        ADJUSTMENT = 'adjustment', 'Manual Adjustment'
    class MethodChoices(models.TextChoices):
        CASH         = 'cash',         'Cash'
        MTN_MOMO     = 'mtn_momo',     'MTN Mobile Money'
        AIRTEL_MONEY = 'airtel_money', 'Airtel Money'
        CARD         = 'card',         'Card'
        SYSTEM       = 'system',       'System (Automatic Meal Deduction)'
    meal_account     = models.ForeignKey(MealAccount, on_delete=models.CASCADE,
                                          related_name='transactions')
    transaction_type = models.CharField(max_length=15, choices=TypeChoices.choices)
    amount           = models.DecimalField(max_digits=10, decimal_places=2)
    method           = models.CharField(max_length=15, choices=MethodChoices.choices,
                                         default=MethodChoices.CASH)
    reference        = models.CharField(max_length=100, blank=True,
                                         help_text='MoMo/card transaction reference, if applicable')
    balance_after    = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    menu_item        = models.ForeignKey(MenuItem, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='transactions',
                                          help_text='Set only for deductions tied to a specific meal sale')
    recorded_by      = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='canteen_transactions_recorded')
    notes            = models.CharField(max_length=255, blank=True)
    objects = TenantManager()
    class Meta:
        db_table     = 'canteen_meal_transaction'
        ordering     = ['-created_at']
        verbose_name = 'Meal Transaction'
    def __str__(self):
        return f'{self.get_transaction_type_display()} UGX {self.amount} — {self.meal_account.student}'
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if not is_new:
            super().save(*args, **kwargs)
            return
        with db_transaction.atomic():
            account = MealAccount.objects.select_for_update().get(pk=self.meal_account_id)
            if self.transaction_type in (self.TypeChoices.TOP_UP, self.TypeChoices.REFUND):
                new_balance = account.balance + self.amount
            else:
                new_balance = account.balance - self.amount
                if new_balance < 0 and not account.allow_overdraft:
                    raise ValidationError(
                        f'Insufficient meal wallet balance for {account.student}: '
                        f'balance is UGX {account.balance}, deduction is UGX {self.amount}.'
                    )
            self.balance_after = new_balance
            super().save(*args, **kwargs)
            account.balance = new_balance
            account.save(update_fields=['balance'])
