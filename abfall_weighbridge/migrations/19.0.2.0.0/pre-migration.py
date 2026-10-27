def migrate(cr, version):
    """Preserve combined-module processing state before narrowing core state."""
    cr.execute("SELECT to_regclass('weighbridge_ticket')")
    if not cr.fetchone()[0]:
        return
    cr.execute("""
        CREATE TABLE IF NOT EXISTS weighbridge_split_migration (
            ticket_id integer PRIMARY KEY,
            legacy_state varchar,
            legacy_settlement_error text
        )
    """)
    cr.execute("""
        INSERT INTO weighbridge_split_migration (ticket_id, legacy_state, legacy_settlement_error)
        SELECT id, state, settlement_error FROM weighbridge_ticket
        ON CONFLICT (ticket_id) DO UPDATE
        SET legacy_state = EXCLUDED.legacy_state,
            legacy_settlement_error = EXCLUDED.legacy_settlement_error
    """)
    cr.execute("""
        UPDATE weighbridge_ticket
        SET state = 'completed'
        WHERE state IN ('settlement_pending', 'settled')
    """)
