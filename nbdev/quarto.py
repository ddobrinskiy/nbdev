# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/API/quarto.ipynb.

# %% ../nbs/API/quarto.ipynb 2
from __future__ import annotations
import warnings

from .config import *
from .doclinks import *

from fastcore.utils import *
from fastcore.script import call_parse
from fastcore.shutil import rmtree,move,copytree
from fastcore.meta import delegates
from .serve import proc_nbs,preview_server

from os import system
import subprocess,sys,shutil,ast

# %% auto 0
__all__ = ['BASE_QUARTO_URL', 'install_quarto', 'install', 'nbdev_sidebar', 'refresh_quarto_yml', 'nbdev_readme', 'nbdev_docs',
           'nbdev_preview', 'deploy', 'prepare']

# %% ../nbs/API/quarto.ipynb 4
def _sprun(cmd):
    try: subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as cpe: sys.exit(cpe.returncode)

# %% ../nbs/API/quarto.ipynb 6
BASE_QUARTO_URL='https://www.quarto.org/download/latest/'

def _install_linux():
    system(f'curl -LO {BASE_QUARTO_URL}quarto-linux-amd64.deb')
    system('sudo dpkg -i *64.deb && rm *64.deb')
    
def _install_mac():
    system(f'curl -LO {BASE_QUARTO_URL}quarto-macos.pkg')
    system('sudo installer -pkg quarto-macos.pkg -target /')

@call_parse
def install_quarto():
    "Install latest Quarto on macOS or Linux, prints instructions for Windows"
    if sys.platform not in ('darwin','linux'):
        return print('Please visit https://quarto.org/docs/get-started/ to install quarto')
    print("Installing or upgrading quarto -- this requires root access.")
    system('sudo touch .installing')
    try:
        installing = Path('.installing')
        if not installing.exists(): return print("Cancelled. Please download and install Quarto from quarto.org.")
        if 'darwin' in sys.platform: _install_mac()
        elif 'linux' in sys.platform: _install_linux()
    finally: system('sudo rm -f .installing')

# %% ../nbs/API/quarto.ipynb 7
@call_parse
def install():
    "Install Quarto and the current library"
    install_quarto.__wrapped__()
    d = get_config().lib_path
    if (d/'__init__.py').exists(): system(f'pip install -e "{d.parent}[dev]"')

# %% ../nbs/API/quarto.ipynb 9
def _pre(p,b=True): return '    ' * (len(p.parts)) + ('- ' if b else '  ')
def _sort(a):
    x,y = a
    if y.startswith('index.'): return x,'00'
    return a

_def_file_re = '\.(?:ipynb|qmd|html)$'

@delegates(nbglob_cli)
def _nbglob_docs(
    path:str=None, # Path to notebooks
    file_glob:str=None, # Only include files matching glob    
    file_re:str=_def_file_re, # Only include files matching regex
    **kwargs):
    return nbglob(path, file_glob=file_glob, file_re=file_re, **kwargs)

# %% ../nbs/API/quarto.ipynb 10
@call_parse
@delegates(_nbglob_docs)
def nbdev_sidebar(
    path:str=None, # Path to notebooks
    printit:bool=False,  # Print YAML for debugging
    force:bool=False,  # Create sidebar even if settings.ini custom_sidebar=False
    skip_folder_re:str='(?:^[_.]|^www$)', # Skip folders matching regex
    **kwargs):
    "Create sidebar.yml"
    if not force and get_config().custom_sidebar: return
    path = get_config().nbs_path if not path else Path(path)
    def _f(a,b): return Path(a),b
    files = nbglob(path, func=_f, skip_folder_re=skip_folder_re, **kwargs).sorted(key=_sort)
    lastd,res = Path(),[]
    for dabs,name in files:
        drel = dabs.relative_to(path)
        d = Path()
        for p in drel.parts:
            d /= p
            if d == lastd: continue
            title = re.sub('^\d+_', '', d.name)
            res.append(_pre(d.parent) + f'section: {title}')
            res.append(_pre(d.parent, False) + 'contents:')
            lastd = d
        res.append(f'{_pre(d)}{d.joinpath(name)}')

    yml_path = path/'sidebar.yml'
    yml = "website:\n  sidebar:\n    contents:\n"
    yml += '\n'.join(f'      {o}' for o in res)
    if printit: return print(yml)
    yml_path.write_text(yml)

# %% ../nbs/API/quarto.ipynb 13
def _ensure_quarto():
    if shutil.which('quarto'): return
    print("Quarto is not installed. We will download and install it for you.")
    install.__wrapped__()

# %% ../nbs/API/quarto.ipynb 14
_quarto_yml="""project:
  type: website
  output-dir: {doc_path}
  preview:
    port: 3000
    browser: false

format:
  html:
    theme: cosmo
    css: styles.css
    toc: true
    toc-depth: 4

website:
  title: "{title}"
  site-url: "{doc_host}{doc_baseurl}"
  description: "{description}"
  twitter-card: true
  open-graph: true
  repo-branch: {branch}
  repo-url: "{git_url}"
  repo-actions: [issue]
  navbar:
    background: primary
    search: true
    right:
      - icon: github
        href: "{git_url}"
  sidebar:
    style: "floating"

metadata-files: 
  - sidebar.yml
  - custom.yml
"""

# %% ../nbs/API/quarto.ipynb 15
def refresh_quarto_yml():
    "Generate `_quarto.yml` from `settings.ini`."
    cfg = get_config()
    if cfg.get('custom_quarto_yml', False): return
    p = cfg.nbs_path/'_quarto.yml'
    vals = {k:cfg[k] for k in ['title', 'description', 'branch', 'git_url', 'doc_host', 'doc_baseurl']}
    vals['doc_path'] = cfg.doc_path.name
    if 'title' not in vals: vals['title'] = vals['lib_name']
    p.write_text(_quarto_yml.format(**vals))

# %% ../nbs/API/quarto.ipynb 16
@call_parse
def nbdev_readme(
    path:str=None, # Path to notebooks
    chk_time:bool=False): # Only build if out of date
    cfg = get_config()
    cfg_path = cfg.config_path
    path = Path(path) if path else cfg.nbs_path
    idx_path = path/cfg.readme_nb
    if not idx_path.exists(): return print(f"Could not find {idx_path}")
    readme_path = cfg_path/'README.md'
    if chk_time and readme_path.exists() and readme_path.stat().st_mtime>=idx_path.stat().st_mtime: return

    yml_path = path/'sidebar.yml'
    moved=False
    if yml_path.exists():
        # move out of the way to avoid rendering whole website
        yml_path.rename(path/'sidebar.yml.bak')
        moved=True

    try:
        cache = proc_nbs.__wrapped__(path)
        idx_cache = cache/cfg.readme_nb
        _sprun(f'cd "{cache}" && quarto render "{idx_cache}" -o README.md -t gfm --no-execute')
    finally:
        if moved: (path/'sidebar.yml.bak').rename(yml_path)
    tmp_doc_path = cache/cfg.doc_path.name
    readme = tmp_doc_path/'README.md'
    if readme.exists():
        _rdmi = tmp_doc_path/(idx_cache.stem + '_files')
        if readme_path.exists(): readme_path.unlink() # py37 doesn't have `missing_ok`
        move(readme, cfg_path)
        if _rdmi.exists(): copytree(_rdmi, cfg_path/_rdmi.name) # Move Supporting files for README

# %% ../nbs/API/quarto.ipynb 18
def _pre_docs(path, **kwargs):
    cfg = get_config()
    path = Path(path) if path else cfg.nbs_path
    _ensure_quarto()
    refresh_quarto_yml()
    import nbdev.doclinks
    nbdev.doclinks._build_modidx()
    nbdev_sidebar.__wrapped__(path=path, **kwargs)
    cache = proc_nbs.__wrapped__(path)
    return cache,cfg,path

# %% ../nbs/API/quarto.ipynb 19
@call_parse
@delegates(_nbglob_docs)
def nbdev_docs(
    path:str=None, # Path to notebooks
    **kwargs):
    "Create Quarto docs and README.md"
    cache,cfg,path = _pre_docs(path, **kwargs)
    nbdev_readme.__wrapped__(path=path, chk_time=True)
    _sprun(f'cd "{cache}" && quarto render --no-cache')
    shutil.rmtree(cfg.doc_path, ignore_errors=True)
    move(cache/cfg.doc_path.name, cfg.config_path)

# %% ../nbs/API/quarto.ipynb 21
@call_parse
@delegates(_nbglob_docs)
def nbdev_preview(
    path:str=None, # Path to notebooks
    port:int=None, # The port on which to run preview
    host:str=None, # The host on which to run preview
    **kwargs):
    "Preview docs locally"
    os.environ['QUARTO_PREVIEW']='1'
    cache,cfg,path = _pre_docs(path, **kwargs)
    if not port: port=cfg.get('preview_port', 3000)
    if not host: host=cfg.get('preview_host', 'localhost')
    xtra = ['--port', str(port), '--host', host]
    preview_server(path, xtra)

# %% ../nbs/API/quarto.ipynb 23
@call_parse
@delegates(nbdev_docs)
def deploy(
    path:str=None, # Path to notebooks
    skip_build:bool=False,  # Don't build docs first
    **kwargs):
    "Deploy docs to GitHub Pages"
    if not skip_build: nbdev_docs.__wrapped__(path, **kwargs)
    try: from ghp_import import ghp_import
    except: return warnings.warn('Please install ghp-import with `pip install ghp-import`')
    ghp_import(get_config().doc_path, push=True, stderr=True, no_history=True)

# %% ../nbs/API/quarto.ipynb 24
@call_parse
def prepare():
    "Export, test, and clean notebooks, and render README if needed"
    import nbdev.test, nbdev.clean
    nbdev_export.__wrapped__()
    nbdev.test.nbdev_test.__wrapped__()
    nbdev.clean.nbdev_clean.__wrapped__()
    refresh_quarto_yml()
    nbdev_readme.__wrapped__(chk_time=True)
