def merge_analytic_distribution(env, distribution, analytic_account):
    """Set analytic_account to 100%, replacing only accounts from its plan."""
    if not analytic_account:
        return distribution

    target_root_plan = analytic_account.root_plan_id or analytic_account.plan_id
    result = {}
    distribution = distribution or {}

    distribution_account_ids = set()
    for account_key in distribution:
        distribution_account_ids.update(_distribution_key_ids(account_key))

    accounts_by_id = {
        account.id: account
        for account in env['account.analytic.account'].browse(distribution_account_ids).exists()
    }

    for account_key, percentage in distribution.items():
        account_ids = _distribution_key_ids(account_key)
        kept_account_ids = [
            account_id
            for account_id in account_ids
            if not _is_account_in_plan(accounts_by_id.get(account_id), target_root_plan)
        ]
        if kept_account_ids:
            result[','.join(str(account_id) for account_id in kept_account_ids)] = percentage

    result[str(analytic_account.id)] = 100.0
    return result


def _distribution_key_ids(account_key):
    return [
        int(account_id)
        for account_id in str(account_key).split(',')
        if account_id
    ]


def _is_account_in_plan(account, root_plan):
    return account and (account.root_plan_id or account.plan_id) == root_plan
