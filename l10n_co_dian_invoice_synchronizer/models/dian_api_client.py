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
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from odoo import api, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# --- Constants (DIAN catalog API) ---
# GetDocumentsPageToken has two contracts (see documents/dian_get_documents_page_token.md).
# Upper bound of pages/blocks per synchronization, only a safety net against a pagination loop.
DIAN_MAX_PAGES = 200
# Page size the legacy block protocol sends in "length" (one of the site's own valid values; it
# does not limit "blockData").
DIAN_INVOICES_PER_PAGE = 50
# Protocol of GetDocumentsPageToken: 'auto' (default), 'token' or 'block'.
DIAN_PROTOCOL_PARAM = 'l10n_co_dian_invoice_synchronizer.documents_protocol'
DIAN_PROTOCOL_TOKEN = 'token'
DIAN_PROTOCOL_BLOCK = 'block'
ASP_NET_SESSION_ID = 'ASP.NET_SessionId'
HTTP_TIMEOUT = 60
# Browser the requests identify as: Chrome of the live capture 2026-10-20.
DIAN_CHROME_VERSION = '154'
DIAN_USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/%s.0.0.0 Safari/537.36' % DIAN_CHROME_VERSION
)
DIAN_SEC_CH_UA = '"Chromium";v="{0}", "Google Chrome";v="{0}", "Not A(Brand";v="99"'.format(
    DIAN_CHROME_VERSION)
# DocumentTypeId of the DIAN events (acknowledgments, acceptance...), which are not imported
DIAN_APPLICATION_RESPONSE_TYPE_ID = '96'

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
    'EmissionDate': 'emission_date',
    'DocumentTypeId': 'type_code',
    'Status': 'status_code',
}

# Tax amounts: resulting dict key -> API key. The same key is used at the top level of
# the item and inside its "TaxesDetail" object (see _extract_taxes).
DIAN_TAX_FIELD_MAP = {
    'tax_amount_5_percent': 'TaxAmountIva5Percent',
    'tax_amount_19_percent': 'TaxAmountIva19Percent',
    'tax_amount_iva': 'TaxAmountIva',
    'tax_amount_ica': 'TaxAmountIca',
    'tax_amount_ipc': 'TaxAmountIpc',
}
# IVA rates only present in "TaxesDetail", added up when the IVA total is missing
DIAN_TAXES_DETAIL_EXTRA_IVA_KEYS = ('TaxAmountIva14Percent', 'TaxAmountIva16Percent')


class DianUnexpectedResponse(ValidationError):
    """GetDocumentsPageToken answered 200 with something that is not JSON."""


class DianApiClient(models.AbstractModel):
    """
    Service for DIAN catalog API: session auth, document list, ZIP download, XML extraction.
    Does not create a DB table (AbstractModel). Use via env['dian.api.client'].
    """
    _name = 'dian.api.client'
    _description = 'DIAN API Client (session, documents, ZIP, XML)'

    def fetch_invoices(self, token_url, start_date, end_date):
        """
        High-level method: validate URL, create session, get documents, download ZIPs, extract XML.
        Returns list of processed results (same structure as the wizard's sync() before).
        Caller is responsible for closing the session if we ever return it; currently we close it here.
        """
        session, response, html_form_token = self._create_authenticated_session(token_url)
        base_url = self._extract_base_url_from_cookies(session, response)

        result = self._get_documents_for_date_range(
            session, base_url, start_date, end_date, html_form_token)

        session.close()

        # (documents_received, discarded, records_filtered, application_response_count,
        #  mapping_errors, protocol)
        return result

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
        token_url = (token_url or '').strip()
        parsed_url = urlparse(token_url)
        if parsed_url.scheme not in ('http', 'https') or not parsed_url.netloc or ' ' in token_url:
            raise ValidationError(_(
                "The DIAN token URL is not valid: it must be the link DIAN sends to generate "
                "the token (https://catalogo-vpfe.dian.gov.co/User/AuthToken?...). Paste the "
                "whole link and try again."))
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
            'User-Agent': DIAN_USER_AGENT,
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
            # Not "_": it would shadow the gettext function used in the except clauses below
            for _hop in range(10):
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
    # GetDocumentsPageToken has two contracts, both still in use (DIAN rolls changes out
    # per tenant): the "token" contract (live capture 2026-10-05: SearchRequested=true,
    # documents in "data", pagination with hasMore/continuationToken) and the legacy
    # "block" contract (capture 2026-09-23: blockIndex/IsNextPage, documents in
    # "blockData"). See documents/dian_get_documents_page_token.md.

    @api.model
    def _get_documents_protocol_setting(self):
        """'auto' (default), 'token' or 'block' (system parameter DIAN_PROTOCOL_PARAM)."""
        value = self.env['ir.config_parameter'].sudo().get_param(DIAN_PROTOCOL_PARAM, 'auto')
        value = (value or 'auto').strip().lower()
        if value not in ('auto', DIAN_PROTOCOL_TOKEN, DIAN_PROTOCOL_BLOCK):
            _logger.warning("Invalid %s=%r, using 'auto'", DIAN_PROTOCOL_PARAM, value)
            return 'auto'
        return value

    def _get_documents_for_date_range(self, session, base_url, start_date, end_date, html_form_token):
        """
        Retrieve all received documents from DIAN for the given date range.

        The XML is not downloaded here (see _get_xml_content, commented out below):
        DIAN protects /Document/DownloadZipFiles with Cloudflare Turnstile, which cannot
        be automated with a plain requests session. l10n_co_bloodo fetches it afterwards
        through the GetXmlByDocumentKey web service (dian.document._cron_fetch_xml).

        The protocol is chosen with DIAN_PROTOCOL_PARAM. In 'auto' the token contract is
        tried first, and the block contract is used when DIAN answers in it (the response
        has "blockData") or when the token contract returns nothing.

        :param session: requests.Session with DIAN cookies
        :param base_url: DIAN catalog base URL
        :param start_date: start date (date)
        :param end_date: end date (date)
        :return: (documents, discarded, records_filtered, total_application_response_count,
            mapping_errors, protocol): documents is list of dicts to process; discarded is list
            of CUFE strings that were skipped (already imported, see _process_raw_documents);
            mapping_errors is a
            list of dicts {cufe, name, error} for raw items that could not be turned into a
            valid document (e.g. missing mandatory fields) - these are neither in documents nor
            discarded, and recordsFiltered = len(documents) + len(discarded) +
            application_response_count + len(mapping_errors) is the identity callers can use to
            detect data loss; protocol is the contract used ('token' or 'block'). Each document
            dict has the keys: cufe, reception, name, type, sender_vat, sender, receiver_vat,
            receiver, result, radina_result, total_amount, emission_date, type_code, status_code,
            tax_amount_5_percent, tax_amount_19_percent, tax_amount_iva, tax_amount_ica,
            tax_amount_ipc (values from API or None; taxes from _extract_taxes).
        """
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        args = (session, base_url, start_str, end_str, html_form_token)
        setting = self._get_documents_protocol_setting()

        if setting == DIAN_PROTOCOL_BLOCK:
            return self._get_documents_block_protocol(*args) + (DIAN_PROTOCOL_BLOCK,)
        if setting == DIAN_PROTOCOL_TOKEN:
            return self._get_documents_token_protocol(*args) + (DIAN_PROTOCOL_TOKEN,)

        # auto: first page with the token contract, then decide
        try:
            first_result = self._post_get_documents(
                session, base_url, self._token_request_data(start_str, end_str, html_form_token, ''), 0)
        except DianUnexpectedResponse:
            # A tenant still on the legacy contract may not understand the token body
            _logger.info("DIAN GetDocumentsPageToken: token protocol answer is not JSON, "
                         "trying the block protocol")
            return self._get_documents_block_protocol(*args) + (DIAN_PROTOCOL_BLOCK,)
        if 'blockData' in first_result:
            _logger.info("DIAN GetDocumentsPageToken: response has 'blockData', using the block protocol")
            return self._get_documents_block_protocol(*args) + (DIAN_PROTOCOL_BLOCK,)
        if not first_result.get('recordsFiltered') and not first_result.get('data'):
            block_result = self._get_documents_block_protocol(*args)
            if block_result[2]:  # records_filtered
                _logger.info("DIAN GetDocumentsPageToken: token protocol returned nothing and the "
                             "block protocol did, using the block protocol")
                return block_result + (DIAN_PROTOCOL_BLOCK,)
        return self._get_documents_token_protocol(*args, first_result=first_result) + (DIAN_PROTOCOL_TOKEN,)

    @api.model
    def _token_request_data(self, start_date_str, end_date_str, html_form_token, continuation_token):
        """Body of the token contract: same fields as DIAN's own "Buscar" request (2026-10-05)."""
        return {
            "DocumentKey": "",
            "SerieAndNumber": "",
            "SenderCode": "",
            "ReceiverCode": "",
            "StartDate": start_date_str,
            "EndDate": end_date_str,
            "DocumentTypeId": "00",
            "Status": "0",
            "RadianStatus": "0",
            "ReferencesType": "00",
            "FilterType": "3",
            "SearchRequested": "true",
            # Token returned by the previous page ("" for the first one)
            "ContinuationToken": continuation_token or "",
            "__RequestVerificationToken": html_form_token,
        }

    @api.model
    def _block_request_data(self, start_date_str, end_date_str, html_form_token, block_index,
                            continuation_token):
        """Body of the legacy block contract (capture 2026-09-23)."""
        return {
            "__RequestVerificationToken": html_form_token,
            "draw": block_index + 1,
            # "start" is always 0: each request fetches one full block from its own
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
            # Field name is "ContinuationToken" (capital C). Must be the token returned by the
            # PREVIOUS block (empty for block 0), never the current block's own token.
            "ContinuationToken": continuation_token or "",
        }

    def _get_documents_token_protocol(self, session, base_url, start_str, end_str, html_form_token,
                                      first_result=None):
        """
        Token contract: documents in "data"; while "hasMore" is true, the next page is
        requested with the "continuationToken" of the previous response.

        In this contract "recordsFiltered" is the count of the page, not of the whole range
        (capture 2026-10-06: 50 with hasMore=true), so the range total is the sum of the
        pages. If a page ever reports more records than it carries (a range total), the
        largest reported value is used instead.
        """
        documents, discarded, mapping_errors = [], [], []
        known_cufes = set()
        records_filtered = 0
        page_counts_sum = 0
        max_reported = 0
        reports_page_count = True
        total_application_response_count = 0
        continuation_token = ''
        seen_tokens = set()
        total_received = 0
        page_index = 0
        result = first_result

        while True:
            if result is None:
                result = self._post_get_documents(
                    session, base_url,
                    self._token_request_data(start_str, end_str, html_form_token, continuation_token),
                    page_index)
            raw_data = result.get('data') or []
            reported = result.get('recordsFiltered', 0) or 0
            page_counts_sum += reported
            max_reported = max(max_reported, reported)
            reports_page_count = reports_page_count and reported == len(raw_data)
            records_filtered = page_counts_sum if reports_page_count else max_reported
            has_more = bool(result.get('hasMore'))
            next_token = result.get('continuationToken') or ''
            documents_page, discarded_page, ar_count, mapping_errors_page = self._process_raw_documents(
                raw_data, known_cufes)
            self._log_documents_page(DIAN_PROTOCOL_TOKEN, page_index, records_filtered, len(raw_data),
                                     documents_page, discarded_page, ar_count, mapping_errors_page)
            documents.extend(documents_page)
            discarded.extend(discarded_page)
            mapping_errors.extend(mapping_errors_page)
            total_application_response_count += ar_count
            total_received += len(raw_data)
            page_index += 1
            if not has_more or not raw_data:
                break
            if not next_token or next_token in seen_tokens or page_index >= DIAN_MAX_PAGES:
                _logger.warning(
                    "DIAN GetDocumentsPageToken: pagination stopped at page %d (hasMore=true but "
                    "token empty, repeated or page limit reached); %d of %d records received.",
                    page_index, total_received, records_filtered,
                )
                break
            seen_tokens.add(next_token)
            continuation_token = next_token
            result = None
        self._log_total_received(total_received, records_filtered)
        return documents, discarded, records_filtered, total_application_response_count, mapping_errors

    def _get_documents_block_protocol(self, session, base_url, start_str, end_str, html_form_token):
        """
        Legacy block contract: blocks (~150 records, real size varies 96-153) read from
        "blockData"; block N+1 is requested with blockIndex=N+1, IsNextPage=true and the
        continuationToken returned by block N, until recordsFiltered records are received.
        """
        documents, discarded, mapping_errors = [], [], []
        known_cufes = set()
        records_filtered = 0
        total_application_response_count = 0
        continuation_token = ''
        total_received = 0
        block_index = 0

        while True:
            result = self._post_get_documents(
                session, base_url,
                self._block_request_data(start_str, end_str, html_form_token, block_index,
                                         continuation_token),
                block_index)
            raw_data = result.get('blockData') or []
            records_filtered = result.get('recordsFiltered', 0)
            continuation_token = result.get('continuationToken') or ''
            documents_page, discarded_page, ar_count, mapping_errors_page = self._process_raw_documents(
                raw_data, known_cufes)
            self._log_documents_page(DIAN_PROTOCOL_BLOCK, block_index, records_filtered, len(raw_data),
                                     documents_page, discarded_page, ar_count, mapping_errors_page)
            if not raw_data:
                break
            documents.extend(documents_page)
            discarded.extend(discarded_page)
            mapping_errors.extend(mapping_errors_page)
            total_application_response_count += ar_count
            total_received += len(raw_data)
            block_index += 1
            if total_received >= records_filtered or block_index >= DIAN_MAX_PAGES:
                break
        self._log_total_received(total_received, records_filtered)
        return documents, discarded, records_filtered, total_application_response_count, mapping_errors

    def _post_get_documents(self, session, base_url, request_data, page_index):
        """POST one GetDocumentsPageToken request and return its JSON."""
        api_url = f"{base_url}/Document/GetDocumentsPageToken"
        # DIAN uses ASP.NET anti-forgery (double-submit): the HTML form token (different from
        # the cookie) must arrive as a form field. JSON bodies are rejected regardless of headers.
        headers = {
            'accept': '*/*',
            'accept-language': 'es-419,es;q=0.9,en;q=0.8',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': base_url,
            'priority': 'u=1, i',
            'referer': f'{base_url}/',
            'sec-ch-ua': DIAN_SEC_CH_UA,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': DIAN_USER_AGENT,
            'x-requested-with': 'XMLHttpRequest',
        }
        _logger.info(
            "DIAN GetDocumentsPageToken request: page=%s, start=%s, end=%s, protocol=%s",
            page_index, request_data.get('StartDate'), request_data.get('EndDate'),
            DIAN_PROTOCOL_BLOCK if 'blockIndex' in request_data else DIAN_PROTOCOL_TOKEN,
        )
        try:
            t0 = time.perf_counter()
            # No redirects: DIAN redirects to its login page when the session is not valid,
            # and following it would turn that into a 200 HTML page.
            api_response = session.post(
                api_url,
                data=request_data,
                headers=headers,
                timeout=HTTP_TIMEOUT,
                allow_redirects=False,
            )
            elapsed = time.perf_counter() - t0
            _logger.info("DIAN GetDocumentsPageToken request took %.2f s (page=%s)", elapsed, page_index)
        except requests.exceptions.RequestException as e:
            raise ValidationError(
                _("Error executing request on page %d: %s") % (page_index, str(e)))
        if api_response.status_code == 403:
            raise ValidationError(
                _("Request error on page %d, status code: 403. "
                  "The session token may have expired. "
                  "Please generate a new token and try again.") % page_index)
        if api_response.status_code in (301, 302, 303, 307, 308):
            location = api_response.headers.get('Location', '')
            _logger.warning("DIAN GetDocumentsPageToken: page %s redirected (%s) to %s",
                            page_index, api_response.status_code, location)
            raise ValidationError(
                _("DIAN redirected the document query (page %(page)d) to %(location)s instead of "
                  "answering it. The DIAN session is not valid or expired: generate a new token "
                  "and try again.", page=page_index, location=location or '?'))
        if api_response.status_code != 200:
            raise ValidationError(
                _("Request error on page %d, status code: %d") % (page_index, api_response.status_code))
        try:
            return api_response.json()
        except ValueError:
            content_type = api_response.headers.get('Content-Type', '')
            body = (api_response.text or '').strip()
            _logger.warning(
                "DIAN GetDocumentsPageToken: page %s answered 200 with a non-JSON body "
                "(content-type=%r, url=%s, %d chars): %s",
                page_index, content_type, api_response.url, len(body), body[:500],
            )
            raise DianUnexpectedResponse(
                _("DIAN answered the document query (page %(page)d) with something that is not "
                  "the expected data (content type: %(type)s, %(size)s characters). The DIAN "
                  "session may have expired, or DIAN changed the service. Generate a new token "
                  "and try again; if it persists, check the server log.",
                  page=page_index, type=content_type or '?', size=len(body)))

    def _process_raw_documents(self, raw_data, known_cufes):
        """
        Turn the items of one page/block into dian.document vals.

        A document is skipped (discarded) when its CUFE is already imported, looked up by
        CUFE and not by date: DIAN filters the range by emission date, while the reception
        date can fall on a later day (e.g. emitted on the last day of the range and
        received in the evening, which is the next day in UTC).

        :param known_cufes: CUFEs already seen in this synchronization (in the database or
            in a previous page); updated in place, so a CUFE repeated by DIAN across pages
            is not created twice.
        :return: (documents, discarded, application_response_count, mapping_errors)
        """
        # Fields available in each item of the DIAN response (reference):
        # Id, DocumentTypeName, SerieAndNumber, SenderCode, SenderName, ReceiverCode,
        # ReceiverName, ReceptionDate, Status, StatusName, RadianStatusName, TotalAmount,
        # TaxAmountIva5Percent, TaxAmountIva19Percent, TaxAmountIva, TaxAmountIca, TaxAmountIpc,
        # EmissionDate, DocumentKey, DocumentTypeId, Number, Serie, TechProviderCode,
        # TechProviderName, GenerationDate, Amount, DiscrepancyCode, DiscrepancyDescription,
        # PartitionKey, DocumentTags, Events, References, TaxesDetail, createFrom,
        # ResidenceDescription, ReceiverIdTypeDescription, TokenConsulta, Identifier
        items = [item for item in raw_data if not self._is_application_response(item)]
        application_response_count = len(raw_data) - len(items)

        documents = []
        for item in items:
            document = {out_key: item.get(api_key) for api_key, out_key in DIAN_DOCUMENT_FIELD_MAP.items()}
            document.update(self._extract_taxes(item))
            documents.append(document)

        page_cufes = {d['cufe'] for d in documents if d.get('cufe')}
        known_cufes |= self._get_existing_cufes(page_cufes - known_cufes)

        kept, discarded = [], []
        for document in documents:
            cufe = document.get('cufe')
            if cufe and cufe in known_cufes:
                discarded.append(cufe)
            else:
                kept.append(document)
                if cufe:
                    known_cufes.add(cufe)

        dian_documents = []
        mapping_errors = []
        for document_received in kept:
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
        return dian_documents, discarded, application_response_count, mapping_errors

    @api.model
    def _is_application_response(self, item):
        """DIAN event (DocumentTypeId 96); the name is checked for items without the id."""
        type_id = item.get('DocumentTypeId')
        if type_id:
            return type_id == DIAN_APPLICATION_RESPONSE_TYPE_ID
        return item.get('DocumentTypeName') == 'Application response'

    @api.model
    def _extract_taxes(self, item):
        """
        Tax amounts of one item, as dian.document vals.

        DIAN reports each amount at the top level of the item and again in "TaxesDetail"
        (token contract), and either one may be 0 while the other has the value (capture
        2026-10-20: TaxAmountIva=716870 with every TaxesDetail amount at 0), so the non-zero
        one is used. When the IVA total is missing it is the sum of the IVA rates.

        The 5%/19% split usually comes as 0 at both levels. It is left at 0 instead of being
        guessed from the totals: l10n_co_bloodo fills the empty tax fields from the XML.
        """
        detail = item.get('TaxesDetail') or {}
        taxes = {
            field_name: item.get(api_key) or detail.get(api_key) or 0.0
            for field_name, api_key in DIAN_TAX_FIELD_MAP.items()
        }
        if not taxes['tax_amount_iva']:
            taxes['tax_amount_iva'] = (
                taxes['tax_amount_5_percent'] + taxes['tax_amount_19_percent']
                + sum(detail.get(key) or 0.0 for key in DIAN_TAXES_DETAIL_EXTRA_IVA_KEYS)
            )
        return taxes

    @api.model
    def _get_existing_cufes(self, cufes):
        """
        CUFEs, among `cufes`, already imported. A CUFE identifies one document, received by
        one company: it is checked in every company (sudo), not only in the companies active
        in the user's session, otherwise the result (and duplicates) would depend on the
        company switcher.
        """
        if not cufes:
            return set()
        documents = self.env['dian.document'].sudo().search_read(
            [('cufe', 'in', list(cufes))], ['cufe'])
        return {document['cufe'] for document in documents}

    @api.model
    def _log_documents_page(self, protocol, page_index, records_filtered, page_size, documents,
                            discarded, ar_count, mapping_errors):
        _logger.info(
            "DIAN GetDocumentsPageToken result (%s): page=%s, records_filtered=%s, page_size=%s, "
            "documents=%s, discarded=%s, application_responses=%s, mapping_errors=%s",
            protocol, page_index, records_filtered, page_size, len(documents), len(discarded),
            ar_count, len(mapping_errors),
        )
        if mapping_errors:
            _logger.warning(
                "DIAN GetDocumentsPageToken: %d document(s) in page %d could not be mapped: %s",
                len(mapping_errors), page_index, mapping_errors,
            )

    @api.model
    def _log_total_received(self, total_received, records_filtered):
        if total_received != records_filtered:
            _logger.warning(
                "DIAN GetDocumentsPageToken: received %d records but DIAN reported %d.",
                total_received, records_filtered,
            )

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
