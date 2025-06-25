from datetime import datetime
import io
from odoo import http
from odoo.http import request, content_disposition
from odoo.tools import pdf
from odoo.modules.module import get_resource_path


class DatenErfassungsProtokollController(http.Controller):

    @http.route('/download/begleitschein/<int:record_id>', type='http', auth='user')
    def download_your_file(self, record_id, **kwargs):
        picking = request.env['stock.picking'].browse(record_id)
        if not picking.exists():
            return request.not_found()

        # Send file as response
        return request.make_response(
            self._print_begleitschein(picking),
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', content_disposition('Begleitschein.pdf'))
            ]
        )

    def _print_begleitschein(self, picking):
        """
        Generates the Begleitschein PDF report.chr
        """
        output_buffer = io.BytesIO()
        file_path = get_resource_path('begleitschein', 'static/data', 'begleitschein.pdf')
        for move in picking.move_ids:
            with open(file_path, "rb") as f:
                reader = pdf.PdfFileReader(f, strict=False)
                writer = pdf.PdfFileWriter()

                form_fields_values_mapping = {
                    "Identifikationsnummer": picking.partner_id.id_numbers.display_name,
                    "Art des Transports oder kein Transport": "1",
                    "Bemerkungen": "",
                    "Abfallbezeichnung 1": move.product_id.name,
                    "Abfallbezeichnung 2": "",
                    "Abfallbezeichnung 3": "",
                    "Schlüsselnummer 1": move.product_id.waste_type_id.key_number,
                    "Schlüsselnummer 2": "",
                    "Spez 1": move.product_id.waste_type_id.dangerous,
                    "Spez 2": "",
                    "Masse in kg - Reihe 1": move.product_qty,
                    "Masse in kg - Reihe 2": "",
                    "Masse in kg - Reihe 3": "",
                    "Überabe: Name": picking.partner_id.complete_name,
                    "Übergabe: Anschrift": picking.partner_id.street,
                    "Übergabe: Absendeort (PLZ)": picking.partner_id.zip,
                    "Übergabe: Bestätigung": "",
                    "Übergabe: Begleitscheinnummer": picking.name,
                    "Übergabe: Jahr": str(picking.scheduled_date.year)[-2:],
                    "Übergabe: Datum des Transportbeginns": datetime.strftime(picking.scheduled_date, "%d%m%y"),
                    "Transport: Name": picking.company_id.partner_id.complete_name,
                    "Transport: Anschrift": picking.company_id.partner_id.street,
                    "Transport: Personen-GLN": picking.company_id.partner_id.id_numbers.display_name,
                    "Transport: Bestätigung": "",
                    "Übernahme: Name": picking.company_id.partner_id.complete_name,
                    "Übernahme: Anschrift": picking.company_id.partner_id.street,
                    "Übernahme: Empfangsort (PLZ)": picking.company_id.partner_id.zip,
                    "Übernahme: Identifikationsnummer": picking.company_id.partner_id.id_numbers.display_name,
                    "Übernahme: Begleitscheinnummer": "00256",
                    "Übernahme: Jahr": str(picking.scheduled_date.year)[-2:],
                    "Übernahme: Datum des Empfangs": datetime.strftime(picking.scheduled_date, "%d%m%y"),
                    "Übernahme: Bestätigung": "",
                    "Streckengeschäft: Name 1": "",
                    "Streckengeschäft: Anschrift 1": "",
                    "Streckengeschäft: Personen-GLN 1": "",
                    "Streckengeschäft: Name 2": "",
                    "Streckengeschäft: Anschrift 2": "",
                    "Streckengeschäft Empfänger: Name": "",
                    "Streckengeschäft Empfänger: Anschrift": "",
                    "Streckengeschäft Empfänger: Empfangsort": "",
                    "Streckengeschäft Empfänger: Begleitscheinnummer": "",
                    "Streckengeschäft Empfänger: Jahr": "",
                    "Streckengeschäft Empfänger: Datum des Empfangs": "",
                    "Streckengeschäft Empfänger: Bestätigung": "",
                    "Streckengeschäft: Personen-GLN 2": "",
                    "Streckengeschäft Empfänger: Identifikationsnummer": "",
                    "Schlüsselnummer 3": "",
                    "Spez 3": "",
                    "POP 3": "",
                }
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    writer.addPage(page)

                pdf.fill_form_fields_pdf(writer, form_fields=form_fields_values_mapping)
                writer.write(output_buffer)

        return output_buffer.getvalue()
