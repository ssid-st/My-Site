#!/usr/bin/env python3
"""
Build the static site.

  python3 tools/build.py                  # regenerate HTML pages and album covers
  python3 tools/build.py --src ORIGINALS  # also re-import photos from a folder of originals

ORIGINALS is a folder laid out like  <section>/<album>/<photos>.jpg
(the old "portfolio" folder). Every photo is resized to at most 1600 px,
saved as an optimised progressive JPEG and stripped of EXIF/GPS metadata.

To add an album: put its photos into portfolio/<section>/<new-album>/
(or into the originals folder and use --src), optionally add a title in
ALBUM_TITLES below, and run the script again. Commit the result.

Needs Pillow:  pip install Pillow
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
from datetime import date

from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = os.path.join(ROOT, 'portfolio')

MAX_SIDE = 1600          # long side of full-size photos
COVER_SIDE = 600         # square album covers
QUALITY = 82
COVER_NAME = 'cover.jpg'

SITE_NAME = 'Stanislav Sidorov'
SITE_DESC = ('Stanislav Sidorov — photographer. Love story, wedding, beauty, '
             'campaign, sport and boudoir photography.')

# Menu order. (section folder, menu label, page title, intro text)
SECTIONS = [
    ('projects', 'Projects', 'Projects', 'Personal and creative photo projects.'),
    ('lovestory', 'Love story', 'Love story', 'Love story photo sessions.'),
    ('weddings', 'Weddings', 'Weddings', 'Wedding day photography.'),
    ('beauty', 'Beauty', 'Beauty', 'Beauty and portrait photography.'),
    ('campaign', 'Campaign', 'Campaign', 'Commercial and fashion campaigns.'),
    ('sport', 'Sport', 'Sport', 'Sport and fitness photography.'),
    ('boudoir', 'Boudoir', 'Boudoir', 'Boudoir photography.'),
]

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

# Used only with --src: map original folders to new ones.
SRC_RENAMES = {
    'weddings/3': 'weddings/wedding-day',
    'projects/cat': 'projects',          # projects/cat/<album> -> projects/<album>
}
SRC_SKIP_DIRS = {'dist1', 'css', 'js', 'ico', 'icons', 'preview'}
# Square previews made by hand for the projects page: used as covers.
SRC_PROJECT_PREVIEWS = {
    'alina': 'alinapr.jpg', 'art': 'artpr.jpg', 'kira': 'kirapr.jpg',
    'ksusha': 'ksushapr.jpg', 'nastya': 'nastyapr.jpg', 'nataly': 'natalipr.jpg',
    'olga': 'olgapr.jpg', 'spring': 'springpr.jpg', 'valeria': 'valeryapr.jpg',
    'victory': 'victorypr.jpg',
}

# Home page carousel: (photo path, alt text)
CAROUSEL = [
    ('portfolio/beauty/alina/05.jpg', 'Beauty portrait of Alina'),
    ('portfolio/beauty/kate/03.jpg', 'Beauty portrait of Kate'),
    ('portfolio/beauty/nataly/01.jpg', 'Beauty portrait of Nataly'),
]

CONTACTS = [
    # (key, label, url, icon, opens new tab)
    ('instagram', 'Instagram — @sidssphoto', 'https://www.instagram.com/sidssphoto/', 'instagram.png', True),
    ('facebook', 'Facebook — ssidorovphoto', 'https://www.facebook.com/ssidorovphoto/', 'facebook.png', True),
    ('telegram', 'Telegram — @sidssphoto', 'https://t.me/sidssphoto', 'telegram.png', True),
    ('viber', 'Viber — +380 66 446 9440', 'viber://chat?number=%2B380664469440', 'viber.png', False),
    ('email', 'E-mail — sidssphoto@icloud.com', 'mailto:sidssphoto@icloud.com', 'mail.png', False),
]

IMG_EXT = ('.jpg', '.jpeg')
NEW_TAB = ' target="_blank" rel="noopener noreferrer"'
CURRENT = ' aria-current="page"'


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
    im = ImageOps.fit(im, (COVER_SIDE, COVER_SIDE), Image.LANCZOS)
    if icc:
        im.info['icc_profile'] = icc
    save_jpeg(im, dst, quality=78)


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


def ensure_cover(album_dir, photos):
    cover = os.path.join(album_dir, COVER_NAME)
    if not os.path.exists(cover):
        make_cover(os.path.join(album_dir, photos[0]), cover)


def image_size(path):
    with Image.open(os.path.join(ROOT, path)) as im:
        return im.size


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
e = html.escape


def page(filename, title, description, body, active=None, extra_scripts=''):
    nav_items = [(f'{s}.html', label) for s, label, _, _ in SECTIONS] + [('contact.html', 'Contact')]
    nav = '\n'.join(
        f'          <li class="nav-item"><a class="nav-link{" active" if href == active else ""}" '
        f'href="{href}"{CURRENT if href == active else ""}>{e(label)}</a></li>'
        for href, label in nav_items)
    social = '\n'.join(
        f'        <li><a href="{e(url)}" aria-label="{e(label)}" title="{e(label)}"'
        f'{NEW_TAB if new_tab else ""}>'
        f'<img src="icons/{icon}" alt="" width="32" height="32"></a></li>'
        for key, label, url, icon, new_tab in CONTACTS)
    full_title = f'{title} — {SITE_NAME} Photography' if title else f'{SITE_NAME} — Photographer'
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(full_title)}</title>
  <meta name="description" content="{e(description)}">
  <meta name="author" content="{SITE_NAME}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{e(full_title)}">
  <meta property="og:description" content="{e(description)}">
  <meta name="theme-color" content="#000000">
  <link rel="apple-touch-icon" sizes="180x180" href="ico/apple-touch-icon.png">
  <link rel="icon" type="image/png" sizes="32x32" href="ico/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="ico/favicon-16x16.png">
  <link rel="manifest" href="ico/site.webmanifest">
  <link rel="mask-icon" href="ico/safari-pinned-tab.svg" color="#000000">
  <meta name="msapplication-TileColor" content="#000000">
  <meta name="msapplication-config" content="ico/browserconfig.xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poiret+One&amp;family=Raleway:wght@400;700&amp;display=swap">
  <link rel="stylesheet" href="vendor/bootstrap/bootstrap.min.css">
  <link rel="stylesheet" href="css/style.css">
</head>
<body>
  <a class="skip-link" href="#content">Skip to content</a>

  <header class="site-header">
    <a class="site-title" href="index.html">Stanislav&nbsp;Sidorov</a>
  </header>

  <nav class="navbar navbar-expand-lg site-nav" aria-label="Main">
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#main-menu"
            aria-controls="main-menu" aria-expanded="false" aria-label="Toggle menu">Menu</button>
    <div class="collapse navbar-collapse" id="main-menu">
      <ul class="navbar-nav">
{nav}
      </ul>
    </div>
  </nav>

  <main id="content">
{body}
  </main>

  <footer class="site-footer">
    <ul class="social-icons">
{social}
    </ul>
    <p class="copyright">&copy; 2018&ndash;{date.today().year} {SITE_NAME}. All rights reserved.</p>
  </footer>

  <script src="vendor/bootstrap/bootstrap.bundle.min.js"></script>
{extra_scripts}</body>
</html>
'''


def write(filename, content):
    with open(os.path.join(ROOT, filename), 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f'  wrote {filename}')


def album_title(slug):
    return ALBUM_TITLES.get(slug, slug.replace('-', ' ').capitalize())


def build_section(section, label, title, intro):
    section_dir = os.path.join(PORTFOLIO, section)
    cards = []
    if os.path.isdir(section_dir):
        for album in sorted(os.listdir(section_dir), key=natural_key):
            album_dir = os.path.join(section_dir, album)
            if not os.path.isdir(album_dir):
                continue
            photos = album_photos(album_dir)
            if not photos:
                continue
            ensure_cover(album_dir, photos)
            base = f'portfolio/{section}/{album}'
            urls = json.dumps([f'{base}/{p}' for p in photos])
            name = album_title(album)
            count = f'{len(photos)} photo' + ('s' if len(photos) != 1 else '')
            cards.append(
                f'      <button type="button" class="album" data-title="{e(name)}" data-photos="{e(urls)}" '
                f'aria-label="Open album {e(name)}, {count}">\n'
                f'        <img src="{base}/{COVER_NAME}" alt="" width="{COVER_SIDE}" height="{COVER_SIDE}" loading="lazy">\n'
                f'        <span class="album-caption">{e(name)}<small>{count}</small></span>\n'
                f'      </button>')
    body = (f'    <h1 class="page-title">{e(title)}</h1>\n'
            f'    <p class="intro">{e(intro)} Tap an album to view it.</p>\n'
            f'    <div class="album-grid">\n' + '\n'.join(cards) + '\n    </div>')
    write(f'{section}.html', page(f'{section}.html', title, f'{intro} {SITE_DESC}', body,
                                  active=f'{section}.html',
                                  extra_scripts='  <script src="js/gallery.js"></script>\n'))


def build_home():
    indicators, items = [], []
    for i, (src, alt) in enumerate(CAROUSEL):
        w, h = image_size(src)
        active = ' active' if i == 0 else ''
        current = ' aria-current="true"' if i == 0 else ''
        indicators.append(
            f'        <button type="button" data-bs-target="#hero" data-bs-slide-to="{i}" '
            f'class="{active.strip()}"{current} aria-label="Slide {i + 1}"></button>')
        loading = '' if i == 0 else ' loading="lazy"'
        items.append(
            f'        <div class="carousel-item{active}">\n'
            f'          <img src="{src}" alt="{e(alt)}" width="{w}" height="{h}"{loading}>\n'
            f'        </div>')
    body = f'''    <h1 class="visually-hidden">Stanislav Sidorov — photographer</h1>
    <div id="hero" class="carousel slide hero" data-bs-ride="carousel">
      <div class="carousel-indicators">
{chr(10).join(indicators)}
      </div>
      <div class="carousel-inner">
{chr(10).join(items)}
      </div>
      <button class="carousel-control-prev" type="button" data-bs-target="#hero" data-bs-slide="prev">
        <span class="carousel-control-prev-icon" aria-hidden="true"></span>
        <span class="visually-hidden">Previous</span>
      </button>
      <button class="carousel-control-next" type="button" data-bs-target="#hero" data-bs-slide="next">
        <span class="carousel-control-next-icon" aria-hidden="true"></span>
        <span class="visually-hidden">Next</span>
      </button>
    </div>'''
    write('index.html', page('index.html', '', SITE_DESC, body))


def build_contact():
    links = '\n'.join(
        f'      <li><a href="{e(url)}"{NEW_TAB if new_tab else ""}>'
        f'<img src="icons/{icon}" alt="" width="28" height="28"><span>{e(label)}</span></a></li>'
        for key, label, url, icon, new_tab in CONTACTS)
    body = (f'    <h1 class="page-title">Contact &amp; prices</h1>\n'
            f'    <p class="intro">To book a photo session or ask about prices, write to me in any messenger '
            f'or by e-mail. I will reply as soon as possible.</p>\n'
            f'    <ul class="contact-list">\n{links}\n    </ul>')
    write('contact.html', page('contact.html', 'Contact & prices',
                               'Book a photo session with Stanislav Sidorov: Instagram, Telegram, Viber, e-mail.',
                               body, active='contact.html'))


def build_404():
    w, h = image_size('images/404.jpg')
    body = f'''    <div class="not-found">
      <img src="images/404.jpg" alt="" width="{w}" height="{h}">
      <div class="not-found-text">
        <h1 class="code">404</h1>
        <p>This page does not exist.</p>
        <a href="index.html">Go to the home page</a>
      </div>
    </div>'''
    write('404.html', page('404.html', 'Page not found', 'Page not found.', body))


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

    print('Building pages…')
    for s in SECTIONS:
        build_section(*s)
    build_home()
    build_contact()
    build_404()


if __name__ == '__main__':
    sys.exit(main())
