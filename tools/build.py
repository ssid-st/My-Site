#!/usr/bin/env python3
"""
Build the static site.

  python3 tools/build.py                  # regenerate pages, covers and WebP images
  python3 tools/build.py --src ORIGINALS  # also re-import photos from a folder of originals

The site is built in three languages: English in the root folder,
German in de/ and Russian in ru/. All texts live in the T dictionary below.

Photos:
  portfolio/<section>/<album>/NN.jpg   master copies (max 1600 px, no EXIF/GPS)
  img/<section>/<album>/NN-800.webp    generated, phones and small screens
  img/<section>/<album>/NN-1600.webp   generated, large screens
  img/<section>/<album>/cover-*.webp   generated 4:5 album covers

WebP files are only regenerated when the JPEG is newer, so a rebuild is quick.

To add an album: put its photos into portfolio/<section>/<new-album>/
(or into the originals folder and use --src), optionally add a title in
ALBUM_TITLES below, and run the script again. Commit the result.

Needs Pillow:  pip install Pillow
"""
import argparse
import base64
import html
import io
import json
import os
import re
import shutil
import sys
from datetime import date

from PIL import Image, ImageChops, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = os.path.join(ROOT, 'portfolio')
IMG = os.path.join(ROOT, 'img')

MAX_SIDE = 1600          # long side of master JPEGs
SIZES = (800, 1600)      # long side of generated WebP files
COVER_W, COVER_H = 480, 600   # 4:5 album covers (plus a 2x copy)
QUALITY = 82
WEBP_QUALITY = 78
COVER_NAME = 'cover.jpg'  # old square covers, still used by the archived versions

SITE_NAME = 'Stanislav Sydorov'
SECTION_KEYS = ['projects', 'lovestory', 'weddings', 'beauty', 'campaign', 'sport', 'boudoir']

# Languages: code -> output folder ('' is the site root)
LANGS = [('en', ''), ('de', 'de'), ('ru', 'ru')]
LANG_NAMES = {'en': 'EN', 'de': 'DE', 'ru': 'RU'}

# Every text on the site, per language.
T = {
    'en': {
        'desc': 'Stanislav Sydorov, photographer. Love story, wedding, beauty, campaign, sport and boudoir photography.',
        'photography': 'Photography', 'photographer': 'Photographer',
        'h1_home': 'Stanislav Sydorov, photographer',
        'menu': 'Menu', 'close': 'Close', 'skip': 'Skip to content', 'main_nav': 'Main',
        'theme': 'Switch light or dark theme', 'language': 'Language',
        'sections': {
            'projects': ('Projects', 'Personal and creative photo projects.'),
            'lovestory': ('Love story', 'Love story photo sessions.'),
            'weddings': ('Weddings', 'Wedding day photography.'),
            'beauty': ('Beauty', 'Beauty and portrait photography.'),
            'campaign': ('Campaign', 'Commercial and fashion campaigns.'),
            'sport': ('Sport', 'Sport and fitness photography.'),
            'boudoir': ('Boudoir', 'Boudoir photography.'),
        },
        'contact': 'Contact', 'contact_title': 'Contact & prices',
        'contact_desc': 'Book a photo session with Stanislav Sydorov: Instagram, Telegram, Viber, e-mail.',
        'contact_intro': 'To book a photo session or ask about prices, write to me in any messenger or by e-mail. '
                         'I will reply as soon as possible.',
        'phone': 'Phone', 'email': 'E-mail',
        'tap': 'Tap an album to view it.',
        'open_album': 'Open album {name}, {count}',
        'view_gallery': 'View gallery', 'selected': 'Selected photos',
        'prev': 'Previous', 'next': 'Next', 'slide': 'Slide',
        'viewer': 'Photo viewer', 'prev_photo': 'Previous photo', 'next_photo': 'Next photo', 'photo': 'photo',
        'not_found_title': 'Page not found', 'not_found': 'This page does not exist.', 'home': 'Go to the home page',
        'rights': 'All rights reserved.', 'versions': 'Site versions',
        'genres': 'Genres', 'selected_works': 'Selected works', 'albums_n': 'albums',
        'cta_title': 'Let’s create something beautiful together',
        'cta_text': 'Tell me about your idea, and I will suggest a location, a mood and a date.',
        'book': 'Book a session', 'view': 'View', 'scroll': 'Scroll',
        'form_title': 'Book a session', 'form_intro': 'Leave a request and I will get back to you within a day.',
        'f_name': 'Your name', 'f_contact': 'Phone, e-mail or Telegram', 'f_type': 'Type of shoot',
        'f_type_any': 'Not sure yet', 'f_date': 'Preferred date', 'f_msg': 'Your idea (optional)',
        'f_send': 'Send request', 'f_sending': 'Sending…',
        'f_ok': 'Thank you! Your request has been sent. I will reply soon.',
        'f_err': 'The request could not be sent. Please write to me directly:',
        'or_write': 'Or write to me directly:',
        'albums': {'wedding-day': 'Wedding day'},
    },
    'de': {
        'desc': 'Stanislav Sydorov, Fotograf. Love Story, Hochzeit, Beauty, Kampagnen, Sport und Boudoir.',
        'photography': 'Fotografie', 'photographer': 'Fotograf',
        'h1_home': 'Stanislav Sydorov, Fotograf',
        'menu': 'Menü', 'close': 'Schließen', 'skip': 'Zum Inhalt springen', 'main_nav': 'Hauptmenü',
        'theme': 'Helles oder dunkles Design', 'language': 'Sprache',
        'sections': {
            'projects': ('Projekte', 'Persönliche und kreative Fotoprojekte.'),
            'lovestory': ('Love Story', 'Love-Story-Fotoshootings für Paare.'),
            'weddings': ('Hochzeiten', 'Hochzeitsfotografie.'),
            'beauty': ('Beauty', 'Beauty- und Porträtfotografie.'),
            'campaign': ('Kampagnen', 'Werbe- und Modekampagnen.'),
            'sport': ('Sport', 'Sport- und Fitnessfotografie.'),
            'boudoir': ('Boudoir', 'Boudoir-Fotografie.'),
        },
        'contact': 'Kontakt', 'contact_title': 'Kontakt & Preise',
        'contact_desc': 'Fotoshooting bei Stanislav Sydorov buchen: Instagram, Telegram, Viber, E-Mail.',
        'contact_intro': 'Um ein Fotoshooting zu buchen oder nach Preisen zu fragen, schreiben Sie mir in einem '
                         'beliebigen Messenger oder per E-Mail. Ich antworte so schnell wie möglich.',
        'phone': 'Telefon', 'email': 'E-Mail',
        'tap': 'Tippen Sie auf ein Album, um es zu öffnen.',
        'open_album': 'Album {name} öffnen, {count}',
        'view_gallery': 'Zur Galerie', 'selected': 'Ausgewählte Fotos',
        'prev': 'Zurück', 'next': 'Weiter', 'slide': 'Bild',
        'viewer': 'Fotoansicht', 'prev_photo': 'Vorheriges Foto', 'next_photo': 'Nächstes Foto', 'photo': 'Foto',
        'not_found_title': 'Seite nicht gefunden', 'not_found': 'Diese Seite existiert nicht.', 'home': 'Zur Startseite',
        'rights': 'Alle Rechte vorbehalten.', 'versions': 'Versionen der Website',
        'genres': 'Genres', 'selected_works': 'Ausgewählte Arbeiten', 'albums_n': 'Alben',
        'cta_title': 'Lassen Sie uns gemeinsam etwas Schönes schaffen',
        'cta_text': 'Erzählen Sie mir von Ihrer Idee, und ich schlage Ort, Stimmung und Termin vor.',
        'book': 'Shooting buchen', 'view': 'Ansehen', 'scroll': 'Scrollen',
        'form_title': 'Shooting buchen', 'form_intro': 'Hinterlassen Sie eine Anfrage, ich melde mich innerhalb eines Tages.',
        'f_name': 'Ihr Name', 'f_contact': 'Telefon, E-Mail oder Telegram', 'f_type': 'Art des Shootings',
        'f_type_any': 'Noch unsicher', 'f_date': 'Wunschtermin', 'f_msg': 'Ihre Idee (optional)',
        'f_send': 'Anfrage senden', 'f_sending': 'Wird gesendet…',
        'f_ok': 'Vielen Dank! Ihre Anfrage wurde gesendet. Ich antworte bald.',
        'f_err': 'Die Anfrage konnte nicht gesendet werden. Bitte schreiben Sie mir direkt:',
        'or_write': 'Oder schreiben Sie mir direkt:',
        'albums': {'wedding-day': 'Hochzeitstag'},
    },
    'ru': {
        'desc': 'Stanislav Sydorov, фотограф. Love story, свадьбы, бьюти, реклама, спорт и будуар.',
        'photography': 'фотограф', 'photographer': 'фотограф',
        'h1_home': 'Stanislav Sydorov, фотограф',
        'menu': 'Меню', 'close': 'Закрыть', 'skip': 'Перейти к содержимому', 'main_nav': 'Главное меню',
        'theme': 'Светлая или тёмная тема', 'language': 'Язык',
        'sections': {
            'projects': ('Проекты', 'Личные и творческие фотопроекты.'),
            'lovestory': ('Love story', 'Фотосессии love story для пар.'),
            'weddings': ('Свадьбы', 'Свадебная фотосъёмка.'),
            'beauty': ('Бьюти', 'Бьюти и портретная съёмка.'),
            'campaign': ('Реклама', 'Рекламные и fashion-съёмки.'),
            'sport': ('Спорт', 'Спортивная и фитнес-съёмка.'),
            'boudoir': ('Будуар', 'Будуарная фотосъёмка.'),
        },
        'contact': 'Контакты', 'contact_title': 'Контакты и цены',
        'contact_desc': 'Записаться на фотосессию к Stanislav Sydorov: Instagram, Telegram, Viber, e-mail.',
        'contact_intro': 'Чтобы записаться на фотосессию или узнать цены, напишите мне в любом мессенджере '
                         'или на e-mail. Я отвечу как можно скорее.',
        'phone': 'Телефон', 'email': 'E-mail',
        'tap': 'Нажмите на альбом, чтобы открыть его.',
        'open_album': 'Открыть альбом {name}, {count}',
        'view_gallery': 'Смотреть галерею', 'selected': 'Избранные фото',
        'prev': 'Назад', 'next': 'Вперёд', 'slide': 'Слайд',
        'viewer': 'Просмотр фото', 'prev_photo': 'Предыдущее фото', 'next_photo': 'Следующее фото', 'photo': 'фото',
        'not_found_title': 'Страница не найдена', 'not_found': 'Такой страницы нет.', 'home': 'На главную',
        'rights': 'Все права защищены.', 'versions': 'Версии сайта',
        'genres': 'Жанры', 'selected_works': 'Избранные работы', 'albums_n': 'альб.',
        'cta_title': 'Давайте создадим что-то красивое вместе',
        'cta_text': 'Расскажите о своей идее, а я предложу место, настроение и дату.',
        'book': 'Записаться', 'view': 'Смотреть', 'scroll': 'Листайте',
        'form_title': 'Запись на съёмку', 'form_intro': 'Оставьте заявку, и я отвечу в течение дня.',
        'f_name': 'Ваше имя', 'f_contact': 'Телефон, e-mail или Telegram', 'f_type': 'Тип съёмки',
        'f_type_any': 'Пока не знаю', 'f_date': 'Желаемая дата', 'f_msg': 'Ваша идея (необязательно)',
        'f_send': 'Отправить заявку', 'f_sending': 'Отправляю…',
        'f_ok': 'Спасибо! Заявка отправлена, я скоро отвечу.',
        'f_err': 'Не получилось отправить заявку. Напишите мне напрямую:',
        'or_write': 'Или напишите мне напрямую:',
        'albums': {'wedding-day': 'День свадьбы'},
    },
}


def count_label(lang, n):
    if lang == 'de':
        return f'{n} Foto' + ('' if n == 1 else 's')
    if lang == 'ru':
        return f'{n} фото'
    return f'{n} photo' + ('' if n == 1 else 's')


# Nice names for album folders; anything missing is just capitalised.
ALBUM_TITLES = {
    'evgengala': 'Evgen & Gala',
    'romanmiroslava': 'Roman & Miroslava',
    'sergesasha': 'Serge & Sasha',
    'andrewvictoria': 'Andrew & Victoria',
    'juliaanton': 'Julia & Anton',
    'wedding-day': 'Wedding day',
    'nataly2': 'Nataly II',
    'kate2': 'Kate II',
    'victory': 'Victoria',
}

# Which photo becomes the 4:5 album cover ("section/album": "file").
# Albums not listed use their first photo. Projects match their old hand-made
# square previews automatically (see pick_cover_photo).
COVER_PHOTOS = {}

# Used only with --src: map original folders to new ones.
SRC_RENAMES = {
    'weddings/3': 'weddings/wedding-day',
    'projects/cat': 'projects',          # projects/cat/<album> -> projects/<album>
}
SRC_SKIP_DIRS = {'dist1', 'css', 'js', 'ico', 'icons', 'preview'}
SRC_PROJECT_PREVIEWS = {
    'alina': 'alinapr.jpg', 'art': 'artpr.jpg', 'kira': 'kirapr.jpg',
    'ksusha': 'ksushapr.jpg', 'nastya': 'nastyapr.jpg', 'nataly': 'natalipr.jpg',
    'olga': 'olgapr.jpg', 'spring': 'springpr.jpg', 'valeria': 'valeryapr.jpg',
    'victory': 'victorypr.jpg',
}

# Home page carousel: (photo, section)
CAROUSEL = [
    ('portfolio/beauty/kate/01.jpg', 'beauty'),
    ('portfolio/weddings/wedding-day/001.jpg', 'weddings'),
    ('portfolio/projects/art/01.jpg', 'projects'),
    ('portfolio/lovestory/evgengala/01.jpg', 'lovestory'),
    ('portfolio/campaign/kate2/01.jpg', 'campaign'),
    ('portfolio/beauty/nastya/01.jpg', 'beauty'),
    ('portfolio/weddings/andrewvictoria/01.jpg', 'weddings'),
    ('portfolio/sport/marina/01.jpg', 'sport'),
    ('portfolio/projects/spring/01.jpg', 'projects'),
    ('portfolio/campaign/tina/01.jpg', 'campaign'),
    ('portfolio/beauty/helen/01.jpg', 'beauty'),
    ('portfolio/projects/valeria/01.jpg', 'projects'),
]
CAROUSEL_INTERVAL = 5500   # ms per slide

CONTACTS = [
    # (key, label or text key, value, url, icon, opens new tab)
    ('instagram', 'Instagram', '@sidssphoto', 'https://www.instagram.com/sidssphoto/', 'instagram.png', True),
    ('facebook', 'Facebook', 'ssidorovphoto', 'https://www.facebook.com/ssidorovphoto/', 'facebook.png', True),
    ('telegram', 'Telegram', '@sidssphoto', 'https://t.me/sidssphoto', 'telegram.png', True),
    ('phone', 'phone', '+49 160 454 21 87', 'tel:+491604542187', 'phone.png', False),
    ('viber', 'Viber', '+49 160 454 21 87', 'viber://chat?number=%2B491604542187', 'viber.png', False),
    ('email', 'email', 'sidssphoto@icloud.com', 'mailto:sidssphoto@icloud.com', 'mail.png', False),
]

IMG_EXT = ('.jpg', '.jpeg')
NEW_TAB = ' target="_blank" rel="noopener noreferrer"'
e = html.escape


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------
def save_jpeg(im, path, quality=QUALITY):
    icc = im.info.get('icc_profile')
    im = im.convert('RGB')
    kwargs = dict(quality=quality, optimize=True, progressive=True)
    if icc:
        kwargs['icc_profile'] = icc
    im.save(path, 'JPEG', **kwargs)    # no exif= -> metadata (incl. GPS) dropped


def save_webp(im, path, quality=WEBP_QUALITY):
    icc = im.info.get('icc_profile')
    kwargs = dict(quality=quality, method=6)
    if icc:
        kwargs['icc_profile'] = icc
    im.convert('RGB').save(path, 'WEBP', **kwargs)


def load(path):
    im = Image.open(path)
    icc = im.info.get('icc_profile')
    im = ImageOps.exif_transpose(im)   # bake rotation in before EXIF is dropped
    if icc:
        im.info['icc_profile'] = icc
    return im


def optimise(src, dst):
    im = load(src)
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    save_jpeg(im, dst)


def make_cover(src, dst):
    im = load(src)
    icc = im.info.get('icc_profile')
    im = ImageOps.fit(im, (600, 600), Image.LANCZOS)
    if icc:
        im.info['icc_profile'] = icc
    save_jpeg(im, dst, quality=78)


def fresh(dst, src):
    return os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src)


def lqip(im):
    """Tiny blurred placeholder as a data: URI (about 150-300 bytes)."""
    small = im.convert('RGB').copy()
    small.thumbnail((16, 16), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, 'WEBP', quality=40)
    return 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode()


_meta_cache = {}


def photo_meta(rel_jpg):
    """Make the WebP copies of a master JPEG; return (base, width, height, lqip).

    base is the WebP path without '-800.webp' / '-1600.webp'."""
    if rel_jpg in _meta_cache:
        return _meta_cache[rel_jpg]
    src = os.path.join(ROOT, rel_jpg)
    parts = rel_jpg.split('/')            # portfolio/<section>/<album>/<file>
    stem = os.path.splitext(parts[-1])[0]
    out_dir = os.path.join(IMG, *parts[1:-1])
    os.makedirs(out_dir, exist_ok=True)
    im = load(src)
    w, h = im.size
    for size in SIZES:
        dst = os.path.join(out_dir, f'{stem}-{size}.webp')
        if not fresh(dst, src):
            copy = im.copy()
            copy.thumbnail((size, size), Image.LANCZOS)
            save_webp(copy, dst)
    base = 'img/' + '/'.join(parts[1:-1]) + '/' + stem
    _meta_cache[rel_jpg] = (base, w, h, lqip(im))
    return _meta_cache[rel_jpg]


def similarity(a, b):
    a = list(a.convert('L').resize((16, 16)).tobytes())
    b = list(b.convert('L').resize((16, 16)).tobytes())
    return sum((x - y) ** 2 for x, y in zip(a, b))


def pick_cover_photo(section, album, photos):
    key = f'{section}/{album}'
    if key in COVER_PHOTOS:
        return COVER_PHOTOS[key]
    square = os.path.join(PORTFOLIO, section, album, COVER_NAME)
    if section == 'projects' and os.path.exists(square):
        # find the album photo the old hand-made square preview was cut from
        prev = Image.open(square)
        best = min(photos, key=lambda p: similarity(
            ImageOps.fit(Image.open(os.path.join(PORTFOLIO, section, album, p)), (64, 64)), prev))
        return best
    return photos[0]


def trim_border(im):
    """Cut off a plain white or black frame around a photo (only used for covers)."""
    rgb = im.convert('RGB')
    corner = rgb.getpixel((0, 0))
    if not (min(corner) > 235 or max(corner) < 20):
        return im
    diff = ImageChops.difference(rgb, Image.new('RGB', rgb.size, corner)).convert('L')
    box = diff.point(lambda v: 255 if v > 24 else 0).getbbox()
    if not box or (box[2] - box[0]) * (box[3] - box[1]) < 0.5 * rgb.size[0] * rgb.size[1]:
        return im
    return im.crop(box)


def make_cover_webp(section, album, photo):
    """4:5 covers in two sizes; returns (path of 1x, path of 2x, lqip)."""
    src = os.path.join(PORTFOLIO, section, album, photo)
    out_dir = os.path.join(IMG, section, album)
    os.makedirs(out_dir, exist_ok=True)
    marker = os.path.join(out_dir, 'cover.txt')
    im = None
    paths = []
    for scale in (1, 2):
        dst = os.path.join(out_dir, f'cover-{COVER_W * scale}.webp')
        paths.append(f'img/{section}/{album}/cover-{COVER_W * scale}.webp')
        same = os.path.exists(marker) and open(marker).read() == photo
        if not (same and fresh(dst, src)):
            im = im or trim_border(load(src))
            fit = ImageOps.fit(im, (COVER_W * scale, COVER_H * scale), Image.LANCZOS, centering=(0.5, 0.3))
            save_webp(fit, dst, quality=74)
    with open(marker, 'w') as f:
        f.write(photo)
    with Image.open(os.path.join(ROOT, paths[0])) as small:
        return paths[0], paths[1], lqip(small)


def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


def is_duplicate_copy(name, names):
    """'119(1).jpg' when '119.jpg' also exists."""
    m = re.match(r'^(.*)\(\d+\)(\.[^.]+)$', name)
    return bool(m) and any(n.lower() == (m.group(1) + m.group(2)).lower() for n in names)


def import_originals(src_root):
    previews_dir = os.path.join(src_root, 'projects', 'preview')
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = sorted(d for d in dirnames if d not in SRC_SKIP_DIRS)
        photos = sorted((f for f in filenames if f.lower().endswith(IMG_EXT)
                         and not is_duplicate_copy(f, filenames)), key=natural_key)
        if not photos:
            continue
        rel = os.path.relpath(dirpath, src_root).replace(os.sep, '/')
        for old, new in SRC_RENAMES.items():
            if rel == old or rel.startswith(old + '/'):
                rel = new + rel[len(old):]
                break
        out = os.path.join(PORTFOLIO, rel)
        if os.path.isdir(out):
            shutil.rmtree(out)
        os.makedirs(out)
        width = max(2, len(str(len(photos))))
        for i, name in enumerate(photos, 1):
            optimise(os.path.join(dirpath, name), os.path.join(out, f'{i:0{width}d}.jpg'))
        album = os.path.basename(rel)
        preview = SRC_PROJECT_PREVIEWS.get(album)
        if rel.startswith('projects/') and preview and os.path.exists(os.path.join(previews_dir, preview)):
            make_cover(os.path.join(previews_dir, preview), os.path.join(out, COVER_NAME))
        print(f'  {rel}: {len(photos)} photos')


def album_photos(album_dir):
    return sorted((f for f in os.listdir(album_dir)
                   if f.lower().endswith(IMG_EXT) and f != COVER_NAME), key=natural_key)


def album_title(slug, lang='en'):
    return T[lang]['albums'].get(slug) or ALBUM_TITLES.get(slug, slug.replace('-', ' ').capitalize())


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
# Requests from the booking form are e-mailed by FormSubmit (no account needed).
# The very first request sends an activation e-mail to this address: confirm it once.
FORM_EMAIL = 'sidssphoto@icloud.com'
FORM_ENDPOINT = f'https://formsubmit.co/ajax/{FORM_EMAIL}'

NAV_IMAGES = {}

# Home page "Selected works": photos from the carousel list, shown in two staggered columns
SELECTED = [1, 3, 4, 6, 7, 9, 10, 11]

ICON_SUN = ('<svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/>'
            '<path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6'
            'M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/></svg>')
ICON_MOON = ('<svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true">'
             '<path d="M20 14.5A8.2 8.2 0 0 1 9.5 4a8.2 8.2 0 1 0 10.5 10.5z"/></svg>')
CHEVRON_L = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 4l-8 8 8 8"/></svg>'
CHEVRON_R = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4l8 8-8 8"/></svg>'
ARROW = '<svg class="arrow" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h15M13 6l6 6-6 6"/></svg>'
CLOSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5l14 14M19 5L5 19"/></svg>'


def num(i):
    return f'{i:02d}'


def booking_dialog(lang):
    t = T[lang]
    options = ''.join(f'<option>{e(t["sections"][s][0])}</option>' for s in SECTION_KEYS if s != 'projects')
    return f'''  <dialog class="booking" id="booking" aria-labelledby="booking-title">
    <form class="booking-form" method="post" action="{FORM_ENDPOINT}" data-endpoint="{FORM_ENDPOINT}"
          data-sending="{e(t['f_sending'])}" data-ok="{e(t['f_ok'])}" data-err="{e(t['f_err'])}">
      <button type="button" class="booking-close" data-close aria-label="{e(t['close'])}">{CLOSE}</button>
      <p class="eyebrow">{e(SITE_NAME)}</p>
      <h2 id="booking-title" class="booking-title">{e(t['form_title'])}</h2>
      <p class="booking-intro">{e(t['form_intro'])}</p>
      <label class="field"><span>{e(t['f_name'])}</span><input name="name" autocomplete="name" required></label>
      <label class="field"><span>{e(t['f_contact'])}</span><input name="contact" autocomplete="email" required></label>
      <div class="field-row">
        <label class="field"><span>{e(t['f_type'])}</span><select name="type"><option>{e(t['f_type_any'])}</option>{options}</select></label>
        <label class="field"><span>{e(t['f_date'])}</span><input name="date" type="date"></label>
      </div>
      <label class="field"><span>{e(t['f_msg'])}</span><textarea name="message" rows="3"></textarea></label>
      <input type="hidden" name="_subject" value="Website request / Anfrage / Заявка">
      <input type="hidden" name="_template" value="table">
      <input type="text" name="_honey" class="honey" tabindex="-1" autocomplete="off" aria-hidden="true">
      <button type="submit" class="btn btn-accent booking-send">{e(t['f_send'])}</button>
      <p class="booking-status" role="status" aria-live="polite"></p>
      <p class="booking-direct">{e(t['or_write'])} <a href="mailto:{FORM_EMAIL}">{FORM_EMAIL}</a> · <a href="https://t.me/sidssphoto" target="_blank" rel="noopener noreferrer">Telegram</a></p>
    </form>
  </dialog>
'''


def page(lang, filename, title, description, body, active=None, scripts=(), body_class=''):
    t = T[lang]
    pre = '' if lang == 'en' else '../'          # path back to the site root
    nav_items = [(f'{s}.html', t['sections'][s][0]) for s in SECTION_KEYS] + [('contact.html', t['contact'])]
    nav = '\n'.join(
        f'          <li style="--n:{i}"><a href="{href}" data-img="{pre}{NAV_IMAGES.get(href, "")}"'
        f'{" aria-current=\"page\"" if href == active else ""}><span class="nav-num">{num(i + 1)}</span>{e(label)}</a></li>'
        for i, (href, label) in enumerate(nav_items))
    langs = '\n'.join(
        f'          <a href="{pre}{"" if code == "en" else folder + "/"}{filename}" hreflang="{code}" lang="{code}"'
        f'{" aria-current=\"true\"" if code == lang else ""}>{LANG_NAMES[code]}</a>'
        for code, folder in LANGS)
    social = '\n'.join(
        f'        <li><a href="{e(url)}" aria-label="{e(t.get(label, label))}: {e(value)}" '
        f'title="{e(t.get(label, label))}"{NEW_TAB if new_tab else ""}>'
        f'<img src="{pre}icons/{icon}" alt="" width="24" height="24"></a></li>'
        for key, label, value, url, icon, new_tab in CONTACTS)
    body_attr = f' class="{body_class}"' if body_class else ''
    full_title = f'{title} — {SITE_NAME} {t["photography"]}' if title else f'{SITE_NAME} — {t["photographer"]}'
    script_tags = ''.join(f'  <script src="{pre}js/{s}" defer></script>\n' for s in ('site.js',) + tuple(scripts))
    return f'''<!DOCTYPE html>
<html lang="{lang}" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <script>(function(d){{d.classList.add('js');try{{var t=localStorage.getItem('theme');if(t)d.setAttribute('data-theme',t)}}catch(e){{}}}})(document.documentElement)</script>
  <title>{e(full_title)}</title>
  <meta name="description" content="{e(description)}">
  <meta name="author" content="{SITE_NAME}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{e(full_title)}">
  <meta property="og:description" content="{e(description)}">
  <meta name="color-scheme" content="dark light">
  <meta name="theme-color" content="#141415">
  <link rel="apple-touch-icon" sizes="180x180" href="{pre}ico/apple-touch-icon.png">
  <link rel="icon" type="image/png" sizes="32x32" href="{pre}ico/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="{pre}ico/favicon-16x16.png">
  <link rel="manifest" href="{pre}ico/site.webmanifest">
  <link rel="mask-icon" href="{pre}ico/safari-pinned-tab.svg" color="#000000">
  <meta name="msapplication-TileColor" content="#000000">
  <meta name="msapplication-config" content="{pre}ico/browserconfig.xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;1,400;1,500&amp;family=Manrope:wght@400;500;700&amp;display=swap">
  <link rel="stylesheet" href="{pre}css/style.css">
</head>
<body{body_attr} data-view="{e(t['view'])}">
  <a class="skip-link" href="#content">{e(t['skip'])}</a>

  <header class="site-header">
    <a class="site-title logo" href="index.html" aria-label="Stanislav Sydorov"><span class="logo-first">Stanislav</span><span class="logo-last">Sydorov</span></a>
    <nav class="site-nav" id="site-nav" aria-label="{e(t['main_nav'])}">
      <ul class="nav-links">
{nav}
      </ul>
      <div class="nav-visual" aria-hidden="true"><img alt="" src="{pre}{NAV_IMAGES.get(active or '', NAV_IMAGES['projects.html'])}" loading="lazy"></div>
      <div class="nav-contact">
        <a href="tel:+491604542187">+49 160 454 21 87</a>
        <span class="nav-social"><a href="https://t.me/sidssphoto" target="_blank" rel="noopener noreferrer">Telegram</a> · <a href="https://www.instagram.com/sidssphoto/" target="_blank" rel="noopener noreferrer">Instagram</a></span>
        <button type="button" class="btn btn-accent" data-book aria-haspopup="dialog">{e(t['book'])}{ARROW}</button>
      </div>
      <div class="nav-tools">
        <div class="lang-switch" role="group" aria-label="{e(t['language'])}">
{langs}
        </div>
        <button type="button" class="theme-toggle" aria-label="{e(t['theme'])}" title="{e(t['theme'])}">{ICON_SUN}{ICON_MOON}</button>
      </div>
    </nav>
    <button type="button" class="menu-toggle" aria-expanded="false" aria-controls="site-nav"
            data-open="{e(t['menu'])}" data-close="{e(t['close'])}"><span class="menu-icon" aria-hidden="true"></span><span class="menu-label">{e(t['menu'])}</span></button>
  </header>

  <main id="content">
{body}
  </main>

  <footer class="site-footer">
    <a class="footer-name logo" href="index.html" aria-label="Stanislav Sydorov"><span class="logo-first">Stanislav</span><span class="logo-last">Sydorov</span><span class="logo-role">{e(t["photographer"])}</span></a>
    <ul class="social-icons">
{social}
    </ul>
    <p class="copyright">&copy; 2018&ndash;{date.today().year} {SITE_NAME}. {e(t['rights'])} &middot; <a href="{pre}versions/index.html">{e(t['versions'])}</a></p>
  </footer>

  <button type="button" class="book-float" data-book aria-haspopup="dialog">{e(t['book'])}</button>
{booking_dialog(lang)}
  <div class="grain" aria-hidden="true"></div>
{script_tags}</body>
</html>
'''


def write(path, content):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f'  wrote {path}')


def out_path(lang, filename):
    folder = dict(LANGS)[lang]
    return f'{folder}/{filename}' if folder else filename


def collect_albums(section):
    """[(slug, photos meta list, cover tuple)] for a section."""
    section_dir = os.path.join(PORTFOLIO, section)
    albums = []
    if not os.path.isdir(section_dir):
        return albums
    for album in sorted(os.listdir(section_dir), key=natural_key):
        album_dir = os.path.join(section_dir, album)
        if not os.path.isdir(album_dir):
            continue
        photos = album_photos(album_dir)
        if not photos:
            continue
        if not os.path.exists(os.path.join(album_dir, COVER_NAME)):
            make_cover(os.path.join(album_dir, photos[0]), os.path.join(album_dir, COVER_NAME))
        metas = [photo_meta(f'portfolio/{section}/{album}/{p}') for p in photos]
        cover = make_cover_webp(section, album, pick_cover_photo(section, album, photos))
        albums.append((album, metas, cover))
    return albums


def big_tiles(n):
    """Which album tiles are shown large (2 × 2) in the editorial grid."""
    if n <= 2:
        return {0}
    return {i for i in range(n) if i == 0 or (i >= 5 and i % 7 == 5)}


def build_section(lang, section, albums):
    t = T[lang]
    pre = '' if lang == 'en' else '../'
    title, intro = t['sections'][section]
    big = big_tiles(len(albums))
    cards = []
    for n, (album, metas, (c1, c2, c_lqip)) in enumerate(albums):
        name = album_title(album, lang)
        count = count_label(lang, len(metas))
        data = json.dumps([[pre + b, w, h, q] for b, w, h, q in metas], separators=(',', ':'))
        size = '(max-width: 700px) 100vw, 50vw' if n in big else '(max-width: 700px) 50vw, 25vw'
        cards.append(
            f'      <figure class="album-item reveal{" is-big" if n in big else ""}">\n'
            f'        <button type="button" class="album" data-title="{e(name)}" data-photos="{e(data)}" '
            f'aria-label="{e(t["open_album"].format(name=name, count=count))}" style="--lqip:url({c_lqip})">\n'
            f'          <img src="{pre}{c1}" srcset="{pre}{c1} {COVER_W}w, {pre}{c2} {COVER_W * 2}w" '
            f'sizes="{size}" alt="" width="{COVER_W}" height="{COVER_H}" '
            f'loading="{"eager" if n < 3 else "lazy"}" decoding="async">\n'
            f'        </button>\n'
            f'        <figcaption><span class="item-num">{num(n + 1)}</span>'
            f'<span class="item-name">{e(name)}</span><span class="item-count">{e(count)}</span></figcaption>\n'
            f'      </figure>')
    index = SECTION_KEYS.index(section) + 1
    body = (f'    <header class="page-head">\n'
            f'      <p class="eyebrow"><span class="accent">{num(index)}</span> / {num(len(SECTION_KEYS))} · {e(count_label(lang, sum(len(a[1]) for a in albums)))}</p>\n'
            f'      <h1 class="page-title">{e(title)}</h1>\n'
            f'      <p class="intro">{e(intro)} {e(t["tap"])}</p>\n'
            f'    </header>\n'
            f'    <div class="album-grid count-{min(len(albums), 4)}" data-labels="{e(json.dumps({k: t[k] for k in ("viewer", "close", "prev_photo", "next_photo", "photo")}))}">\n'
            + '\n'.join(cards) + '\n    </div>\n' + cta_block(lang))
    write(out_path(lang, f'{section}.html'),
          page(lang, f'{section}.html', title, f'{intro} {t["desc"]}', body,
               active=f'{section}.html', scripts=('gallery.js',)))


def cta_block(lang):
    t = T[lang]
    return f'''    <section class="cta reveal">
      <p class="eyebrow">{e(t['contact'])}</p>
      <h2 class="cta-title">{e(t['cta_title'])}</h2>
      <p class="cta-text">{e(t['cta_text'])}</p>
      <button type="button" class="btn btn-accent" data-book aria-haspopup="dialog">{e(t['book'])}{ARROW}</button>
    </section>'''


def build_home(lang, albums):
    t = T[lang]
    pre = '' if lang == 'en' else '../'
    dots, items = [], []
    total = len(CAROUSEL)
    for i, (src, section) in enumerate(CAROUSEL):
        base, w, h, q = photo_meta(src)
        label = t['sections'][section][0]
        album = album_title(src.split('/')[2], lang)
        alt = f'{label}: {album}'
        active = ' is-active' if i == 0 else ''
        dots.append(f'        <button type="button" class="{active.strip()}" aria-label="{e(t["slide"])} {i + 1}: {e(alt)}"'
                    f'{" aria-current=\"true\"" if i == 0 else ""}></button>')
        srcset = f'{pre}{base}-800.webp 800w, {pre}{base}-1600.webp 1600w'
        if i < 2:
            img_attr = f'src="{pre}{base}-1600.webp" srcset="{srcset}"'
            fetch = ' fetchpriority="high"' if i == 0 else ''
        else:
            img_attr = f'data-src="{pre}{base}-1600.webp" data-srcset="{srcset}"'
            fetch = ''
        items.append(
            f'      <div class="hero-slide{active}" style="--lqip:url({q})" aria-roledescription="slide" '
            f'aria-label="{i + 1} / {total}">\n'
            f'        <img class="hero-photo" {img_attr} sizes="100vw" alt="{e(alt)}" width="{w}" height="{h}"{fetch}>\n'
            f'        <div class="hero-caption">\n'
            f'          <span class="hero-count"><span class="accent">{num(i + 1)}</span> / {num(total)} · {e(label)}</span>\n'
            f'          <span class="hero-album"><span>{e(album)}</span></span>\n'
            f'          <a class="hero-link" href="{section}.html">{e(t["view_gallery"])}{ARROW}</a>\n'
            f'        </div>\n'
            f'      </div>')

    # genre index: one big line per section with a preview photo
    carousel_by_section = {}
    for src, section in CAROUSEL:
        carousel_by_section.setdefault(section, src)
    rows = []
    for i, s in enumerate(SECTION_KEYS):
        if s in carousel_by_section:
            base, w, h, q = photo_meta(carousel_by_section[s])
            img = f'{pre}{base}-800.webp'
        else:
            img = pre + albums[s][0][2][1]
        n_albums = len(albums[s])
        rows.append(
            f'        <li class="reveal"><a class="genre" href="{s}.html" data-img="{img}">'
            f'<span class="genre-num">{num(i + 1)}</span>'
            f'<span class="genre-name">{e(t["sections"][s][0])}</span>'
            f'<span class="genre-meta">{n_albums} {e(t["albums_n"])}</span>'
            f'<img class="genre-thumb" src="{img}" alt="" loading="lazy" decoding="async" width="80" height="100">'
            f'</a></li>')

    works = []
    for k, idx in enumerate(SELECTED):
        src, section = CAROUSEL[idx]
        base, w, h, q = photo_meta(src)
        album = album_title(src.split('/')[2], lang)
        works.append(
            f'        <a class="work reveal" href="{section}.html" style="--lqip:url({q})">\n'
            f'          <span class="work-frame" style="aspect-ratio:{w}/{h}"><img src="{pre}{base}-800.webp" '
            f'srcset="{pre}{base}-800.webp 800w, {pre}{base}-1600.webp 1600w" sizes="(max-width: 700px) 100vw, 45vw" '
            f'alt="{e(t["sections"][section][0])}: {e(album)}" width="{w}" height="{h}" loading="lazy" decoding="async"></span>\n'
            f'          <span class="work-cap"><span class="accent">{num(k + 1)}</span> {e(album)} <em>{e(t["sections"][section][0])}</em></span>\n'
            f'        </a>')

    body = f'''    <h1 class="visually-hidden">{e(t['h1_home'])}</h1>
    <section class="hero" id="hero" data-interval="{CAROUSEL_INTERVAL}" aria-roledescription="carousel" aria-label="{e(t['selected'])}">
{chr(10).join(items)}
      <button type="button" class="hero-arrow hero-prev" aria-label="{e(t['prev'])}">{CHEVRON_L}</button>
      <button type="button" class="hero-arrow hero-next" aria-label="{e(t['next'])}">{CHEVRON_R}</button>
      <div class="hero-dots">
{chr(10).join(dots)}
      </div>
      <span class="hero-scroll" aria-hidden="true">{e(t['scroll'])}</span>
    </section>

    <section class="genres" aria-labelledby="genres-title">
      <div class="section-head">
        <p class="eyebrow"><span class="accent">I</span> — {e(t['genres'])}</p>
        <h2 id="genres-title" class="visually-hidden">{e(t['genres'])}</h2>
      </div>
      <ul class="genre-list">
{chr(10).join(rows)}
      </ul>
      <div class="genre-preview" aria-hidden="true"><img alt=""></div>
    </section>

    <section class="works" aria-labelledby="works-title">
      <div class="section-head">
        <p class="eyebrow"><span class="accent">II</span> — {e(t['selected_works'])}</p>
        <h2 id="works-title" class="section-title">{e(t['selected_works'])}</h2>
      </div>
      <div class="works-grid">
        <div class="works-col">
{chr(10).join(works[0::2])}
        </div>
        <div class="works-col">
{chr(10).join(works[1::2])}
        </div>
      </div>
    </section>

{cta_block(lang)}'''
    write(out_path(lang, 'index.html'),
          page(lang, 'index.html', '', t['desc'], body, body_class='home', scripts=('hero.js',)))


def build_contact(lang):
    t = T[lang]
    pre = '' if lang == 'en' else '../'
    links = '\n'.join(
        f'      <li><a href="{e(url)}"{NEW_TAB if new_tab else ""}>'
        f'<img src="{pre}icons/{icon}" alt="" width="28" height="28">'
        f'<span>{e(t.get(label, label))}<small>{e(value)}</small></span>{ARROW}</a></li>'
        for key, label, value, url, icon, new_tab in CONTACTS)
    body = (f'    <header class="page-head">\n'
            f'      <p class="eyebrow"><span class="accent">{num(len(SECTION_KEYS) + 1)}</span> / {e(t["contact"])}</p>\n'
            f'      <h1 class="page-title">{e(t["contact_title"])}</h1>\n'
            f'      <p class="intro">{e(t["contact_intro"])}</p>\n'
            f'      <button type="button" class="btn btn-accent" data-book aria-haspopup="dialog">{e(t["book"])}{ARROW}</button>\n'
            f'    </header>\n'
            f'    <ul class="contact-list">\n{links}\n    </ul>')
    write(out_path(lang, 'contact.html'),
          page(lang, 'contact.html', t['contact_title'], t['contact_desc'], body, active='contact.html'))


def build_404(lang):
    t = T[lang]
    pre = '' if lang == 'en' else '../'
    w, h = image_size('images/404.jpg')
    body = f'''    <div class="not-found">
      <img src="{pre}images/404.jpg" alt="" width="{w}" height="{h}">
      <div class="not-found-text">
        <h1 class="code">404</h1>
        <p>{e(t['not_found'])}</p>
        <a href="index.html">{e(t['home'])}</a>
      </div>
    </div>'''
    write(out_path(lang, '404.html'), page(lang, '404.html', t['not_found_title'], t['not_found'], body))


def image_size(path):
    with Image.open(os.path.join(ROOT, path)) as im:
        return im.size


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', help='folder with original photos (<section>/<album>/*.jpg)')
    ap.add_argument('--src-404', help='original image for the 404 page')
    args = ap.parse_args()

    if args.src:
        print('Importing photos…')
        import_originals(args.src)
    if args.src_404:
        os.makedirs(os.path.join(ROOT, 'images'), exist_ok=True)
        optimise(args.src_404, os.path.join(ROOT, 'images', '404.jpg'))

    print('Preparing images…')
    albums = {s: collect_albums(s) for s in SECTION_KEYS}
    # photo shown next to each item of the full-screen menu
    for src, section in reversed(CAROUSEL):
        NAV_IMAGES[f'{section}.html'] = photo_meta(src)[0] + '-800.webp'
    for s in SECTION_KEYS:
        NAV_IMAGES.setdefault(f'{s}.html', albums[s][0][2][1])
    NAV_IMAGES['contact.html'] = photo_meta(CAROUSEL[0][0])[0] + '-800.webp'
    print('Building pages…')
    for lang, _ in LANGS:
        for s in SECTION_KEYS:
            build_section(lang, s, albums[s])
        build_home(lang, albums)
        build_contact(lang)
        build_404(lang)


if __name__ == '__main__':
    sys.exit(main())
