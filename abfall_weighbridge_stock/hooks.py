def post_init_hook(env):
    """Restore downstream state when upgrading from the former combined addon."""
    env.cr.execute("SELECT to_regclass('weighbridge_split_migration')")
    if not env.cr.fetchone()[0]:
        return
    env.cr.execute("""
        UPDATE weighbridge_ticket AS ticket
        SET stock_state = CASE migration.legacy_state
                WHEN 'settled' THEN 'done'
                WHEN 'settlement_pending' THEN 'error'
                ELSE 'pending'
            END,
            stock_error = migration.legacy_settlement_error
        FROM weighbridge_split_migration AS migration
        WHERE migration.ticket_id = ticket.id
          AND ticket.state = 'completed'
    """)
