import base64

from odoo.tools.misc import file_open

# Menú principal replicado del sitio adipack.com.co: (nombre, url, submenús)
# En Odoo un menú con submenús no puede tener enlace propio, por eso la página
# general de cada grupo queda como primer submenú.
MAIN_MENU = [
    ('INICIO', '/', []),
    ('ENVASADORAS ASÉPTICAS', '/envasadoras-asepticas', [
        ('Envasadoras Asépticas', '/envasadoras-asepticas'),
        ('Envasadora Aséptica ADIAS G8', '/envasadoras-asepticas-adias-g8'),
        ('Envasadora para productos viscosos', '/envasadora-productos-viscosos'),
        ('Envasadora ULTRALIMPIA', '/envasadora-ultralimpia'),
        ('Envasadoras ADI 1X27', '/envasadoras-adi-1x27'),
    ]),
    ('EQUIPOS DE PROCESO', '/equipos-de-proceso', [
        ('Equipos de Proceso', '/equipos-de-proceso'),
        ('Esterilizadores UHT', '/esterilizadores-uht'),
        ('Dosificador Aséptico', '/dosificador-aseptico'),
        ('Pasteurizadores HTST', '/pasteurizadores-htst'),
        ('Homogeneizadores', '/homogeneizadores'),
        ('Centrífuga Higienizadora y Descremadoras', '/centrifuga-higienizadora-y-descremadoras'),
        ('Bactofugadoras', '/bactofugadoras'),
    ]),
    ('NUESTRA EMPRESA', '/nuestra-empresa', []),
    ('ALIADOS', '/aliados', []),
    ('EVENTOS', '/eventos', []),
    ('SERVICIOS', '/servicios', []),
    ('CONTACTAR', '/contactar', []),
    ('/ENGLISH', '/adipack-adinox-aseptic-pouch-packaging-machines-for-dairy-products-flexible-bag', []),
]

# Menú de las páginas en inglés del sitio original
EN_MENU = [
    ('HOME', '/adipack-adinox-aseptic-pouch-packaging-machines-for-dairy-products-flexible-bag', []),
    ('ASEPTIC POUCH PACKAGING MACHINES', '/aseptic-pouch-packaging-machines', [
        ('Aseptic Pouch Packaging Machines', '/aseptic-pouch-packaging-machines'),
        ('ASEPTIC FORM/FILL/SEAL MACHINES ADIAS G8', '/aseptic-form-fill-seal-machines-adias-g8'),
        ('ASEPTIC FILLING MACHINE FOR VISCOUS PRODUCTS', '/aseptic-filling-machine-for-viscous-products'),
        ('PACKAGING MACHINE TYPE HIGH-HYGIENE / ULTRA CLEAN', '/packaging-machine-type-high-hygiene-ultra-clean'),
        ('ASEPTIC POUCH PACKAGING MACHINE ADI 1X27', '/aseptic-pouch-packaging-machine-adi-1x27'),
    ]),
    ('PROCESS EQUIPMENT', '/process-equipment', [
        ('Process Equipment', '/process-equipment'),
        ('UHT Sterilizer', '/uht-sterilizer'),
        ('Aseptic Dosing Unit', '/aseptic-dosing-unit'),
        ('HTST Pasteurizers', '/htst-pasteurizers'),
        ('Homogenizers', '/homogenizers'),
        ('Hygienizing centrifuge machine and milk skimming centrifuge', '/hygienizing-centrifuge-machine-and-milk-skimming-centrifuge'),
        ('Bactofuge Units', '/bactofuge-units'),
    ]),
    ('OUR COMPANY', '/our-company', []),
    ('ALLIES', '/allies', []),
    ('EVENTS', '/events', []),
    ('SERVICES', '/services', []),
    ('CONTACT US', '/contact-us', []),
    ('/ESPAÑOL', '/', []),
]

LOGO_PATH = 'website_adipack/static/src/uploads/2018/01/adinox-adipack-logo-resplandor-ext-20182-2.png'


def _create_menu_items(env, website, root, items):
    Menu = env['website.menu']
    for seq, (name, url, children) in enumerate(items, start=1):
        parent = Menu.create({
            'name': name,
            'url': url,
            'parent_id': root.id,
            'website_id': website.id,
            'sequence': seq * 10,
        })
        for sub_seq, (sub_name, sub_url) in enumerate(children, start=1):
            Menu.create({
                'name': sub_name,
                'url': sub_url,
                'parent_id': parent.id,
                'website_id': website.id,
                'sequence': sub_seq * 10,
            })


def _setup_menu(env, website):
    website.adipack_menu_en_id.unlink()
    root = website.menu_id
    root.child_id.unlink()
    _create_menu_items(env, website, root, MAIN_MENU)
    # Segunda raíz (después de la principal) con el menú de las páginas en inglés
    root_en = env['website.menu'].create({
        'name': 'English Menu',
        'website_id': website.id,
        'sequence': root.sequence + 1000,
    })
    _create_menu_items(env, website, root_en, EN_MENU)
    website.adipack_menu_en_id = root_en


def _post_init_hook(env):
    with file_open(LOGO_PATH, 'rb') as f:
        logo = base64.b64encode(f.read())
    # El sitio actual es en español; la versión en inglés son páginas propias.
    lang_es = env['res.lang']._activate_lang('es_CO')
    for website in env['website'].search([]):
        website.write({
            'name': 'Adipack - Adinox',
            'logo': logo,
            'language_ids': [(6, 0, lang_es.ids)],
            'default_lang_id': lang_es.id,
            'social_facebook': 'https://www.facebook.com/adipack.com.co',
            'social_youtube': 'https://www.youtube.com/channel/UC1kDTGruVSdEmT3gQe5xrJQ/videos',
        })
        _setup_menu(env, website)
        # Cabecera: logo centrado arriba y menú centrado debajo, como en el sitio actual.
        # Se aplica igual que desde el editor, para que el cliente pueda cambiarla después.
        theme_utils = env['theme.utils'].with_context(website_id=website.id)
        theme_utils.enable_view('website.template_header_vertical')
        theme_utils.enable_view('website.template_header_vertical_align_center')
        # El sitio actual no tiene inicio de sesión, texto ni botón de llamado a la acción en la cabecera.
        theme_utils.disable_view('portal.user_sign_in')
        theme_utils.disable_view('website.header_text_element')
        theme_utils.disable_view('website.header_call_to_action')
