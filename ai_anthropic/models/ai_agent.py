# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import ValidationError

from ..utils.llm_api_service import PROVIDER_NAME


class AiAgent(models.Model):
    _inherit = 'ai.agent'

    @api.constrains('llm_model', 'sources_ids')
    def _check_anthropic_sources(self):
        for agent in self:
            if agent.sources_ids and agent._get_provider() == PROVIDER_NAME:
                raise ValidationError(_(
                    "Agent %s runs on Claude and cannot have sources: Anthropic has no "
                    "embeddings API. Give the information to the agent with a tool or "
                    "in its instructions.", agent.name))


class AiAgentSource(models.Model):
    _inherit = 'ai.agent.source'

    @api.constrains('agent_id')
    def _check_anthropic_agent(self):
        self.agent_id._check_anthropic_sources()
