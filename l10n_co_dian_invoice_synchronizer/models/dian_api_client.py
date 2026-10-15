# -*- coding: utf-8 -*-
"""
DIAN API client: authentication, document listing, ZIP download and XML extraction.
This logic is independent of the wizard so it can be reused (e.g. cron, other models).
"""

import logging
import re
import time
# import io  # only used by the commented-out _get_xml_content (see below)
# import zipfile  # only used by the commented-out _get_xml_content (see below)
from datetime import timedelta
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from odoo import models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# --- Constants (DIAN catalog API) ---
# DIAN's own frontend nominally caches/paginates documents in blocks of ~150 (see
# "maxItemCount" in the Received documents page JS, /Document/Received). In practice the actual
# "blockData" size per request varies (observed 96-153) regardless of "length", so nothing here
# assumes a fixed block size - the pagination loop below tracks the real cumulative count instead.
DIAN_INVOICES_PER_PAGE = 50
ASP_NET_SESSION_ID = 'ASP.NET_SessionId'
HTTP_TIMEOUT = 60

# Mapping from API key -> resulting dict key (cufe = Id for download_zip_files)
DIAN_DOCUMENT_FIELD_MAP = {
    'Id': 'cufe',
    'ReceptionDate': 'reception',
    'SerieAndNumber': 'name',
    'DocumentTypeName': 'type',
    'SenderCode': 'sender_vat',
    'SenderName': 'sender',
    'ReceiverCode': 'receiver_vat',
    'ReceiverName': 'receiver',
    'StatusName': 'result',
    'RadianStatusName': 'radina_result',
    'TotalAmount': 'total_amount',
    'TaxAmountIva5Percent': 'tax_amount_5_percent',
    'TaxAmountIva19Percent': 'tax_amount_19_percent',
    'TaxAmountIva': 'tax_amount_iva',
    'TaxAmountIca': 'tax_amount_ica',
    'TaxAmountIpc': 'tax_amount_ipc',
}


class DianApiClient(models.AbstractModel):
    """
    Service for DIAN catalog API: session auth, document list, ZIP download, XML extraction.
    Does not create a DB table (AbstractModel). Use via env['dian.api.client'].
    """
    _name = 'dian.api.client'
    _description = 'DIAN API Client (session, documents, ZIP, XML)'

    def fetch_invoices(self, token_url, start_date, end_date, company):
        """
        High-level method: validate URL, create session, get documents, download ZIPs, extract XML.
        Returns list of processed results (same structure as the wizard's sync() before).
        The HTTP session is closed after the request, including on errors.
        """
        session, response, html_form_token = self._create_authenticated_session(token_url)
        try:
            base_url = self._extract_base_url_from_cookies(session, response)
            end_date_inclusive = end_date + timedelta(days=1)
            existing_docs = set(
                self.env['dian.document'].search([
                    ('company_id', '=', company.id),
                    ('reception', '>=', start_date),
                    ('reception', '<', end_date_inclusive),
                ]).mapped('cufe')
            )
            return self._get_documents_for_date_range(
                session, base_url, start_date, end_date, existing_docs, html_form_token)
        finally:
            session.close()

    # -------------------------------------------------------------------------
    # DIAN session: authenticated session creation
    # -------------------------------------------------------------------------

    def _create_authenticated_session(self, token_url):
        """
        Create a requests session and authenticate with DIAN using token_url.
        If the first response is a redirect (e.g. Sophos protection) with a Location
        header, follows that URL to obtain the actual DIAN AuthToken page and cookies.
        Returns (session, response). Caller must close session when done.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        try:
            # Follow the full redirect chain manually (one hop at a time).
            # When allow_redirects=False, requests only populates response.cookies but
            # does NOT update session.cookies (that only happens inside resolve_redirects,
            # which is bypassed). We must copy each hop's cookies into the session jar
            # explicitly so they are sent on the next hop and on subsequent API calls.
            response = session.get(
                token_url,
                headers=headers,
                allow_redirects=False,
                timeout=HTTP_TIMEOUT,
            )
            for _ in range(10):
                for cookie in response.cookies:
                    session.cookies.set_cookie(cookie)
                if response.status_code not in (301, 302, 303, 307, 308):
                    break
                location = response.headers.get('Location')
                if not location:
                    break
                redirect_url = location if location.startswith('http') else urljoin(response.url, location)
                response = session.get(
                    redirect_url,
                    headers=headers,
                    allow_redirects=False,
                    timeout=HTTP_TIMEOUT,
                )
            else:
                session.close()
                raise ValidationError(_("Too many redirects during DIAN authentication."))

            if response.status_code not in (200, 302):
                session.close()
                raise ValidationError(
                    _("Unexpected response status from DIAN: %d") % response.status_code)
            html_form_token = self._extract_html_form_token(response.text)
            if not html_form_token:
                session.close()
                raise ValidationError(
                    _("Could not extract anti-forgery token from DIAN page. The page structure may have changed."))
            return session, response, html_form_token
        except requests.exceptions.Timeout:
            session.close()
            raise ValidationError(
                _("Connection timeout. The DIAN service did not respond in time. Please try again."))
        except requests.exceptions.ConnectionError:
            session.close()
            raise ValidationError(
                _("Connection error. Could not connect to the DIAN service. Please check your internet connection and try again."))
        except requests.exceptions.RequestException as e:
            session.close()
            raise ValidationError(
                _("Error during authentication request to DIAN service: %s") % str(e))

    def _extract_html_form_token(self, html):
        """Extract the __RequestVerificationToken value from a hidden form field in the HTML."""
        m = re.search(
            r'<input[^>]+name=["\']__RequestVerificationToken["\'][^>]+value=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r'<input[^>]+value=["\']([^"\']+)["\'][^>]+name=["\']__RequestVerificationToken["\']',
                html, re.IGNORECASE,
            )
        return m.group(1) if m else None

    def _extract_base_url_from_cookies(self, session, response):
        """Extract base URL from session cookies accumulated across all redirect hops."""
        # Prefer the ASP.NET_SessionId cookie domain as the canonical DIAN domain.
        # All cookies (including those set on intermediate redirects) are in session.cookies.
        domain = None
        for cookie in session.cookies:
            if cookie.name == ASP_NET_SESSION_ID and cookie.domain:
                domain = cookie.domain
                break
        if not domain:
            # Fallback: derive domain from the final response URL (after redirect chain).
            parsed = urlparse(response.url)
            if parsed.netloc:
                domain = parsed.netloc
        if not domain:
            raise ValidationError(
                _("Could not determine DIAN domain. ASP.NET_SessionId cookie not found and response URL is empty."))
        return f"https://{domain}"

    # -------------------------------------------------------------------------
    # DIAN received documents (query / list)
    # -------------------------------------------------------------------------
    def _get_documents_for_date_range(self, session, base_url, start_date, end_date, existing_docs, html_form_token):
        """
        Retrieve all received documents from DIAN for the given date range.

        XML download is currently disabled (see _get_xml_content, commented out below):
        DIAN protects /Document/DownloadZipFiles with Cloudflare Turnstile, which cannot
        be automated with a plain requests session. xml_query_result is set to None for
        every document; document_received_to_vals handles that by setting has_xml_info=False.

        :param session: requests.Session with DIAN cookies
        :param base_url: DIAN catalog base URL
        :param start_date: start date (date)
        :param end_date: end date (date)
        :param existing_docs: set of CUFE strings for documents already in DB (skipped).
        :return: (documents, discarded, records_filtered, total_application_response_count, mapping_errors):
            documents is list of dicts to process; discarded is list of CUFE strings that were
            skipped (already in existing_docs); mapping_errors is a list of dicts
            {cufe, name, error} for raw items that could not be turned into a valid document
            (e.g. missing mandatory fields) - these are neither in documents nor discarded, and
            recordsFiltered = len(documents) + len(discarded) + application_response_count +
            len(mapping_errors) is the identity callers can use to detect data loss. Each document
            dict has the keys: cufe, reception, name, type, sender_vat, sender, receiver_vat,
            receiver, result, radina_result, total_amount, tax_amount_5_percent,
            tax_amount_19_percent, tax_amount_iva, tax_amount_ica, tax_amount_ipc (values from API
            or None), and xml_query_result (currently always None).
        """
        documents = []
        discarded = []
        mapping_errors = []
        records_filtered = 1
        total_application_response_count = 0
        # DIAN's own frontend (Received documents page) never queries by a global offset past
        # the first block of records: it fetches blocks (nominally ~150 each, but the real size
        # returned per block varies - observed 96-153 in practice, never a fixed number), caches
        # each one client-side, and slices pages out of the cached block in the browser.
        # Replicated here (confirmed against the real page JS and a live capture): request block 0
        # with blockIndex=0/IsNextPage=false/ContinuationToken="", read the block from "blockData"
        # (NOT "data" - "data" is only a UI-page-sized slice DIAN's own JS mostly ignores), then
        # for each following block send blockIndex=N/IsNextPage=true/ContinuationToken=<token
        # returned by block N-1>, until we've covered recordsFiltered records. total_received
        # tracks the actual (not assumed) cumulative count so the stop condition never depends on
        # guessing the block size.
        block_index = 0
        continuation_token = ''
        total_received = 0
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        while True:
            _logger.info(
                "DIAN GetDocumentsPageToken request: block_index=%s, start_str=%s, end_str=%s",
                block_index, start_str, end_str,
            )
            records_filtered, documents_page, discarded_page, block_size, ar_count, mapping_errors_page, continuation_token = self._post_get_documents_page_token(
                session, base_url, block_index, start_str, end_str, existing_docs, html_form_token, continuation_token)
            _logger.info(
                "DIAN GetDocumentsPageToken result: records_filtered=%s, block_size=%s, documents_page=%s, "
                "discarded_page=%s, application_responses=%s, mapping_errors=%s",
                records_filtered, block_size, len(documents_page), len(discarded_page), ar_count,
                len(mapping_errors_page),
            )
            if mapping_errors_page:
                _logger.warning(
                    "DIAN GetDocumentsPageToken: %d document(s) in block %d could not be mapped: %s",
                    len(mapping_errors_page), block_index, mapping_errors_page,
                )
            if not block_size:
                break
            documents.extend(documents_page)
            discarded.extend(discarded_page)
            mapping_errors.extend(mapping_errors_page)
            total_application_response_count += ar_count
            total_received += block_size
            block_index += 1
            if total_received >= records_filtered:
                break
        return documents, discarded, records_filtered, total_application_response_count, mapping_errors

    def _post_get_documents_page_token(self, session, base_url, block_index, start_date_str, end_date_str,
                                        existing_docs, html_form_token, continuation_token=''):
        api_url = f"{base_url}/Document/GetDocumentsPageToken"
        # DIAN uses ASP.NET anti-forgery (double-submit): the HTML form token (different from
        # the cookie) must arrive as a form field. JSON bodies are rejected regardless of headers.
        request_data = {
            "__RequestVerificationToken": html_form_token,
            "draw": block_index + 1,
            # "start" is always 0: each request here fetches one full block from its own
            # beginning (DIAN's frontend only sends a non-zero "start" for a within-block UI
            # page whose block is already cached; we always want the whole block).
            "start": 0,
            "length": DIAN_INVOICES_PER_PAGE,
            "DocumentKey": "",
            "SerieAndNumber": "",
            "SenderCode": "",
            "ReceiverCode": "",
            "StartDate": start_date_str,
            "EndDate": end_date_str,
            "DocumentTypeId": "00",
            "Status": "0",
            "IsNextPage": "true" if block_index > 0 else "false",
            "FilterType": "3",
            "blockIndex": block_index,
            "RadianStatus": "0",
            # Field name is "ContinuationToken" (capital C) - confirmed from a live capture of
            # DIAN's own request. Must be the token returned by the PREVIOUS block (empty for
            # block 0), never the current block's own token.
            "ContinuationToken": continuation_token or "",
        }
        headers = {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'es-419,es;q=0.9,en;q=0.8',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': base_url,
            'priority': 'u=1, i',
            'referer': f'{base_url}/',
            'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
        }
        try:
            t0 = time.perf_counter()
            api_response = session.post(
                api_url,
                data=request_data,
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
            elapsed = time.perf_counter() - t0
            _logger.info("DIAN GetDocumentsPageToken request took %.2f s (block_index=%s)", elapsed, block_index)
        except requests.exceptions.RequestException as e:
            raise ValidationError(
                _("Error executing request on block %d: %s") % (block_index, str(e)))
        if api_response.status_code == 403:
            raise ValidationError(
                _("Request error on block %d, status code: 403. "
                  "The session token may have expired. "
                  "Please generate a new token and try again.") % block_index)
        if api_response.status_code != 200:
            raise ValidationError(
                _("Request error on block %d, status code: %d") % (block_index, api_response.status_code))
        result = api_response.json()

        # Fields available in each item of the DIAN response (reference):
        # Id, DocumentTypeName, SerieAndNumber, SenderCode, SenderName, ReceiverCode,
        # ReceiverName, ReceptionDate, Status, StatusName, RadianStatusName, TotalAmount,
        # TaxAmountIva5Percent, TaxAmountIva19Percent, TaxAmountIva, TaxAmountIca, TaxAmountIpc,
        # EmissionDate, DocumentKey, DocumentTypeId, Number, Serie, TechProviderCode,
        # TechProviderName, GenerationDate, Amount, DiscrepancyCode, DiscrepancyDescription,
        # PartitionKey, DocumentTags, Events, References, TaxesDetail, createFrom,
        # ResidenceDescription, ReceiverIdTypeDescription, TokenConsulta, Identifier
        #
        # "blockData" (not "data") is the authoritative payload: DIAN's own frontend caches
        # blockData client-side and slices UI pages out of it; "data" is only a "length"-sized
        # slice DIAN's JS uses for a single special case (auto-download on a unique-key search).
        raw_data = result.get("blockData", [])
        next_continuation_token = result.get("continuationToken") or ''

        block_size = len(raw_data)
        application_response_count = sum(
            1 for item in raw_data if item.get('DocumentTypeName') == 'Application response'
        )

        documents = [
            {out_key: item.get(api_key) for api_key,
             out_key in DIAN_DOCUMENT_FIELD_MAP.items()}
            for item in raw_data
            if item.get('DocumentTypeName') != 'Application response'
        ]

        kept = [d for d in documents if d.get('cufe') not in existing_docs]
        discarded = [d.get('cufe')
                     for d in documents if d.get('cufe') in existing_docs]

        dian_documents = []
        mapping_errors = []
        for document_received in kept:
            # XML download disabled: DIAN now protects DownloadZipFiles with Cloudflare
            # Turnstile, which blocks automated retrieval (verified 2026-07-16, see
            # _get_xml_content below, commented out). document_received_to_vals handles
            # a missing/None xml_query_result gracefully (sets has_xml_info=False).
            document_received['xml_query_result'] = None
            cufe = document_received.get('cufe')
            try:
                # cufe/name/reception are required=True on dian.document: catch a missing one
                # here (recorded as a mapping error) instead of letting create() blow up the
                # whole batch later, which would silently drop the entire sync.
                if not cufe or not document_received.get('name') or not document_received.get('reception'):
                    raise ValueError(_(
                        "Missing mandatory field(s) from DIAN response (cufe/name/reception)."))
                dian_document = self.env['dian.document'].document_received_to_vals(
                    document_received)
                dian_documents.append(dian_document)
            except Exception as e:
                _logger.error(
                    "DIAN document mapping failed for cufe=%s: %s", cufe, e)
                mapping_errors.append({
                    'cufe': cufe or '',
                    'name': document_received.get('name') or '',
                    'error': str(e),
                })

        return (result.get("recordsFiltered", 0), dian_documents, discarded, block_size,
                application_response_count, mapping_errors, next_continuation_token)

    # Disabled 2026-07-16: DIAN added Cloudflare Turnstile protection to
    # /Document/DownloadZipFiles. Every download now requires a fresh, single-use
    # token (query param "captcha=...") generated client-side by Cloudflare's JS
    # challenge on the /Document/Received page. This cannot be replicated with a
    # plain requests session. A Playwright-based proof of concept (headless and
    # headful, including a manual click on the Turnstile checkbox) confirmed
    # Cloudflare rejects the automated browser in all cases. Kept commented out
    # for reference / in case DIAN provides an official automated channel later.
    #
    # def _get_xml_content(self, session, base_url, document_received):
    #     """
    #     Download the ZIP for one document from DIAN, extract the XML file and decode it.
    #
    #     :param session: requests.Session with DIAN cookies
    #     :param base_url: DIAN catalog base URL (e.g. https://...)
    #     :param document_received: dict with at least 'cufe' (track ID)
    #     :return: dict with 'status' ('success'|'error') and either 'xml_content' or 'message'
    #     """
    #     api_url = f"{base_url}/Document/DownloadZipFiles"
    #     cufe = document_received.get('cufe')
    #     if not cufe:
    #         return {
    #             'status': 'error',
    #             'message': _("Document has no CUFE."),
    #         }
    #
    #     params = {"trackId": cufe}
    #     try:
    #         t0 = time.perf_counter()
    #         response = session.get(
    #             api_url, params=params, timeout=HTTP_TIMEOUT)
    #         elapsed = time.perf_counter() - t0
    #         _logger.info("DIAN DownloadZipFiles request took %.2f s (trackId=%s)", elapsed, cufe[:16] + "..." if len(cufe) > 16 else cufe)
    #         response.raise_for_status()
    #     except requests.exceptions.Timeout:
    #         return {
    #             'status': 'error',
    #             'message': _("Timeout error downloading ZIP file. The server did not respond in time."),
    #         }
    #     except Exception as e:
    #         return {
    #             'status': 'error',
    #             'message': _("HTTP error downloading ZIP file. Details: %s") % str(e),
    #         }
    #
    #     content_type = response.headers.get('Content-Type', '')
    #     if 'application/zip' not in content_type:
    #         return {
    #             'status': 'error',
    #             'message': _("Unexpected Content-Type for document with track ID %s. Expected application/zip, got: %s")
    #             % (cufe, content_type),
    #         }
    #
    #     file_content = response.content
    #     if not file_content:
    #         return {
    #             'status': 'error',
    #             'message': _("Empty file received for document with track ID %s") % cufe,
    #         }
    #
    #     content_length = response.headers.get('Content-Length')
    #     if content_length and int(content_length) != len(file_content):
    #         return {
    #             'status': 'error',
    #             'message': _("Content-Length mismatch for document with track ID %s. Expected %s bytes, received %d bytes")
    #             % (cufe, content_length, len(file_content)),
    #         }
    #
    #     try:
    #         zip_file = zipfile.ZipFile(io.BytesIO(file_content))
    #     except zipfile.BadZipFile:
    #         return {
    #             'status': 'error',
    #             'message': _("Invalid ZIP file format for track ID %s") % cufe,
    #         }
    #     except Exception as e:
    #         return {
    #             'status': 'error',
    #             'message': _("Error opening ZIP for track ID %s. Details: %s") % (cufe, str(e)),
    #         }
    #
    #     try:
    #         xml_filter = filter(lambda x: x.lower().endswith(
    #             '.xml'), zip_file.namelist())
    #         xml_file = next(xml_filter, None)
    #         if not xml_file:
    #             return {
    #                 'status': 'error',
    #                 'message': _("XML file not found for track ID %s") % cufe,
    #             }
    #         xml_content_bytes = zip_file.read(xml_file)
    #     except Exception as e:
    #         return {
    #             'status': 'error',
    #             'message': _("Error reading from ZIP for track ID %s. Details: %s") % (cufe, str(e)),
    #         }
    #     finally:
    #         zip_file.close()
    #
    #     xml_content = ''
    #     error_message = ''
    #     for strategy in ['utf-8', 'latin-1']:
    #         if xml_content:
    #             break
    #         try:
    #             xml_content = xml_content_bytes.decode(strategy)
    #         except Exception:
    #             error_message = _(
    #                 "Cannot decode XML content for track ID %s") % cufe
    #
    #     if not xml_content:
    #         return {
    #             'status': 'error',
    #             'message': error_message or _("Cannot decode XML content for track ID %s") % cufe,
    #         }
    #
    #     return {
    #         'status': 'success',
    #         'xml_content': xml_content,
    #     }
