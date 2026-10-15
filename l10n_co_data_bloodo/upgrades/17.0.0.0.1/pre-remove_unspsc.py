def migrate(cr, version):
    cr.execute("""
        delete from product_unspsc_code;
    """)
    cr.execute("""
        delete from ir_model_fields where model = 'product.unspsc.code';
    """)
    cr.execute("""
        delete from ir_model where model = 'product.unspsc.code';
    """)
    cr.execute("""
        delete from ir_model_data where model = 'product.unspsc.code';
    """)
    cr.execute("""
        delete from ir_model_data where model = 'ir.model' and name ilike '%unspsc_code%';
    """)