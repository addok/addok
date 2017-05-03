from datetime import date
from hashlib import md5
from io import StringIO
from pathlib import Path
from string import Template as BaseTemplate

from invoke import task


class Template(BaseTemplate):
    # Default delimiter ($) clashes at least with Nginx DSL.
    delimiter = '$$'


def render_template(path, **context):
    with Path(path).open() as f:
        template = Template(f.read())
        return StringIO(template.substitute(**context))


def as_user(ctx, user, cmd, *args, **kwargs):
    ctx.run('sudo --set-home --preserve-env --user {} '
            '{}'.format(user, cmd), *args, **kwargs)


def as_addok(ctx, cmd, *args, **kwargs):
    as_user(ctx, 'addok', cmd, *args, **kwargs)


def sudo_put(ctx, local, remote, chown=None):
    tmp = str(Path('/tmp') / md5(remote.encode()).hexdigest())
    ctx.put(local, tmp)
    ctx.run('sudo mv {} {}'.format(tmp, remote))
    if chown:
        ctx.run('sudo chown {} {}'.format(chown, remote))


@task
def addok(ctx, cmd):
    as_addok(ctx, '/srv/addok/venv/bin/addok {}'.format(cmd))


@task
def system(ctx):
    ctx.run('sudo apt update')
    ctx.run('sudo apt install redis-server python3.5 python3.5-dev '
            'python-virtualenv build-essential git wget uwsgi '
            'uwsgi-plugin-python3 bzip2 --yes')
    if not ctx.config.get('skip_nginx'):
        ctx.run('sudo apt install nginx --yes')
    ctx.run('sudo mkdir -p /etc/addok')
    ctx.run('sudo useradd -N addok -m -d /srv/addok/ || exit 0')
    ctx.run('sudo chsh -s /bin/bash addok')


@task
def venv(ctx):
    as_addok(ctx, 'virtualenv /srv/addok/venv --python=python3')
    as_addok(ctx, '/srv/addok/venv/bin/pip install pip -U')


@task
def settings(ctx):
    if ctx.settings:
        sudo_put(ctx, ctx.settings, '/etc/addok/addok.conf',
                 chown='addok:users')


@task
def http(ctx):
    sudo_put(ctx, 'fabfile/uwsgi_params', '/srv/addok/uwsgi_params')
    uwsgi_conf = render_template('fabfile/uwsgi.ini',
                                 processes=ctx.config.get('processes', 4))
    sudo_put(ctx, uwsgi_conf, '/etc/uwsgi/apps-enabled/addok.ini')
    if not ctx.config.get('skip_nginx'):
        nginx_conf = render_template('fabfile/nginx.conf',
                                     domain=ctx.config.domain)
        sudo_put(ctx, nginx_conf, '/etc/nginx/sites-enabled/addok')


@task
def bootstrap(ctx):
    system(ctx)
    venv(ctx)
    settings(ctx)
    http(ctx)


@task
def fetch(ctx):
    ctx.run('wget {} --output-document=/tmp/data.bz2 --quiet'.format(
        ctx.config.data_uri))
    ctx.run('bunzip2 /tmp/data.bz2 --stdout > /tmp/data.json')


@task
def batch(ctx):
    ctx.run('redis-cli config set save ""')
    addok(ctx, 'batch /tmp/data.json')
    if ctx.config.get('data'):
        ctx.put(StringIO('\n'.join(ctx.config.data)), '/tmp/extra.json')
        addok('batch /tmp/extra.json')
    addok(ctx, 'ngrams')
    ctx.run('redis-cli save')


@task
def reload(ctx):
    fetch(ctx)
    ctx.run('sudo systemctl stop uwsgi')
    addok(ctx, 'reset')
    batch(ctx)
    restart(ctx)


@task
def deploy(ctx):
    cmd = '/srv/addok/venv/bin/pip install {} --upgrade'
    as_addok(ctx, cmd.format('addok'))
    if ctx.config.get('plugins'):
        as_addok(ctx, cmd.format(' '.join(ctx.config.plugins)))
    restart(ctx)


@task
def restart(ctx):
    ctx.run('sudo systemctl restart uwsgi')
    if not ctx.config.get('skip_nginx'):
        ctx.run('sudo systemctl restart nginx')


@task
def backup(ctx):
    today = date.today().isoformat()
    backup_filename = 'addok-backup.{}.tar.bz2'.format(today)
    ctx.run('redis-cli save')
    ctx.run('cp /etc/addok/addok.conf /tmp/local.{}.py'.format(today))
    ctx.run('cp /srv/addok/addok.db /tmp/sqlite.{}.db'.format(today))
    ctx.run('cp /var/lib/redis/dump.rdb /tmp/redis.{}.rdb'.format(today))
    ctx.run('cd /tmp && tar -jcvf {filename} sqlite.{today}.db '
            'redis.{today}.rdb local.{today}.py'.format(
                filename=backup_filename, today=today))
    scp = 'rsync --progress -e ssh'  # Allows to display progress.
    ctx.local('{scp} {ctx.user}@{ctx.host}:/tmp/{filename} .'.format(
        scp=scp, ctx=ctx, filename=backup_filename))


@task
def use_backup(ctx, backup_date=date.today().isoformat()):
    ctx.local('tar -xvjf addok-backup.{}.tar.bz2'.format(backup_date))
    with open('local.{}.py'.format(backup_date), 'r+') as configuration:
        content = configuration.read()
        if "SQLITE_DB_PATH = '/srv/addok/addok.db'" in content:
            content = content.replace(
                "SQLITE_DB_PATH = '/srv/addok/addok.db'",
                "SQLITE_DB_PATH = 'sqlite.{}.db'".format(backup_date))
            configuration.seek(0)  # Overwrite file.
            configuration.write(content)
    ctx.local('echo "dbfilename redis.{}.rdb" | redis-server -'.format(
        backup_date))
