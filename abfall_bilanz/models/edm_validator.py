# -*- coding: utf-8 -*-
"""
EDM Validation Framework for Abfallbilanz

Implements local validation of EDM rules before XML generation.
Validations are warnings only - they do not block XML generation.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date


class EDMSeverity(Enum):
    """Severity levels matching EDM validation categories."""
    CRITICAL = 'critical'  # Would block upload to EDM
    ERROR = 'error'        # Would block submission to authorities (from 2027)
    WARNING = 'warning'    # Should be fixed but submission allowed
    HINT = 'hint'          # Possibly incorrect, check manually


@dataclass
class EDMValidationError:
    """A single validation error or warning."""
    rule_id: str  # E.g. 'R131', 'C316'
    severity: EDMSeverity
    message: str
    record_name: Optional[str] = None  # Display name of the affected record
    record_model: Optional[str] = None  # Odoo model name
    record_id: Optional[int] = None  # Database ID


@dataclass
class EDMValidationResult:
    """Collection of validation results."""
    errors: List[EDMValidationError] = field(default_factory=list)
    
    def add_error(self, rule_id: str, severity: EDMSeverity, message: str,
                  record_name: str = None, record_model: str = None, record_id: int = None):
        """Add a validation error."""
        self.errors.append(EDMValidationError(
            rule_id=rule_id,
            severity=severity,
            message=message,
            record_name=record_name,
            record_model=record_model,
            record_id=record_id
        ))
    
    def add_critical(self, rule_id: str, message: str, **kwargs):
        """Convenience method for critical errors."""
        self.add_error(rule_id, EDMSeverity.CRITICAL, message, **kwargs)
    
    def add_error_level(self, rule_id: str, message: str, **kwargs):
        """Convenience method for error level issues."""
        self.add_error(rule_id, EDMSeverity.ERROR, message, **kwargs)
    
    def add_warning(self, rule_id: str, message: str, **kwargs):
        """Convenience method for warnings."""
        self.add_error(rule_id, EDMSeverity.WARNING, message, **kwargs)
    
    def add_hint(self, rule_id: str, message: str, **kwargs):
        """Convenience method for hints."""
        self.add_error(rule_id, EDMSeverity.HINT, message, **kwargs)
    
    @property
    def has_critical(self) -> bool:
        """Check if there are any critical errors."""
        return any(e.severity == EDMSeverity.CRITICAL for e in self.errors)
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any error-level or higher issues."""
        return any(e.severity in (EDMSeverity.CRITICAL, EDMSeverity.ERROR) for e in self.errors)
    
    @property
    def critical_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == EDMSeverity.CRITICAL)
    
    @property
    def error_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == EDMSeverity.ERROR)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == EDMSeverity.WARNING)
    
    @property
    def hint_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == EDMSeverity.HINT)
    
    def to_html(self) -> str:
        """Generate HTML summary for display in Odoo."""
        if not self.errors:
            return '<p style="color: green;">✓ All validations passed</p>'
        
        html_parts = ['<div class="edm-validation-results">']
        
        # Group by severity
        for severity in EDMSeverity:
            severity_errors = [e for e in self.errors if e.severity == severity]
            if not severity_errors:
                continue
            
            color = {
                EDMSeverity.CRITICAL: '#dc3545',
                EDMSeverity.ERROR: '#fd7e14',
                EDMSeverity.WARNING: '#ffc107',
                EDMSeverity.HINT: '#17a2b8'
            }.get(severity, '#6c757d')
            
            icon = {
                EDMSeverity.CRITICAL: '⛔',
                EDMSeverity.ERROR: '❌',
                EDMSeverity.WARNING: '⚠️',
                EDMSeverity.HINT: 'ℹ️'
            }.get(severity, '•')
            
            html_parts.append(f'<h4 style="color: {color};">{icon} {severity.value.title()} ({len(severity_errors)})</h4>')
            html_parts.append('<ul>')
            for err in severity_errors[:20]:  # Limit display
                record_info = f' [{err.record_name}]' if err.record_name else ''
                html_parts.append(f'<li><strong>{err.rule_id}</strong>: {err.message}{record_info}</li>')
            if len(severity_errors) > 20:
                html_parts.append(f'<li>... and {len(severity_errors) - 20} more</li>')
            html_parts.append('</ul>')
        
        html_parts.append('</div>')
        return ''.join(html_parts)


class EDMValidator:
    """
    Validates Odoo records against EDM rules.
    
    Usage:
        validator = EDMValidator(env)
        result = validator.validate_submission(submission_record)
        if result.has_errors:
            # Display warnings but don't block
            pass
    """
    
    def __init__(self, env):
        self.env = env
        self.result = EDMValidationResult()
    
    def validate_submission(self, submission):
        """Validate an entire submission record."""
        self.result = EDMValidationResult()
        
        # Validate company/obligated party
        self._validate_obligated_party(submission)
        
        # Validate date ranges
        self._validate_date_range(submission)
        
        # Validate all waste moves
        year = int(submission.year)
        moves = self.env['waste.move'].search([
            ('date', '>=', f'{year}-01-01'),
            ('date', '<=', f'{year}-12-31'),
            ('state', '=', 'approved'),
            ('company_id', '=', submission.company_id.id)
        ])
        for move in moves:
            self._validate_waste_move(move)
        
        # Validate storage states
        storage_states = self.env['waste.storage.state'].search([
            ('reporting_date', '>=', f'{year}-01-01'),
            ('reporting_date', '<=', f'{year}-12-31'),
            ('company_id', '=', submission.company_id.id)
        ])
        for state in storage_states:
            self._validate_storage_state(state)
        
        # Validate reclassifications
        reclassifications = self.env['waste.reclassification'].search([
            ('reporting_date', '>=', f'{year}-01-01'),
            ('reporting_date', '<=', f'{year}-12-31'),
            ('company_id', '=', submission.company_id.id)
        ])
        for reclass in reclassifications:
            self._validate_reclassification(reclass)
        
        return self.result
    
    def _validate_obligated_party(self, submission):
        """Validate the obligated party (reporting company)."""
        company = submission.company_id
        partner = company.partner_id
        
        # C316: Valid person GLN required
        if not partner.person_gln:
            self.result.add_critical('C316',
                'Company must have a valid person_gln (Personen-GLN) configured',
                record_name=company.name, record_model='res.company', record_id=company.id)
        elif len(partner.person_gln) != 13 or not partner.person_gln.isdigit():
            self.result.add_critical('C316',
                f'Invalid GLN format: {partner.person_gln} (must be 13 digits)',
                record_name=company.name, record_model='res.company', record_id=company.id)
    
    def _validate_date_range(self, submission):
        """Validate the reporting period."""
        year = int(submission.year)
        
        # C486: Period must be within a calendar year (already ensured by year field)
        # C400: Period must not be in the future
        current_year = date.today().year
        if year > current_year:
            self.result.add_critical('C400',
                f'Reporting year {year} is in the future',
                record_name=f'Year {year}')
    
    def _validate_waste_move(self, move):
        """Validate a single waste move."""
        record_info = dict(
            record_name=move.name,
            record_model='waste.move',
            record_id=move.id
        )
        
        # R131: Negative mass
        if move.amount < 0:
            self.result.add_error_level('R131',
                f'Mass cannot be negative ({move.amount} kg)',
                **record_info)
        
        # R867: Zero mass
        if move.amount == 0:
            self.result.add_error_level('R867',
                'Mass cannot be zero',
                **record_info)
        
        # R784: Excessively large mass
        if move.amount > 100_000_000_000:
            self.result.add_error_level('R784',
                f'Mass exceeds maximum (100 billion kg): {move.amount}',
                **record_info)
        
        # Booking Type Logic (BookingTypeCode rules)
        # 1. Takeover (Übernahme) - Recipient is own installation
        if move.recipient_installation and not move.origin_installation:
            # R979: Origin location missing
            if not move.origin_site and not (move.origin_partner and (move.origin_partner.person_gln or (move.origin_partner.city and move.origin_partner.zip))):
                self.result.add_warning('R979',
                    'Origin location (Absendeort) is missing or incomplete for takeover',
                    **record_info)
            # R901: Treatment procedure missing
            if not move.recycling_type:
                self.result.add_warning('R901',
                    'Treatment procedure (Verbleibsverfahren) is missing for takeover',
                    **record_info)
        
        # 2. Handover (Übergabe) - Origin is own installation
        elif move.origin_installation and not move.recipient_installation:
            # R402: Destination location missing
            if not move.recipient_site and not (move.recipient_partner and (move.recipient_partner.person_gln or (move.recipient_partner.city and move.recipient_partner.zip))):
                self.result.add_warning('R402',
                    'Destination location (Empfangsort) is missing or incomplete for handover',
                    **record_info)
            # R108: Origin treatment procedure missing
            if not move.origin_type:
                self.result.add_warning('R108',
                    'Origin treatment procedure (Herkunftsverfahren) is missing for handover',
                    **record_info)

        # 3. Internal Move (Internal) - Both installations belong to own company
        elif move.origin_installation and move.recipient_installation:
             # Both should be own installations
             pass

        # Validate GLN format for waste type
        if move.abfallart and move.abfallart.gtin:
            if len(move.abfallart.gtin) != 13:
                self.result.add_warning('R351',
                    f'Invalid waste type GTIN format: {move.abfallart.gtin}',
                    **record_info)
        
        # Validate partner GLNs
        if move.origin_partner and move.origin_partner.person_gln:
            gln = move.origin_partner.person_gln
            if len(gln) != 13 or not gln.isdigit():
                self.result.add_warning('R688',
                    f'Invalid origin partner GLN: {gln}',
                    **record_info)
        
        if move.recipient_partner and move.recipient_partner.person_gln:
            gln = move.recipient_partner.person_gln
            if len(gln) != 13 or not gln.isdigit():
                self.result.add_warning('R688',
                    f'Invalid recipient partner GLN: {gln}',
                    **record_info)

    def _validate_storage_state(self, state):
        """Validate a storage state record."""
        record_info = dict(
            record_name=f'{state.installation_id.name} - {state.reporting_date}',
            record_model='waste.storage.state',
            record_id=state.id
        )
        
        # R757: Storage amount cannot be negative
        if state.amount < 0:
            self.result.add_error_level('R757',
                f'Storage amount cannot be negative ({state.amount} kg)',
                **record_info)
        
        # R753: Date should be start or end of year  
        if state.reporting_date:
            day = state.reporting_date.day
            month = state.reporting_date.month
            if not ((month == 1 and day == 1) or (month == 12 and day == 31)):
                self.result.add_hint('R753',
                    'Storage state date should be January 1 or December 31',
                    **record_info)
        
        # Installation validation
        if not state.installation_id:
            self.result.add_error_level('R889',
                'Installation is required for storage state',
                **record_info)
        elif state.installation_id.gtin:
            if len(state.installation_id.gtin) != 13:
                self.result.add_warning('R687',
                    f'Invalid installation GTIN format: {state.installation_id.gtin}',
                    **record_info)
        
        # Consistency Check (only if approved)
        if state.state == 'approved':
             self._check_storage_consistency(state)

    def _check_storage_consistency(self, state):
        """Check if approved storage state matches calculated inventory."""
        installation = state.installation_id
        waste_type = state.abfallart
        year = state.reporting_date.year
        
        # Simple formula matching WasteBilanz wizard
        # Note: In a real ERP, we might need more complex checks, but let's match the existing wizard logic
        prev_stock = self._get_previous_inventory(installation, waste_type, year)
        
        # Takeovers
        takeovers = self.env['waste.move'].search([
            ('recipient_installation', '=', installation.id),
            ('abfallart', '=', waste_type.id),
            ('date', '>=', f'{year}-01-01'),
            ('date', '<=', f'{year}-12-31'),
            ('state', '=', 'approved'),
        ])
        takeover_amount = sum(takeovers.mapped('amount'))

        # Handovers
        handovers = self.env['waste.move'].search([
            ('origin_installation', '=', installation.id),
            ('abfallart', '=', waste_type.id),
            ('date', '>=', f'{year}-01-01'),
            ('date', '<=', f'{year}-12-31'),
            ('state', '=', 'approved'),
        ])
        handover_amount = sum(handovers.mapped('amount'))
        
        # Corrections
        corrections = self.env['waste.storage.correction'].search([
            ('installation_id', '=', installation.id),
            ('abfallart', '=', waste_type.id),
            ('reporting_date', '>=', f'{year}-01-01'),
            ('reporting_date', '<=', f'{year}-12-31'),
        ])
        correction_amount = sum(corrections.mapped('amount'))
        
        # Reclassifications
        reclasses_in = self.env['waste.reclassification'].search([
            ('installation_id', '=', installation.id),
            ('new_abfallart', '=', waste_type.id),
            ('reporting_date', '>=', f'{year}-01-01'),
            ('reporting_date', '<=', f'{year}-12-31'),
        ])
        reclass_in_amount = sum(reclasses_in.mapped('amount'))

        reclasses_out = self.env['waste.reclassification'].search([
            ('installation_id', '=', installation.id),
            ('preliminary_abfallart', '=', waste_type.id),
            ('reporting_date', '>=', f'{year}-01-01'),
            ('reporting_date', '<=', f'{year}-12-31'),
        ])
        reclass_out_amount = sum(reclasses_out.mapped('amount'))

        expected_stock = prev_stock + takeover_amount - handover_amount + correction_amount + reclass_in_amount - reclass_out_amount
        
        if abs(expected_stock - state.amount) > 0.001:
            self.result.add_warning('CONSISTENCY',
                f'Storage state ({state.amount} kg) does not match calculated inventory ({expected_stock:.2f} kg). '
                f'Diff: {state.amount - expected_stock:.2f} kg',
                record_name=f'{installation.name} - {waste_type.name}',
                record_model='waste.storage.state', record_id=state.id)

    def _get_previous_inventory(self, installation, waste_type, year):
        """Finds the most recent approved inventory before the given year"""
        prev_state = self.env['waste.storage.state'].search([
            ('installation_id', '=', installation.id),
            ('abfallart', '=', waste_type.id),
            ('reporting_date', '<', f'{year}-01-01'),
            ('state', '=', 'approved'),
        ], order='reporting_date desc', limit=1)
        
        return prev_state.amount if prev_state else 0.0

    def _validate_reclassification(self, reclass):
        """Validate a reclassification record."""
        record_info = dict(
            record_name=f'{reclass.installation_id.name} - {reclass.reporting_date}',
            record_model='waste.reclassification',
            record_id=reclass.id
        )
        
        # R928: New waste type required
        if not reclass.new_abfallart:
            self.result.add_error_level('R928',
                'New waste type (Klassifikation) is required',
                **record_info)
        
        # R936: Preliminary waste type required
        if not reclass.preliminary_abfallart:
            self.result.add_error_level('R936',
                'Preliminary waste type is required',
                **record_info)
        
        # R941: Installation required
        if not reclass.installation_id:
            self.result.add_error_level('R941',
                'Installation is required for reclassification',
                **record_info)
        
        # Amount validation
        if reclass.amount <= 0:
            self.result.add_error_level('R867',
                f'Reclassification amount must be > 0 ({reclass.amount} kg)',
                **record_info)

