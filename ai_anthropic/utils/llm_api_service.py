# -*- coding: utf-8 -*-
"""
Anthropic provider of the standard LLM service (odoo.addons.ai.utils).

The standard module has no extension point for providers: PROVIDERS is a module
level list and LLMApiService a plain Python class that lists them in several
methods. They are patched here, once, when this module is imported. Every patched
method falls back to the original one for any other provider, so the patch has no
effect on the agents of other providers, nor on databases of the same server that
do not have this module installed.
"""
import logging
import os

from odoo import _
from odoo.exceptions import UserError

from odoo.addons.ai.utils import llm_api_service, llm_providers
from odoo.addons.ai.utils.ai_logging import api_call_logging

_logger = logging.getLogger(__name__)

PROVIDER_NAME = 'anthropic'
API_KEY_PARAM = 'ai.anthropic_key'
API_KEY_ENV = 'ODOO_AI_ANTHROPIC_TOKEN'

MODELS = [
    ('claude-opus-5-5', 'Claude Opus 5.5'),
    ('claude-sonnet-5-5', 'Claude Sonnet 5.5'),
    ('claude-haiku-4-5', 'Claude Haiku 4.5'),
]
# Models that accept adaptive thinking and the effort parameter
ADAPTIVE_MODELS = ('claude-opus-5-5', 'claude-sonnet-5-5')
# When the safety classifiers decline a request, the API re-runs it on a fallback model
FALLBACK_BETA = 'server-side-fallback-2026-07-01'
MAX_TOKENS = 16000
TEMPERATURE_TO_EFFORT = {0.2: 'high', 0.5: 'medium', 0.8: 'low'}


def _get_client(api_key):
    # Imported here: the module is also imported on databases where it is not
    # installed, in which case external_dependencies was never checked.
    import anthropic  # noqa: PLC0415
    return anthropic.Anthropic(api_key=api_key)


def _build_file(file):
    mimetype = file['mimetype']
    if mimetype == 'text/plain':
        return {'type': 'text', 'text': file['value']}
    source = {'type': 'base64', 'media_type': mimetype, 'data': file['value']}
    if mimetype == 'application/pdf':
        return {'type': 'document', 'source': source}
    if mimetype.startswith('image/'):
        return {'type': 'image', 'source': source}
    raise UserError(_("Claude does not support files of type %s", mimetype))


def _build_messages(user_prompts, files, inputs):
    """
    Build the request messages. The service appends one input per tool result, while
    the API expects all the results of a turn in a single user message.
    """
    content = [_build_file(file) for file in files or ()]
    content += [{'type': 'text', 'text': prompt} for prompt in user_prompts or ()]
    messages = [{'role': 'user', 'content': content}] if content else []
    for message in inputs or ():
        if messages and message['role'] == 'user' and messages[-1]['role'] == 'user':
            previous = messages[-1]['content']
            if isinstance(previous, str):
                previous = [{'type': 'text', 'text': previous}]
            current = message['content']
            if isinstance(current, str):
                current = [{'type': 'text', 'text': current}]
            messages[-1] = {'role': 'user', 'content': previous + current}
        else:
            messages.append(message)
    return messages


def _build_request(llm_model, system_prompts, messages, tools, schema, temperature):
    body = {
        'model': llm_model,
        'max_tokens': MAX_TOKENS,
        'messages': messages,
        # The tools and the system prompt are repeated on every call of the tool loop
        'cache_control': {'type': 'ephemeral'},
    }
    if system_prompts:
        body['system'] = '\n\n'.join(system_prompts)
    output_config = {}
    if llm_model in ADAPTIVE_MODELS:
        body['thinking'] = {'type': 'adaptive'}
        body['betas'] = [FALLBACK_BETA]
        body['fallbacks'] = 'default'
        output_config['effort'] = TEMPERATURE_TO_EFFORT.get(temperature, 'medium')
    if schema:
        output_config['format'] = {'type': 'json_schema', 'schema': schema}
    if output_config:
        body['output_config'] = output_config
    if tools:
        body['tools'] = [{
            'name': tool_name,
            'description': tool_description,
            'input_schema': tool_parameter_schema,
        } for tool_name, (tool_description, __, __, tool_parameter_schema) in tools.items()]
    return body


def _request_llm_anthropic(
    self, llm_model, system_prompts, user_prompts, tools=None,
    files=None, schema=None, temperature=0.5, inputs=(), web_grounding=False,
):
    """Make a single request to the LLM, same contract as _request_llm_openai."""
    if web_grounding:
        raise NotImplementedError("The Anthropic provider does not support web grounding")
    messages = _build_messages(user_prompts, files, inputs)
    body = _build_request(llm_model, system_prompts, messages, tools, schema, temperature)
    with api_call_logging(messages, tools) as record_response:
        response, to_call, next_inputs, token_usage = self._request_llm_anthropic_helper(body, inputs)
        if record_response:
            record_response(to_call, response, token_usage)
        return response, to_call, next_inputs


def _request_llm_anthropic_helper(self, body, inputs=()):
    import anthropic  # noqa: PLC0415
    client = _get_client(self._get_api_token())
    try:
        if 'betas' in body:
            llm_response = client.beta.messages.create(**body)
        else:
            llm_response = client.messages.create(**body)
    except anthropic.APIStatusError as e:
        _logger.warning("Anthropic API request failed (%s): %s", e.status_code, e.message)
        raise UserError(e.message) from e
    except anthropic.APIConnectionError as e:
        _logger.warning("Anthropic API connection failed: %s", e)
        raise UserError(_("Could not connect to the Anthropic API: %s", e)) from e

    if llm_response.stop_reason == 'refusal':
        raise UserError(_("Claude declined to process this request."))
    if llm_response.stop_reason == 'max_tokens':
        # A tool call cut by the limit has incomplete arguments, it must not be run
        raise UserError(_("Claude reached the maximum response size before finishing."))

    to_call = [
        (block.name, block.id, block.input)
        for block in llm_response.content if block.type == 'tool_use'
    ]
    next_inputs = list(inputs or ())
    response = []
    if to_call:
        # Echoed unchanged: thinking blocks are only valid in their original form
        next_inputs.append({
            'role': 'assistant',
            'content': [block.to_dict() for block in llm_response.content],
        })
    else:
        response = [block.text for block in llm_response.content if block.type == 'text']

    usage = llm_response.usage
    token_usage = {
        'input_tokens': usage.input_tokens or 0,
        'cached_tokens': getattr(usage, 'cache_read_input_tokens', 0) or 0,
        'output_tokens': usage.output_tokens or 0,
    }
    # Callers that report consumption (usage per run, per company...) pass a dict
    collector = self.env.context.get('ai_usage_collector')
    if collector is not None:
        for key, value in token_usage.items():
            collector[key] = collector.get(key, 0) + value
        collector['model'] = llm_response.model
    return response, to_call, next_inputs, token_usage


def _patch():
    service = llm_api_service.LLMApiService
    if hasattr(service, '_request_llm_anthropic'):
        return

    llm_providers.PROVIDERS.append(llm_providers.Provider(
        PROVIDER_NAME, 'Anthropic', '', {}, MODELS, [], {},
    ))

    original_init = service.__init__
    original_get_api_token = service._get_api_token
    original_request_llm = service._request_llm
    original_build_tool_call_response = service._build_tool_call_response

    def __init__(self, env, provider='openai'):
        if provider != PROVIDER_NAME:
            return original_init(self, env, provider)
        self.provider = provider
        self.base_url = None
        self.env = env

    def _get_api_token(self):
        if self.provider != PROVIDER_NAME:
            return original_get_api_token(self)
        api_key = self.env['ir.config_parameter'].sudo().get_param(API_KEY_PARAM) or os.getenv(API_KEY_ENV)
        if not api_key:
            raise UserError(_("No API key set for provider '%s'", self.provider))
        return api_key

    def _request_llm(self, *args, **kwargs):
        if self.provider != PROVIDER_NAME:
            return original_request_llm(self, *args, **kwargs)
        return self._request_llm_anthropic(*args, **kwargs)

    def _build_tool_call_response(self, tool_call_id, return_value):
        if self.provider != PROVIDER_NAME:
            return original_build_tool_call_response(self, tool_call_id, return_value)
        return {
            'role': 'user',
            'content': [{
                'type': 'tool_result',
                'tool_use_id': tool_call_id,
                'content': str(return_value),
            }],
        }

    service.__init__ = __init__
    service._get_api_token = _get_api_token
    service._request_llm = _request_llm
    service._build_tool_call_response = _build_tool_call_response
    service._request_llm_anthropic = _request_llm_anthropic
    service._request_llm_anthropic_helper = _request_llm_anthropic_helper


_patch()
