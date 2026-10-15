# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Vincula los productos que ya estaban replicados a mano entre compañías.

    Se agrupan por referencia interna (`default_code`). Un grupo solo se vincula si
    tiene como máximo un producto por compañía; los grupos ambiguos se dejan intactos
    y se reportan en el log para revisión manual.
    """
    env.cr.execute("""
        SELECT pp.default_code,
               pt.company_id,
               array_agg(pt.id ORDER BY pt.id) AS template_ids
          FROM product_product pp
          JOIN product_template pt ON pt.id = pp.product_tmpl_id
         WHERE pp.default_code IS NOT NULL
           AND btrim(pp.default_code) <> ''
           AND pt.company_id IS NOT NULL
      GROUP BY pp.default_code, pt.company_id
      ORDER BY pp.default_code
    """)

    by_code = {}
    for default_code, _company_id, template_ids in env.cr.fetchall():
        by_code.setdefault(default_code, []).append(template_ids)

    linked_groups = 0
    linked_templates = 0
    skipped = []

    for default_code, per_company in by_code.items():
        if len(per_company) < 2:
            # Presente en una sola compañía: no hay nada que vincular.
            continue
        if any(len(ids) > 1 for ids in per_company):
            # Referencia duplicada dentro de una misma compañía: ambiguo.
            skipped.append(default_code)
            continue

        template_ids = sorted(ids[0] for ids in per_company)
        origin_id, replica_ids = template_ids[0], template_ids[1:]

        env.cr.execute("""
            UPDATE product_template
               SET replica_origin_id = %s
             WHERE id IN %s
               AND replica_origin_id IS NULL
        """, (origin_id, tuple(replica_ids)))
        newly_linked = env.cr.rowcount

        if newly_linked:
            # Apuntador many2many: mantiene la relación completa desde el origen.
            for replica_id in replica_ids:
                env.cr.execute("""
                    INSERT INTO product_template_replica_rel (origin_id, replica_id)
                    SELECT %(origin_id)s, %(replica_id)s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM product_template_replica_rel
                         WHERE origin_id = %(origin_id)s AND replica_id = %(replica_id)s
                    )
                """, {'origin_id': origin_id, 'replica_id': replica_id})

        linked_groups += 1
        linked_templates += newly_linked

    _logger.info(
        'product_company_replication: %s grupos vinculados (%s productos) '
        'a partir de la referencia interna.',
        linked_groups, linked_templates,
    )
    if skipped:
        _logger.warning(
            'product_company_replication: %s referencia(s) no vinculadas por estar '
            'duplicadas dentro de una misma compañía, requieren revisión manual: %s',
            len(skipped), ', '.join(sorted(skipped)[:20]),
        )
