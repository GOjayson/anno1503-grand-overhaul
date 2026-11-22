/* Included by the in-game menu build. The native socket hooks read a copy. */
static SRWLOCK menu_plan_lock = SRWLOCK_INIT;
static TrialSettings menu_plan;
static _Thread_local TrialSettings menu_plan_read;

static const TrialSettings *settings(void)
{
    AcquireSRWLockShared(&menu_plan_lock);
    menu_plan_read = menu_plan;
    ReleaseSRWLockShared(&menu_plan_lock);
    return &menu_plan_read;
}

static bool menu_coop_plan(const TrialSettings *plan)
{
    return (plan->role == TRIAL_HOST || plan->role == TRIAL_GUEST) && !plan->prefix &&
           (memcmp(plan->signature, "ANNOCOOP", 8) == 0 || memcmp(plan->signature, "ANNOCNET", 8) == 0);
}

static inline bool menu_coop_active(void)
{
    return menu_coop_plan(settings());
}

static void menu_set_plan(const TrialSettings *plan)
{
    AcquireSRWLockExclusive(&menu_plan_lock);
    if (plan)
        menu_plan = *plan;
    else
        memset(&menu_plan, 0, sizeof menu_plan);
    ReleaseSRWLockExclusive(&menu_plan_lock);
}
