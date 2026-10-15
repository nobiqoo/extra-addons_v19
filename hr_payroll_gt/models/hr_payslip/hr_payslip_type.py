# -*- coding: utf-8 -*-
from odoo import models


class HrPayslipType(models.Model):
    _inherit = 'hr.payslip.type'

    def get_categories_novelty_gt(self, categories_novelty):
        if self.id in categories_novelty:
            return
        categories_novelty[self.id] = tmp = {}
        if self.novelty_types_ids.ids:
            tmp['hr.novelty.line'] = self.novelty_types_ids.ids
        if self.leave_types_ids.ids:
            tmp['hr.leave.line'] = self.leave_types_ids.ids
        if self.overtime_types_ids.ids:
            tmp['hr.overtime'] = self.overtime_types_ids.ids

    def get_sorted_concepts_gt(self, sorted_concepts):
        if self.id in sorted_concepts:
            return
        sorted_concepts[self.id] = sorted(
            self.concepts_ids, key=lambda x: x.get_seq_concept_category_gt())
