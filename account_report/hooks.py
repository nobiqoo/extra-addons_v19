
def post_init_hook(env):

    query = '''
    update account_group ag
    set parent_id = agp.id
    from account_group agp
    where agp.code = left(ag.code, -2)
    and ag.id != agp.id;
    '''
    env.cr.execute(query)

    query = '''
    update account_group ag
    set parent_id = agp.id
    from account_group agp
    where agp.code = left(ag.code, -1)
    and ag.id != agp.id
    and length(ag.code) = 2;
    '''
    env.cr.execute(query)

