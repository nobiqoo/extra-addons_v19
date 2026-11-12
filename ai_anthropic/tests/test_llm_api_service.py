# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

import anthropic
import httpx2

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.ai.utils.llm_providers import get_provider

from ..utils import llm_api_service as module


def _api_message(content, stop_reason='end_turn', model='claude-opus-5-5'):
    return {
        'id': 'msg_1', 'type': 'message', 'role': 'assistant', 'model': model,
        'content': content, 'stop_reason': stop_reason, 'stop_sequence': None,
        'usage': {'input_tokens': 10, 'output_tokens': 5, 'cache_read_input_tokens': 2},
    }


@tagged('post_install', '-at_install')
class TestAnthropicProvider(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('ai.anthropic_key', 'test-key')
        self.requests = []
        self.answers = []

        def handler(request):
            self.requests.append({
                'body': json.loads(request.content),
                'headers': request.headers,
            })
            answer = self.answers.pop(0)
            if isinstance(answer, int):
                return httpx2.Response(answer, json={
                    'type': 'error', 'error': {'type': 'api_error', 'message': 'API failed'},
                })
            return httpx2.Response(200, json=answer)

        def get_client(api_key):
            return anthropic.Anthropic(
                api_key=api_key, max_retries=0,
                http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
            )

        patcher = patch.object(module, '_get_client', get_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = LLMApiService(self.env, provider='anthropic')

    def test_models_belong_to_provider(self):
        self.assertEqual(get_provider(self.env, 'claude-opus-5-5'), 'anthropic')
        selection = dict(self.env['ai.agent']._fields['llm_model']._description_selection(self.env))
        self.assertIn('claude-sonnet-5-5', selection)

    def test_other_providers_are_not_affected(self):
        self.assertEqual(LLMApiService(self.env).base_url, 'https://api.openai.com/v1')
        with self.assertRaises(NotImplementedError):
            LLMApiService(self.env, provider='other')

    def test_missing_api_key(self):
        self.env['ir.config_parameter'].sudo().set_param('ai.anthropic_key', False)
        with patch.dict('os.environ', {module.API_KEY_ENV: ''}), self.assertRaises(UserError):
            self.service._get_api_token()

    def test_simple_request(self):
        self.answers = [_api_message([{'type': 'text', 'text': 'OK'}])]
        collector = {}
        service = LLMApiService(self.env(context=dict(self.env.context, ai_usage_collector=collector)), 'anthropic')
        response = service.request_llm('claude-opus-5-5', ['System'], ['Hello'], temperature=0.2)
        self.assertEqual(response, ['OK'])
        request = self.requests[0]
        self.assertEqual(request['headers']['authorization'], 'Bearer test-key')
        self.assertIn(module.FALLBACK_BETA, request['headers']['anthropic-beta'])
        body = request['body']
        self.assertEqual(body['system'], 'System')
        self.assertEqual(body['fallbacks'], 'default')
        self.assertEqual(body['thinking'], {'type': 'adaptive'})
        self.assertEqual(body['output_config'], {'effort': 'high'})
        self.assertNotIn('temperature', body)
        self.assertEqual(collector, {
            'input_tokens': 10, 'cached_tokens': 2, 'output_tokens': 5, 'model': 'claude-opus-5-5',
        })

    def test_haiku_has_no_adaptive_parameters(self):
        self.answers = [_api_message([{'type': 'text', 'text': 'OK'}], model='claude-haiku-4-5')]
        self.service.request_llm('claude-haiku-4-5', [], ['Hello'])
        body = self.requests[0]['body']
        for key in ('thinking', 'output_config', 'fallbacks'):
            self.assertNotIn(key, body)

    def test_tool_loop_groups_results_and_echoes_thinking(self):
        thinking = {'type': 'thinking', 'thinking': '', 'signature': 'sig'}
        self.answers = [
            _api_message([
                thinking,
                {'type': 'tool_use', 'id': 'call_1', 'name': 'tool_a', 'input': {'value': 1}},
                {'type': 'tool_use', 'id': 'call_2', 'name': 'tool_a', 'input': {'value': 2}},
            ], stop_reason='tool_use'),
            _api_message([{'type': 'text', 'text': 'Done'}]),
        ]
        calls = []

        def tool(arguments):
            calls.append(arguments['value'])
            return arguments['value'] * 10, None

        tools = {'tool_a': ('A tool', False, tool, {
            'type': 'object', 'properties': {'value': {'type': 'integer'}}, 'required': ['value'],
        })}
        response = self.service.request_llm('claude-opus-5-5', [], ['Hello'], tools=tools)
        self.assertEqual(response, ['Done'])
        self.assertEqual(calls, [1, 2])
        self.assertEqual(self.requests[0]['body']['tools'][0]['name'], 'tool_a')
        messages = self.requests[1]['body']['messages']
        self.assertEqual([m['role'] for m in messages], ['user', 'assistant', 'user'])
        self.assertEqual(messages[1]['content'][0], thinking)
        self.assertEqual(
            [(b['type'], b['tool_use_id'], b['content']) for b in messages[2]['content']],
            [('tool_result', 'call_1', '10'), ('tool_result', 'call_2', '20')],
        )

    def test_structured_output(self):
        self.answers = [_api_message([{'type': 'text', 'text': '{"a": 1}'}])]
        schema = {'type': 'object', 'properties': {'a': {'type': 'integer'}},
                  'required': ['a'], 'additionalProperties': False}
        self.service.request_llm('claude-opus-5-5', [], ['Hello'], schema=schema)
        self.assertEqual(self.requests[0]['body']['output_config']['format'],
                         {'type': 'json_schema', 'schema': schema})

    def test_refusal_and_truncation_raise(self):
        for stop_reason in ('refusal', 'max_tokens'):
            self.answers = [_api_message([], stop_reason=stop_reason)]
            with self.assertRaises(UserError):
                self.service.request_llm('claude-opus-5-5', [], ['Hello'])

    def test_api_error_raises_user_error(self):
        self.answers = [400]
        with self.assertRaisesRegex(UserError, 'API failed'):
            self.service.request_llm('claude-opus-5-5', [], ['Hello'])

    def test_agent_on_claude_cannot_have_sources(self):
        agent = self.env['ai.agent'].create({'name': 'Claude', 'llm_model': 'claude-opus-5-5'})
        attachment = self.env['ir.attachment'].create({'name': 'a.txt', 'raw': b'x'})
        with self.assertRaises(ValidationError):
            self.env['ai.agent.source'].create({
                'name': 'a.txt', 'agent_id': agent.id, 'attachment_id': attachment.id,
                'type': 'binary',
            })
