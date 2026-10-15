"""
ORM utilities for database opeartions
for more information:
    https://www.psycopg.org/docs/usage.html
"""
import odoo
import logging
import psycopg2
from datetime import datetime
from psycopg2.extensions import AsIs
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
quote = '"{}"'.format


def log_message(message):
    _logger.info(message)


def create_cursor(cursor: odoo.sql_db.Cursor) -> psycopg2.extensions.cursor:
    """
    Create a new detached cursor based on input cursor parameters
    @params:
        cursor: odoo.sql_db.Cursor database cursor e.g. self.env.cr
    @return:
        cursor (psycopg2.extensions.cursor)
    """
    return cursor


def commit_cursor(cursor: psycopg2.extensions.cursor):
    cursor.connection.commit()


def fetchall(cursor: odoo.sql_db.Cursor, query, params):
    for pm in params:
        if type(params) in (list, dict, tuple):
            p = params[pm] if type(params) == dict else pm
            if type(p) in (list, tuple) and not pm:
                raise ValidationError(
                    'Los parametros listas o tuplas deben tener elementos')
    cr = create_cursor(cursor)
    cr.execute(query, params)
    return cr.fetchall()


def _fetchall(cr, query, params):
    cr.execute(query, params)
    return cr.fetchall()


def create(cursor, user, model, data, progress=False, cr_aux=False):
    """
    Hace inserts en determinada tabla
    @params:
        cursor: odoo.sql_db.Cursor database cursor e.g. self.env.cr
        user: int id del usuario e.g. self.env.uid
        model: str nombre de la tabla e.g res_partner
        data: list lista de diccionarios con llaves como nombre del campo e.g. [{'name':'hola'},{'name':'mundo'}]
        progress: bool determina si en el log se ve el progreso de la operacion
    @return:
        Lista de tuplas de un solo id e.g [(542,), (543,)]
        Tiempo trasncurrudo en la operacion
    """
    if not data:
        return
    cr, start, model, table, is_m2m = init_var(cursor, model, cr_aux)
    if not is_m2m:
        check_perm(cr, model, user, 'create')
    model_company_id = """
    SELECT name FROM ir_model_fields
    WHERE model = %(model)s AND
    relation = %(relation)s AND
    ttype = %(ttype)s
    """
    model_company_id = _fetchall(cr, model_company_id, {
                                 'model': model, 'relation': 'res.company', 'ttype': 'many2one'})
    if model_company_id:
        field_name = model_company_id[0][0]
        for d in data:
            if not (field_name in d and d[field_name]):
                raise ValidationError(
                    f'No se encontró un valor válido para {field_name} en el modelo {model}, no cumple multi-compañia')
    allow_metadata = """
    SELECT id FROM ir_model_fields
    WHERE model = %(model)s AND
    name in ('create_uid','create_date','write_uid','write_date')
    """
    allow_metadata = _fetchall(cr, allow_metadata, {'model': model})
    metadata = {} if len(allow_metadata) != 4 else {
        'create_uid': user,
        'create_date': AsIs("(now() at time zone 'UTC')"),
        'write_uid': user,
        'write_date': AsIs("(now() at time zone 'UTC')"),
    }
    ids = []
    total = len(data)
    value_eval = int(total/10) if int(total/10) > 0 else 1
    for i, d in enumerate(data):
        d.update(metadata)
        if progress and i % value_eval == 0:
            log_message(f'Creando {model}: {i+1} de {total}')

        query = "INSERT INTO {} ({}) VALUES ({}) {}".format(
            quote(table),
            ", ".join(quote(name) for name in d),
            ", ".join(f'%({name})s' for name in d),
            " " if is_m2m else "RETURNING id"
        )
        if is_m2m:
            cr.execute(query, d)
        else:
            ids.append(_fetchall(cr, query, d)[0])
    commit_cursor(cr)
    process_time = datetime.now() - start
    log_message(f'Tiempo del proceso create {model} = {process_time}')
    return ids, process_time


def update(cursor, user, model, data_update, data_where_noupdate, cr_aux=False):
    """
    Hace update en determinada tabla
    @params:
        cursor: odoo.sql_db.Cursor database cursor e.g. self.env.cr
        user: int id del usuario e.g. self.env.uid
        model: str nombre de la tabla e.g res_partner
        data_update: dict diccionario con llaves como nombre del campo, valores a actualizar e.g. {'name':'hola', 'date':'2020-01-01'}
        data_where_noupdate: dict diccionario con llaves como nombre del campo, valores de seleccion e.g. {'name':'hola', 'date':'2020-01-01'}
    @return:
        Tiempo trasncurrudo en la operacion
    """
    if not data_update or not data_where_noupdate:
        return
    cr, start, model, table, is_m2m = init_var(cursor, model, cr_aux)
    if not is_m2m:
        check_perm(cr, model, user, 'write')
    allow_metadata = """
    SELECT id FROM ir_model_fields
    WHERE model = %(model)s AND
    name in ('write_uid','write_date')
    """
    allow_metadata = _fetchall(cr, allow_metadata, {'model': model})
    metadata = {} if len(allow_metadata) != 2 else {
        'write_uid': user,
        'write_date': AsIs("(now() at time zone 'UTC')"),
    }
    param = {}
    data_where = data_where_noupdate.copy()
    set_data_where(data_where, param)
    for du in data_update:
        param[du + '_du'] = data_update[du]
    if not param:
        return
    query = "UPDATE {} SET {} WHERE {}".format(
        quote(table),
        ", ".join(f"{du} = %({du}_du)s" for du in data_update),
        "AND ".join(f"{dw} {data_where[dw]} %({dw}_dw)s" for dw in data_where)
    )
    cr.execute(query, param)
    commit_cursor(cr)
    process_time = datetime.now() - start
    log_message(f'Tiempo del proceso {model} update = {process_time}')
    return process_time


def delete(cursor, user, model, data_where_noupdate, cr_aux=False):
    """
    Hace delete en determinada tabla
    @params:
        cursor: odoo.sql_db.Cursor database cursor e.g. self.env.cr
        user: int id del usuario e.g. self.env.uid
        model: str nombre de la tabla e.g res_partner
        data_where_noupdate: dict diccionario con llaves como nombre del campo, valores de seleccion e.g. {'name':'hola', 'date':'2020-01-01'}
    @return:
        Tiempo trasncurrudo en la operacion
    """
    if not data_where_noupdate:
        return
    cr, start, model, table, is_m2m = init_var(cursor, model, cr_aux)
    if not is_m2m:
        check_perm(cr, model, user, 'unlink')
    param = {}
    data_where = data_where_noupdate.copy()
    set_data_where(data_where, param)
    if not param:
        return
    query = "DELETE FROM {} WHERE {}".format(
        quote(table),
        "AND ".join(f"{dw} {data_where[dw]} %({dw}_dw)s" for dw in data_where)
    )
    cr.execute(query, param)
    commit_cursor(cr)
    process_time = datetime.now() - start
    log_message(f'Tiempo del proceso {model} delete = {process_time}')
    return process_time


def restart_sequence(cursor: odoo.sql_db.Cursor, sequence, number):
    cr = create_cursor(cursor)
    cr.execute(f"ALTER SEQUENCE {quote(sequence)} RESTART WITH %s", [number])
    commit_cursor(cr)


def check_perm(cr, model, user, type_perm):
    # type_perm:
    # -create
    # -write
    # -unlink
    message = {'create': 'crear', 'write': 'editar', 'unlink': 'borrar'}
    access_model = """
    SELECT IMA.id
    FROM ir_model_access as IMA
    INNER JOIN ir_model as IM
        on IM.id = IMA.model_id
    INNER JOIN res_groups_users_rel as RGRU
        on RGRU.gid = IMA.group_id
    WHERE IMA.perm_{type_perm} and IMA.active
        AND IM.model = %(model)s
        AND RGRU.uid = %(user)s
    """.format(type_perm=type_perm)
    access = _fetchall(cr, access_model, {'model': model, 'user': user})
    if not access:
        raise UserError(
            'No tiene permisos para %s registros de %s' % (message[type_perm], model))


def init_var(cursor, model, cr_aux):
    cr = cr_aux if cr_aux else create_cursor(cursor)
    start = datetime.now()
    model = model.replace('_', '.')
    table = model.replace('.', '_')
    is_m2m = table[-4:] == '_rel'
    return cr, start, model, table, is_m2m


def set_data_where(data_where, param):
    keys_pop = []
    for dw in list(data_where):
        data = data_where[dw]
        if type(data) in (list, tuple):
            if not data:
                keys_pop.append(dw)
            elif len(data) == 1:
                data_where[dw] = "="
                param[dw + '_dw'] = data[0]
            else:
                data_where[dw] = "IN"
                param[dw + '_dw'] = tuple([d for d in data])
        else:
            data_where[dw] = "="
            param[dw + '_dw'] = data
    for kp in keys_pop:
        data_where.pop(kp)
